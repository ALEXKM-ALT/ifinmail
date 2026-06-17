import email.utils
import logging
import os
import smtplib
import uuid
from datetime import UTC
from email.message import EmailMessage
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from aiosmtpd.smtp import MISSING
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ifinmail.api.config import settings
from ifinmail.api.filter_engine import apply_filters_for_mailbox
from ifinmail.api.personalize import MemberInfo, personalise
from ifinmail.db.models import (
    Alias,
    Attachment,
    Contact,
    Domain,
    ForwardingRule,
    Mailbox,
    Message,
    Organization,
    OrganizationMember,
    VacationResponder,
)

logger = logging.getLogger("ifinmail.smtp")

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)


class SMTPHandler:
    async def handle_RCPT(
        self,
        _server,
        _session,
        _envelope,
        address: str,
        _rcpt_options: list[str],
    ):
        db = SessionLocal()
        try:
            if _recipient_exists(db, address):
                return MISSING
            return "550 No such user"
        finally:
            db.close()

    async def handle_DATA(
        self,
        _server,
        _session,
        envelope,
    ):
        mailfrom = envelope.mail_from
        rcpttos = envelope.rcpt_tos
        data = envelope.content

        parsed = BytesParser(policy=default).parsebytes(data)
        subject = parsed.get("subject", "")
        message_id = parsed.get("message-id", email.utils.make_msgid())

        body_text = ""
        body_html = ""
        attachments: list[tuple[str, str, bytes]] = []

        if parsed.is_multipart():
            for part in parsed.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                ctype = part.get_content_type()
                disp = part.get_content_disposition() or ""
                is_attachment = disp.startswith("attachment") or (
                    disp.startswith("inline") and ctype not in ("text/plain", "text/html")
                )
                if is_attachment:
                    filename = part.get_filename() or "untitled"
                    attachments.append((filename, ctype, part.get_payload(decode=True) or b""))
                elif ctype == "text/plain" and not body_text:
                    body_text = _decode_part(part)
                elif ctype == "text/html" and not body_html:
                    body_html = _decode_part(part)
        else:
            body_text = _decode_part(parsed)

        to_addr = parsed.get("to", "")
        cc_addr = parsed.get("cc", "")

        db = SessionLocal()
        try:
            stored = 0
            for rcpt in rcpttos:
                mailboxes = _resolve_recipients(db, rcpt)
                org_member_map: dict[int, OrganizationMember] = {}
                org = db.query(Organization).filter(Organization.email == rcpt).first()
                if org:
                    org_members = (
                        db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
                    )
                    org_member_map = {om.user_id: om for om in org_members}
                for mailbox in mailboxes:
                    if (
                        message_id
                        and db.query(Message)
                        .filter(
                            Message.mailbox_id == mailbox.id,
                            Message.message_id == message_id,
                        )
                        .first()
                    ):
                        continue
                    _subj = subject
                    _text = body_text
                    _html = body_html or None
                    om = org_member_map.get(mailbox.user_id)
                    if om:
                        _fn = om.first_name or (om.user.first_name if om.user else "")
                        _ln = om.last_name or (om.user.last_name if om.user else "")
                        info = MemberInfo(
                            first_name=_fn or mailbox.email.split("@")[0], last_name=_ln, email=mailbox.email
                        )
                        _subj = personalise(_subj, info)
                        _text = personalise(_text, info)
                        _html = personalise(_html, info) if _html else None
                    msg = Message(
                        mailbox_id=mailbox.id,
                        message_id=message_id,
                        from_addr=mailfrom,
                        to_addrs=to_addr,
                        cc_addrs=cc_addr or None,
                        subject=_subj,
                        body_text=_text,
                        body_html=_html,
                        size=len(data),
                        folder="INBOX",
                        has_attachments=1 if attachments else 0,
                    )
                    from ifinmail.api.priority import score_message

                    msg.priority_score = score_message(msg, db)
                    apply_filters_for_mailbox(
                        db,
                        mailbox,
                        rcpt,
                        {
                            "from_addr": mailfrom,
                            "subject": subject,
                            "body_text": body_text,
                            "body_html": body_html or "",
                        },
                        msg,
                    )
                    db.add(msg)
                    db.flush()

                    for filename, ctype, payload in attachments:
                        storage_path = os.environ.get("IFINMAIL_ATTACHMENT_STORAGE") or settings.attachment_storage
                        storage_dir = Path(storage_path)
                        storage_dir.mkdir(parents=True, exist_ok=True)
                        unique = f"{uuid.uuid4().hex}_{filename}"
                        (storage_dir / unique).write_bytes(payload)
                        att = Attachment(
                            message_id=msg.id,
                            filename=filename,
                            content_type=ctype,
                            size=len(payload),
                            storage_path=str(unique),
                        )
                        db.add(att)

                    stored += 1
            db.commit()
            logger.info(
                "Stored %d/%d messages from %s (%d attachments)",
                stored,
                len(rcpttos),
                mailfrom,
                len(attachments),
            )

            # Post-storage: forwarding and auto-reply
            for rcpt in rcpttos:
                mailboxes = _resolve_recipients(db, rcpt)
                for mailbox in mailboxes:
                    _handle_forwarding(
                        db, mailbox, mailfrom, to_addr, cc_addr, subject, body_text, body_html, data, attachments
                    )
                    _handle_autoreply(db, mailbox, mailfrom, mailboxes[0].id if mailboxes else 0)

            if stored == 0:
                return "550 No valid recipients"
            return MISSING
        except Exception:
            db.rollback()
            logger.exception("Failed to store message from %s", mailfrom)
            return "450 Temporary failure"
        finally:
            db.close()


