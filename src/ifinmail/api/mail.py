import email.utils
import logging
import smtplib
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import desc
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.api.deps import get_db
from ifinmail.api.ws_manager import notify_user
from ifinmail.db.models import Attachment, CustomFolder, Domain, Message, User
from ifinmail.db.models import Mailbox as MailboxModel

logger = logging.getLogger("ifinmail.mail")

router = APIRouter(prefix="/mail", tags=["mail"])


class MessageOut(BaseModel):
    id: int
    mailbox_id: int
    message_id: str | None
    from_addr: str
    to_addrs: str
    cc_addrs: str | None
    bcc_addrs: str | None
    subject: str | None
    body_text: str | None
    body_html: str | None
    size: int
    read: bool
    starred: bool
    has_attachments: bool
    folder: str
    in_reply_to: str | None
    references: str | None
    labels: str | None
    previous_folder: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v.isoformat()


class SendRequest(BaseModel):
    to: str
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None
    cc: str | None = None
    bcc: str | None = None
    in_reply_to: str | None = None
    attachment_ids: list[int] | None = None
    draft: bool = False


class SendResponse(BaseModel):
    message: str
    id: int


class PatchMessage(BaseModel):
    read: bool | None = None
    starred: bool | None = None
    labels: str | None = None
    folder: str | None = None
    to: str | None = None
    subject: str | None = None
    body_text: str | None = None
    attachment_ids: list[int] | None = None


class MoveRequest(BaseModel):
    folder: str


