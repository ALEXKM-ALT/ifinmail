from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.vapid import get_vapid_public_key_b64
from ifinmail.db.models import PushSubscription, User

router = APIRouter(prefix="/push", tags=["push"])


class SubscribeRequest(BaseModel):
    endpoint: str
    keys: dict


class SubscribeResponse(BaseModel):
    message: str


@router.get("/vapid-public-key")
def vapid_public_key():
    return {"public_key": get_vapid_public_key_b64()}


@router.post("/subscribe")
def subscribe(
    req: SubscribeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    existing = (
        db.query(PushSubscription)
        .filter(PushSubscription.user_id == user.id, PushSubscription.endpoint == req.endpoint)
        .first()
    )
    if existing:
        existing.p256dh_key = req.keys.get("p256dh", existing.p256dh_key)
        existing.auth_key = req.keys.get("auth", existing.auth_key)
    else:
        sub = PushSubscription(
            user_id=user.id,
            endpoint=req.endpoint,
            p256dh_key=req.keys.get("p256dh", ""),
            auth_key=req.keys.get("auth", ""),
        )
        db.add(sub)
    db.commit()
    return SubscribeResponse(message="Subscribed")


@router.delete("/subscribe")
def unsubscribe(
    endpoint: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    db.query(PushSubscription).filter(
        PushSubscription.user_id == user.id, PushSubscription.endpoint == endpoint
    ).delete()
    db.commit()
    return {"message": "Unsubscribed"}
