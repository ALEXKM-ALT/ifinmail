import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import Mailbox, Message, Organization, OrganizationMember, OrgSharedInboxMessage, User

logger = logging.getLogger("ifinmail.sandbox")

router = APIRouter(prefix="/sandbox", tags=["sandbox"])

_captured: dict[str, dict] = {}


class SandboxSend(BaseModel):
    to: str
    subject: str = ""
    body_text: str = ""
    body_html: str | None = None
    cc: str | None = None


class SandboxResponse(BaseModel):
    status: str
    preview_url: str
    capture_id: str
    captured_at: str


@router.post("/send", response_model=SandboxResponse)
def sandbox_send(
    req: SandboxSend,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    capture_id = uuid.uuid4().hex[:12]
    captured = {
        "capture_id": capture_id,
        "user_id": user.id,
        "user_email": user.email,
        "to": req.to,
        "subject": req.subject,
        "body_text": req.body_text,
        "body_html": req.body_html,
        "cc": req.cc,
        "captured_at": datetime.now(UTC).isoformat(),
    }
    _captured[capture_id] = captured
    logger.info("Sandbox capture %s for %s", capture_id, user.email)

    org = db.query(Organization).filter(Organization.email == req.to).first()
    if org:
        delivered = 0
        members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
        for m in members:
            mb = db.query(Mailbox).filter(Mailbox.user_id == m.user_id).first()
            if not mb:
                continue
            msg = Message(
                mailbox_id=mb.id,
                message_id=capture_id,
                from_addr=user.email,
                to_addrs=req.to,
                cc_addrs=req.cc or "",
                subject=req.subject,
                body_text=req.body_text or "",
                body_html=req.body_html or "",
                size=len(req.body_text or "") + len(req.body_html or ""),
                folder="INBOX",
            )
            db.add(msg)
            delivered += 1

        shared = OrgSharedInboxMessage(
            organization_id=org.id,
            from_email=user.email,
            to_email=req.to,
            subject=req.subject,
            body_text=req.body_text or "",
            body_html=req.body_html or "",
        )
        db.add(shared)

        if delivered:
            db.commit()
            logger.info("Sandbox delivered %s to %d org members + shared inbox", capture_id, delivered)

    return SandboxResponse(
        status="captured",
        preview_url=f"/sandbox/preview/{capture_id}",
        capture_id=capture_id,
        captured_at=captured["captured_at"],
    )


@router.get("/preview/{capture_id}")
def sandbox_preview(
    capture_id: str,
    user: User = Depends(get_current_user),
):
    captured = _captured.get(capture_id)
    if not captured or captured["user_id"] != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture not found")
    return captured


@router.get("/captures")
def sandbox_captures(
    user: User = Depends(get_current_user),
):
    return [c for c in _captured.values() if c["user_id"] == user.id]
