import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.limiter import user_moderate
from ifinmail.db.models import ForwardingRule, User, VacationResponder
from ifinmail.db.models import Mailbox as MailboxModel

logger = logging.getLogger("ifinmail.settings")

router = APIRouter(prefix="/mail/settings", tags=["mail_settings"])


def _get_mailbox(user: User, db: Session) -> MailboxModel:
    mailbox = db.query(MailboxModel).filter(MailboxModel.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    return mailbox


# ── Vacation / Auto-reply ──


class VacationRequest(BaseModel):
    subject: str = "Auto-reply"
    body: str = ""
    enabled: bool = False


class VacationResponse(BaseModel):
    subject: str
    body: str
    enabled: bool


@router.get("/vacation", response_model=VacationResponse)
def get_vacation(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mailbox = _get_mailbox(user, db)
    vr = db.query(VacationResponder).filter(VacationResponder.mailbox_id == mailbox.id).first()
    if not vr:
        return VacationResponse(subject="Auto-reply", body="", enabled=False)
    return VacationResponse(subject=vr.subject, body=vr.body, enabled=bool(vr.enabled))


@router.put("/vacation", response_model=VacationResponse)
def set_vacation(
    req: VacationRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    mailbox = _get_mailbox(user, db)
    vr = db.query(VacationResponder).filter(VacationResponder.mailbox_id == mailbox.id).first()
    if not vr:
        vr = VacationResponder(mailbox_id=mailbox.id)
        db.add(vr)
    vr.subject = req.subject
    vr.body = req.body
    vr.enabled = int(req.enabled)
    db.commit()
    db.refresh(vr)
    return VacationResponse(subject=vr.subject, body=vr.body, enabled=bool(vr.enabled))


# ── Forwarding ──


class ForwardingRequest(BaseModel):
    target_email: str
    enabled: bool = True


class ForwardingUpdateRequest(BaseModel):
    target_email: str | None = None
    enabled: bool | None = None


class ForwardingResponse(BaseModel):
    id: int
    target_email: str
    enabled: bool


@router.get("/forwarding", response_model=list[ForwardingResponse])
def get_forwarding(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mailbox = _get_mailbox(user, db)
    rules = db.query(ForwardingRule).filter(ForwardingRule.mailbox_id == mailbox.id).all()
    return [ForwardingResponse(id=r.id, target_email=r.target_email, enabled=bool(r.enabled)) for r in rules]


@router.post("/forwarding", response_model=ForwardingResponse, status_code=status.HTTP_201_CREATED)
def add_forwarding(
    req: ForwardingRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    mailbox = _get_mailbox(user, db)
    rule = ForwardingRule(mailbox_id=mailbox.id, target_email=req.target_email, enabled=int(req.enabled))
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return ForwardingResponse(id=rule.id, target_email=rule.target_email, enabled=bool(rule.enabled))


@router.put("/forwarding/{rule_id}", response_model=ForwardingResponse)
def update_forwarding(
    rule_id: int,
    req: ForwardingUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    mailbox = _get_mailbox(user, db)
    rule = (
        db.query(ForwardingRule).filter(ForwardingRule.id == rule_id, ForwardingRule.mailbox_id == mailbox.id).first()
    )
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    if req.target_email is not None:
        rule.target_email = req.target_email
    if req.enabled is not None:
        rule.enabled = int(req.enabled)
    db.commit()
    db.refresh(rule)
    return ForwardingResponse(id=rule.id, target_email=rule.target_email, enabled=bool(rule.enabled))


@router.delete("/forwarding/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_forwarding(rule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mailbox = _get_mailbox(user, db)
    rule = (
        db.query(ForwardingRule).filter(ForwardingRule.id == rule_id, ForwardingRule.mailbox_id == mailbox.id).first()
    )
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Rule not found")
    db.delete(rule)
    db.commit()