def _recipient_exists(db: Session, email_addr: str) -> bool:
    domain_part = email_addr.split("@", 1)[-1]
    domain = db.query(Domain).filter(Domain.domain == domain_part).first()
    if not domain:
        return False
    mailbox = db.query(Mailbox).filter(Mailbox.email == email_addr).first()
    if mailbox:
        return True
    alias = db.query(Alias).filter(Alias.source == email_addr, Alias.enabled == 1).first()
    if alias:
        return True
    org = db.query(Organization).filter(Organization.email == email_addr).first()
    if org:
        return True
    return False


def _resolve_recipients(db: Session, email_addr: str) -> list[Mailbox]:
    mailbox = db.query(Mailbox).filter(Mailbox.email == email_addr).first()
    if mailbox:
        return [mailbox]

    org = db.query(Organization).filter(Organization.email == email_addr).first()
    if org:
        members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
        mailboxes = []
        for m in members:
            mb = db.query(Mailbox).filter(Mailbox.user_id == m.user_id).first()
            if mb:
                mailboxes.append(mb)
        return mailboxes

    aliases = db.query(Alias).filter(Alias.source == email_addr, Alias.enabled == 1).all()
    mailboxes = []
    seen = set()
    for alias in aliases:
        mb = db.query(Mailbox).filter(Mailbox.email == alias.target).first()
        if mb and mb.id not in seen:
            seen.add(mb.id)
            mailboxes.append(mb)
    return mailboxes


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")


_autoreply_sent: dict[tuple[int, str], str] = {}
"""In-memory cache: (mailbox_id, sender_lower) -> date_string (YYYY-MM-DD).
Prevents sending more than one auto-reply per sender per day per mailbox."""


def _now_date() -> str:
    from datetime import date

    return date.today().isoformat()


