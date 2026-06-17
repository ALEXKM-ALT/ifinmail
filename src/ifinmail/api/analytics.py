import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.tracking import geo_lookup, parse_user_agent
from ifinmail.db.models import (
    Campaign,
    CampaignStep,
    Contact,
    EmailDelivery,
    Message,
    ScheduledMessage,
    TrackingEvent,
    User,
)

logger = logging.getLogger("ifinmail.analytics")

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _notify_delivery_event(db: Session, delivery: EmailDelivery, event_type: str) -> None:
    from ifinmail.api.ws_manager import fire_notification

    message = db.query(Message).filter(Message.id == delivery.message_id).first()
    if message:
        mailbox = message.mailbox
        if mailbox and mailbox.user_id:
            fire_notification(
                mailbox.user_id,
                "delivery.updated",
                {
                    "delivery_id": delivery.id,
                    "event": event_type,
                    "recipient": delivery.recipient,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
            )


@router.get("/track/{delivery_id}/open.gif")
def track_open(
    delivery_id: int,
    request: Request,
    db: Session = Depends(get_db),
):
    delivery = db.query(EmailDelivery).filter(EmailDelivery.id == delivery_id).first()
    if delivery:
        if not delivery.opened_at:
            delivery.opened_at = datetime.now(UTC)
        ip = request.client.host if request.client else "unknown"
        ua = request.headers.get("user-agent", "") or ""
        geo = geo_lookup(ip)
        ua_info = parse_user_agent(ua)
        event = TrackingEvent(
            delivery_id=delivery.id,
            event_type="open",
            ip_address=ip,
            user_agent=ua[:512] if ua else None,
            city=geo.get("city"),
            region=geo.get("region"),
            country=geo.get("country"),
            device_type=ua_info["device_type"],
            os=ua_info["os"],
            browser=ua_info["browser"],
        )
        db.add(event)
        db.commit()
        _notify_delivery_event(db, delivery, "opened")
        # Read receipt — notify sender if requested
        msg = db.query(Message).filter(Message.id == delivery.message_id).first()
        if msg and msg.read_receipt_requested:
            sender_mailbox = msg.mailbox
            if sender_mailbox and sender_mailbox.user_id:
                from ifinmail.api.ws_manager import fire_notification

                fire_notification(
                    sender_mailbox.user_id,
                    "read_receipt",
                    {
                        "delivery_id": delivery.id,
                        "recipient": delivery.recipient,
                        "message_id": msg.id,
                        "subject": msg.subject or "(no subject)",
                        "opened_at": delivery.opened_at.isoformat() if delivery.opened_at else None,
                    },
                )
    return Response(
        content=b"\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x00\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x44\x01\x00\x3b",
        media_type="image/gif",
    )


@router.get("/track/{delivery_id}/click")
def track_click(
    delivery_id: int,
    url: str = Query(...),
    request: Request = None,
    db: Session = Depends(get_db),
):
    delivery = db.query(EmailDelivery).filter(EmailDelivery.id == delivery_id).first()
    if delivery:
        if not delivery.clicked_at:
            delivery.clicked_at = datetime.now(UTC)
        ip = request.client.host if request and request.client else "unknown"
        ua = request.headers.get("user-agent", "") if request else ""
        geo = geo_lookup(ip)
        ua_info = parse_user_agent(ua)
        event = TrackingEvent(
            delivery_id=delivery.id,
            event_type="click",
            clicked_url=url[:2048] if url else None,
            ip_address=ip,
            user_agent=ua[:512] if ua else None,
            city=geo.get("city"),
            region=geo.get("region"),
            country=geo.get("country"),
            device_type=ua_info["device_type"],
            os=ua_info["os"],
            browser=ua_info["browser"],
        )
        db.add(event)
        db.commit()
        _notify_delivery_event(db, delivery, "clicked")
    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=url)


@router.get("/deliverability")
def deliverability(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(EmailDelivery.status, sa_func.count(EmailDelivery.id))
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id, EmailDelivery.created_at >= since)
        .group_by(EmailDelivery.status)
        .all()
    )
    total = sum(r[1] for r in rows)
    opened = (
        db.query(sa_func.count(EmailDelivery.id))
        .filter(
            EmailDelivery.opened_at.isnot(None),
            EmailDelivery.created_at >= since,
        )
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id)
        .scalar()
        or 0
    )
    clicked = (
        db.query(sa_func.count(EmailDelivery.id))
        .filter(
            EmailDelivery.clicked_at.isnot(None),
            EmailDelivery.created_at >= since,
        )
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id)
        .scalar()
        or 0
    )
    return {
        "total": total,
        "by_status": {r[0]: r[1] for r in rows},
        "opened": opened,
        "clicked": clicked,
        "open_rate": round(opened / total * 100, 2) if total else 0,
        "click_rate": round(clicked / total * 100, 2) if total else 0,
    }