def _get_mailbox(user: User, db: Session) -> MailboxModel:
    mailbox = db.query(MailboxModel).filter(MailboxModel.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    return mailbox


# ── List messages ──


@router.get("", response_model=list[MessageOut])
def list_messages(
    response: Response,
    folder: str = Query("INBOX"),
    search: str | None = Query(None),
    from_addr: str | None = Query(None, alias="from"),
    to_addr: str | None = Query(None, alias="to"),
    subject: str | None = Query(None),
    before: str | None = Query(None),
    after: str | None = Query(None),
    has_attachment: bool | None = Query(None),
    read: bool | None = Query(None),
    starred: bool | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    query = db.query(Message).filter(Message.mailbox_id == mailbox.id)

    if folder:
        query = query.filter(Message.folder == folder.upper())
    if read is not None:
        query = query.filter(Message.read == int(read))
    if starred is not None:
        query = query.filter(Message.starred == int(starred))
    if from_addr:
        query = query.filter(Message.from_addr.ilike(f"%{from_addr}%"))
    if to_addr:
        query = query.filter(Message.to_addrs.ilike(f"%{to_addr}%"))
    if subject:
        query = query.filter(Message.subject.ilike(f"%{subject}%"))
    if before:
        try:
            dt = datetime.fromisoformat(before)
            query = query.filter(Message.created_at < dt)
        except ValueError:
            pass
    if after:
        try:
            dt = datetime.fromisoformat(after)
            query = query.filter(Message.created_at >= dt)
        except ValueError:
            pass
    if has_attachment is not None:
        query = query.filter(Message.has_attachments == int(has_attachment))
    if search:
        like = f"%{search}%"
        query = query.filter(
            Message.subject.ilike(like)
            | Message.body_text.ilike(like)
            | Message.from_addr.ilike(like)
            | Message.to_addrs.ilike(like)
        )

    total = query.count()
    offset = (page - 1) * per_page
    messages = query.order_by(desc(Message.created_at)).offset(offset).limit(per_page).all()
    response.headers["X-Total-Count"] = str(total)
    return messages


# ── Fixed-path routes (MUST be before /{message_id}) ──


@router.get("/unread-count")
def unread_count(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    count = (
        db.query(Message)
        .filter(
            Message.mailbox_id == mailbox.id,
            Message.read == 0,
            Message.folder == "INBOX",
        )
        .count()
    )
    return {"count": count}


@router.post("/mark-all-read")
def mark_all_read(
    folder: str = Query("INBOX"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    db.query(Message).filter(
        Message.mailbox_id == mailbox.id,
        Message.folder == folder.upper(),
        Message.read == 0,
    ).update({"read": 1}, synchronize_session=False)
    db.commit()
    return {"message": f"All messages in {folder.upper()} marked as read"}


class BulkIdsRequest(BaseModel):
    ids: list[int]
    permanent: bool = False


@router.post("/bulk-delete")
def bulk_delete(
    req: BulkIdsRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msgs = (
        db.query(Message)
        .filter(
            Message.id.in_(req.ids),
            Message.mailbox_id == mailbox.id,
        )
        .all()
    )
    for msg in msgs:
        if req.permanent or msg.folder == "TRASH":
            db.query(Attachment).filter(Attachment.message_id == msg.id).delete()
            db.delete(msg)
        else:
            msg.previous_folder = msg.folder
            msg.folder = "TRASH"
    db.commit()
    return {"deleted": len(msgs)}


class BulkMoveRequest(BaseModel):
    ids: list[int]
    folder: str


@router.post("/bulk-move")
def bulk_move(
    req: BulkMoveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    valid_folders = {"INBOX", "SENT", "DRAFTS", "TRASH", "SPAM", "ARCHIVE"}
    folder = req.folder.upper()
    mailbox = _get_mailbox(user, db)
    if folder not in valid_folders:
        custom = db.query(CustomFolder).filter(
            CustomFolder.mailbox_id == mailbox.id,
            CustomFolder.name == folder,
        ).first()
        if not custom:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid folder.",
            )
    db.query(Message).filter(
        Message.id.in_(req.ids),
        Message.mailbox_id == mailbox.id,
    ).update({"folder": folder}, synchronize_session=False)
    db.commit()
    return {"moved": len(req.ids)}


class FolderCreate(BaseModel):
    name: str


class FolderResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/folders", response_model=list[FolderResponse])
def list_folders(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    return db.query(CustomFolder).filter(CustomFolder.mailbox_id == mailbox.id).order_by(CustomFolder.name).all()


@router.post("/folders", response_model=FolderResponse, status_code=status.HTTP_201_CREATED)
def create_folder(
    req: FolderCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = req.name.strip().upper()
    if not name or name in {"INBOX", "SENT", "DRAFTS", "ARCHIVE", "SPAM", "TRASH"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or reserved folder name")
    mailbox = _get_mailbox(user, db)
    existing = (
        db.query(CustomFolder)
        .filter(
            CustomFolder.mailbox_id == mailbox.id,
            CustomFolder.name == name,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Folder already exists")
    folder = CustomFolder(mailbox_id=mailbox.id, name=name)
    db.add(folder)
    db.commit()
    db.refresh(folder)
    return folder


@router.delete("/folders/{folder_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_folder(
    folder_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    folder = (
        db.query(CustomFolder)
        .filter(
            CustomFolder.id == folder_id,
            CustomFolder.mailbox_id == mailbox.id,
        )
        .first()
    )
    if not folder:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Folder not found")
    db.query(Message).filter(
        Message.mailbox_id == mailbox.id,
        Message.folder == folder.name,
    ).update({"folder": "INBOX"}, synchronize_session=False)
    db.delete(folder)
    db.commit()


# ── Get single message ──


@router.get("/{message_id}", response_model=MessageOut)
def get_message(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return msg


# ── Send email ──


@router.post("", response_model=SendResponse, status_code=status.HTTP_201_CREATED)
async def send_email(
    req: SendRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)

    body_text = req.body_text or ""
    body_html = req.body_html

    folder = "DRAFTS" if req.draft else "SENT"

    msg = Message(
        mailbox_id=mailbox.id,
        message_id=email.utils.make_msgid(domain=user.email.split("@")[-1]),
        from_addr=user.email,
        to_addrs=req.to,
        cc_addrs=req.cc,
        bcc_addrs=req.bcc,
        subject=req.subject,
        body_text=body_text,
        body_html=body_html,
        size=len(body_text.encode("utf-8")) + (len(body_html.encode("utf-8")) if body_html else 0),
        folder=folder,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)

    if req.attachment_ids:
        db.query(Attachment).filter(
            Attachment.id.in_(req.attachment_ids),
        ).update({"message_id": msg.id}, synchronize_session=False)
        att_count = db.query(Attachment).filter(Attachment.message_id == msg.id).count()
        if att_count:
            msg.has_attachments = 1
        db.commit()

    if req.draft:
        return SendResponse(message="Draft saved", id=msg.id)

    # Local delivery — store copy in recipient INBOX
    def _deliver_local(addr: str):
        if not addr or "@" not in addr:
            return None
        domain_part = addr.split("@", 1)[-1]
        domain = db.query(Domain).filter(Domain.domain == domain_part).first()
        if not domain:
            return None
        recipient_mailbox = db.query(MailboxModel).filter(MailboxModel.email == addr).first()
        if not recipient_mailbox:
            return None
        local_msg = Message(
            mailbox_id=recipient_mailbox.id,
            message_id=msg.message_id,
            from_addr=user.email,
            to_addrs=req.to,
            cc_addrs=req.cc,
            bcc_addrs=req.bcc,
            subject=req.subject,
            body_text=body_text,
            body_html=body_html,
            size=msg.size,
            folder="INBOX",
        )
        db.add(local_msg)
        db.flush()
        if req.attachment_ids and msg.has_attachments:
            from ifinmail.api.attachments import _storage_dir

            storage_dir = _storage_dir()
            for att_id in req.attachment_ids:
                att = db.query(Attachment).filter(Attachment.id == att_id).first()
                if att:
                    src = storage_dir / att.storage_path
                    if src.exists():
                        unique = f"{uuid.uuid4().hex}_{att.filename}"
                        dest = storage_dir / unique
                        dest.write_bytes(src.read_bytes())
                        storage_path = str(unique)
                    else:
                        storage_path = att.storage_path
                    copy = Attachment(
                        message_id=local_msg.id,
                        filename=att.filename,
                        content_type=att.content_type,
                        size=att.size,
                        storage_path=storage_path,
                    )
                    db.add(copy)
            local_msg.has_attachments = 1
        return recipient_mailbox.user_id

    notify_uids = []
    for addr in [req.to] + ([req.cc] if req.cc else []) + ([req.bcc] if req.bcc else []):
        uid = _deliver_local(addr)
        if uid:
            notify_uids.append(uid)
    db.commit()

    for uid in notify_uids:
        await notify_user(uid, "new_mail", {"from": user.email, "subject": req.subject or "(no subject)"})

    if settings.smtp_host:
        try:
            _relay_send(user.email, req.to, req.subject, body_text, body_html, req.cc, req.bcc)
        except Exception as exc:
            logger.warning("SMTP relay failed for %s: %s", user.email, exc)

    return SendResponse(message="Message sent", id=msg.id)


def _relay_send(
    from_addr: str,
    to_addr: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
):
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Message-ID"] = email.utils.make_msgid(domain=from_addr.split("@")[-1])
    msg["Date"] = email.utils.formatdate(localtime=True)

    if cc:
        msg["Cc"] = cc

    recipients = [to_addr]
    if cc:
        recipients.append(cc)
    if bcc:
        recipients.append(bcc)

    if body_html:
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")
    else:
        msg.set_content(body_text)

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as server:
        if settings.smtp_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(from_addr, recipients, msg.as_string())


# ── Update flags ──


@router.patch("/{message_id}", response_model=MessageOut)
def patch_message(
    message_id: int,
    req: PatchMessage,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if req.read is not None:
        msg.read = int(req.read)
    if req.starred is not None:
        msg.starred = int(req.starred)
    if req.labels is not None:
        msg.labels = req.labels
    if req.folder is not None:
        msg.folder = req.folder
        if req.folder != "TRASH":
            msg.previous_folder = None
    if req.to is not None:
        msg.to_addrs = req.to
    if req.subject is not None:
        msg.subject = req.subject
    if req.body_text is not None:
        msg.body_text = req.body_text
        msg.size = len(req.body_text.encode("utf-8"))
    if req.attachment_ids is not None:
        db.query(Attachment).filter(
            Attachment.id.in_(req.attachment_ids),
        ).update({"message_id": msg.id}, synchronize_session=False)
        att_count = db.query(Attachment).filter(Attachment.message_id == msg.id).count()
        msg.has_attachments = 1 if att_count else 0

    db.commit()
    db.refresh(msg)
    return msg


# ── Move to folder ──


@router.put("/{message_id}/move", response_model=MessageOut)
def move_message(
    message_id: int,
    req: MoveRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    valid_folders = {"INBOX", "SENT", "DRAFTS", "TRASH", "SPAM", "ARCHIVE"}
    folder = req.folder.upper()
    mailbox = _get_mailbox(user, db)
    if folder not in valid_folders:
        custom = db.query(CustomFolder).filter(
            CustomFolder.mailbox_id == mailbox.id,
            CustomFolder.name == folder,
        ).first()
        if not custom:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid folder. Choose from: {', '.join(sorted(valid_folders))}",
            )

    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    msg.folder = folder
    db.commit()
    db.refresh(msg)
    return msg


# ── Soft delete (move to trash) ──


@router.delete("/{message_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_message(
    message_id: int,
    permanent: bool = Query(False),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if permanent or msg.folder == "TRASH":
        db.query(Attachment).filter(Attachment.message_id == msg.id).delete()
        db.delete(msg)
    else:
        msg.previous_folder = msg.folder
        msg.folder = "TRASH"
    db.commit()
