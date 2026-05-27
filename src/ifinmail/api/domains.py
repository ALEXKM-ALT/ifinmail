import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import Domain, User

router = APIRouter(prefix="/domains", tags=["domains"])


class DomainCreate(BaseModel):
    domain: str


class DomainVerifyResponse(BaseModel):
    domain: str
    verified: bool
    dns_records: list[dict]


class DomainResponse(BaseModel):
    id: int
    domain: str
    verified: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[DomainResponse])
def list_user_domains(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    # Non-admin users see all domains (they can send to any domain)
    return db.query(Domain).order_by(Domain.domain).all()


@router.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
def add_domain(
    req: DomainCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    domain_name = req.domain.lower().strip()
    if not domain_name or "." not in domain_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid domain")
    existing = db.query(Domain).filter(Domain.domain == domain_name).first()
    if existing:
        if user.is_admin:
            return JSONResponse(content=DomainResponse.model_validate(existing).model_dump(mode="json"), status_code=200)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain already exists")
    domain = Domain(domain=domain_name, verified=0)
    db.add(domain)
    db.commit()
    db.refresh(domain)
    return domain


@router.get("/{domain_id}/verify", response_model=DomainVerifyResponse)
def verify_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    verification_token = secrets.token_hex(16)
    dns_records = [
        {"type": "MX", "name": domain.domain, "value": "mail.ifinmail.com", "priority": 10},
        {"type": "TXT", "name": domain.domain, "value": "v=spf1 include:ifinmail.com -all"},
        {"type": "TXT", "name": f"_verify.{domain.domain}", "value": verification_token},
    ]
    return DomainVerifyResponse(
        domain=domain.domain,
        verified=bool(domain.verified),
        dns_records=dns_records,
    )


@router.delete("/{domain_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_domain(
    domain_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    if not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    db.delete(domain)
    db.commit()
