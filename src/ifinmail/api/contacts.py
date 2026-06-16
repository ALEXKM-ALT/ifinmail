import csv
import io
import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import Contact, ContactGroup, ContactGroupMember, EmailDelivery, Message, TrackingEvent, User

logger = logging.getLogger("ifinmail.contacts")

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _calc_engagement(stats: dict) -> float:
    total = stats.get("sent", 0)
    if total == 0:
        return 0.0
    opens = stats.get("opens", 0)
    clicks = stats.get("clicks", 0)
    return round((opens / total * 0.6 + clicks / total * 0.4) * 100, 1)


class ContactCreate(BaseModel):
    email: str
    name: str | None = None
    notes: str | None = None


class ContactUpdate(BaseModel):
    email: str | None = None
    name: str | None = None
    notes: str | None = None


class ContactResponse(BaseModel):
    id: int
    email: str
    name: str | None = None
    notes: str | None = None
    engagement_score: float = 0.0
    total_sent: int = 0
    total_opens: int = 0
    total_clicks: int = 0
    created_at: str
    updated_at: str

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[ContactResponse])
def list_contacts(
    search: str | None = Query(None),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = db.query(Contact).filter(Contact.user_id == user.id)
    if search:
        like = f"%{search}%"
        query = query.filter(
            or_(Contact.email.ilike(like), Contact.name.ilike(like))
        )
    total = query.count()
    items = query.order_by(Contact.name.asc().nullslast(), Contact.email.asc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    # Compute engagement scores
    mailbox = db.query(Message).filter(Message.mailbox_id == user.mailbox.id).first()
    contact_emails = [c.email for c in items]
    delivery_stats: dict[str, dict] = {}
    if mailbox and contact_emails:
        deliveries = (
            db.query(EmailDelivery)
            .join(Message)
            .filter(
                Message.mailbox_id == user.mailbox.id,
                EmailDelivery.recipient.in_(contact_emails),
            )
            .all()
        )
        for d in deliveries:
            if d.recipient not in delivery_stats:
                delivery_stats[d.recipient] = {"sent": 0, "opens": 0, "clicks": 0}
            delivery_stats[d.recipient]["sent"] += 1
            if d.opened_at is not None:
                delivery_stats[d.recipient]["opens"] += 1
            if d.clicked_at is not None:
                delivery_stats[d.recipient]["clicks"] += 1

    return [
        ContactResponse(
            id=c.id,
            email=c.email,
            name=c.name,
            notes=c.notes,
            engagement_score=_calc_engagement(delivery_stats.get(c.email, {})),
            total_sent=delivery_stats.get(c.email, {}).get("sent", 0),
            total_opens=delivery_stats.get(c.email, {}).get("opens", 0),
            total_clicks=delivery_stats.get(c.email, {}).get("clicks", 0),
            created_at=c.created_at.isoformat() if c.created_at else "",
            updated_at=c.updated_at.isoformat() if c.updated_at else "",
        )
        for c in items
    ]


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ContactResponse)
def create_contact(
    req: ContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
    existing = db.query(Contact).filter(
        Contact.user_id == user.id,
        Contact.email == req.email,
    ).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Contact already exists")
    contact = Contact(user_id=user.id, email=req.email, name=req.name, notes=req.notes)
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return ContactResponse(
        id=contact.id,
        email=contact.email,
        name=contact.name,
        notes=contact.notes,
        created_at=contact.created_at.isoformat() if contact.created_at else "",
        updated_at=contact.updated_at.isoformat() if contact.updated_at else "",
    )


@router.get("/{contact_id}", response_model=ContactResponse)
def get_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return ContactResponse(
        id=contact.id,
        email=contact.email,
        name=contact.name,
        notes=contact.notes,
        created_at=contact.created_at.isoformat() if contact.created_at else "",
        updated_at=contact.updated_at.isoformat() if contact.updated_at else "",
    )


@router.put("/{contact_id}", response_model=ContactResponse)
def update_contact(
    contact_id: int,
    req: ContactUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    if req.email is not None:
        if "@" not in req.email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
        dup = db.query(Contact).filter(
            Contact.user_id == user.id,
            Contact.email == req.email,
            Contact.id != contact_id,
        ).first()
        if dup:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already in contacts")
        contact.email = req.email
    if req.name is not None:
        contact.name = req.name
    if req.notes is not None:
        contact.notes = req.notes
    contact.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(contact)
    return ContactResponse(
        id=contact.id,
        email=contact.email,
        name=contact.name,
        notes=contact.notes,
        created_at=contact.created_at.isoformat() if contact.created_at else "",
        updated_at=contact.updated_at.isoformat() if contact.updated_at else "",
    )


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_contact(
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    db.delete(contact)
    db.commit()


@router.get("/export/csv")
def export_contacts_csv(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contacts = db.query(Contact).filter(Contact.user_id == user.id).order_by(Contact.email).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["email", "name", "notes"])
    for c in contacts:
        writer.writerow([c.email, c.name or "", c.notes or ""])
    csv_content = output.getvalue()
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=contacts.csv"},
    )


class CSVImportResponse(BaseModel):
    imported: int
    skipped: int
    errors: list[str]


@router.post("/import/csv", status_code=status.HTTP_201_CREATED)
def import_contacts_csv(
    body: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    csv_text = body.get("csv", "")
    if not csv_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No CSV data provided")
    reader = csv.DictReader(io.StringIO(csv_text))
    imported = 0
    skipped = 0
    errors = []
    for row in reader:
        email = row.get("email", "").strip().lower()
        if not email or "@" not in email:
            skipped += 1
            continue
        existing = db.query(Contact).filter(
            Contact.user_id == user.id,
            Contact.email == email,
        ).first()
        if existing:
            skipped += 1
            continue
        contact = Contact(
            user_id=user.id,
            email=email,
            name=row.get("name", "").strip() or None,
            notes=row.get("notes", "").strip() or None,
        )
        db.add(contact)
        imported += 1
    db.commit()
    return CSVImportResponse(imported=imported, skipped=skipped, errors=errors)


class DeliveryEvent(BaseModel):
    id: int
    recipient: str
    status: str
    subject: str
    opened_at: str | None = None
    clicked_at: str | None = None
    sent_at: str
    tracking_events: list[dict]


class ContactEngagementResponse(BaseModel):
    contact_id: int
    email: str
    name: str | None = None
    engagement_score: float
    total_sent: int
    total_opens: int
    total_clicks: int
    deliveries: list[DeliveryEvent]


@router.get("/{contact_id}/engagement")
def contact_engagement_detail(
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    contact = db.query(Contact).filter(Contact.id == contact_id, Contact.user_id == user.id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")

    deliveries = (
        db.query(EmailDelivery)
        .join(Message)
        .filter(
            Message.mailbox_id == user.mailbox.id,
            EmailDelivery.recipient == contact.email,
        )
        .order_by(EmailDelivery.created_at.desc())
        .limit(100)
        .all()
    )

    total_sent = len(deliveries)
    total_opens = sum(1 for d in deliveries if d.opened_at is not None)
    total_clicks = sum(1 for d in deliveries if d.clicked_at is not None)
    score = _calc_engagement({"sent": total_sent, "opens": total_opens, "clicks": total_clicks})

    delivery_list = []
    for d in deliveries:
        subject = d.message.subject if d.message else ""
        tracking = db.query(TrackingEvent).filter(TrackingEvent.delivery_id == d.id).all()
        delivery_list.append(DeliveryEvent(
            id=d.id,
            recipient=d.recipient,
            status=d.status,
            subject=subject,
            opened_at=d.opened_at.isoformat() if d.opened_at else None,
            clicked_at=d.clicked_at.isoformat() if d.clicked_at else None,
            sent_at=d.created_at.isoformat() if d.created_at else "",
            tracking_events=[
                {
                    "event_type": e.event_type,
                    "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                    "ip_address": e.ip_address,
                    "city": e.city,
                    "country": e.country,
                    "device_type": e.device_type,
                    "os": e.os,
                    "browser": e.browser,
                    "clicked_url": e.clicked_url,
                }
                for e in tracking
            ],
        ))

    return ContactEngagementResponse(
        contact_id=contact.id,
        email=contact.email,
        name=contact.name,
        engagement_score=score,
        total_sent=total_sent,
        total_opens=total_opens,
        total_clicks=total_clicks,
        deliveries=delivery_list,
    )


# ── Contact Groups ──


class GroupCreate(BaseModel):
    name: str


class GroupResponse(BaseModel):
    id: int
    name: str
    member_count: int = 0
    created_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class GroupAddRemove(BaseModel):
    contact_ids: list[int]


@router.get("/groups")
def list_groups(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    groups = db.query(ContactGroup).filter(ContactGroup.user_id == user.id).order_by(ContactGroup.name).all()
    return [
        GroupResponse(
            id=g.id,
            name=g.name,
            member_count=db.query(ContactGroupMember).filter(ContactGroupMember.group_id == g.id).count(),
            created_at=g.created_at,
        )
        for g in groups
    ]


@router.post("/groups", status_code=status.HTTP_201_CREATED)
def create_group(
    req: GroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    name = req.name.strip()
    if not name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Group name is required")
    existing = db.query(ContactGroup).filter(ContactGroup.user_id == user.id, ContactGroup.name == name).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Group already exists")
    group = ContactGroup(user_id=user.id, name=name)
    db.add(group)
    db.commit()
    db.refresh(group)
    return GroupResponse(id=group.id, name=group.name, created_at=group.created_at)


@router.get("/groups/{group_id}")
def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = db.query(ContactGroup).filter(ContactGroup.id == group_id, ContactGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    members = (
        db.query(Contact)
        .join(ContactGroupMember, ContactGroupMember.contact_id == Contact.id)
        .filter(ContactGroupMember.group_id == group.id)
        .all()
    )
    return {
        "id": group.id,
        "name": group.name,
        "members": [
            {"id": c.id, "email": c.email, "name": c.name}
            for c in members
        ],
        "member_count": len(members),
        "created_at": group.created_at.isoformat() if group.created_at else None,
    }


@router.put("/groups/{group_id}")
def update_group(
    group_id: int,
    req: GroupCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = db.query(ContactGroup).filter(ContactGroup.id == group_id, ContactGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    group.name = req.name.strip()
    db.commit()
    db.refresh(group)
    return GroupResponse(id=group.id, name=group.name, created_at=group.created_at)


@router.delete("/groups/{group_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = db.query(ContactGroup).filter(ContactGroup.id == group_id, ContactGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    db.delete(group)
    db.commit()


@router.post("/groups/{group_id}/members")
def add_group_members(
    group_id: int,
    req: GroupAddRemove,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = db.query(ContactGroup).filter(ContactGroup.id == group_id, ContactGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    added = 0
    for cid in req.contact_ids:
        contact = db.query(Contact).filter(Contact.id == cid, Contact.user_id == user.id).first()
        if not contact:
            continue
        existing = db.query(ContactGroupMember).filter(
            ContactGroupMember.group_id == group.id,
            ContactGroupMember.contact_id == cid,
        ).first()
        if existing:
            continue
        db.add(ContactGroupMember(group_id=group.id, contact_id=cid))
        added += 1
    db.commit()
    return {"added": added, "message": f"{added} contact(s) added to group"}


@router.delete("/groups/{group_id}/members")
def remove_group_members(
    group_id: int,
    req: GroupAddRemove,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    group = db.query(ContactGroup).filter(ContactGroup.id == group_id, ContactGroup.user_id == user.id).first()
    if not group:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Group not found")
    deleted = (
        db.query(ContactGroupMember)
        .filter(
            ContactGroupMember.group_id == group.id,
            ContactGroupMember.contact_id.in_(req.contact_ids),
        )
        .delete(synchronize_session=False)
    )
    db.commit()
    return {"removed": deleted, "message": f"{deleted} contact(s) removed from group"}
