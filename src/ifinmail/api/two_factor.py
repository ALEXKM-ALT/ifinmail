import hashlib
import json
import logging
import secrets

import pyotp
import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import _create_access_token, get_current_user
from ifinmail.api.deps import get_db
from ifinmail.api.limiter import strict
from ifinmail.db.models import TwoFactor, User

logger = logging.getLogger("ifinmail.2fa")

router = APIRouter(prefix="/2fa", tags=["2fa"])

RECOVERY_CODE_COUNT = 8


class SetupResponse(BaseModel):
    secret: str
    qr_code: str
    uri: str
    recovery_codes: list[str]


class VerifyRequest(BaseModel):
    code: str


class VerifyResponse(BaseModel):
    verified: bool


class RecoveryRequest(BaseModel):
    code: str


def _hash_recovery(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def _generate_recovery_codes() -> list[str]:
    return [secrets.token_hex(4) for _ in range(RECOVERY_CODE_COUNT)]


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

    codes = _generate_recovery_codes()
    hashed = [_hash_recovery(c) for c in codes]
    tf = TwoFactor(user_id=user.id, secret=secret, enabled=0, recovery_codes=json.dumps(hashed))
    db.add(tf)
    db.commit()

    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgImage)
    qr_svg = img.to_string().decode()

    return SetupResponse(secret=secret, qr_code=qr_svg, uri=uri, recovery_codes=codes)


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


@router.post("/recovery")
def recover_2fa(
    req: RecoveryRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = strict,
):
    all_tf = db.query(TwoFactor).filter(TwoFactor.enabled == 1, TwoFactor.recovery_codes.isnot(None)).all()
    target = None
    for tf in all_tf:
        codes = json.loads(tf.recovery_codes)
        hashed_input = _hash_recovery(req.code)
        if hashed_input in codes:
            codes.remove(hashed_input)
            tf.recovery_codes = json.dumps(codes)
            target = tf
            break

    if not target:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid recovery code")

    user = db.query(User).filter(User.id == target.user_id).first()
    target.enabled = 0
    db.commit()

    token = _create_access_token(user.id)
    return {
        "access_token": token,
        "token_type": "bearer",
        "message": "2FA has been disabled. Set it up again to re-enable.",
    }


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
    recovery_count = 0
    if tf and tf.recovery_codes:
        recovery_count = len(json.loads(tf.recovery_codes))
    return {
        "enabled": bool(tf and tf.enabled),
        "configured": tf is not None,
        "recovery_codes_remaining": recovery_count,
    }
