import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.limiter import user_moderate
from ifinmail.db.models import Alias, Domain, User

logger = logging.getLogger("ifinmail.aliases")

router = APIRouter(prefix="/aliases", tags=["aliases"])


class AliasCreate(BaseModel):
    source: str
    target: str


class AliasOut(BaseModel):
    id: int
    source: str
    target: str
    enabled: bool
    created_at: str | None = None

    model_config = ConfigDict(from_attributes=True)


def _get_user_domain(user: User, db: Session) -> Domain:
    domain = db.query(Domain).filter(Domain.id == user.domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="User has no domain")
    return domain


@router.get("", response_model=list[AliasOut])
def list_aliases(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    domain = _get_user_domain(user, db)
    aliases = db.query(Alias).filter(Alias.domain_id == domain.id).order_by(Alias.source).all()
    return [
        AliasOut(
            id=a.id,
            source=a.source,
            target=a.target,
            enabled=bool(a.enabled),
            created_at=a.created_at.isoformat() if a.created_at else None,
        )
        for a in aliases
    ]


@router.post("", response_model=AliasOut, status_code=status.HTTP_201_CREATED)
def create_alias(
    req: AliasCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    domain = _get_user_domain(user, db)
    source = req.source.lower().strip()
    target = req.target.lower().strip()
    if "@" not in source or "@" not in target:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid email address")
    source_domain = source.split("@")[-1]
    if source_domain != domain.domain:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Source domain does not match your domain")
    existing = db.query(Alias).filter(Alias.source == source, Alias.target == target).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Alias already exists")
    alias = Alias(source=source, target=target, domain_id=domain.id, enabled=1)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return AliasOut(
        id=alias.id,
        source=alias.source,
        target=alias.target,
        enabled=bool(alias.enabled),
        created_at=alias.created_at.isoformat() if alias.created_at else None,
    )


@router.put("/{alias_id}/toggle", response_model=AliasOut)
def toggle_alias(alias_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    domain = _get_user_domain(user, db)
    alias = db.query(Alias).filter(Alias.id == alias_id, Alias.domain_id == domain.id).first()
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found")
    alias.enabled = 1 - alias.enabled
    db.commit()
    db.refresh(alias)
    return AliasOut(
        id=alias.id,
        source=alias.source,
        target=alias.target,
        enabled=bool(alias.enabled),
        created_at=alias.created_at.isoformat() if alias.created_at else None,
    )


@router.delete("/{alias_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alias(alias_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    domain = _get_user_domain(user, db)
    alias = db.query(Alias).filter(Alias.id == alias_id, Alias.domain_id == domain.id).first()
    if not alias:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alias not found")
    db.delete(alias)
    db.commit()
