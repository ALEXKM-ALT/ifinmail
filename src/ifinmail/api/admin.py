from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import Alias, Attachment, Domain, Mailbox, Message, User

router = APIRouter(prefix="/admin", tags=["admin"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def admin_required(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return user


class DomainCreate(BaseModel):
    domain: str


class DomainResponse(BaseModel):
    id: int
    domain: str
    verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UserCreate(BaseModel):
    email: str
    password: str
    is_admin: bool = False


class UserUpdatePassword(BaseModel):
    password: str


class UserUpdate(BaseModel):
    email: str | None = None
    is_admin: bool | None = None
    password: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    is_admin: bool
    domain_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MailboxCreate(BaseModel):
    email: str
    quota_mb: int = 1024


class MailboxResponse(BaseModel):
    id: int
    email: str
    quota_mb: int
    used_mb: int
    enabled: bool
    plan: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AliasCreate(BaseModel):
    source: str
    target: str


class AliasResponse(BaseModel):
    id: int
    source: str
    target: str
    enabled: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ── Domains ──


@router.get("/domains", response_model=list[DomainResponse])
def list_domains(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(Domain).order_by(Domain.domain).all()


@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
def create_domain(req: DomainCreate, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    domain_name = req.domain.lower().strip()
    existing = db.query(Domain).filter(Domain.domain == domain_name).first()
    if existing:
        return JSONResponse(content=DomainResponse.model_validate(existing).model_dump(mode="json"), status_code=200)
    domain = Domain(domain=domain_name)
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.get("/domains/{domain_id}", response_model=DomainResponse)
def get_domain(domain_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    return domain


@router.delete("/domains/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain(domain_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    db.delete(domain)
    db.commit()


# ── Users ──


@router.get("/users", response_model=list[UserResponse])
def list_users(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(User).order_by(User.email).all()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(req: UserCreate, db: Session = Depends(get_db), _: User = Depends(admin_required)):
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
    user = User(email=req.email, password=hashed, domain_id=domain.id, is_admin=int(req.is_admin))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user


@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(user_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    db.delete(user)
    db.commit()


@router.put("/users/{user_id}/password")
def update_user_password(
    user_id: int,
    req: UserUpdatePassword,
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password too short")
    user.password = pwd_context.hash(req.password)
    db.commit()
    return {"message": "Password updated"}


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    req: UserUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(admin_required),
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
    db.commit()
    db.refresh(user)
    return user


# ── Stats ──


class StatsResponse(BaseModel):
    total_users: int
    total_domains: int
    total_mailboxes: int
    total_messages: int
    total_attachments: int
    total_storage_bytes: int
    messages_by_folder: dict[str, int]
    users_last_24h: int


@router.get("/stats", response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    total_users = db.query(sa_func.count(User.id)).scalar() or 0
    total_domains = db.query(sa_func.count(Domain.id)).scalar() or 0
    total_mailboxes = db.query(sa_func.count(Mailbox.id)).scalar() or 0
    total_messages = db.query(sa_func.count(Message.id)).scalar() or 0
    total_attachments = db.query(sa_func.count(Attachment.id)).scalar() or 0
    total_storage = db.query(sa_func.coalesce(sa_func.sum(Message.size), 0)).scalar() or 0
    since = datetime.now(UTC)
    users_24h = db.query(sa_func.count(User.id)).filter(User.created_at >= since).scalar() or 0

    folder_counts = {}
    for row in db.query(Message.folder, sa_func.count(Message.id)).group_by(Message.folder).all():
        folder_counts[row[0]] = row[1]

    return StatsResponse(
        total_users=total_users,
        total_domains=total_domains,
        total_mailboxes=total_mailboxes,
        total_messages=total_messages,
        total_attachments=total_attachments,
        total_storage_bytes=total_storage,
        messages_by_folder=folder_counts,
        users_last_24h=users_24h,
    )


# ── Mailboxes ──


@router.get("/mailboxes", response_model=list[MailboxResponse])
def list_mailboxes(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(Mailbox).order_by(Mailbox.email).all()


@router.post("/mailboxes", response_model=MailboxResponse, status_code=status.HTTP_201_CREATED)
def create_mailbox(req: MailboxCreate, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User not found")
    existing = db.query(Mailbox).filter(Mailbox.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Mailbox already exists")
    mailbox = Mailbox(email=req.email, user_id=user.id, quota_mb=req.quota_mb, plan="free")
    db.add(mailbox)
    db.commit()
    db.refresh(mailbox)
    return mailbox


@router.delete("/mailboxes/{mailbox_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mailbox(mailbox_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    mailbox = db.query(Mailbox).filter(Mailbox.id == mailbox_id).first()
    if not mailbox:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mailbox not found")
    db.delete(mailbox)
    db.commit()


# ── Aliases ──


@router.get("/aliases", response_model=list[AliasResponse])
def list_aliases(db: Session = Depends(get_db), _: User = Depends(admin_required)):
    return db.query(Alias).order_by(Alias.source).all()


@router.post("/aliases", response_model=AliasResponse, status_code=status.HTTP_201_CREATED)
def create_alias(req: AliasCreate, db: Session = Depends(get_db), _: User = Depends(admin_required)):
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
    db.commit()
    db.refresh(alias)
    return alias


@router.delete("/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alias(alias_id: int, db: Session = Depends(get_db), _: User = Depends(admin_required)):
    alias = db.query(Alias).filter(Alias.id == alias_id).first()
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found")
    db.delete(alias)
    db.commit()