def _relay_send(from_addr: str, to_addr: str, subject: str, body_text: str, body_html: str | None = None):
    """Send an email via the configured SMTP relay."""
    if not settings.smtp_host:
        logger.warning("SMTP relay not configured, cannot send")
        return
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Message-ID"] = email.utils.make_msgid(domain=from_addr.split("@")[-1])
    msg["Date"] = email.utils.formatdate(localtime=True)
    if body_html:
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")
    else:
        msg.set_content(body_text)
    raw = msg.as_string()
    domain_part = from_addr.split("@")[-1] if "@" in from_addr else ""
    if domain_part:
        from ifinmail.api.deps import get_db
        from ifinmail.api.dkim_utils import dkim_sign_message
        from ifinmail.db.models import Domain

        try:
            sess = next(get_db())
            dom = sess.query(Domain).filter(Domain.domain == domain_part).first()
            if dom and dom.dkim_private_key:
                signed = dkim_sign_message(
                    raw.encode(),
                    domain=domain_part,
                    selector=dom.dkim_selector or "default",
                    private_key_pem=dom.dkim_private_key,
                )
                raw = signed.decode() if isinstance(signed, bytes) else signed
            sess.close()
        except Exception:
            pass
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as server:
            if settings.smtp_tls:
                server.starttls()
            if settings.smtp_user:
                server.login(settings.smtp_user, settings.smtp_password)
            server.sendmail(from_addr, [to_addr], raw)
        logger.info("Relayed email to %s via SMTP", to_addr)
    except Exception:
        logger.exception("Failed to relay email to %s", to_addr)


def _handle_forwarding(
    db: Session,
    mailbox: Mailbox,
    mailfrom: str,
    to_addr: str,
    cc_addr: str | None,
    subject: str,
    body_text: str,
    body_html: str | None,
    raw_data: bytes,
    attachments: list[tuple[str, str, bytes]],
):
    """Forward a copy of the message to each enabled forwarding target."""
    rules = (
        db.query(ForwardingRule)
        .filter(
            ForwardingRule.mailbox_id == mailbox.id,
            ForwardingRule.enabled == 1,
        )
        .all()
    )
    if not rules:
        return

    original_to = to_addr or mailbox.email
    for rule in rules:
        if rule.target_email == mailfrom:
            continue
        target = rule.target_email
        # Build a forward message — keep original subject with prefix
        fwd_subject = f"Fwd: {subject}" if subject else "(no subject)"
        fwd_body = (
            f"---------- Forwarded message ----------\n"
            f"From: {mailfrom}\n"
            f"To: {original_to}\n"
            f"Subject: {subject}\n"
            f"Date: {email.utils.formatdate(localtime=True)}\n\n"
            f"{body_text}"
        )
        fwd_html = None
        if body_html:
            fwd_html = (
                f"<hr><p><strong>Forwarded message</strong><br>"
                f"From: {mailfrom}<br>To: {original_to}<br>"
                f"Subject: {subject}<br>Date: {email.utils.formatdate(localtime=True)}</p>"
                f"<hr>{body_html}"
            )
        _relay_send(mailbox.email, target, fwd_subject, fwd_body, fwd_html)


def _handle_autoreply(
    db: Session,
    mailbox: Mailbox,
    mailfrom: str,
    rcpt_mailbox_id: int,
):
    """Send a vacation auto-reply if enabled, max once per sender per day."""
    from datetime import datetime

    vr = (
        db.query(VacationResponder)
        .filter(
            VacationResponder.mailbox_id == mailbox.id,
            VacationResponder.enabled == 1,
        )
        .first()
    )
    if not vr:
        return

    now = datetime.now(UTC)
    if vr.start_date and vr.start_date.replace(tzinfo=UTC) > now:
        return
    if vr.end_date and vr.end_date.replace(tzinfo=UTC) < now:
        return

    if vr.only_contacts:
        contact = (
            db.query(Contact)
            .filter(
                Contact.email == mailfrom,
                Contact.user_id == mailbox.user_id,
            )
            .first()
        )
        if not contact:
            return

    today = _now_date()
    key = (mailbox.id, mailfrom.lower())
    if _autoreply_sent.get(key) == today:
        return

    reply_subject = vr.subject or "Auto-reply"
    reply_body = vr.body or ""
    _relay_send(mailbox.email, mailfrom, reply_subject, reply_body)
    _autoreply_sent[key] = today
    logger.info("Sent auto-reply from %s to %s", mailbox.email, mailfrom)
