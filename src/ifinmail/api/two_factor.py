import logging

import pyotp
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import get_current_user
from ifinmail.api.deps import get_db
from ifinmail.db.models import TwoFactor, User

logger = logging.getLogger("ifinmail.2fa")

router = APIRouter(prefix="/2fa", tags=["2fa"])


class SetupResponse(BaseModel):
    secret: str
    qr_code: str
    uri: str


class VerifyRequest(BaseModel):
    code: str


class VerifyResponse(BaseModel):
    verified: bool


@router.post("/setup")
def setup_2fa(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    existing = db.query(TwoFactor).filter(TwoFactor.user_id == user.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="2FA already configured")

    secret = pyotp.random_base32()
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(user.email, issuer_name="ifinmail")

    tf = TwoFactor(user_id=user.id, secret=secret, enabled=0)
    db.add(tf)
    db.commit()

    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    qr_svg = img.to_string().decode()

    return SetupResponse(secret=secret, qr_code=qr_svg, uri=uri)


@router.post("/verify", response_model=VerifyResponse)
def verify_2fa(
    req: VerifyRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tf = db.query(TwoFactor).filter(TwoFactor.user_id == user.id).first()
    if not tf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="2FA not configured")

    totp = pyotp.TOTP(tf.secret)
    valid = totp.verify(req.code, valid_window=1)
    if not valid:
        return VerifyResponse(verified=False)

    if not tf.enabled:
        tf.enabled = 1
        db.commit()

    return VerifyResponse(verified=True)


@router.post("/disable")
def disable_2fa(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tf = db.query(TwoFactor).filter(TwoFactor.user_id == user.id).first()
    if not tf:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="2FA not configured")
    db.delete(tf)
    db.commit()
    return {"message": "2FA disabled"}


@router.get("/status")
def status_2fa(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    tf = db.query(TwoFactor).filter(TwoFactor.user_id == user.id).first()
    return {"enabled": bool(tf and tf.enabled), "configured": tf is not None}