@router.get("/volume")
def message_volume(
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    mailbox_ids = [user.mailbox.id]
    if not mailbox_ids:
        return {"by_folder": [], "daily": [], "total": 0}

    by_folder = [
        {"folder": r[0], "count": r[1]}
        for r in db.query(Message.folder, sa_func.count(Message.id))
        .filter(Message.mailbox_id.in_(mailbox_ids))
        .group_by(Message.folder)
        .all()
    ]

    daily = (
        db.query(sa_func.date(Message.created_at).label("date"), sa_func.count(Message.id))
        .filter(Message.mailbox_id.in_(mailbox_ids), Message.created_at >= since)
        .group_by(sa_func.date(Message.created_at))
        .order_by(sa_func.date(Message.created_at))
        .all()
    )

    return {
        "by_folder": by_folder,
        "daily": [{"date": str(r[0]), "count": r[1]} for r in daily],
        "total": sum(f["count"] for f in by_folder),
    }


@router.get("/top-contacts")
def top_contacts(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    mailbox_ids = [user.mailbox.id]
    if not mailbox_ids:
        return {"senders": [], "recipients": []}

    senders = (
        db.query(Message.from_addr, sa_func.count(Message.id))
        .filter(Message.mailbox_id.in_(mailbox_ids), Message.folder == "INBOX", Message.created_at >= since)
        .group_by(Message.from_addr)
        .order_by(sa_func.count(Message.id).desc())
        .limit(limit)
        .all()
    )

    recipients = (
        db.query(Message.to_addrs, sa_func.count(Message.id))
        .filter(Message.mailbox_id.in_(mailbox_ids), Message.folder == "SENT", Message.created_at >= since)
        .group_by(Message.to_addrs)
        .order_by(sa_func.count(Message.id).desc())
        .limit(limit)
        .all()
    )

    return {
        "senders": [{"email": r[0], "count": r[1]} for r in senders],
        "recipients": [{"email": r[0], "count": r[1]} for r in recipients],
    }


@router.get("/tracking/summary")
def tracking_summary(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    delivery_ids = (
        db.query(EmailDelivery.id)
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id, EmailDelivery.created_at >= since)
    ).subquery()

    total_opens = (
        db.query(sa_func.count(TrackingEvent.id))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.event_type == "open",
        )
        .scalar()
        or 0
    )

    total_clicks = (
        db.query(sa_func.count(TrackingEvent.id))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.event_type == "click",
        )
        .scalar()
        or 0
    )

    unique_opens = (
        db.query(sa_func.count(sa_func.distinct(TrackingEvent.delivery_id)))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.event_type == "open",
        )
        .scalar()
        or 0
    )

    unique_clicks = (
        db.query(sa_func.count(sa_func.distinct(TrackingEvent.delivery_id)))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.event_type == "click",
        )
        .scalar()
        or 0
    )

    total_deliveries = (
        db.query(sa_func.count(EmailDelivery.id))
        .filter(
            EmailDelivery.id.in_(db.query(delivery_ids.c.id)),
        )
        .scalar()
        or 0
    )

    return {
        "total_opens": total_opens,
        "total_clicks": total_clicks,
        "unique_opens": unique_opens,
        "unique_clicks": unique_clicks,
        "total_deliveries": total_deliveries,
        "open_rate": round(unique_opens / total_deliveries * 100, 2) if total_deliveries else 0,
        "click_rate": round(unique_clicks / total_deliveries * 100, 2) if total_deliveries else 0,
        "click_to_open_rate": round(unique_clicks / unique_opens * 100, 2) if unique_opens else 0,
    }


@router.get("/tracking/hourly")
def tracking_hourly(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    delivery_ids = (
        db.query(EmailDelivery.id)
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id, EmailDelivery.created_at >= since)
    ).subquery()

    rows = (
        db.query(
            sa_func.extract("hour", TrackingEvent.timestamp).label("hour"),
            TrackingEvent.event_type,
            sa_func.count(TrackingEvent.id),
        )
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.timestamp >= since,
        )
        .group_by("hour", TrackingEvent.event_type)
        .order_by("hour")
        .all()
    )

    hours = list(range(24))
    opens_by_hour = {h: 0 for h in hours}
    clicks_by_hour = {h: 0 for h in hours}
    for hour_str, event_type, count in rows:
        h = int(hour_str)
        if event_type == "open":
            opens_by_hour[h] = count
        elif event_type == "click":
            clicks_by_hour[h] = count

    return {
        "labels": [f"{h:02d}:00" for h in hours],
        "opens": [opens_by_hour[h] for h in hours],
        "clicks": [clicks_by_hour[h] for h in hours],
    }


