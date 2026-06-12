import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import User, Webhook, WebhookDeliveryLog

logger = logging.getLogger("ifinmail.webhook")

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


class WebhookCreate(BaseModel):
    url: str
    events: list[str]


class WebhookUpdate(BaseModel):
    url: str | None = None
    events: list[str] | None = None
    active: bool | None = None


class WebhookResponse(BaseModel):
    id: int
    url: str
    events: list[str]
    active: bool
    created_at: str

    model_config = ConfigDict(from_attributes=True)


VALID_EVENTS = {
    "email.received",
    "email.sent",
    "user.created",
    "user.deleted",
    "bounce.received",
    "spam.detected",
    "org.member.added",
    "org.member.removed",
    "org.shared_inbox.new",
    "org.shared_inbox.assigned",
    "org.shared_inbox.resolved",
    "org.shared_inbox.note_added",
    "org.deleted",
}


@router.get("", response_model=list[WebhookResponse])
def list_webhooks(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hooks = db.query(Webhook).filter(Webhook.user_id == user.id).order_by(Webhook.created_at.desc()).all()
    result = []
    for h in hooks:
        result.append(WebhookResponse(
            id=h.id,
            url=h.url,
            events=json.loads(h.events) if h.events else [],
            active=bool(h.active),
            created_at=h.created_at.isoformat() if h.created_at else "",
        ))
    return result


@router.post("", status_code=status.HTTP_201_CREATED)
def create_webhook(
    req: WebhookCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    for event in req.events:
        if event not in VALID_EVENTS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid event '{event}'. Valid: {', '.join(sorted(VALID_EVENTS))}",
            )
    secret = hashlib.sha256(json.dumps({"url": req.url, "user": user.id}).encode()).hexdigest()[:32]
    hook = Webhook(
        user_id=user.id,
        url=req.url,
        events=json.dumps(req.events),
        secret=secret,
        active=1,
    )
    db.add(hook)
    db.commit()
    db.refresh(hook)
    return {
        "id": hook.id,
        "url": hook.url,
        "events": req.events,
        "secret": secret,
        "message": "Webhook created. Save the secret - it will not be shown again.",
    }


@router.put("/{webhook_id}", response_model=WebhookResponse)
def update_webhook(
    webhook_id: int,
    req: WebhookUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hook = db.query(Webhook).filter(Webhook.id == webhook_id, Webhook.user_id == user.id).first()
    if not hook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    if req.url is not None:
        hook.url = req.url
    if req.events is not None:
        for event in req.events:
            if event not in VALID_EVENTS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid event '{event}'",
                )
        hook.events = json.dumps(req.events)
    if req.active is not None:
        hook.active = int(req.active)
    db.commit()
    db.refresh(hook)
    return WebhookResponse(
        id=hook.id,
        url=hook.url,
        events=json.loads(hook.events) if hook.events else [],
        active=bool(hook.active),
        created_at=hook.created_at.isoformat() if hook.created_at else "",
    )


@router.delete("/{webhook_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_webhook(
    webhook_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hook = db.query(Webhook).filter(Webhook.id == webhook_id, Webhook.user_id == user.id).first()
    if not hook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    db.delete(hook)
    db.commit()


@router.get("/{webhook_id}/deliveries")
def webhook_deliveries(
    webhook_id: int,
    page: int = 1,
    per_page: int = 50,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    hook = db.query(Webhook).filter(Webhook.id == webhook_id, Webhook.user_id == user.id).first()
    if not hook:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")
    total = db.query(WebhookDeliveryLog).filter(WebhookDeliveryLog.webhook_id == hook.id).count()
    logs = (
        db.query(WebhookDeliveryLog)
        .filter(WebhookDeliveryLog.webhook_id == hook.id)
        .order_by(WebhookDeliveryLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return {
        "items": [
            {
                "id": log.id,
                "event": log.event,
                "status": log.status,
                "response_code": log.response_code,
                "error": log.error,
                "retry_count": log.retry_count,
                "next_retry_at": log.next_retry_at.isoformat() if log.next_retry_at else None,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            }
            for log in logs
        ],
        "total": total,
    }


def _schedule_retry(hook_id: int, event: str, log_id: int, db: Session, retry_count: int = 0) -> None:
    max_retries = 5
    if retry_count >= max_retries:
        return
    delay_minutes = 2 ** (retry_count + 1)
    next_retry = datetime.now(UTC) + timedelta(minutes=delay_minutes)
    log = db.query(WebhookDeliveryLog).filter(WebhookDeliveryLog.id == log_id).first()
    if log:
        log.next_retry_at = next_retry
        log.retry_count = retry_count + 1
    db.flush()


def fire_webhook(user_id: int, event: str, data: dict, db: Session) -> None:
    """Fire-and-forget async webhook from a sync context."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(send_webhook(user_id, event, data, db))
    except RuntimeError:
        try:
            asyncio.run(send_webhook(user_id, event, data, db))
        except Exception:
            pass


async def send_webhook(user_id: int, event: str, data: dict, db: Session) -> None:
    import httpx

    hooks = db.query(Webhook).filter(
        Webhook.user_id == user_id,
        Webhook.active == 1,
    ).all()
    for hook in hooks:
        try:
            events = json.loads(hook.events) if hook.events else []
            if event not in events:
                continue
            payload = json.dumps({
                "event": event,
                "timestamp": __import__("datetime").datetime.now(__import__("datetime").UTC).isoformat(),
                "data": data,
            }, default=str)
            signature = hmac.new(
                hook.secret.encode(),
                payload.encode(),
                hashlib.sha256,
            ).hexdigest()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    hook.url,
                    content=payload,
                    headers={
                        "Content-Type": "application/json",
                        "X-Webhook-Signature": signature,
                    },
                )
            log = WebhookDeliveryLog(
                webhook_id=hook.id,
                event=event,
                status="success" if resp.is_success else "failed",
                response_code=resp.status_code,
            )
            db.add(log)
            if not resp.is_success:
                _schedule_retry(hook.id, event, log.id, db)
        except Exception as exc:
            logger.warning("Webhook %s failed: %s", hook.url, exc)
            log = WebhookDeliveryLog(
                webhook_id=hook.id,
                event=event,
                status="failed",
                error=str(exc)[:500],
            )
            db.add(log)
            _schedule_retry(hook.id, event, log.id, db)
    db.flush()
