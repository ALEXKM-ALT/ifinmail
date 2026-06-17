import email.utils
import logging
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.config import settings
from ifinmail.api.deps import get_db
from ifinmail.api.personalize import MemberInfo, personalise
from ifinmail.api.webhooks import fire_webhook
from ifinmail.api.ws_manager import fire_notification
from ifinmail.db.models import (
    Alias,
    Domain,
    Mailbox,
    Message,
    Organization,
    OrganizationInvite,
    OrganizationMember,
    OrgContact,
    OrgEmailAssignment,
    OrgEmailNote,
    OrgSharedInboxMessage,
    OrgSharedInboxNote,
    User,
)

logger = logging.getLogger("ifinmail.orgs")

router = APIRouter(prefix="/orgs", tags=["organizations"])


class OrgCreate(BaseModel):
    name: str
    email: str | None = None


class OrgUpdate(BaseModel):
    name: str | None = None
    email: str | None = None
    max_users: int | None = None


class InviteMember(BaseModel):
    email: str
    role: str = "member"
    first_name: str | None = None
    last_name: str | None = None


class OrgContactCreate(BaseModel):
    email: str
    name: str | None = None


class StatusUpdateRequest(BaseModel):
    status: str


def _sync_org_aliases(db: Session, org_id: int) -> None:
    org = db.query(Organization).filter(Organization.id == org_id).first()
    if not org or not org.email:
        return

    domain_part = org.email.split("@", 1)[-1]
    domain = db.query(Domain).filter(Domain.domain == domain_part).first()
    if not domain:
        return

    db.query(Alias).filter(Alias.source == org.email).delete()

    members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
    seen = set()
    for m in members:
        mb = db.query(Mailbox).filter(Mailbox.user_id == m.user_id).first()
        if mb and mb.email not in seen:
            seen.add(mb.email)
            alias = Alias(
                source=org.email,
                target=mb.email,
                domain_id=domain.id,
                enabled=1,
            )
            db.add(alias)
    db.commit()