@router.get("/tracking/devices")
def tracking_devices(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    delivery_ids = (
        db.query(EmailDelivery.id)
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id, EmailDelivery.created_at >= since)
    ).subquery()

    devices = (
        db.query(TrackingEvent.device_type, sa_func.count(TrackingEvent.id))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.timestamp >= since,
        )
        .group_by(TrackingEvent.device_type)
        .all()
    )

    oss = (
        db.query(TrackingEvent.os, sa_func.count(TrackingEvent.id))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.timestamp >= since,
        )
        .group_by(TrackingEvent.os)
        .all()
    )

    browsers = (
        db.query(TrackingEvent.browser, sa_func.count(TrackingEvent.id))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.timestamp >= since,
        )
        .group_by(TrackingEvent.browser)
        .all()
    )

    return {
        "devices": [{"name": r[0] or "unknown", "count": r[1]} for r in devices],
        "os": [{"name": r[0] or "unknown", "count": r[1]} for r in oss],
        "browsers": [{"name": r[0] or "unknown", "count": r[1]} for r in browsers],
    }


@router.get("/tracking/locations")
def tracking_locations(
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    delivery_ids = (
        db.query(EmailDelivery.id)
        .join(Message, EmailDelivery.message_id == Message.id)
        .join(User, Message.mailbox_id == User.id)
        .filter(User.id == user.id, EmailDelivery.created_at >= since)
    ).subquery()

    cities = (
        db.query(TrackingEvent.city, TrackingEvent.country, sa_func.count(TrackingEvent.id))
        .filter(
            TrackingEvent.delivery_id.in_(db.query(delivery_ids.c.id)),
            TrackingEvent.timestamp >= since,
            TrackingEvent.city.isnot(None),
            TrackingEvent.city != "",
        )
        .group_by(TrackingEvent.city, TrackingEvent.country)
        .order_by(sa_func.count(TrackingEvent.id).desc())
        .limit(limit)
        .all()
    )

    return {
        "cities": [{"city": r[0], "country": r[1] or "", "count": r[2]} for r in cities],
    }


# ── Contact Engagement Scoring ──


@router.get("/contact-engagement")
def contact_engagement(
    days: int = Query(90, ge=1, le=365),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    since = datetime.now(UTC) - timedelta(days=days)
    mailbox = db.query(Message).filter(Message.mailbox_id == user.mailbox.id).first()
    if not mailbox:
        return {"contacts": []}

    contacts = db.query(Contact).filter(Contact.user_id == user.id).all()
    result = []
    for c in contacts:
        deliveries = (
            db.query(EmailDelivery)
            .join(Message)
            .filter(
                Message.mailbox_id == user.mailbox.id,
                EmailDelivery.recipient == c.email,
                EmailDelivery.created_at >= since,
            )
            .all()
        )
        total_sent = len(deliveries)
        total_opens = sum(1 for d in deliveries if d.opened_at is not None)
        total_clicks = sum(1 for d in deliveries if d.clicked_at is not None)

        if total_sent == 0:
            score = 0.0
        else:
            score = round((total_opens / total_sent * 0.6 + total_clicks / total_sent * 0.4) * 100, 1)

        result.append(
            {
                "contact_id": c.id,
                "email": c.email,
                "name": c.name,
                "total_sent": total_sent,
                "total_opens": total_opens,
                "total_clicks": total_clicks,
                "engagement_score": score,
            }
        )

    result.sort(key=lambda r: r["engagement_score"], reverse=True)
    return {"contacts": result}


# ── Campaign / Sequence Analytics ──


@router.get("/campaign-stats")
def campaign_stats(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    campaigns = db.query(Campaign).filter(Campaign.created_by == user.id).all()
    result = []
    for c in campaigns:
        steps = db.query(CampaignStep).filter(CampaignStep.campaign_id == c.id).order_by(CampaignStep.order).all()
        step_stats = []
        for s in steps:
            sms = (
                db.query(ScheduledMessage)
                .filter(
                    ScheduledMessage.campaign_step_id == s.id,
                    ScheduledMessage.campaign_id == c.id,
                )
                .all()
            )
            total = len(sms)
            if total == 0:
                sent = opened = clicked = 0
            else:
                sent = sum(1 for m in sms if m.status == "sent")
                opened = 0
                clicked = 0
                msg_ids = [m.message_id for m in sms if m.message_id is not None]
                if msg_ids:
                    deliveries = db.query(EmailDelivery).filter(EmailDelivery.message_id.in_(msg_ids)).all()
                    opened = sum(1 for d in deliveries if d.opened_at is not None)
                    clicked = sum(1 for d in deliveries if d.clicked_at is not None)
            step_stats.append(
                {
                    "step_id": s.id,
                    "order": s.order,
                    "subject": s.subject,
                    "delay_days": s.delay_days,
                    "total": total,
                    "sent": sent,
                    "opened": opened,
                    "clicked": clicked,
                }
            )
        result.append(
            {
                "campaign_id": c.id,
                "name": c.name,
                "total_steps": len(step_stats),
                "steps": step_stats,
            }
        )
    return {"campaigns": result}
