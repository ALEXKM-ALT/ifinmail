import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.dkim_utils import dkim_dns_record, generate_dkim_key
from ifinmail.api.dns_utils import check_dkim, check_dmarc, check_mx, check_spf, check_verification_token
from ifinmail.api.limiter import user_moderate
from ifinmail.db.models import Domain, User

router = APIRouter(prefix="/domains", tags=["domains"])


class DomainCreate(BaseModel):
    domain: str


class DomainVerifyResponse(BaseModel):
    domain: str
    verified: bool
    verification_token: str
    dns_records: list[dict]


class DnsCheckResult(BaseModel):
    spf: dict
    dkim: dict
    dmarc: dict
    mx: dict
    ownership: dict
    all_ok: bool


class DnsCheckResponse(BaseModel):
    domain: str
    verified: bool
    checks: DnsCheckResult


class DomainResponse(BaseModel):
    id: int
    domain: str
    verified: bool
    verification_token: str | None = None
    spf_ok: bool
    dkim_ok: bool
    dmarc_ok: bool
    mx_ok: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("", response_model=list[DomainResponse])
def list_user_domains(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    domains = db.query(Domain).order_by(Domain.domain).all()
    return domains


@router.post("", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
def add_domain(
    req: DomainCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    _: None = user_moderate,
):
    domain_name = req.domain.lower().strip()
    if not domain_name or "." not in domain_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid domain")
    existing = db.query(Domain).filter(Domain.domain == domain_name).first()
    if existing:
        if user.is_admin:
            return JSONResponse(
                content=DomainResponse.model_validate(existing).model_dump(mode="json"), status_code=200
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Domain already exists")
    token = secrets.token_hex(16)
    domain = Domain(domain=domain_name, verified=0, verification_token=token)
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
    if not domain.verification_token:
        domain.verification_token = secrets.token_hex(16)
        db.commit()
    token = domain.verification_token
    dns_records = [
        {
            "type": "MX",
            "name": domain.domain,
            "value": "mail.ifinmail.com",
            "priority": 10,
            "purpose": "Route email to ifinmail",
        },
        {
            "type": "TXT",
            "name": domain.domain,
            "value": "v=spf1 include:ifinmail.com ~all",
            "purpose": "Authorise ifinmail to send email",
        },
        {
            "type": "TXT",
            "name": f"default._domainkey.{domain.domain}",
            "value": "v=DKIM1; h=sha256; k=rsa; p=MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQC..." + token[:8],
            "purpose": "DKIM signing key",
        },
        {
            "type": "TXT",
            "name": f"_dmarc.{domain.domain}",
            "value": "v=DMARC1; p=quarantine; rua=mailto:dmarc@{domain.domain}",
            "purpose": "DMARC policy",
        },
        {
            "type": "TXT",
            "name": f"_verify.{domain.domain}",
            "value": token,
            "purpose": "Domain ownership verification",
        },
    ]
    return DomainVerifyResponse(
        domain=domain.domain,
        verified=bool(domain.verified),
        verification_token=token,
        dns_records=dns_records,
    )


@router.post("/{domain_id}/check-dns", response_model=DnsCheckResponse)
def check_domain_dns(
    domain_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    if not domain.verification_token:
        domain.verification_token = secrets.token_hex(16)
        db.commit()

    spf = check_spf(domain.domain)
    dkim = check_dkim(domain.domain)
    dmarc = check_dmarc(domain.domain)
    mx = check_mx(domain.domain)
    ownership = check_verification_token(domain.domain, domain.verification_token)

    domain.spf_ok = 1 if spf["ok"] else 0
    domain.dkim_ok = 1 if dkim["ok"] else 0
    domain.dmarc_ok = 1 if dmarc["ok"] else 0
    domain.mx_ok = 1 if mx["ok"] else 0
    if ownership["ok"] and spf["ok"]:
        domain.verified = 1
    elif domain.verified and not ownership["ok"]:
        domain.verified = 0

    db.commit()
    db.refresh(domain)

    return DnsCheckResponse(
        domain=domain.domain,
        verified=bool(domain.verified),
        checks=DnsCheckResult(
            spf=spf,
            dkim=dkim,
            dmarc=dmarc,
            mx=mx,
            ownership=ownership,
            all_ok=bool(domain.verified and domain.spf_ok and domain.dkim_ok and domain.dmarc_ok and domain.mx_ok),
        ),
    )


@router.post("/{domain_id}/generate-dkim-key")
def generate_dkim_key_endpoint(
    domain_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    domain = db.query(Domain).filter(Domain.id == domain_id).first()
    if not domain:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Domain not found")
    try:
        priv, pub = generate_dkim_key()
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate DKIM key: {e}")
    selector = "default"
    domain.dkim_private_key = priv
    domain.dkim_selector = selector
    db.commit()
    return {
        "selector": selector,
        "private_key": priv,
        "dns_record": {
            "type": "TXT",
            "name": f"{selector}._domainkey.{domain.domain}",
            "value": dkim_dns_record(pub),
            "purpose": "DKIM signing key — publish this in your DNS",
        },
        "warning": "Save the private key now — it will not be shown again.",
    }


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
