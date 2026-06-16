import email.utils
import logging
import smtplib
import uuid
import threading
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, field_serializer
from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ifinmail.api.ai_assistant import PROMPT_REPLY, _call_openai
from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.api.deps import get_db
from ifinmail.api.filter_engine import apply_filters_for_mailbox
from ifinmail.api.limiter import user_moderate
from ifinmail.api.personalize import MemberInfo, personalise
from ifinmail.api.tracking import inject_tracking
from ifinmail.api.ws_manager import fire_notification
from ifinmail.db.models import (
    Attachment,
    Contact,
    CustomFolder,
    Domain,
    EmailDelivery,
    Message,
    Organization,
    OrganizationMember,
    OrgSharedInboxMessage,
    SpamReport,
    User,
    VacationResponder,
)
from ifinmail.db.models import Mailbox as MailboxModel

logger = logging.getLogger("ifinmail.mail")

router = APIRouter(prefix="/mail", tags=["mail"])

_undo_timers: dict[int, threading.Timer] = {}
"""Pending undo timers keyed by sent Message.id. Cancelled on undo."""

STANDARD_FOLDERS = {"INBOX", "SENT", "DRAFTS", "TRASH", "SPAM", "ARCHIVE"}


def _validate_folder(folder: str, mailbox: MailboxModel, db: Session) -> None:
    if folder not in STANDARD_FOLDERS:
        custom = (
            db.query(CustomFolder)
            .filter(
                CustomFolder.mailbox_id == mailbox.id,
                CustomFolder.name == folder,
            )
            .first()
        )
        if not custom:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid folder. Choose from: {', '.join(sorted(STANDARD_FOLDERS))}",
            )


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
    priority_score: float = 0.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime) -> str:
        if v.tzinfo is None:
            v = v.replace(tzinfo=UTC)
        return v.isoformat()


class ConversationOut(BaseModel):
    id: str
    subject: str | None
    messages: list[MessageOut]
    total_count: int
    read_count: int
    unread_count: int
    participants: list[str]
    latest_at: datetime
    latest_from: str
    snippet: str

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("latest_at")
    def serialize_latest_at(self, v: datetime) -> str:
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
    undo_seconds: int = 0
    request_read_receipt: bool = False


class SendResponse(BaseModel):
    message: str
    id: int
    undo_available_until: datetime | None = None

    @field_serializer("undo_available_until")
    def serialize_dt(self, v: datetime | None) -> str | None:
        return v.isoformat() if v else None


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

    folder_val = folder.upper() if folder else ""
    now_utc = datetime.now(UTC)

    if folder_val == "INBOX":
        # Restore expired snoozed messages back to inbox
        db.query(Message).filter(
            Message.mailbox_id == mailbox.id,
            Message.folder == "SNOOZED",
            Message.snoozed_until.isnot(None),
            Message.snoozed_until <= now_utc,
        ).update({"folder": Message.previous_folder, "snoozed_until": None, "previous_folder": None})
        db.commit()
        query = query.filter(
            Message.folder == "INBOX",
            Message.snoozed_until.is_(None),
        )
    elif folder_val == "PRIORITY":
        query = query.filter(
            Message.folder == "INBOX",
            Message.snoozed_until.is_(None),
        )
        priority_order = desc(Message.priority_score)
    elif folder_val == "SNOOZED":
        query = query.filter(
            Message.folder == "SNOOZED",
            Message.snoozed_until > now_utc,
        )
    elif folder:
        query = query.filter(Message.folder == folder_val)

    order_col = priority_order if folder_val == "PRIORITY" else desc(Message.created_at)

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
        from ifinmail.api.search_parser import parse_search
        search_filters, free_text = parse_search(search)
        if search_filters.get("from_addr"):
            query = query.filter(Message.from_addr.ilike(f"%{search_filters['from_addr']}%"))
        if search_filters.get("to_addr"):
            query = query.filter(Message.to_addrs.ilike(f"%{search_filters['to_addr']}%"))
        if search_filters.get("subject"):
            query = query.filter(Message.subject.ilike(f"%{search_filters['subject']}%"))
        if search_filters.get("has_attachment"):
            query = query.filter(Message.has_attachments == 1)
        if "read" in search_filters:
            query = query.filter(Message.read == int(search_filters["read"]))
        if "starred" in search_filters:
            query = query.filter(Message.starred == int(search_filters["starred"]))
        if search_filters.get("before"):
            try:
                query = query.filter(Message.created_at < datetime.fromisoformat(search_filters["before"]))
            except ValueError:
                pass
        if search_filters.get("after"):
            try:
                query = query.filter(Message.created_at >= datetime.fromisoformat(search_filters["after"]))
            except ValueError:
                pass
        if search_filters.get("folder"):
            query = query.filter(Message.folder == search_filters["folder"])
        if search_filters.get("label"):
            query = query.filter(Message.labels.ilike(f"%{search_filters['label']}%"))
        if free_text:
            like = f"%{free_text}%"
            query = query.filter(
                Message.subject.ilike(like)
                | Message.body_text.ilike(like)
                | Message.from_addr.ilike(like)
                | Message.to_addrs.ilike(like)
            )

    total = query.count()
    offset = (page - 1) * per_page
    messages = query.order_by(order_col).offset(offset).limit(per_page).all()
    response.headers["X-Total-Count"] = str(total)
    return messages


