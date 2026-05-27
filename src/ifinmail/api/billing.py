from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import Mailbox as MailboxModel
from ifinmail.db.models import User

router = APIRouter(prefix="/billing", tags=["billing"])

PLANS = {
    "free": {"name": "Free", "price": 0, "quota_mb": 1024, "max_domains": 1, "max_aliases": 5},
    "starter": {"name": "Starter", "price": 5, "quota_mb": 5120, "max_domains": 3, "max_aliases": 25},
    "pro": {"name": "Pro", "price": 15, "quota_mb": 25600, "max_domains": 10, "max_aliases": 100},
    "enterprise": {"name": "Enterprise", "price": 50, "quota_mb": 102400, "max_domains": -1, "max_aliases": -1},
}


class PlanResponse(BaseModel):
    id: str
    name: str
    price: int
    quota_mb: int
    max_domains: int
    max_aliases: int


class SubscribeRequest(BaseModel):
    plan: str


class SubscriptionResponse(BaseModel):
    plan: str
    quota_mb: int
    used_mb: int
    status: str


@router.get("/plans", response_model=list[PlanResponse])
def list_plans():
    return [PlanResponse(id=k, **v) for k, v in PLANS.items()]


@router.post("/subscribe", response_model=SubscriptionResponse)
def subscribe(
    req: SubscribeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    plan = PLANS.get(req.plan)
    if not plan:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan")
    mailbox = db.query(MailboxModel).filter(MailboxModel.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    mailbox.quota_mb = plan["quota_mb"]
    mailbox.plan = req.plan
    db.commit()
    db.refresh(mailbox)
    return SubscriptionResponse(
        plan=req.plan,
        quota_mb=mailbox.quota_mb,
        used_mb=mailbox.used_mb,
        status="active",
    )


@router.get("/current", response_model=SubscriptionResponse)
def current_subscription(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    mailbox = db.query(MailboxModel).filter(MailboxModel.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    current_plan = mailbox.plan or "free"
    return SubscriptionResponse(
        plan=current_plan,
        quota_mb=mailbox.quota_mb,
        used_mb=mailbox.used_mb,
        status="active",
    )
