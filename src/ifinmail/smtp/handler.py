import email.utils
import logging
import os
import uuid
from email.parser import BytesParser
from email.policy import default
from pathlib import Path

from aiosmtpd.smtp import MISSING
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ifinmail.api.config import settings
from ifinmail.db.models import Alias, Attachment, Domain, Mailbox, Message

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
                mailbox = _resolve_recipient(db, rcpt)
                if not mailbox:
                    continue
                msg = Message(
                    mailbox_id=mailbox.id,
                    message_id=message_id,
                    from_addr=mailfrom,
                    to_addrs=to_addr,
                    cc_addrs=cc_addr or None,
                    subject=subject,
                    body_text=body_text,
                    body_html=body_html or None,
                    size=len(data),
                    folder="INBOX",
                    has_attachments=1 if attachments else 0,
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
    return False


def _resolve_recipient(db: Session, email_addr: str) -> Mailbox | None:
    mailbox = db.query(Mailbox).filter(Mailbox.email == email_addr).first()
    if mailbox:
        return mailbox
    alias = db.query(Alias).filter(Alias.source == email_addr, Alias.enabled == 1).first()
    if alias:
        return db.query(Mailbox).filter(Mailbox.email == alias.target).first()
    return None


def _decode_part(part) -> str:
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, UnicodeDecodeError):
        return payload.decode("utf-8", errors="replace")
