import email as email_parser
import imaplib
import logging
import os
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.api.deps import get_db
from ifinmail.db.models import Attachment, ImapImport, Message, User

logger = logging.getLogger("ifinmail.imap_import")

router = APIRouter(prefix="/mail/import", tags=["mail-import"])


class ImapConfigRequest(BaseModel):
    host: str = "imap.gmail.com"
    port: int = 993
    username: str
    password: str
    use_ssl: bool = True
    folder: str = "INBOX"


class ImapConfigResponse(BaseModel):
    host: str
    port: int
    username: str
    use_ssl: bool
    folder: str
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_run_count: int = 0


class ImapImportStatus(BaseModel):
    running: bool
    last_run_at: str | None = None
    last_run_status: str | None = None
    last_run_count: int = 0
    total_in_account: int = 0


_import_in_progress: dict[int, bool] = {}


@router.get("/imap")
def get_imap_config(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImapConfigResponse | None:
    cfg = db.query(ImapImport).filter(ImapImport.user_id == user.id).first()
    if not cfg:
        return None
    return ImapConfigResponse(
        host=cfg.host,
        port=cfg.port,
        username=cfg.username,
        use_ssl=bool(cfg.use_ssl),
        folder=cfg.folder,
        last_run_at=cfg.last_run_at.isoformat() if cfg.last_run_at else None,
        last_run_status=cfg.last_run_status,
        last_run_count=cfg.last_run_count or 0,
    )


@router.post("/imap", status_code=status.HTTP_201_CREATED)
def configure_imap(
    req: ImapConfigRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = db.query(ImapImport).filter(ImapImport.user_id == user.id).first()
    if not cfg:
        cfg = ImapImport(user_id=user.id)
        db.add(cfg)
    cfg.host = req.host
    cfg.port = req.port
    cfg.username = req.username
    cfg.password = req.password
    cfg.use_ssl = 1 if req.use_ssl else 0
    cfg.folder = req.folder
    db.commit()
    return {"detail": "IMAP configuration saved"}


@router.post("/imap/test")
def test_imap_connection(
    req: ImapConfigRequest,
    user: User = Depends(get_current_user),
):
    try:
        if req.use_ssl:
            conn = imaplib.IMAP4_SSL(req.host, req.port, timeout=15)
        else:
            conn = imaplib.IMAP4(req.host, req.port, timeout=15)
        conn.login(req.username, req.password)
        folder_count = len(conn.list()[1])
        conn.logout()
        return {"ok": True, "folders": folder_count, "detail": f"Connected. Found {folder_count} folders."}
    except imaplib.IMAP4.error as e:
        return {"ok": False, "detail": f"IMAP login failed: {e}"}
    except Exception as e:
        return {"ok": False, "detail": f"Connection failed: {e}"}


def _do_import(user_id: int, db_factory):
    """Background task: import emails from IMAP."""
    db = next(db_factory())
    try:
        cfg = db.query(ImapImport).filter(ImapImport.user_id == user_id).first()
        if not cfg:
            return
        _import_in_progress[user_id] = True

        if cfg.use_ssl:
            conn = imaplib.IMAP4_SSL(cfg.host, cfg.port, timeout=30)
        else:
            conn = imaplib.IMAP4(cfg.host, cfg.port, timeout=30)
        conn.login(cfg.username, cfg.password)
        conn.select(cfg.folder)

        _typ, data = conn.search(None, "ALL")
        msg_ids = data[0].split() if data[0] else []
        imported = 0

        existing_ids = {
            r[0]
            for r in db.query(Message.message_id)
            .filter(Message.mailbox_id == cfg.user.mailbox.id)
            .all()
            if r[0]
        }

        mailbox = cfg.user.mailbox
        storage = os.path.expanduser(settings.attachment_storage)
        os.makedirs(storage, exist_ok=True)

        batch = []
        for mid in msg_ids:
            if not _import_in_progress.get(user_id):
                break
            _typ, data = conn.fetch(mid, "(RFC822)")
            if not data or data[0] is None:
                continue
            raw = data[0][1] if isinstance(data[0], tuple) else data[0]
            if isinstance(raw, bytes):
                msg_parsed = email_parser.message_from_bytes(raw)
            else:
                msg_parsed = email_parser.message_from_string(raw)

            msg_id_val = msg_parsed.get("Message-ID", "").strip()
            if msg_id_val and msg_id_val in existing_ids:
                continue

            subject = msg_parsed.get("Subject", "")
            if subject and subject.startswith("=?"):
                try:
                    decoded_parts = email_parser.header.decode_header(subject)
                    subject = "".join(
                        part.decode(charset or "utf-8", errors="replace") if isinstance(part, bytes) else part
                        for part, charset in decoded_parts
                    )
                except Exception:
                    pass
            from_addr = msg_parsed.get("From", "")
            to_addrs = msg_parsed.get("To", "")
            cc_addrs = msg_parsed.get("Cc", "") or None
            date_str = msg_parsed.get("Date", "")

            body_text = ""
            body_html = ""
            attachments = []
            if msg_parsed.is_multipart():
                for part in msg_parsed.walk():
                    ct = part.get_content_type()
                    filename = part.get_filename()
                    if filename:
                        attachments.append((filename, ct, part.get_payload(decode=True) or b""))
                    elif ct == "text/plain":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            try:
                                body_text += payload.decode(charset, errors="replace")
                            except (LookupError, UnicodeDecodeError):
                                body_text += payload.decode("utf-8", errors="replace")
                    elif ct == "text/html":
                        payload = part.get_payload(decode=True)
                        if payload:
                            charset = part.get_content_charset() or "utf-8"
                            try:
                                body_html += payload.decode(charset, errors="replace")
                            except (LookupError, UnicodeDecodeError):
                                body_html += payload.decode("utf-8", errors="replace")
            else:
                ct = msg_parsed.get_content_type()
                payload = msg_parsed.get_payload(decode=True)
                if payload:
                    charset = msg_parsed.get_content_charset() or "utf-8"
                    try:
                        decoded = payload.decode(charset, errors="replace")
                    except (LookupError, UnicodeDecodeError):
                        decoded = payload.decode("utf-8", errors="replace")
                    if ct == "text/html":
                        body_html = decoded
                    else:
                        body_text = decoded

            if not body_text and not body_html:
                continue

            parsed_date = None
            if date_str:
                try:
                    parsed_date = email_parser.utils.parsedate_to_datetime(date_str)
                except Exception:
                    pass

            msg = Message(
                mailbox_id=mailbox.id,
                message_id=msg_id_val or None,
                from_addr=from_addr or "unknown@unknown.com",
                to_addrs=to_addrs or "",
                cc_addrs=cc_addrs,
                subject=subject or "(no subject)",
                body_text=body_text,
                body_html=body_html,
                size=len(raw) if isinstance(raw, bytes) else len(raw.encode()),
                folder="INBOX",
                created_at=parsed_date or datetime.now(UTC),
            )
            db.add(msg)
            db.flush()
            batch.append(msg)
            if msg_id_val:
                existing_ids.add(msg_id_val)
            imported += 1

            for fname, ct, data_bytes in attachments:
                if data_bytes:
                    disk_name = f"{uuid.uuid4().hex}_{fname}"
                    disk_path = os.path.join(storage, disk_name)
                    with open(disk_path, "wb") as f:
                        f.write(data_bytes)
                    att = Attachment(
                        message_id=msg.id,
                        filename=fname,
                        content_type=ct,
                        disk_path=disk_path,
                        size=len(data_bytes),
                    )
                    db.add(att)

            if len(batch) >= 50:
                db.commit()
                batch.clear()

        db.commit()
        conn.logout()

        cfg.last_run_at = datetime.now(UTC)
        cfg.last_run_status = "completed"
        cfg.last_run_count = imported
        db.commit()
    except Exception as e:
        logger.exception("IMAP import failed for user %s", user_id)
        try:
            cfg = db.query(ImapImport).filter(ImapImport.user_id == user_id).first()
            if cfg:
                cfg.last_run_at = datetime.now(UTC)
                cfg.last_run_status = f"failed: {e}"
                db.commit()
        except Exception:
            pass
    finally:
        _import_in_progress[user_id] = False
        db.close()


@router.post("/imap/run")
def run_imap_import(
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    cfg = db.query(ImapImport).filter(ImapImport.user_id == user.id).first()
    if not cfg:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Configure IMAP settings first")
    if _import_in_progress.get(user.id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Import already in progress")

    from ifinmail.api.deps import get_db as get_db_gen

    background_tasks.add_task(_do_import, user.id, get_db_gen)
    cfg.last_run_status = "running"
    db.commit()
    return {"detail": "Import started in background"}


@router.get("/imap/status")
def get_import_status(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> ImapImportStatus:
    cfg = db.query(ImapImport).filter(ImapImport.user_id == user.id).first()
    if not cfg:
        return ImapImportStatus(running=False)
    return ImapImportStatus(
        running=_import_in_progress.get(user.id, False),
        last_run_at=cfg.last_run_at.isoformat() if cfg.last_run_at else None,
        last_run_status=cfg.last_run_status,
        last_run_count=cfg.last_run_count or 0,
        total_in_account=0,
    )
