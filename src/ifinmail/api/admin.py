import os
import subprocess
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy import asc as sa_asc
from sqlalchemy import desc as sa_desc
from sqlalchemy import func as sa_func
from sqlalchemy import text
from sqlalchemy.orm import Session

from ifinmail.api.audit import log_admin_action
from ifinmail.api.auth import _create_access_token, get_current_user
from ifinmail.api.billing import PLANS
from ifinmail.api.deps import get_db
from ifinmail.api.limiter import admin_strict
from ifinmail.db.models import Alias, Attachment, AuditLog, Backup, Domain, Mailbox, Message, SecurityEvent, User

router = APIRouter(prefix="/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def admin_required(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


# ── Pydantic models ──


class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    total_pages: int


class PaginatedResponse(BaseModel):
    items: list
    pagination: PaginationMeta


class DomainCreate(BaseModel):
    domain: str


class DomainUpdate(BaseModel):
    verified: bool | None = None


class DomainResponse(BaseModel):
    id: int
    domain: str
    verified: bool
    spf_ok: bool
    dkim_ok: bool
    dmarc_ok: bool
    mx_ok: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: str
    password: str
    is_admin: bool = False
    first_name: str | None = None
    last_name: str | None = None


class UserUpdate(BaseModel):
    email: str | None = None
    is_admin: bool | None = None
    password: str | None = None
    first_name: str | None = None
    last_name: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    is_admin: bool
    domain_id: int
    first_name: str | None = None
    last_name: str | None = None
    last_login: datetime | None = None
    storage_limit: int = 0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MailboxResponse(BaseModel):
    id: int
    email: str
    quota_mb: int
    used_mb: int
    enabled: bool
    plan: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AliasResponse(BaseModel):
    id: int
    source: str
    target: str
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionResponse(BaseModel):
    id: int
    email: str
    plan: str | None
    quota_mb: int
    used_mb: int
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PlanUpdate(BaseModel):
    name: str | None = None
    price: int | None = None
    quota_mb: int | None = None
    max_domains: int | None = None
    max_aliases: int | None = None


class PasswordUpdate(BaseModel):
    password: str


class MailboxCreate(BaseModel):
    email: str
    quota_mb: int = 1024


class AliasCreate(BaseModel):
    source: str
    target: str


class SubscriptionUpdate(BaseModel):
    plan: str | None = None
    quota_mb: int | None = None
    enabled: bool | None = None


class PlanResponse(BaseModel):
    id: str
    name: str
    price: int
    quota_mb: int
    max_domains: int
    max_aliases: int


class StatsOverviewResponse(BaseModel):
    total_users: int
    total_domains: int
    total_mailboxes: int
    total_messages: int
    total_attachments: int
    total_storage_bytes: int
    messages_by_folder: dict[str, int]
    users_last_24h: int
    active_today: int
    total_aliases: int


class HealthResponse(BaseModel):
    status: str
    database: str
    uptime_seconds: float | None = None
    version: str = "0.1.0"


class SecurityEventCreate(BaseModel):
    event_type: str
    description: str | None = None
    ip_address: str | None = None
    user_id: int | None = None


class SecurityEventResponse(BaseModel):
    id: int
    event_type: str
    description: str | None = None
    ip_address: str | None = None
    user_id: int | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class IPBlockRequest(BaseModel):
    ip: str
    reason: str | None = None


class BackupResponse(BaseModel):
    id: int
    filename: str
    size_bytes: int
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Domains (enhanced) ──


@router.get("/domains")
def list_domains(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str | None = None,
    sort_by: str = "domain",
    sort_desc: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    query = db.query(Domain)
    if search:
        query = query.filter(Domain.domain.ilike(f"%{search}%"))
    total = query.count()
    sort_col = getattr(Domain, sort_by, Domain.domain)
    order = sa_desc(sort_col) if sort_desc else sa_asc(sort_col)
    items = query.order_by(order).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [DomainResponse.model_validate(d).model_dump(mode="json") for d in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
def create_domain(
    req: DomainCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
    __: None = admin_strict,
):
    domain_name = req.domain.lower().strip()
    existing = db.query(Domain).filter(Domain.domain == domain_name).first()
    if existing:
        return JSONResponse(content=DomainResponse.model_validate(existing).model_dump(mode="json"), status_code=200)
    domain = Domain(domain=domain_name)
    db.add(domain)
    db.flush()
    ip_address = request.client.host if request.client else None
    log_admin_action(db, admin, "create_domain", target_email=domain_name, ip_address=ip_address)
    db.commit()
    db.refresh(domain)
    return domain


@router.get("/domains/{domain_id}", response_model=DomainResponse)
def get_domain(domain_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    return domain


@router.put("/domains/{domain_id}", response_model=DomainResponse)
def update_domain(
    domain_id: int,
    req: DomainUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    if req.verified is not None:
        domain.verified = int(req.verified)
    log_admin_action(db, admin, "update_domain", target_email=domain.domain, details=f"verified={req.verified}", ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(domain)
    return domain


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(
    domain_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    log_admin_action(db, admin, "delete_domain", target_email=domain.domain, ip_address=request.client.host if request.client else None)
    db.delete(domain)
    db.commit()


# ── Users (enhanced) ──


@router.get("/users")
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    search: str | None = None,
    sort_by: str = "email",
    sort_desc: bool = False,
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    query = db.query(User)
    if search:
        query = query.filter(User.email.ilike(f"%{search}%"))
    total = query.count()
    sort_col = getattr(User, sort_by, User.email)
    order = sa_desc(sort_col) if sort_desc else sa_asc(sort_col)
    items = query.order_by(order).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "items": [UserResponse.model_validate(u).model_dump(mode="json") for u in items],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    req: UserCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
    __: None = admin_strict,
):
    if not req.email or "@" not in req.email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already exists")
    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
    domain_part = req.email.split("@", 1)[-1]
    domain = db.query(Domain).filter(Domain.domain == domain_part).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Domain '{domain_part}' not found")
    hashed = pwd_context.hash(req.password)
    user = User(
        email=req.email,
        password=hashed,
        domain_id=domain.id,
        is_admin=int(req.is_admin),
        first_name=req.first_name,
        last_name=req.last_name,
    )
    db.add(user)
    db.flush()
    log_admin_action(db, admin, "create_user", target_user=req.email, ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    req: UserUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if req.email is not None:
        if "@" not in req.email:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email")
        domain_part = req.email.split("@", 1)[-1]
        domain = db.query(Domain).filter(Domain.domain == domain_part).first()
        if not domain:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Domain '{domain_part}' not found")
        user.email = req.email
        user.domain_id = domain.id
    if req.is_admin is not None:
        user.is_admin = int(req.is_admin)
    if req.password is not None:
        if len(req.password) < 6:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
        user.password = pwd_context.hash(req.password)
    if req.first_name is not None:
        user.first_name = req.first_name
    if req.last_name is not None:
        user.last_name = req.last_name
    log_admin_action(db, admin, "update_user", target_user=user.email, details=f"is_admin={req.is_admin}" if req.is_admin is not None else None, ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(user)
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    log_admin_action(db, admin, "delete_user", target_user=user.email, ip_address=request.client.host if request.client else None)
    db.delete(user)
    db.commit()


@router.put("/users/{user_id}/password")
def update_user_password(
    user_id: int,
    req: PasswordUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
    user.password = pwd_context.hash(req.password)
    log_admin_action(db, admin, "update_password", target_user=user.email, ip_address=request.client.host if request.client else None)
    db.commit()
    return {"message": "Password updated"}


# ── Stats (enhanced) ──


@router.get("/stats", response_model=StatsOverviewResponse)
def get_stats(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    total_users = db.query(sa_func.count(User.id)).scalar() or 0
    total_domains = db.query(sa_func.count(Domain.id)).scalar() or 0
    total_mailboxes = db.query(sa_func.count(Mailbox.id)).scalar() or 0
    total_messages = db.query(sa_func.count(Message.id)).scalar() or 0
    total_attachments = db.query(sa_func.count(Attachment.id)).scalar() or 0
    total_aliases = db.query(sa_func.count(Alias.id)).scalar() or 0
    total_storage = db.query(sa_func.coalesce(sa_func.sum(Message.size), 0)).scalar() or 0
    since_24h = datetime.now(UTC) - timedelta(hours=24)
    users_last_24h = db.query(sa_func.count(User.id)).filter(User.created_at >= since_24h).scalar() or 0
    active_today = db.query(sa_func.count(User.id)).filter(User.last_login >= since_24h).scalar() or 0

    folder_counts = {}
    for row in db.query(Message.folder, sa_func.count(Message.id)).group_by(Message.folder).all():
        folder_counts[row[0]] = row[1]

    return StatsOverviewResponse(
        total_users=total_users,
        total_domains=total_domains,
        total_mailboxes=total_mailboxes,
        total_messages=total_messages,
        total_attachments=total_attachments,
        total_storage_bytes=total_storage,
        messages_by_folder=folder_counts,
        users_last_24h=users_last_24h,
        active_today=active_today,
        total_aliases=total_aliases,
    )


@router.get("/stats/growth")
def get_user_growth(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    since = datetime.now(UTC) - timedelta(days=days)
    results = (
        db.query(
            sa_func.date(User.created_at).label("date"),
            sa_func.count(User.id),
        )
        .filter(User.created_at >= since)
        .group_by(sa_func.date(User.created_at))
        .order_by(sa_func.date(User.created_at))
        .all()
    )
    return [{"date": str(r[0]), "count": r[1]} for r in results]


@router.get("/stats/emails")
def get_email_volume(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    since = datetime.now(UTC) - timedelta(days=days)
    results = (
        db.query(
            sa_func.date(Message.created_at).label("date"),
            sa_func.count(Message.id),
        )
        .filter(Message.created_at >= since)
        .group_by(sa_func.date(Message.created_at))
        .order_by(sa_func.date(Message.created_at))
        .all()
    )
    return [{"date": str(r[0]), "count": r[1]} for r in results]


# ── Mailboxes ──


@router.get("/mailboxes", response_model=list[MailboxResponse])
def list_mailboxes(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(Mailbox).order_by(Mailbox.email).all()


@router.post("/mailboxes", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
def create_mailbox(
    req: MailboxCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    email = req.email
    quota_mb = req.quota_mb
    user_obj = db.query(User).filter(User.email == email).first()
    if not user_obj:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    existing = db.query(Mailbox).filter(Mailbox.email == email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mailbox already exists")
    mailbox = Mailbox(email=email, user_id=user_obj.id, quota_mb=quota_mb, plan="free")
    db.add(mailbox)
    db.flush()
    log_admin_action(db, admin, "create_mailbox", target_email=email, ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(mailbox)
    return mailbox


@router.delete("/mailboxes/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mailbox(
    mailbox_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    mailbox = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    log_admin_action(db, admin, "delete_mailbox", target_email=mailbox.email, ip_address=request.client.host if request.client else None)
    db.delete(mailbox)
    db.commit()


# ── Aliases ──


@router.get("/aliases", response_model=list[AliasResponse])
def list_aliases(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(Alias).order_by(Alias.source).all()


@router.post("/aliases", response_model=AliasResponse, status_code=status.HTTP_201_CREATED)
def create_alias(
    req: AliasCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    source = req.source.lower().strip()
    target = req.target.lower().strip()
    existing = db.query(Alias).filter(Alias.source == source).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alias already exists")
    domain_part = source.split("@", 1)[-1]
    domain = db.query(Domain).filter(Domain.domain == domain_part).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Domain '{domain_part}' not found")
    alias = Alias(source=source, target=target, domain_id=domain.id)
    db.add(alias)
    db.flush()
    log_admin_action(db, admin, "create_alias", target_email=source, details=f"target={target}", ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(alias)
    return alias


@router.delete("/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alias(
    alias_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    alias = db.query(Alias).filter(Alias.id == alias_id).first()
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found")
    log_admin_action(db, admin, "delete_alias", target_email=alias.source, ip_address=request.client.host if request.client else None)
    db.delete(alias)
    db.commit()


# ── Billing / Plans ──


@router.get("/billing/plans", response_model=list[PlanResponse])
def admin_list_plans(_: User = Depends(admin_required)):
    return [PlanResponse(id=k, **v) for k, v in PLANS.items()]


@router.put("/billing/plans/{plan_id}")
def admin_update_plan(
    plan_id: str,
    req: PlanUpdate,
    _: User = Depends(admin_required),
):
    if plan_id not in PLANS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Plan not found")
    plan = PLANS[plan_id]
    if req.name is not None:
        plan["name"] = req.name
    if req.price is not None:
        plan["price"] = req.price
    if req.quota_mb is not None:
        plan["quota_mb"] = req.quota_mb
    if req.max_domains is not None:
        plan["max_domains"] = req.max_domains
    if req.max_aliases is not None:
        plan["max_aliases"] = req.max_aliases
    return {"id": plan_id, **plan}


@router.get("/billing/subscriptions", response_model=list[SubscriptionResponse])
def admin_list_subscriptions(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(Mailbox).order_by(Mailbox.email).all()


@router.put("/billing/subscriptions/{mailbox_id}", response_model=SubscriptionResponse)
def admin_update_subscription(
    mailbox_id: int,
    req: SubscriptionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    mailbox = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    if req.plan:
        if req.plan not in PLANS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid plan")
        mailbox.plan = req.plan
        mailbox.quota_mb = PLANS[req.plan]["quota_mb"]
    if req.quota_mb is not None:
        mailbox.quota_mb = req.quota_mb
    if req.enabled is not None:
        mailbox.enabled = int(req.enabled)
    log_admin_action(db, admin, "update_subscription", target_email=mailbox.email, details=f"plan={req.plan}" if req.plan else None, ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(mailbox)
    return mailbox


@router.delete("/billing/subscriptions/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
def admin_delete_subscription(
    mailbox_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    mailbox = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    log_admin_action(db, admin, "delete_subscription", target_email=mailbox.email, ip_address=request.client.host if request.client else None)
    db.delete(mailbox)
    db.commit()


# ── System Health ──


@router.get("/system/health", response_model=HealthResponse)
def system_health(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    db_ok = False
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        pass
    status_val = "ok" if db_ok else "degraded"
    return HealthResponse(
        status=status_val,
        database="up" if db_ok else "down",
    )


@router.get("/system/logs")
def system_logs(
    lines: int = Query(100, ge=1, le=5000),
    _: User = Depends(admin_required),
):
    log_paths = [
        "/var/log/ifinmail/app.log",
        "/var/log/ifinmail/smtp.log",
    ]
    entries = []
    for path in log_paths:
        if os.path.exists(path):
            try:
                with open(path) as f:
                    content = f.readlines()
                tail = content[-lines:]
                for line in tail:
                    entries.append({"source": os.path.basename(path), "message": line.rstrip("\n")})
            except Exception:
                pass
    return entries[-lines:]


@router.delete("/system/logs", status_code=status.HTTP_204_NO_CONTENT)
def clear_logs(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    log_paths = [
        "/var/log/ifinmail/app.log",
        "/var/log/ifinmail/smtp.log",
    ]
    for path in log_paths:
        if os.path.exists(path):
            try:
                with open(path, "w") as f:
                    f.truncate()
            except Exception:
                pass
    log_admin_action(db, admin, "clear_logs", ip_address=request.client.host if request.client else None)
    return None


# ── Backup ──


@router.post("/system/backup", response_model=BackupResponse, status_code=status.HTTP_201_CREATED)
def create_backup(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    filename = f"ifinmail_backup_{ts}.sqlite"
    backup_dir = "/tmp/ifinmail_backups"
    os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, filename)
    try:
        from ifinmail.api.database import engine

        db_url = str(engine.url)
        if db_url.startswith("sqlite"):
            src = db_url.replace("sqlite:///", "")
            import shutil

            shutil.copy2(src, backup_path)
        size = os.path.getsize(backup_path)
        backup = Backup(filename=filename, size_bytes=size, status="completed")
    except Exception:
        size = 0
        backup = Backup(filename=filename, size_bytes=0, status="failed")
    db.add(backup)
    db.flush()
    log_admin_action(db, admin, "create_backup", details=f"filename={filename}", ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(backup)
    return backup


@router.get("/system/backups", response_model=list[BackupResponse])
def list_backups(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(Backup).order_by(Backup.created_at.desc()).all()


@router.post("/system/backup/{backup_id}/restore")
def restore_backup(
    backup_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    backup = db.query(Backup).filter(Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")
    backup_dir = "/tmp/ifinmail_backups"
    backup_path = os.path.join(backup_dir, backup.filename)
    if not os.path.exists(backup_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup file not found on disk")
    try:
        from ifinmail.api.database import engine

        db_url = str(engine.url)
        if db_url.startswith("sqlite"):
            src = db_url.replace("sqlite:///", "")
            import shutil

            shutil.copy2(backup_path, src)
        return {"message": "Backup restored", "filename": backup.filename}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.delete("/system/backups/{backup_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_backup(
    backup_id: int,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    backup = db.query(Backup).filter(Backup.id == backup_id).first()
    if not backup:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup not found")
    backup_dir = "/tmp/ifinmail_backups"
    backup_path = os.path.join(backup_dir, backup.filename)
    if os.path.exists(backup_path):
        os.remove(backup_path)
    log_admin_action(db, admin, "delete_backup", details=f"filename={backup.filename}", ip_address=request.client.host if request.client else None)
    db.delete(backup)
    db.commit()


# ── User emails (admin view) ──


@router.get("/users/{user_id}/emails")
def admin_user_emails(
    user_id: int,
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    folder: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    mailbox = db.query(Mailbox).filter(Mailbox.user_id == user.id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    query = db.query(Message).filter(Message.mailbox_id == mailbox.id)
    if folder:
        query = query.filter(Message.folder == folder.upper())
    total = query.count()
    messages = query.order_by(Message.created_at.desc()).offset((page - 1) * per_page).limit(per_page).all()
    return {
        "user": {"id": user.id, "email": user.email},
        "items": [
            {
                "id": m.id,
                "from": m.from_addr,
                "to": m.to_addrs,
                "subject": m.subject,
                "folder": m.folder,
                "read": bool(m.read),
                "size": m.size,
                "created_at": m.created_at.isoformat() if m.created_at else None,
            }
            for m in messages
        ],
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, -(-total // per_page)),
        },
    }


# ── User activity log ──


@router.get("/users/{user_id}/activity")
def admin_user_activity(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    logs = (
        db.query(AuditLog)
        .filter(AuditLog.target_user == user.email)
        .order_by(AuditLog.created_at.desc())
        .limit(100)
        .all()
    )
    return {
        "user": {"id": user.id, "email": user.email, "last_login": user.last_login.isoformat() if user.last_login else None},
        "activity": [
            {
                "id": log.id,
                "action": log.action,
                "details": log.details,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            }
            for log in logs
        ],
    }


# ── Impersonate user ──


class ImpersonateResponse(BaseModel):
    token: str
    message: str
    warning: str


@router.post("/users/{user_id}/impersonate", response_model=ImpersonateResponse)
def impersonate_user(
    user_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    target = db.query(User).filter(User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    impersonate_token = _create_access_token(target.id)
    log = AuditLog(
        admin_id=admin.id,
        action="impersonate",
        target_user=target.email,
        details=f"Admin {admin.email} impersonated {target.email}",
    )
    db.add(log)
    db.commit()
    return ImpersonateResponse(
        token=impersonate_token,
        message=f"Logged in as {target.email}",
        warning="This session expires based on token configuration.",
    )


# ── Mail queue ──


@router.get("/queue")
def admin_mail_queue(_: User = Depends(admin_required)):
    try:
        result = subprocess.run(["mailq"], capture_output=True, text=True, timeout=10)
        lines = result.stdout.strip().split("\n") if result.stdout else []
        total = 0
        entries = []
        in_queue = False
        for line in lines:
            if not line.strip():
                continue
            if line.startswith("Mail queue is empty"):
                return {"total_messages": 0, "queue": [], "timestamp": datetime.now(UTC).isoformat()}
            if "--Queue ID--" in line:
                in_queue = True
                continue
            if in_queue:
                total += 1
                entries.append(line.strip())
        return {
            "total_messages": total,
            "queue": entries[:200],
            "timestamp": datetime.now(UTC).isoformat(),
        }
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="mailq not available on this system")
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="mailq timed out")


@router.post("/queue/flush")
def admin_flush_queue(_: User = Depends(admin_required)):
    try:
        subprocess.run(["postqueue", "-f"], capture_output=True, timeout=30)
        return {"success": True, "message": "Mail queue flush initiated"}
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_501_NOT_IMPLEMENTED, detail="postqueue not available on this system")


# ── Security ──


@router.get("/security/events", response_model=list[SecurityEventResponse])
def list_security_events(
    event_type: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    query = db.query(SecurityEvent)
    if event_type:
        query = query.filter(SecurityEvent.event_type == event_type)
    return query.order_by(SecurityEvent.created_at.desc()).limit(limit).all()


@router.post("/security/events", response_model=SecurityEventResponse, status_code=status.HTTP_201_CREATED)
def create_security_event(
    req: SecurityEventCreate,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    event = SecurityEvent(
        event_type=req.event_type,
        description=req.description,
        ip_address=req.ip_address,
        user_id=req.user_id,
    )
    db.add(event)
    db.flush()
    log_admin_action(db, admin, "create_security_event", details=f"type={req.event_type}", ip_address=request.client.host if request.client else None)
    db.commit()
    db.refresh(event)
    return event


@router.delete("/security/events", status_code=status.HTTP_204_NO_CONTENT)
def clear_security_events(
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    log_admin_action(db, admin, "clear_security_events", ip_address=request.client.host if request.client else None)
    db.query(SecurityEvent).delete()
    db.commit()
    return None


@router.get("/security/blocked-ips")
def list_blocked_ips(_: User = Depends(admin_required)):
    try:
        from ifinmail.api.deps import get_redis

        r = get_redis()
        keys = r.keys("blocked_ip:*")
        result = []
        for key in keys:
            ip = key.split(":", 1)[-1]
            ttl = r.ttl(key)
            reason = r.get(key) or "Blocked"
            result.append({"ip": ip, "reason": reason, "ttl_seconds": ttl})
        return result
    except Exception:
        return []


@router.post("/security/block")
def block_ip(
    req: IPBlockRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    try:
        from ifinmail.api.deps import get_redis

        r = get_redis()
        key = f"blocked_ip:{req.ip}"
        r.setex(key, 86400, req.reason or "Blocked by admin")
        log_admin_action(db, admin, "block_ip", details=f"ip={req.ip} reason={req.reason}", ip_address=request.client.host if request.client else None)
        return {"message": f"IP {req.ip} blocked", "ip": req.ip}
    except Exception:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Redis not available")


@router.delete("/security/block/{ip}", status_code=status.HTTP_204_NO_CONTENT)
def unblock_ip(
    ip: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    try:
        from ifinmail.api.deps import get_redis

        r = get_redis()
        r.delete(f"blocked_ip:{ip}")
        log_admin_action(db, admin, "unblock_ip", details=f"ip={ip}", ip_address=request.client.host if request.client else None)
    except Exception:
        pass
    return None


class AuditLogResponse(BaseModel):
    id: int
    admin_email: str | None = None
    action: str
    target_user: str | None = None
    target_email: str | None = None
    details: str | None = None
    ip_address: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/audit-logs")
def admin_audit_logs(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    action: str | None = Query(None),
    target_user: str | None = Query(None),
    db: Session = Depends(get_db),
    admin: User = Depends(admin_required),
):
    query = db.query(AuditLog)
    if action:
        query = query.filter(AuditLog.action == action)
    if target_user:
        query = query.filter(AuditLog.target_user.ilike(f"%{target_user}%"))
    total = query.count()
    items = (
        query.order_by(AuditLog.created_at.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    result = []
    for log in items:
        admin_email = None
        if log.admin:
            admin_email = log.admin.email
        result.append({
            "id": log.id,
            "admin_email": admin_email,
            "action": log.action,
            "target_user": log.target_user,
            "target_email": log.target_email,
            "details": log.details,
            "ip_address": log.ip_address,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        })
    return {
        "items": result,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "total_pages": max(1, -(-total // per_page)),
        },
    }
