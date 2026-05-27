import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.api.deps import get_db
from ifinmail.db.models import Attachment, Message, User
from ifinmail.db.models import Mailbox as MailboxModel

router = APIRouter(prefix="/mail", tags=["mail"])


class AttachmentOut(BaseModel):
    id: int
    message_id: int | None
    filename: str
    content_type: str
    size: int

    model_config = ConfigDict(from_attributes=True)


def _storage_dir() -> Path:
    path = os.environ.get("IFINMAIL_ATTACHMENT_STORAGE") or settings.attachment_storage
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def _get_mailbox(user: User, db: Session) -> MailboxModel:
    mailbox = db.query(MailboxModel).filter(MailboxModel.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    return mailbox


@router.post("/attachments", response_model=AttachmentOut, status_code=status.HTTP_201_CREATED)
def upload_attachment(
    file: UploadFile,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    storage_dir = _storage_dir()
    unique = f"{uuid.uuid4().hex}_{file.filename}"
    dest = storage_dir / unique
    content = file.file.read()
    dest.write_bytes(content)

    att = Attachment(
        message_id=None,
        filename=file.filename or "untitled",
        content_type=file.content_type or "application/octet-stream",
        size=len(content),
        storage_path=str(unique),
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    return att


@router.get("/{message_id}/attachments", response_model=list[AttachmentOut])
def list_attachments(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return db.query(Attachment).filter(Attachment.message_id == message_id).all()


@router.get("/{message_id}/attachments/{attachment_id}", response_model=AttachmentOut)
def get_attachment_meta(
    message_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    att = db.query(Attachment).filter(Attachment.id == attachment_id, Attachment.message_id == message_id).first()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    return att


@router.get("/{message_id}/attachments/{attachment_id}/download")
def download_attachment(
    message_id: int,
    attachment_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    att = db.query(Attachment).filter(Attachment.id == attachment_id, Attachment.message_id == message_id).first()
    if not att:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attachment not found")
    full_path = _storage_dir() / att.storage_path
    if not full_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
    return FileResponse(
        path=str(full_path),
        filename=att.filename,
        media_type=att.content_type,
    )
