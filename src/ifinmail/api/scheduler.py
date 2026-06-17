import email.utils
import json
import logging
from datetime import datetime
from email.message import EmailMessage

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from ifinmail.api.config import settings
from ifinmail.db.models import Attachment, Message, ScheduledMessage

logger = logging.getLogger("ifinmail.scheduler")

_engine = create_engine(settings.database_url, pool_pre_ping=True)
_SessionLocal = sessionmaker(bind=_engine)

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler()
    return _scheduler


async def start_scheduler():
    sched = get_scheduler()
    sched.add_job(
        _process_due_messages,
        trigger="interval",
        seconds=30,
        id="process_scheduled_messages",
        replace_existing=True,
    )
    sched.add_job(
        _unsnooze_expired,
        trigger="interval",
        seconds=60,
        id="unsnooze_expired",
        replace_existing=True,
    )
    sched.start()
    logger.info("Scheduler started (interval=30s)")


async def stop_scheduler():
    global _scheduler
    if _scheduler is not None and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None
        logger.info("Scheduler stopped")


def _process_due_messages():
    db = _SessionLocal()
    try:
        now = datetime.utcnow()
        due = (
            db.query(ScheduledMessage)
            .filter(ScheduledMessage.status == "pending", ScheduledMessage.scheduled_at <= now)
            .all()
        )
        if not due:
            return
        logger.info("Processing %d due scheduled messages", len(due))
        for sm in due:
            try:
                _send_scheduled(db, sm)
            except Exception as exc:
                sm.status = "failed"
                sm.error = str(exc)
                logger.exception("Failed to send scheduled message %d", sm.id)
        db.commit()
    except Exception:
        logger.exception("Error in scheduler job")
    finally:
        db.close()


def _send_scheduled(db: Session, sm: ScheduledMessage):
    msg = EmailMessage()
    msg["From"] = sm.user.email if sm.user else "noreply"
    msg["To"] = sm.to_addr
    msg["Subject"] = sm.subject
    msg["Message-ID"] = email.utils.make_msgid(domain=msg["From"].split("@")[-1])
    msg["Date"] = email.utils.formatdate(localtime=True)
    if sm.cc_addr:
        msg["Cc"] = sm.cc_addr
    if sm.body_html:
        msg.set_content(sm.body_text or "")
        msg.add_alternative(sm.body_html, subtype="html")
    else:
        msg.set_content(sm.body_text or "")

    recipients = [sm.to_addr]
    if sm.cc_addr:
        recipients.append(sm.cc_addr)
    if sm.bcc_addr:
        recipients.append(sm.bcc_addr)

    import smtplib

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as server:
        if settings.smtp_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(msg["From"], recipients, msg.as_string())

    msg_id = None
    if settings.database_url.startswith("sqlite"):
        from sqlalchemy import text as sa_text

        db.execute(sa_text("PRAGMA foreign_keys=OFF"))
        try:
            record = Message(
                mailbox_id=sm.user.mailbox.id,
                message_id=msg["Message-ID"],
                from_addr=msg["From"],
                to_addrs=sm.to_addr,
                cc_addrs=sm.cc_addr or None,
                bcc_addrs=sm.bcc_addr or None,
                subject=sm.subject,
                body_text=sm.body_text or "",
                body_html=sm.body_html or None,
                size=len(msg.as_bytes()),
                folder="SENT",
            )
            db.add(record)
            db.flush()
            msg_id = record.id
            if sm.attachment_ids:
                att_ids = json.loads(sm.attachment_ids) if isinstance(sm.attachment_ids, str) else sm.attachment_ids
                for att_id in att_ids:
                    att = db.query(Attachment).filter(Attachment.id == att_id).first()
                    if att:
                        new_att = Attachment(
                            message_id=record.id,
                            filename=att.filename,
                            content_type=att.content_type,
                            size=att.size,
                            storage_path=att.storage_path,
                        )
                        db.add(new_att)
        finally:
            db.execute(sa_text("PRAGMA foreign_keys=ON"))

    sm.status = "sent"
    sm.sent_at = datetime.utcnow()
    sm.message_id = msg_id
    sm.error = None
    logger.info("Sent scheduled message %d to %s", sm.id, sm.to_addr)

    if sm.repeat_interval and (not sm.repeat_until or sm.repeat_until > datetime.utcnow()):
        from datetime import timedelta

        delta = None
        if sm.repeat_interval == "daily":
            delta = timedelta(days=1)
        elif sm.repeat_interval == "weekly":
            delta = timedelta(weeks=1)
        elif sm.repeat_interval == "monthly":
            delta = timedelta(days=30)
        if delta:
            next_at = sm.scheduled_at + delta
            if not sm.repeat_until or next_at <= sm.repeat_until:
                new_sm = ScheduledMessage(
                    user_id=sm.user_id,
                    campaign_id=sm.campaign_id,
                    campaign_step_id=sm.campaign_step_id,
                    to_addr=sm.to_addr,
                    cc_addr=sm.cc_addr,
                    bcc_addr=sm.bcc_addr,
                    subject=sm.subject,
                    body_text=sm.body_text,
                    body_html=sm.body_html,
                    attachment_ids=sm.attachment_ids,
                    scheduled_at=next_at,
                    repeat_interval=sm.repeat_interval,
                    repeat_until=sm.repeat_until,
                )
                db.add(new_sm)
                logger.info("Scheduled next recurring message %s for %s", sm.repeat_interval, next_at)


def _unsnooze_expired():
    """Move snoozed messages back to their original folder after resume_at passes."""
    from datetime import UTC, datetime

    db = _SessionLocal()
    try:
        now = datetime.now(UTC)
        rows = (
            db.query(Message)
            .filter(Message.folder == "SNOOZED", Message.snoozed_until.isnot(None), Message.snoozed_until <= now)
            .all()
        )
        for msg in rows:
            msg.folder = msg.previous_folder or "INBOX"
            msg.previous_folder = None
            msg.snoozed_until = None
        if rows:
            db.commit()
            logger.info("Unsnoozed %d messages", len(rows))
    except Exception:
        logger.exception("Failed to unsnooze messages")
    finally:
        db.close()
