import base64
import hashlib
import logging
import secrets
import urllib.parse
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from passlib.context import CryptContext
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ifinmail.api.auth import _create_access_token, _create_refresh_token
from ifinmail.api.config import settings
from ifinmail.api.deps import get_db
from ifinmail.db.models import Domain, Mailbox, SSOState, User

logger = logging.getLogger("ifinmail.sso")

router = APIRouter(prefix="/sso", tags=["sso"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

GOOGLE_CONFIG = {
    "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_url": "https://oauth2.googleapis.com/token",
    "userinfo_url": "https://www.googleapis.com/oauth2/v2/userinfo",
    "scopes": "openid email profile",
}

MICROSOFT_CONFIG = {
    "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
    "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
    "userinfo_url": "https://graph.microsoft.com/v1.0/me",
    "scopes": "openid email User.Read",
}


class SSOLoginResponse(BaseModel):
    authorize_url: str


class SSOCallbackResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_admin: bool = False


class SSOStatusResponse(BaseModel):
    google: bool
    microsoft: bool


def _get_sso_config(provider: str) -> dict:
    client_id = getattr(settings, f"sso_{provider}_client_id", None) or ""
    client_secret = getattr(settings, f"sso_{provider}_client_secret", None) or ""
    config_map = {"google": GOOGLE_CONFIG, "microsoft": MICROSOFT_CONFIG}
    base = config_map.get(provider)
    if not base:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown provider: {provider}")
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=(
                f"SSO {provider} is not configured. "
                f"Set SSO_{provider.upper()}_CLIENT_ID and SSO_{provider.upper()}_CLIENT_SECRET in .env"
            ),
        )
    cfg = dict(base)
    cfg["client_id"] = client_id
    cfg["client_secret"] = client_secret
    return cfg


def _cleanup_expired_states(db: Session) -> None:
    db.query(SSOState).filter(SSOState.expires_at < datetime.now(UTC)).delete()
    db.commit()


def _generate_pkce() -> tuple[str, str]:
    code_verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(code_verifier.encode()).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return code_verifier, code_challenge


@router.get("/status", response_model=SSOStatusResponse)
def sso_status():
    return SSOStatusResponse(
        google=bool(settings.sso_google_client_id and settings.sso_google_client_secret),
        microsoft=bool(settings.sso_microsoft_client_id and settings.sso_microsoft_client_secret),
    )


@router.get("/{provider}/login", response_model=SSOLoginResponse)
def sso_login(
    provider: str,
    redirect_uri: str = Query(...),
    db: Session = Depends(get_db),
):
    cfg = _get_sso_config(provider)
    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = _generate_pkce()

    sso_state = SSOState(
        state=state,
        provider=provider,
        redirect_uri=redirect_uri,
        code_verifier=code_verifier,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    db.add(sso_state)
    db.commit()

    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": cfg["scopes"],
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    url = f"{cfg['authorize_url']}?{urllib.parse.urlencode(params)}"
    return SSOLoginResponse(authorize_url=url)


def _sso_exchange(sso_state: SSOState, provider: str, code: str, db: Session) -> SSOCallbackResponse:
    if datetime.now(UTC) > sso_state.expires_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="State expired")

    cfg = _get_sso_config(provider)

    try:
        token_data = {
            "code": code,
            "client_id": cfg["client_id"],
            "client_secret": cfg["client_secret"],
            "redirect_uri": sso_state.redirect_uri,
            "grant_type": "authorization_code",
        }
        if sso_state.code_verifier:
            token_data["code_verifier"] = sso_state.code_verifier

        with httpx.Client() as client:
            token_resp = client.post(cfg["token_url"], data=token_data)
            token_json = token_resp.json()
            access_token = token_json.get("access_token")
            if not access_token:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Failed to get access token")

            headers = {"Authorization": f"Bearer {access_token}"}
            if provider == "google":
                user_resp = client.get(cfg["userinfo_url"], headers=headers)
                info = user_resp.json()
                email = info.get("email", "")
                name = info.get("name", "")
            elif provider == "microsoft":
                user_resp = client.get(cfg["userinfo_url"], headers=headers)
                info = user_resp.json()
                email = info.get("mail") or info.get("userPrincipalName", "")
                name = info.get("displayName", "")
            else:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unknown provider")

            if not email or "@" not in email:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not get email from provider")

            user = db.query(User).filter(User.email == email).first()
            if not user:
                domain_part = email.split("@", 1)[-1]
                domain_obj = db.query(Domain).filter(Domain.domain == domain_part).first()
                if not domain_obj:
                    domain_obj = Domain(domain=domain_part, verified=0)
                    db.add(domain_obj)
                    db.flush()
                user_count = db.query(User).count()
                first_name = name.split()[0] if name and " " in name else name
                last_name = name.split(None, 1)[-1] if name and " " in name else None
                user = User(
                    email=email,
                    password=pwd_context.hash(secrets.token_urlsafe(16)),
                    domain_id=domain_obj.id,
                    is_admin=1 if user_count == 0 else 0,
                    first_name=first_name,
                    last_name=last_name,
                )
                db.add(user)
                db.flush()
                mailbox = Mailbox(email=email, user_id=user.id, plan="free")
                db.add(mailbox)

            user.last_login = datetime.now(UTC)

            jwt_token = _create_access_token(user.id)
            refresh_token = _create_refresh_token(user.id)
            return SSOCallbackResponse(
                access_token=jwt_token,
                refresh_token=refresh_token,
                is_admin=bool(user.is_admin),
            )
    except httpx.HTTPError as e:
        logger.error("SSO HTTP error: %s", e)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="SSO provider communication failed")


@router.get("/callback", response_model=SSOCallbackResponse)
def sso_callback_generic(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    _cleanup_expired_states(db)

    sso_state = db.query(SSOState).filter(SSOState.state == state).first()
    if not sso_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")

    provider = sso_state.provider
    db.delete(sso_state)
    db.commit()

    return _sso_exchange(sso_state, provider, code, db)


@router.get("/{provider}/callback", response_model=SSOCallbackResponse)
def sso_callback(
    provider: str,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
):
    _cleanup_expired_states(db)

    sso_state = (
        db.query(SSOState)
        .filter(
            SSOState.state == state,
            SSOState.provider == provider,
        )
        .first()
    )
    if not sso_state:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired state")

    db.delete(sso_state)
    db.commit()

    return _sso_exchange(sso_state, provider, code, db)