@router.post("", status_code=status.HTTP_201_CREATED)
def create_org(
    req: OrgCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    org = Organization(name=req.name, email=req.email, owner_id=user.id)
    db.add(org)
    db.flush()
    member = OrganizationMember(organization_id=org.id, user_id=user.id, role="owner")
    db.add(member)
    db.commit()
    db.refresh(org)
    fire_notification(user.id, "org.created", {"id": org.id, "name": org.name})
    if org.email:
        _sync_org_aliases(db, org.id)
    return {"id": org.id, "name": org.name, "email": org.email, "owner_id": org.owner_id}


@router.get("")
def list_orgs(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    memberships = db.query(OrganizationMember).filter(OrganizationMember.user_id == user.id).all()
    orgs = []
    for m in memberships:
        org = m.organization
        member_count = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).count()
        orgs.append(
            {
                "id": org.id,
                "name": org.name,
                "email": org.email,
                "role": m.role,
                "member_count": member_count,
                "max_users": org.max_users,
                "created_at": org.created_at.isoformat() if org.created_at else "",
            }
        )
    return orgs


@router.get("/{org_id}")
def get_org(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org = membership.organization
    members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
    return {
        "id": org.id,
        "name": org.name,
        "email": org.email,
        "owner_id": org.owner_id,
        "my_role": membership.role,
        "max_users": org.max_users,
        "members": [
            {
                "id": m.id,
                "user_id": m.user_id,
                "email": m.user.email if m.user else None,
                "role": m.role,
                "first_name": m.first_name or (m.user.first_name if m.user else None),
                "last_name": m.last_name or (m.user.last_name if m.user else None),
            }
            for m in members
        ],
    }


@router.put("/{org_id}")
def update_org(
    org_id: int,
    req: OrgUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.role == "owner",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can update the organization")
    org = membership.organization
    if req.name is not None:
        org.name = req.name
    if req.email is not None:
        stripped = req.email.strip()
        org.email = stripped if stripped else None
    if req.max_users is not None:
        org.max_users = req.max_users
    db.commit()
    if org.email:
        _sync_org_aliases(db, org.id)
    return {"message": "Organization updated"}


@router.post("/{org_id}/invite")
def invite_member(
    org_id: int,
    req: InviteMember,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners/admins can invite members")
    org = membership.organization
    current_count = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).count()
    if current_count >= org.max_users:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Organization user limit reached")

    existing = (
        db.query(OrganizationMember)
        .join(User)
        .filter(
            OrganizationMember.organization_id == org.id,
            User.email == req.email,
        )
        .first()
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already a member")

    existing_invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.organization_id == org.id,
            OrganizationInvite.email == req.email,
            OrganizationInvite.accepted == 0,
            OrganizationInvite.expires_at > datetime.now(UTC),
        )
        .first()
    )
    if existing_invite:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Invite already sent to this email")

    target = db.query(User).filter(User.email == req.email).first()
    if target:
        member = OrganizationMember(
            organization_id=org.id,
            user_id=target.id,
            role=req.role,
            first_name=req.first_name or target.first_name,
            last_name=req.last_name or target.last_name,
        )
        db.add(member)
        db.commit()
        fire_notification(
            target.id, "org.invite", {"organization_id": org.id, "organization_name": org.name, "role": req.role}
        )
        fire_webhook(
            target.id,
            "org.member.added",
            {"organization_id": org.id, "organization_name": org.name, "role": req.role},
            db,
        )
        _sync_org_aliases(db, org.id)
        return {"message": f"{req.email} invited", "user_id": target.id, "invited": True}

    token = secrets.token_urlsafe(32)
    invite = OrganizationInvite(
        organization_id=org.id,
        email=req.email,
        token=token,
        role=req.role,
        first_name=req.first_name,
        last_name=req.last_name,
        expires_at=datetime.now(UTC) + timedelta(hours=48),
    )
    db.add(invite)
    db.commit()

    accept_url = f"{settings.app_url}/?accept_invite={token}"

    if settings.smtp_host:
        try:
            msg = EmailMessage()
            if settings.smtp_user and "@" in settings.smtp_user:
                domain = settings.smtp_user.split("@")[-1]
            else:
                domain = settings.default_domain
            msg["From"] = f"ifinmail <noreply@{domain}>"
            msg["To"] = req.email
            msg["Subject"] = f"You've been invited to join {org.name}"
            msg["Message-ID"] = email.utils.make_msgid()
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg.set_content(
                f"You've been invited to join {org.name} on ifinmail.\n\n"
                f"Click the link to accept the invitation:\n\n{accept_url}\n\n"
                f"This link expires in 48 hours."
            )
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as server:
                if settings.smtp_tls:
                    server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(msg["From"], [req.email], msg.as_string())
        except Exception as exc:
            logger.warning("Failed to send invite email: %s", exc)

    fire_webhook(user.id, "org.member.added", {"organization_id": org.id, "email": req.email, "invited": False}, db)
    return {
        "message": f"Invitation sent to {req.email}",
        "invite_token": token,
        "accept_url": accept_url,
        "invited": False,
    }


@router.post("/accept-invite")
def accept_invite(
    token: str = Query(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    invite = (
        db.query(OrganizationInvite)
        .filter(
            OrganizationInvite.token == token,
            OrganizationInvite.accepted == 0,
            OrganizationInvite.expires_at > datetime.now(UTC),
        )
        .first()
    )
    if not invite:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Invalid or expired invite token")
    if invite.email != user.email:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="This invite was sent to a different email address"
        )
    existing = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == invite.organization_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if existing:
        invite.accepted = 1
        db.commit()
        return {"message": "Already a member", "organization_id": invite.organization_id}
    member = OrganizationMember(
        organization_id=invite.organization_id,
        user_id=user.id,
        role=invite.role,
        first_name=invite.first_name or user.first_name,
        last_name=invite.last_name or user.last_name,
    )
    db.add(member)
    invite.accepted = 1
    db.commit()
    org = db.query(Organization).filter(Organization.id == invite.organization_id).first()
    fire_notification(
        user.id,
        "org.invite.accepted",
        {"organization_id": invite.organization_id, "organization_name": org.name if org else None},
    )
    _sync_org_aliases(db, invite.organization_id)
    return {
        "message": "Invitation accepted",
        "organization_id": invite.organization_id,
        "organization_name": org.name if org else None,
    }


@router.get("/{org_id}/member-contacts")
def org_member_contacts(
    org_id: int,
    q: str = Query("", max_length=100),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    query = (
        db.query(User)
        .join(OrganizationMember, OrganizationMember.user_id == User.id)
        .filter(
            OrganizationMember.organization_id == org_id,
        )
    )
    if q:
        query = query.filter(User.email.ilike(f"%{q}%") | User.first_name.ilike(f"%{q}%"))
    users = query.all()
    return [{"email": u.email, "name": f"{u.first_name or ''} {u.last_name or ''}".strip() or None} for u in users]


@router.get("/{org_id}/contacts")
def list_org_contacts(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    contacts = db.query(OrgContact).filter(OrgContact.organization_id == org_id).all()
    return [
        {"id": c.id, "email": c.email, "name": c.name, "created_at": c.created_at.isoformat() if c.created_at else ""}
        for c in contacts
    ]


@router.post("/{org_id}/contacts", status_code=status.HTTP_201_CREATED)
def add_org_contact(
    org_id: int,
    req: OrgContactCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    contact = OrgContact(organization_id=org_id, email=req.email, name=req.name, created_by=user.id)
    db.add(contact)
    db.commit()
    return {"id": contact.id, "email": contact.email, "name": contact.name}


@router.delete("/{org_id}/contacts/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org_contact(
    org_id: int,
    contact_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners/admins can delete contacts")
    contact = db.query(OrgContact).filter(OrgContact.id == contact_id, OrgContact.organization_id == org_id).first()
    if not contact:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Contact not found")
    db.delete(contact)
    db.commit()


@router.post("/{org_id}/remove/{user_id}")
def remove_member(
    org_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners/admins can remove members")
    if user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself")
    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove the owner")
    db.delete(target)
    db.commit()
    fire_notification(user_id, "org.removed", {"organization_id": org_id})
    fire_webhook(user_id, "org.member.removed", {"organization_id": org_id}, db)
    _sync_org_aliases(db, org_id)
    return {"message": "Member removed"}


@router.post("/{org_id}/leave")
def leave_org(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not a member")
    if membership.role == "owner":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Owner cannot leave. Transfer ownership first or delete the org",
        )
    db.delete(membership)
    db.commit()
    _sync_org_aliases(db, org_id)
    return {"message": "Left organization"}


@router.delete("/{org_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_org(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.role == "owner",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can delete the organization")
    org = membership.organization
    member_ids = [
        m.user_id for m in db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
    ]
    org_name = org.name
    db.query(OrgSharedInboxNote).filter(
        OrgSharedInboxNote.shared_inbox_message_id.in_(
            db.query(OrgSharedInboxMessage.id).filter(OrgSharedInboxMessage.organization_id == org.id)
        )
    ).delete(synchronize_session=False)
    db.query(OrgSharedInboxMessage).filter(OrgSharedInboxMessage.organization_id == org.id).delete(
        synchronize_session=False
    )
    db.query(OrgEmailNote).filter(OrgEmailNote.organization_id == org.id).delete(synchronize_session=False)
    db.query(OrgEmailAssignment).filter(OrgEmailAssignment.organization_id == org.id).delete(synchronize_session=False)
    db.query(OrgContact).filter(OrgContact.organization_id == org.id).delete(synchronize_session=False)
    if org.email:
        db.query(Alias).filter(Alias.source == org.email).delete(synchronize_session=False)
    db.query(OrganizationInvite).filter(OrganizationInvite.organization_id == org.id).delete(synchronize_session=False)
    db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).delete(synchronize_session=False)
    db.delete(org)
    db.commit()
    for mid in member_ids:
        fire_notification(mid, "org.deleted", {"organization_id": org_id, "name": org_name})
    fire_webhook(user.id, "org.deleted", {"organization_id": org_id, "name": org_name}, db)


# ── Shared Inbox ──


@router.get("/{org_id}/inbox")
def org_shared_inbox(
    org_id: int,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    member_ids = [
        m.user_id for m in db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_id).all()
    ]
    mailboxes = db.query(Mailbox).filter(Mailbox.user_id.in_(member_ids)).all()
    if not mailboxes:
        return {"items": [], "total": 0}
    mb_ids = [mb.id for mb in mailboxes]

    total = db.query(Message).filter(Message.mailbox_id.in_(mb_ids)).count()
    # Deduplicate by message_id, take latest
    msgs = (
        db.query(Message)
        .filter(Message.mailbox_id.in_(mb_ids))
        .order_by(Message.created_at.desc())
        .offset(offset)
        .limit(limit * 2)
        .all()
    )
    seen = set()
    unique = []
    for m in msgs:
        key = m.message_id or str(m.id)
        if key not in seen:
            seen.add(key)
            unique.append(m)
        if len(unique) >= limit:
            break

    return {
        "items": [
            {
                "id": m.id,
                "message_id": m.message_id,
                "from_addr": m.from_addr,
                "to_addrs": m.to_addrs,
                "subject": m.subject or "",
                "body_text": (m.body_text or "")[:200],
                "folder": m.folder,
                "read": bool(m.read),
                "starred": bool(m.starred),
                "has_attachments": bool(m.has_attachments),
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in unique
        ],
        "total": total,
    }


# ── Email Assignment ──


class AssignRequest(BaseModel):
    user_id: int


@router.post("/{org_id}/emails/{message_id}/assign")
def assign_email(
    org_id: int,
    message_id: int,
    req: AssignRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners/admins can assign emails")

    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == req.user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found in this org")

    existing = (
        db.query(OrgEmailAssignment)
        .filter(
            OrgEmailAssignment.organization_id == org_id,
            OrgEmailAssignment.message_id == message_id,
        )
        .first()
    )
    if existing:
        existing.assigned_to = req.user_id
        existing.assigned_by = user.id
    else:
        assignment = OrgEmailAssignment(
            organization_id=org_id,
            message_id=message_id,
            assigned_to=req.user_id,
            assigned_by=user.id,
        )
        db.add(assignment)
    db.commit()
    return {"message": "Email assigned", "user_id": req.user_id}


@router.delete("/{org_id}/emails/{message_id}/assign", status_code=status.HTTP_204_NO_CONTENT)
def unassign_email(
    org_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners/admins can unassign emails")

    assignment = (
        db.query(OrgEmailAssignment)
        .filter(
            OrgEmailAssignment.organization_id == org_id,
            OrgEmailAssignment.message_id == message_id,
        )
        .first()
    )
    if assignment:
        db.delete(assignment)
        db.commit()
    return None


@router.get("/{org_id}/emails/{message_id}/assign")
def get_assignment(
    org_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    assignment = (
        db.query(OrgEmailAssignment)
        .filter(
            OrgEmailAssignment.organization_id == org_id,
            OrgEmailAssignment.message_id == message_id,
        )
        .first()
    )
    if not assignment:
        return {"assigned": False}
    assignee = db.query(User).filter(User.id == assignment.assigned_to).first()
    return {
        "assigned": True,
        "user_id": assignment.assigned_to,
        "email": assignee.email if assignee else None,
        "assigned_by": assignment.assigned_by,
    }


# ── Internal Notes ──


class NoteRequest(BaseModel):
    note: str


@router.post("/{org_id}/emails/{message_id}/notes")
def add_email_note(
    org_id: int,
    message_id: int,
    req: NoteRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    if not req.note.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note cannot be empty")

    note = OrgEmailNote(organization_id=org_id, message_id=message_id, user_id=user.id, note=req.note.strip())
    db.add(note)
    db.commit()
    return {"message": "Note added", "note_id": note.id}


@router.get("/{org_id}/emails/{message_id}/notes")
def list_email_notes(
    org_id: int,
    message_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    notes = (
        db.query(OrgEmailNote)
        .filter(
            OrgEmailNote.organization_id == org_id,
            OrgEmailNote.message_id == message_id,
        )
        .order_by(OrgEmailNote.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "user_id": n.user_id,
            "user_email": n.user.email if n.user else None,
            "note": n.note,
            "created_at": n.created_at.isoformat() if n.created_at else "",
        }
        for n in notes
    ]


# ── Role Management ──


class ChangeRoleRequest(BaseModel):
    role: str


@router.put("/{org_id}/members/{member_id}/role")
def change_member_role(
    org_id: int,
    member_id: int,
    req: ChangeRoleRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.role not in ("owner", "admin", "member"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid role. Must be owner, admin, or member"
        )

    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.role == "owner",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can change roles")

    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.id == member_id,
            OrganizationMember.organization_id == org_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if target.role == "owner":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot change the owner's role")

    target.role = req.role
    db.commit()
    return {"message": f"Role changed to {req.role}", "user_id": target.user_id, "role": req.role}


# ── Transfer Ownership ──


@router.post("/{org_id}/transfer/{user_id}")
def transfer_ownership(
    org_id: int,
    user_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
            OrganizationMember.role == "owner",
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only the owner can transfer ownership")
    if user_id == user.id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot transfer ownership to yourself")

    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    org = membership.organization
    org.owner_id = user_id
    membership.role = "admin"
    target.role = "owner"
    db.commit()
    return {"message": "Ownership transferred", "new_owner_id": user_id}


# ── Shared Inbox ──


@router.get("/{org_id}/shared-inbox")
def list_shared_inbox(
    org_id: int,
    filter_status: str | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    query = db.query(OrgSharedInboxMessage).filter(OrgSharedInboxMessage.organization_id == org_id)
    if filter_status:
        query = query.filter(OrgSharedInboxMessage.status == filter_status)
    total = query.count()
    msgs = query.order_by(OrgSharedInboxMessage.created_at.desc()).offset(offset).limit(limit).all()
    return {
        "items": [
            {
                "id": m.id,
                "from_email": m.from_email,
                "to_email": m.to_email,
                "subject": m.subject or "",
                "body_text": (m.body_text or "")[:300],
                "status": m.status,
                "assigned_to": m.assigned_to,
                "assignee_email": m.assignee.email if m.assignee else None,
                "assigned_at": m.assigned_at.isoformat() if m.assigned_at else None,
                "resolved_at": m.resolved_at.isoformat() if m.resolved_at else None,
                "created_at": m.created_at.isoformat() if m.created_at else "",
            }
            for m in msgs
        ],
        "total": total,
    }


@router.get("/{org_id}/shared-inbox/{msg_id}")
def get_shared_inbox_message(
    org_id: int,
    msg_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    msg = (
        db.query(OrgSharedInboxMessage)
        .filter(
            OrgSharedInboxMessage.id == msg_id,
            OrgSharedInboxMessage.organization_id == org_id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    notes = (
        db.query(OrgSharedInboxNote)
        .filter(
            OrgSharedInboxNote.shared_inbox_message_id == msg.id,
        )
        .order_by(OrgSharedInboxNote.created_at.desc())
        .all()
    )

    return {
        "id": msg.id,
        "from_email": msg.from_email,
        "to_email": msg.to_email,
        "subject": msg.subject or "",
        "body_text": msg.body_text or "",
        "body_html": msg.body_html or "",
        "status": msg.status,
        "assigned_to": msg.assigned_to,
        "assignee_email": msg.assignee.email if msg.assignee else None,
        "assigned_by": msg.assigned_by,
        "assigned_at": msg.assigned_at.isoformat() if msg.assigned_at else None,
        "resolved_at": msg.resolved_at.isoformat() if msg.resolved_at else None,
        "created_at": msg.created_at.isoformat() if msg.created_at else "",
        "notes": [
            {
                "id": n.id,
                "user_id": n.user_id,
                "user_email": n.user.email if n.user else None,
                "note": n.note,
                "created_at": n.created_at.isoformat() if n.created_at else "",
            }
            for n in notes
        ],
    }


class AssignSharedInboxRequest(BaseModel):
    user_id: int


@router.post("/{org_id}/shared-inbox/{msg_id}/assign")
def assign_shared_inbox_message(
    org_id: int,
    msg_id: int,
    req: AssignSharedInboxRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners/admins can assign messages")

    target = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == req.user_id,
        )
        .first()
    )
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    msg = (
        db.query(OrgSharedInboxMessage)
        .filter(
            OrgSharedInboxMessage.id == msg_id,
            OrgSharedInboxMessage.organization_id == org_id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    msg.assigned_to = req.user_id
    msg.assigned_by = user.id
    msg.assigned_at = datetime.now(UTC)
    if msg.status == "pending":
        msg.status = "assigned"
    db.commit()
    fire_notification(
        req.user_id,
        "org.shared_inbox.assigned",
        {
            "organization_id": org_id,
            "message_id": msg_id,
            "subject": msg.subject,
            "assigned_by": user.email,
        },
    )
    fire_webhook(
        req.user_id,
        "org.shared_inbox.assigned",
        {
            "organization_id": org_id,
            "message_id": msg_id,
            "subject": msg.subject,
        },
        db,
    )
    return {"message": "Assigned", "user_id": req.user_id, "status": msg.status}


@router.post("/{org_id}/shared-inbox/{msg_id}/unassign")
def unassign_shared_inbox_message(
    org_id: int,
    msg_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership or membership.role not in ("owner", "admin"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only owners/admins can unassign messages")

    msg = (
        db.query(OrgSharedInboxMessage)
        .filter(
            OrgSharedInboxMessage.id == msg_id,
            OrgSharedInboxMessage.organization_id == org_id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    prev_assignee = msg.assigned_to
    msg.assigned_to = None
    msg.assigned_by = None
    msg.assigned_at = None
    if msg.status == "assigned":
        msg.status = "pending"
    db.commit()
    if prev_assignee:
        fire_notification(
            prev_assignee,
            "org.shared_inbox.unassigned",
            {
                "organization_id": org_id,
                "message_id": msg_id,
                "subject": msg.subject,
            },
        )
    return {"message": "Unassigned", "status": msg.status}


@router.post("/{org_id}/shared-inbox/{msg_id}/status")
def update_shared_inbox_status(
    org_id: int,
    msg_id: int,
    req: StatusUpdateRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if req.status not in ("pending", "assigned", "resolved"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")

    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    msg = (
        db.query(OrgSharedInboxMessage)
        .filter(
            OrgSharedInboxMessage.id == msg_id,
            OrgSharedInboxMessage.organization_id == org_id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    msg.status = req.status
    if req.status == "resolved":
        msg.resolved_at = datetime.now(UTC)
    elif req.status == "pending":
        msg.assigned_to = None
        msg.assigned_by = None
        msg.assigned_at = None
        msg.resolved_at = None
    db.commit()
    if req.status == "resolved":
        fire_notification(
            user.id,
            "org.shared_inbox.resolved",
            {
                "organization_id": org_id,
                "message_id": msg_id,
                "subject": msg.subject,
            },
        )
        fire_webhook(
            user.id,
            "org.shared_inbox.resolved",
            {
                "organization_id": org_id,
                "message_id": msg_id,
                "subject": msg.subject,
            },
            db,
        )
    return {"message": "Status changed to " + req.status, "status": msg.status}


class ReplyRequest(BaseModel):
    body_text: str


@router.post("/{org_id}/shared-inbox/{msg_id}/reply")
def reply_shared_inbox_message(
    org_id: int,
    msg_id: int,
    req: ReplyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    if not req.body_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Reply body cannot be empty")

    msg = (
        db.query(OrgSharedInboxMessage)
        .filter(
            OrgSharedInboxMessage.id == msg_id,
            OrgSharedInboxMessage.organization_id == org_id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    mailbox = db.query(Mailbox).filter(Mailbox.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")

    reply_subject = "Re: " + (msg.subject or "")
    reply_body = req.body_text.strip()

    sent_msg = Message(
        mailbox_id=mailbox.id,
        message_id=email.utils.make_msgid(domain=user.email.split("@")[-1]),
        from_addr=user.email,
        to_addrs=msg.from_email,
        subject=reply_subject,
        body_text=reply_body,
        size=len(reply_body.encode("utf-8")),
        folder="SENT",
    )
    db.add(sent_msg)

    if msg.status != "resolved":
        msg.status = "resolved"
        msg.resolved_at = datetime.now(UTC)

    db.commit()
    fire_webhook(
        user.id,
        "org.shared_inbox.resolved",
        {
            "organization_id": org_id,
            "message_id": msg_id,
            "reply_id": sent_msg.id,
        },
        db,
    )
    return {"message": "Reply sent", "id": sent_msg.id, "status": msg.status}


class SharedInboxNoteCreate(BaseModel):
    note: str


@router.post("/{org_id}/shared-inbox/{msg_id}/notes")
def add_shared_inbox_note(
    org_id: int,
    msg_id: int,
    req: SharedInboxNoteCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")
    if not req.note.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Note cannot be empty")

    msg = (
        db.query(OrgSharedInboxMessage)
        .filter(
            OrgSharedInboxMessage.id == msg_id,
            OrgSharedInboxMessage.organization_id == org_id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    note = OrgSharedInboxNote(shared_inbox_message_id=msg.id, user_id=user.id, note=req.note.strip())
    db.add(note)
    db.commit()
    members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org_id).all()
    for m in members:
        if m.user_id != user.id:
            fire_notification(
                m.user_id,
                "org.shared_inbox.note_added",
                {
                    "organization_id": org_id,
                    "message_id": msg_id,
                    "by_user": user.email,
                },
            )
    fire_webhook(
        user.id,
        "org.shared_inbox.note_added",
        {
            "organization_id": org_id,
            "message_id": msg_id,
        },
        db,
    )
    return {"message": "Note added", "note_id": note.id}


@router.get("/{org_id}/shared-inbox/{msg_id}/notes")
def list_shared_inbox_notes(
    org_id: int,
    msg_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not a member")

    msg = (
        db.query(OrgSharedInboxMessage)
        .filter(
            OrgSharedInboxMessage.id == msg_id,
            OrgSharedInboxMessage.organization_id == org_id,
        )
        .first()
    )
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    notes = (
        db.query(OrgSharedInboxNote)
        .filter(
            OrgSharedInboxNote.shared_inbox_message_id == msg.id,
        )
        .order_by(OrgSharedInboxNote.created_at.desc())
        .all()
    )
    return [
        {
            "id": n.id,
            "user_id": n.user_id,
            "user_email": n.user.email if n.user else None,
            "note": n.note,
            "created_at": n.created_at.isoformat() if n.created_at else "",
        }
        for n in notes
    ]


@router.post("/{org_id}/test-email")
def send_org_test_email(
    org_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    membership = (
        db.query(OrganizationMember)
        .filter(
            OrganizationMember.organization_id == org_id,
            OrganizationMember.user_id == user.id,
        )
        .first()
    )
    if not membership:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Organization not found")
    org = membership.organization
    if not org.email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No mailing list email set for this organization"
        )

    mailbox = db.query(Mailbox).filter(Mailbox.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have no mailbox")

    subject = f"Test email from {user.email} to {org.name}"
    body_text = (
        f"This is a test email sent to the {org.name} mailing list.\n\n"
        f"From: {user.email}\n"
        f"To: {org.email}\n"
        f"Organization: {org.name}\n\n"
        f"If you received this, the mailing list is working correctly!"
    )
    msg_id_str = email.utils.make_msgid(domain=user.email.split("@")[-1])
    size = len(body_text.encode("utf-8"))

    sent_msg = Message(
        mailbox_id=mailbox.id,
        message_id=msg_id_str,
        from_addr=user.email,
        to_addrs=org.email,
        subject=subject,
        body_text=body_text,
        size=size,
        folder="SENT",
    )
    db.add(sent_msg)
    db.flush()

    members = db.query(OrganizationMember).filter(OrganizationMember.organization_id == org.id).all()
    first_msg_id = None
    for m in members:
        mb = db.query(Mailbox).filter(Mailbox.user_id == m.user_id).first()
        if not mb:
            continue
        _fn = m.first_name or (m.user.first_name if m.user else "")
        _ln = m.last_name or (m.user.last_name if m.user else "")
        info = MemberInfo(first_name=_fn or mb.email.split("@")[0], last_name=_ln, email=mb.email)
        local_msg = Message(
            mailbox_id=mb.id,
            message_id=msg_id_str,
            from_addr=user.email,
            to_addrs=org.email,
            subject=personalise(subject, info),
            body_text=personalise(body_text, info),
            size=size,
            folder="INBOX",
        )
        db.add(local_msg)
        db.flush()
        if first_msg_id is None:
            first_msg_id = local_msg.id

    if first_msg_id:
        shared = OrgSharedInboxMessage(
            organization_id=org.id,
            from_email=user.email,
            to_email=org.email,
            subject=subject,
            body_text=body_text,
            status="pending",
        )
        db.add(shared)
        db.flush()
        for m in members:
            if m.user_id != user.id:
                fire_notification(
                    m.user_id,
                    "org.shared_inbox.new",
                    {
                        "organization_id": org.id,
                        "message_id": shared.id,
                        "from": user.email,
                        "subject": subject,
                    },
                )
        fire_webhook(
            user.id,
            "org.shared_inbox.new",
            {
                "organization_id": org.id,
                "message_id": shared.id,
            },
            db,
        )

    db.commit()
    return {"message": "Test email sent to mailing list", "shared_inbox_id": shared.id if first_msg_id else None}
