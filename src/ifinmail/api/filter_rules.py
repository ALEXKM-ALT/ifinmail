import json
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.limiter import user_moderate
from ifinmail.db.models import FilterRule, User
from ifinmail.db.models import Mailbox as MailboxModel

logger = logging.getLogger("ifinmail.filter_api")

router = APIRouter(prefix="/mail/filters", tags=["mail_filters"])


def _get_mailbox(user: User, db: Session) -> MailboxModel:
    mb = db.query(MailboxModel).filter(MailboxModel.user_id == user.id).first()
    if not mb:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    return mb


# ── Schemas ──


class FilterCondition(BaseModel):
    field: str  # from_addr, to_addr, subject, body_text
    operator: str  # contains, not_contains, equals, not_equals, starts_with, ends_with, regex
    value: str


class FilterAction(BaseModel):
    type: str  # move_to_folder, mark_read, mark_starred, add_label, discard
    value: str = ""


class FilterRuleCreate(BaseModel):
    name: str = ""
    enabled: bool = True
    order: int = 0
    match_logic: str = "all"  # all or any
    conditions: list[FilterCondition]
    actions: list[FilterAction]


class FilterRuleUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    order: int | None = None
    match_logic: str | None = None
    conditions: list[FilterCondition] | None = None
    actions: list[FilterAction] | None = None


class FilterRuleOut(BaseModel):
    id: int
    name: str
    enabled: bool
    order: int
    match_logic: str
    conditions: list[FilterCondition]
    actions: list[FilterAction]

    model_config = ConfigDict(from_attributes=True)


# ── Endpoints ──


@router.get("", response_model=list[FilterRuleOut])
def list_filters(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mailbox = _get_mailbox(user, db)
    rules = db.query(FilterRule).filter(FilterRule.mailbox_id == mailbox.id).order_by(FilterRule.order.asc()).all()
    return [_rule_to_out(r) for r in rules]


@router.post("", response_model=FilterRuleOut, status_code=status.HTTP_201_CREATED)
def create_filter(
    req: FilterRuleCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    mailbox = _get_mailbox(user, db)
    rule = FilterRule(
        mailbox_id=mailbox.id,
        name=req.name,
        enabled=int(req.enabled),
        order=req.order,
        match_logic=req.match_logic,
        conditions=json.dumps([c.model_dump() for c in req.conditions]),
        actions=json.dumps([a.model_dump() for a in req.actions]),
    )
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return _rule_to_out(rule)


@router.put("/{rule_id}", response_model=FilterRuleOut)
def update_filter(
    rule_id: int,
    req: FilterRuleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    mailbox = _get_mailbox(user, db)
    rule = db.query(FilterRule).filter(FilterRule.id == rule_id, FilterRule.mailbox_id == mailbox.id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter rule not found")
    if req.name is not None:
        rule.name = req.name
    if req.enabled is not None:
        rule.enabled = int(req.enabled)
    if req.order is not None:
        rule.order = req.order
    if req.match_logic is not None:
        rule.match_logic = req.match_logic
    if req.conditions is not None:
        rule.conditions = json.dumps([c.model_dump() for c in req.conditions])
    if req.actions is not None:
        rule.actions = json.dumps([a.model_dump() for a in req.actions])
    db.commit()
    db.refresh(rule)
    return _rule_to_out(rule)


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_filter(rule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mailbox = _get_mailbox(user, db)
    rule = db.query(FilterRule).filter(FilterRule.id == rule_id, FilterRule.mailbox_id == mailbox.id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter rule not found")
    db.delete(rule)
    db.commit()


@router.put("/{rule_id}/toggle", response_model=FilterRuleOut)
def toggle_filter(rule_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mailbox = _get_mailbox(user, db)
    rule = db.query(FilterRule).filter(FilterRule.id == rule_id, FilterRule.mailbox_id == mailbox.id).first()
    if not rule:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Filter rule not found")
    rule.enabled = 1 - rule.enabled
    db.commit()
    db.refresh(rule)
    return _rule_to_out(rule)


def _rule_to_out(rule: FilterRule) -> FilterRuleOut:
    return FilterRuleOut(
        id=rule.id,
        name=rule.name or "",
        enabled=bool(rule.enabled),
        order=rule.order,
        match_logic=rule.match_logic,
        conditions=[FilterCondition(**c) for c in json.loads(rule.conditions)],
        actions=[FilterAction(**a) for a in json.loads(rule.actions)],
    )