def _normalize_subject(subject: str | None) -> str:
    if not subject:
        return ""
    s = subject.strip()
    while True:
        lowered = s.lower()
        if lowered.startswith("re:"):
            s = s[3:].strip()
        elif lowered.startswith("fwd:"):
            s = s[4:].strip()
        elif lowered.startswith("fw:"):
            s = s[3:].strip()
        else:
            break
    return s.strip().lower()


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(
    response: Response,
    folder: str = Query("INBOX"),
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    now_utc = datetime.now(UTC)

    base_query = db.query(Message).filter(Message.mailbox_id == mailbox.id)

    folder_val = folder.upper() if folder else "INBOX"
    if folder_val == "INBOX":
        db.query(Message).filter(
            Message.mailbox_id == mailbox.id,
            Message.folder == "SNOOZED",
            Message.snoozed_until.isnot(None),
            Message.snoozed_until <= now_utc,
        ).update({"folder": Message.previous_folder, "snoozed_until": None, "previous_folder": None})
        db.commit()
        base_query = base_query.filter(
            Message.folder == "INBOX",
            Message.snoozed_until.is_(None),
        )
    else:
        base_query = base_query.filter(Message.folder == folder_val)

    if search:
        from ifinmail.api.search_parser import parse_search
        search_filters, free_text = parse_search(search)
        if search_filters.get("from_addr"):
            base_query = base_query.filter(Message.from_addr.ilike(f"%{search_filters['from_addr']}%"))
        if search_filters.get("to_addr"):
            base_query = base_query.filter(Message.to_addrs.ilike(f"%{search_filters['to_addr']}%"))
        if search_filters.get("subject"):
            base_query = base_query.filter(Message.subject.ilike(f"%{search_filters['subject']}%"))
        if search_filters.get("has_attachment"):
            base_query = base_query.filter(Message.has_attachments == 1)
        if "read" in search_filters:
            base_query = base_query.filter(Message.read == int(search_filters["read"]))
        if "starred" in search_filters:
            base_query = base_query.filter(Message.starred == int(search_filters["starred"]))
        if search_filters.get("before"):
            try:
                base_query = base_query.filter(Message.created_at < datetime.fromisoformat(search_filters["before"]))
            except ValueError:
                pass
        if search_filters.get("after"):
            try:
                base_query = base_query.filter(Message.created_at >= datetime.fromisoformat(search_filters["after"]))
            except ValueError:
                pass
        if search_filters.get("folder"):
            base_query = base_query.filter(Message.folder == search_filters["folder"])
        if search_filters.get("label"):
            base_query = base_query.filter(Message.labels.ilike(f"%{search_filters['label']}%"))
        if free_text:
            like = f"%{free_text}%"
            base_query = base_query.filter(
                Message.subject.ilike(like)
                | Message.body_text.ilike(like)
                | Message.from_addr.ilike(like)
                | Message.to_addrs.ilike(like)
            )

    all_msgs = base_query.order_by(desc(Message.created_at)).all()

    groups: dict[str, list[Message]] = {}
    for msg in all_msgs:
        key = _normalize_subject(msg.subject) or f"__no_subject_{msg.id}"
        groups.setdefault(key, []).append(msg)

    conversations: list[ConversationOut] = []
    for key, msgs in groups.items():
        msgs.sort(key=lambda m: m.created_at)
        latest = msgs[-1]
        participants = list({m.from_addr for m in msgs})
        read_count = sum(1 for m in msgs if m.read)
        unread_count = len(msgs) - read_count
        snippet = (latest.body_text or latest.body_html or "")[:120]
        conversations.append(ConversationOut(
            id=key,
            subject=latest.subject,
            messages=msgs,
            total_count=len(msgs),
            read_count=read_count,
            unread_count=unread_count,
            participants=participants,
            latest_at=latest.created_at,
            latest_from=latest.from_addr,
            snippet=snippet,
        ))

    conversations.sort(key=lambda c: c.latest_at, reverse=True)

    total = len(conversations)
    offset = (page - 1) * per_page
    page_convos = conversations[offset : offset + per_page]
    response.headers["X-Total-Count"] = str(total)
    return page_convos


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


@router.get("/folder-counts")
def folder_counts(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    rows = (
        db.query(Message.folder, func.count(Message.id))
        .filter(
            Message.mailbox_id == mailbox.id,
            Message.read == 0,
        )
        .group_by(Message.folder)
        .all()
    )
    result = {row[0]: row[1] for row in rows}
    priority_unread = (
        db.query(func.count(Message.id))
        .filter(
            Message.mailbox_id == mailbox.id,
            Message.read == 0,
            Message.folder == "INBOX",
            Message.snoozed_until.is_(None),
            Message.priority_score >= 2.0,
        )
        .scalar()
        or 0
    )
    result["PRIORITY"] = priority_unread
    return result


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
    folder = req.folder.upper()
    mailbox = _get_mailbox(user, db)
    _validate_folder(folder, mailbox, db)
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
def send_email(
    req: SendRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
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
        read_receipt_requested=int(req.request_read_receipt),
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

    all_recipients = [r for r in [req.to] + ([req.cc] if req.cc else []) + ([req.bcc] if req.bcc else []) if r and "@" in r]
    for addr in all_recipients:
        delivery = EmailDelivery(message_id=msg.id, recipient=addr, status="sent")
        db.add(delivery)
    db.commit()

    first_delivery = db.query(EmailDelivery).filter(EmailDelivery.message_id == msg.id).first()
    if body_html and first_delivery:
        body_html = inject_tracking(body_html, first_delivery.id)
        msg.body_html = body_html
        db.commit()

    # Local delivery — store copy in recipient INBOX
    def _deliver_local(addr: str):
        if not addr or "@" not in addr:
            return []

        org = db.query(Organization).filter(Organization.email == addr).first()
        if org:
            member_uids = []
            members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
            first_msg_id = None
            for m in members:
                mb = db.query(MailboxModel).filter(MailboxModel.user_id == m.user_id).first()
                if not mb:
                    continue
                _fn = m.first_name or (m.user.first_name if m.user else "")
                _ln = m.last_name or (m.user.last_name if m.user else "")
                info = MemberInfo(first_name=_fn or mb.email.split("@")[0], last_name=_ln, email=mb.email)
                local_msg = Message(
                    mailbox_id=mb.id,
                    message_id=msg.message_id,
                    from_addr=user.email,
                    to_addrs=req.to,
                    cc_addrs=req.cc,
                    bcc_addrs=req.bcc,
                    subject=personalise(req.subject or "", info) if req.to == addr else (req.subject or ""),
                    body_text=personalise(body_text, info) if req.to == addr else body_text,
                    body_html=personalise(body_html, info) if body_html and req.to == addr else body_html,
                    size=msg.size,
                    folder="INBOX",
                )
                apply_filters_for_mailbox(
                    db, mb, addr,
                    {"from_addr": user.email, "subject": req.subject or "", "body_text": body_text, "body_html": body_html or ""},
                    local_msg,
                )
                db.add(local_msg)
                db.flush()
                if first_msg_id is None:
                    first_msg_id = local_msg.id
                if req.attachment_ids and msg.has_attachments:
                    _copy_attachments(req.attachment_ids, local_msg.id)
                _maybe_autoreply(mb, user.email)
                member_uids.append(mb.user_id)

            if first_msg_id:
                existing_shared = db.query(OrgSharedInboxMessage).filter(
                    OrgSharedInboxMessage.organization_id == org.id,
                    OrgSharedInboxMessage.from_email == user.email,
                    OrgSharedInboxMessage.subject == req.subject,
                ).first()
                if not existing_shared:
                    shared = OrgSharedInboxMessage(
                        organization_id=org.id,
                        from_email=user.email,
                        to_email=addr,
                        subject=req.subject,
                        body_text=body_text,
                        body_html=body_html,
                    )
                    db.add(shared)
                    db.flush()
                    shared_inbox_msgs.append({"id": shared.id, "org_id": org.id, "subject": req.subject or ""})
            return member_uids

        domain_part = addr.split("@", 1)[-1]
        domain = db.query(Domain).filter(Domain.domain == domain_part).first()
        if not domain:
            return []
        recipient_mailbox = db.query(MailboxModel).filter(MailboxModel.email == addr).first()
        if not recipient_mailbox:
            return []
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
        apply_filters_for_mailbox(
            db, recipient_mailbox, addr,
            {"from_addr": user.email, "subject": req.subject or "", "body_text": body_text, "body_html": body_html or ""},
            local_msg,
        )
        db.add(local_msg)
        db.flush()
        if req.attachment_ids and msg.has_attachments:
            _copy_attachments(req.attachment_ids, local_msg.id)
        _maybe_autoreply(recipient_mailbox, user.email)
        return [recipient_mailbox.user_id]

    def _maybe_autoreply(mbox: MailboxModel, sender_email: str) -> None:
        vr = db.query(VacationResponder).filter(
            VacationResponder.mailbox_id == mbox.id,
            VacationResponder.enabled == 1,
        ).first()
        if not vr:
            return
        now = datetime.now(UTC)
        if vr.start_date and vr.start_date.replace(tzinfo=UTC) > now:
            return
        if vr.end_date and vr.end_date.replace(tzinfo=UTC) < now:
            return
        if vr.only_contacts:
            contact = db.query(Contact).filter(
                Contact.email == sender_email,
                Contact.user_id == mbox.user_id,
            ).first()
            if not contact:
                return
        from ifinmail.api.ws_manager import fire_notification as _fire_notif
        _fire_notif(mbox.user_id, "autoreply.sent", {
            "to": sender_email,
            "subject": vr.subject or "Auto-reply",
        })

    def _copy_attachments(att_ids: list[int], target_msg_id: int):
        from ifinmail.api.attachments import _storage_dir
        storage_dir = _storage_dir()
        for att_id in att_ids:
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
                    message_id=target_msg_id,
                    filename=att.filename,
                    content_type=att.content_type,
                    size=att.size,
                    storage_path=storage_path,
                )
                db.add(copy)

    shared_inbox_msgs: list[dict] = []
    notify_uids = []
    for addr in [req.to] + ([req.cc] if req.cc else []) + ([req.bcc] if req.bcc else []):
        uids = _deliver_local(addr)
        notify_uids.extend(uids)
    db.commit()

    undo_window = max(0, min(req.undo_seconds, 30))
    deadline = datetime.now(UTC) + timedelta(seconds=undo_window) if undo_window > 0 else None

    if deadline:
        msg.undo_deadline = deadline
        db.commit()

    def _commit_send():
        """Relay via SMTP + fire notifications. Called after undo window expires."""
        try:
            with next(get_db()) as s:
                s.query(Message).filter(Message.id == msg.id).update({"undo_deadline": None})
                s.commit()
        except Exception:
            pass
        if settings.smtp_host:
            try:
                _relay_send(user.email, req.to, req.subject, body_text, body_html, req.cc, req.bcc, read_receipt_requested=bool(req.request_read_receipt))
            except Exception as exc:
                logger.warning("SMTP relay failed for %s: %s", user.email, exc)
        for uid in notify_uids:
            fire_notification(uid, "new_mail", {"from": user.email, "subject": req.subject or "(no subject)"})
        for si in shared_inbox_msgs:
            member_ids_ns = []
            try:
                with next(get_db()) as s:
                    member_ids_ns = [m.user_id for m in s.query(OrganizationMember).filter(OrganizationMember.organization_id == si["org_id"]).all()]
            except Exception:
                pass
            for mid in member_ids_ns:
                fire_notification(mid, "org.shared_inbox.new", {
                    "organization_id": si["org_id"],
                    "message_id": si["id"],
                    "subject": si["subject"],
                    "from_email": user.email,
                })
        fire_notification(user.id, "mail.sent", {
            "message_id": msg.id,
            "to": req.to,
            "subject": req.subject,
            "timestamp": datetime.now(UTC).isoformat(),
        })

    if deadline:
        timer = threading.Timer(undo_window, _commit_send)
        timer.daemon = True
        _undo_timers[msg.id] = timer
        timer.start()
        return SendResponse(message="Message sent (undo available)", id=msg.id, undo_available_until=deadline)

    for uid in notify_uids:
        fire_notification(uid, "new_mail", {"from": user.email, "subject": req.subject or "(no subject)"})
    for si in shared_inbox_msgs:
        member_ids = [m.user_id for m in db.query(OrganizationMember).filter(OrganizationMember.organization_id == si["org_id"]).all()]
        for mid in member_ids:
            fire_notification(mid, "org.shared_inbox.new", {
                "organization_id": si["org_id"],
                "message_id": si["id"],
                "subject": si["subject"],
                "from_email": user.email,
            })
    if settings.smtp_host:
        try:
            _relay_send(user.email, req.to, req.subject, body_text, body_html, req.cc, req.bcc, read_receipt_requested=bool(req.request_read_receipt))
        except Exception as exc:
            logger.warning("SMTP relay failed for %s: %s", user.email, exc)
    fire_notification(user.id, "mail.sent", {
        "message_id": msg.id,
        "to": req.to,
        "subject": req.subject,
        "timestamp": datetime.now(UTC).isoformat(),
    })
    return SendResponse(message="Message sent", id=msg.id)


def _relay_send(
    from_addr: str,
    to_addr: str,
    subject: str,
    body_text: str,
    body_html: str | None = None,
    cc: str | None = None,
    bcc: str | None = None,
    read_receipt_requested: bool = False,
):
    msg = EmailMessage()
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg["Message-ID"] = email.utils.make_msgid(domain=from_addr.split("@")[-1])
    msg["Date"] = email.utils.formatdate(localtime=True)

    if read_receipt_requested:
        msg["Disposition-Notification-To"] = from_addr

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
                raw = dkim_sign_message(
                    raw.encode(),
                    domain=domain_part,
                    selector=dom.dkim_selector or "default",
                    private_key_pem=dom.dkim_private_key,
                )
                raw = raw.decode() if isinstance(raw, bytes) else raw
            sess.close()
        except Exception:
            pass

    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as server:
        if settings.smtp_tls:
            server.starttls()
        if settings.smtp_user:
            server.login(settings.smtp_user, settings.smtp_password)
        server.sendmail(from_addr, recipients, raw)
    from ifinmail.api.metrics import emails_sent_total
    emails_sent_total.inc((to_addr, "success"))


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
    folder = req.folder.upper()
    mailbox = _get_mailbox(user, db)
    _validate_folder(folder, mailbox, db)

    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    msg.folder = folder
    db.commit()
    db.refresh(msg)
    return msg


# ── Undo send ──


class UndoResponse(BaseModel):
    message: str
    id: int


@router.post("/{message_id}/undo", response_model=UndoResponse)
def undo_send(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if not msg.undo_deadline:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Undo not available for this message")
    if datetime.now(UTC) > msg.undo_deadline:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Undo window has expired")

    timer = _undo_timers.pop(message_id, None)
    if timer:
        timer.cancel()

    msg.undo_deadline = None
    msg.folder = "DRAFTS"
    db.flush()

    # Remove copies from recipients' inboxes (same message_id within this mailbox scope)
    recipient_msgs = db.query(Message).filter(
        Message.message_id == msg.message_id,
        Message.folder == "INBOX",
    ).all()
    for rmsg in recipient_msgs:
        db.delete(rmsg)
    db.commit()

    return UndoResponse(message="Send undone, message moved to drafts", id=msg.id)


# ── Snooze ──


class SnoozeRequest(BaseModel):
    resume_at: datetime


class SnoozeResponse(BaseModel):
    message: str
    id: int
    snoozed_until: str | None = None


@router.post("/{message_id}/snooze", response_model=SnoozeResponse)
def snooze_message(
    message_id: int,
    req: SnoozeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if msg.snoozed_until and msg.snoozed_until > datetime.now(UTC):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is already snoozed")
    if msg.folder != "INBOX":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only inbox messages can be snoozed")

    msg.previous_folder = msg.folder
    msg.folder = "SNOOZED"
    msg.snoozed_until = req.resume_at
    db.commit()
    return SnoozeResponse(message="Message snoozed", id=msg.id, snoozed_until=req.resume_at.isoformat())


@router.post("/{message_id}/unsnooze", response_model=SnoozeResponse)
def unsnooze_message(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if not msg.snoozed_until:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message is not snoozed")

    msg.folder = msg.previous_folder or "INBOX"
    msg.previous_folder = None
    msg.snoozed_until = None
    db.commit()
    return SnoozeResponse(message="Message unsnoozed", id=msg.id)


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


# ── Smart Reply ──


class SuggestReplyResponse(BaseModel):
    suggestions: list[str]


@router.post("/{message_id}/suggest-reply", response_model=SuggestReplyResponse)
def suggest_reply(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    original = f"Subject: {msg.subject or ''}\nBody: {(msg.body_text or msg.body_html or '')[:2000]}"
    try:
        prompt = PROMPT_REPLY.format(original_email=original, key_points="", tone="professional")
        result = _call_openai(prompt)
        if isinstance(result, dict) and "body" in result and "would appear" not in result["body"]:
            return SuggestReplyResponse(suggestions=[result["body"]])
    except Exception:
        pass

    return SuggestReplyResponse(suggestions=_rule_based_suggestions(msg))


def _rule_based_suggestions(msg: Message) -> list[str]:
    body = (msg.body_text or msg.body_html or "").lower()
    subject = (msg.subject or "").lower()

    suggestions = ["Thanks, I'll look into this and get back to you."]

    if any(w in body for w in {"question", "?", "could you", "can you", "please"}):
        suggestions = [
            "Sure, I'll take care of it.",
            "Let me check and get back to you.",
            "Thanks for the question. Here's what I know...",
        ]
    elif any(w in body for w in {"thanks", "thank you", "appreciate"}):
        suggestions = [
            "You're welcome! Happy to help.",
            "Glad I could assist!",
            "Anytime, let me know if you need anything else.",
        ]
    elif any(w in body for w in {"meeting", "schedule", "calendar", "appointment"}):
        suggestions = [
            "That time works for me. See you then.",
            "Could we reschedule? I have a conflict at that time.",
            "Thanks for the invite. I'll be there.",
        ]
    elif any(w in subject + body for w in {"urgent", "asap", "important", "deadline"}):
        suggestions = [
            "Got it. I'll prioritize this and get back to you shortly.",
            "On it. I'll have an update for you soon.",
            "Understood. Let me see what I can do.",
        ]
    elif any(w in body for w in {"sorry", "apologize", "apologies", "regret"}):
        suggestions = [
            "No worries, thanks for letting me know.",
            "Apology accepted. Let's move forward.",
            "I understand, these things happen.",
        ]

    return suggestions


# ── Spam Learning ──


class SpamReportResponse(BaseModel):
    message: str


@router.post("/{message_id}/report-spam", response_model=SpamReportResponse)
def report_spam(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    existing = db.query(SpamReport).filter(
        SpamReport.message_id == message_id,
        SpamReport.user_id == user.id,
    ).first()
    if existing:
        existing.report_type = "spam"
    else:
        report = SpamReport(message_id=message_id, user_id=user.id, report_type="spam")
        db.add(report)

    if msg.folder != "SPAM":
        msg.previous_folder = msg.folder
        msg.folder = "SPAM"
    db.commit()
    logger.info("User %d reported message %d as spam", user.id, message_id)
    return SpamReportResponse(message="Message marked as spam")


@router.post("/{message_id}/report-ham", response_model=SpamReportResponse)
def report_ham(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    existing = db.query(SpamReport).filter(
        SpamReport.message_id == message_id,
        SpamReport.user_id == user.id,
    ).first()
    if existing:
        existing.report_type = "ham"
    else:
        report = SpamReport(message_id=message_id, user_id=user.id, report_type="ham")
        db.add(report)

    if msg.folder == "SPAM":
        msg.folder = msg.previous_folder or "INBOX"
        msg.previous_folder = None
    db.commit()
    logger.info("User %d reported message %d as ham", user.id, message_id)
    return SpamReportResponse(message="Message marked as not spam")


# ── Delivery status ──


class DeliveryUpdateRequest(BaseModel):
    status: str
    error: str | None = None
    bounce_type: str | None = None


class DeliveryResponse(BaseModel):
    id: int
    message_id: int
    recipient: str
    status: str
    opened_at: str | None = None
    clicked_at: str | None = None
    bounce_type: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


@router.patch("/deliveries/{delivery_id}/status", status_code=status.HTTP_204_NO_CONTENT)
def update_delivery_status(
    delivery_id: int,
    req: DeliveryUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    delivery = (
        db.query(EmailDelivery)
        .join(Message)
        .filter(
            EmailDelivery.id == delivery_id,
            Message.mailbox_id == user.mailbox.id,
        )
        .first()
    )
    if not delivery:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery not found")
    delivery.status = req.status
    if req.error is not None:
        delivery.error = req.error
    if req.bounce_type is not None:
        delivery.bounce_type = req.bounce_type
    db.commit()
    fire_notification(user.id, "delivery.updated", {
        "delivery_id": delivery.id,
        "event": "status_change",
        "status": req.status,
        "recipient": delivery.recipient,
        "timestamp": datetime.now(UTC).isoformat(),
    })


@router.get("/{message_id}/deliveries", response_model=list[DeliveryResponse])
def list_message_deliveries(
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = _get_mailbox(user, db)
    msg = db.query(Message).filter(Message.id == message_id, Message.mailbox_id == mailbox.id).first()
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    return (
        db.query(EmailDelivery)
        .filter(EmailDelivery.message_id == message_id)
        .all()
    )
