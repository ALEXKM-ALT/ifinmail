import email.utils
import hashlib
import logging
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from ifinmail.api.config import settings
from ifinmail.api.deps import get_db, get_redis
from ifinmail.api.limiter import strict
from ifinmail.db.models import ApiKey, Domain, Mailbox, User, UserSession

logger = logging.getLogger("ifinmail.auth")

router = APIRouter(prefix="/auth", tags=["auth"])
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    is_admin: bool = False


class RefreshRequest(BaseModel):
    refresh_token: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    password: str


class UserResponse(BaseModel):
    id: int
    email: str
    is_admin: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class RegisterResponse(BaseModel):
    message: str
    email: str
    id: int
    is_admin: bool


def _create_access_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_expire_minutes),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _create_refresh_token(user_id: int) -> str:
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=settings.refresh_token_expire_days),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_token(token: str, expected_type: str) -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != expected_type:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
        user_id = int(payload.get("sub", ""))
        if not user_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        return user_id
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


def decode_token(token: str) -> int | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") == "access":
            return int(payload.get("sub", 0))
    except JWTError:
        pass
    return None


def _is_token_blacklisted(token: str) -> bool:
    try:
        redis = get_redis()
        return bool(redis.get(f"blacklist:{token}"))
    except Exception:
        return False


def _blacklist_token(token: str, expire_seconds: int) -> None:
    try:
        redis = get_redis()
        redis.setex(f"blacklist:{token}", expire_seconds, "1")
    except Exception:
        pass


def _create_session(
    db: Session,
    user: User,
    refresh_token: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> UserSession:
    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    now = datetime.now(UTC)
    session = UserSession(
        user_id=user.id,
        token_hash=token_hash,
        ip_address=ip_address,
        user_agent=user_agent[:512] if user_agent else None,
        last_used_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
    )
    db.add(session)
    return session


def _ensure_domain(email: str, db: Session) -> Domain:
    domain_part = email.split("@", 1)[-1]
    domain = db.query(Domain).filter(Domain.domain == domain_part).first()
    if not domain:
        domain = Domain(domain=domain_part, verified=0)
        db.add(domain)
        db.flush()
    return domain


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(security, use_cache=False),
    db: Session = Depends(get_db),
    x_api_key: str | None = Header(None, alias="X-Api-Key"),
) -> User:
    if x_api_key:
        key_hash = hashlib.sha256(x_api_key.encode()).hexdigest()
        api_key = (
            db.query(ApiKey)
            .filter(
                ApiKey.key_hash == key_hash,
                ApiKey.active == 1,
            )
            .first()
        )
        if not api_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
        user = db.query(User).filter(User.id == api_key.user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
        api_key.last_used_at = datetime.now(UTC)
        db.flush()
        return user
    if creds is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    token = creds.credentials
    if _is_token_blacklisted(token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")
    user_id = _decode_token(token, "access")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
def register(req: RegisterRequest, db: Session = Depends(get_db), _: None = strict):
    from ifinmail.api.verify import validate_email_syntax

    syntax_err = validate_email_syntax(req.email)
    if syntax_err:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=syntax_err)

    existing = db.query(User).filter(User.email == req.email).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")

    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    domain = _ensure_domain(req.email, db)
    hashed = pwd_context.hash(req.password)
    user_count = db.query(User).count()
    user = User(
        email=req.email,
        password=hashed,
        domain_id=domain.id,
        is_admin=1 if user_count == 0 else 0,
    )
    db.add(user)
    db.flush()

    mailbox = Mailbox(email=req.email, user_id=user.id, plan="free")
    db.add(mailbox)
    db.commit()

    return RegisterResponse(message="User registered", email=req.email, id=user.id, is_admin=bool(user.is_admin))


LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_MINUTES = 15


def _login_attempt_key(email: str) -> str:
    return f"login_attempts:{email.lower()}"


@router.post("/login")
def login(
    req: LoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    _: None = strict,
):
    email_lower = req.email.lower().strip()
    try:
        r = get_redis()
        attempts_key = _login_attempt_key(email_lower)
        failed = int(r.get(attempts_key) or 0)
        if failed >= LOGIN_MAX_ATTEMPTS:
            ttl = r.ttl(attempts_key)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked. Try again in {max(1, ttl // 60)} minute(s).",
            )
    except HTTPException:
        raise
    except Exception:
        pass

    user = db.query(User).filter(User.email == email_lower).first()
    if not user or not pwd_context.verify(req.password, user.password):
        try:
            r = get_redis()
            r.incr(attempts_key)
            r.expire(attempts_key, LOGIN_LOCKOUT_MINUTES * 60)
        except Exception:
            pass
        from ifinmail.api.metrics import failed_logins_total

        failed_logins_total.inc()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")

    try:
        r = get_redis()
        r.delete(attempts_key)
    except Exception:
        pass

    access_token = _create_access_token(user.id)
    refresh_token = _create_refresh_token(user.id)

    user_agent = request.headers.get("user-agent")
    ip_address = request.client.host if request.client else None
    _create_session(db, user, refresh_token, ip_address=ip_address, user_agent=user_agent)
    db.commit()

    return TokenResponse(access_token=access_token, refresh_token=refresh_token, is_admin=bool(user.is_admin))


@router.post("/refresh")
def refresh(req: RefreshRequest, db: Session = Depends(get_db), _: None = strict):
    if _is_token_blacklisted(req.refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    user_id = _decode_token(req.refresh_token, "refresh")
    access_token = _create_access_token(user_id)
    user = db.query(User).filter(User.id == user_id).first()

    token_hash = hashlib.sha256(req.refresh_token.encode()).hexdigest()
    session = db.query(UserSession).filter(UserSession.token_hash == token_hash).first()
    if session:
        session.last_used_at = datetime.now(UTC)
        db.commit()

    return {"access_token": access_token, "token_type": "bearer", "is_admin": bool(user.is_admin) if user else False}


@router.get("/sessions")
def list_sessions(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sessions = (
        db.query(UserSession).filter(UserSession.user_id == user.id).order_by(UserSession.last_used_at.desc()).all()
    )
    return [
        {
            "id": s.id,
            "ip_address": s.ip_address,
            "user_agent": s.user_agent,
            "last_used_at": s.last_used_at.isoformat() if s.last_used_at else None,
            "created_at": s.created_at.isoformat() if s.created_at else None,
            "expires_at": s.expires_at.isoformat() if s.expires_at else None,
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_session(
    session_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    session = (
        db.query(UserSession)
        .filter(
            UserSession.id == session_id,
            UserSession.user_id == user.id,
        )
        .first()
    )
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    db.delete(session)
    db.commit()


@router.post("/logout")
def logout(req: RefreshRequest):
    try:
        payload = jwt.decode(req.refresh_token, settings.secret_key, algorithms=[settings.algorithm])
        exp = payload.get("exp", 0)
        now = datetime.now(UTC).timestamp()
        ttl = max(int(exp - now), 0)
        _blacklist_token(req.refresh_token, ttl)
    except JWTError:
        pass
    return {"message": "Logged out"}


@router.post("/forgot-password")
def forgot_password(req: ForgotPasswordRequest, db: Session = Depends(get_db), _: None = strict):
    user = db.query(User).filter(User.email == req.email).first()
    if not user:
        return {"message": "If that email exists, a reset link has been sent."}

    now = datetime.now(UTC)
    token = jwt.encode(
        {"sub": str(user.id), "type": "password_reset", "iat": now, "exp": now + timedelta(minutes=15)},
        settings.secret_key,
        algorithm=settings.algorithm,
    )

    reset_url = f"{settings.app_url}/?token={token}"

    if settings.smtp_host:
        try:
            msg = EmailMessage()
            if settings.smtp_user and "@" in settings.smtp_user:
                domain = settings.smtp_user.split("@")[-1]
            else:
                domain = settings.default_domain
            msg["From"] = f"ifinmail <noreply@{domain}>"
            msg["To"] = req.email
            msg["Subject"] = "Password Reset"
            msg["Message-ID"] = email.utils.make_msgid()
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg.set_content(
                f"Click the link to reset your password:\n\n{reset_url}\n\nThis link expires in 15 minutes."
            )
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout) as server:
                if settings.smtp_tls:
                    server.starttls()
                if settings.smtp_user:
                    server.login(settings.smtp_user, settings.smtp_password)
                server.sendmail(msg["From"], [req.email], msg.as_string())
        except Exception:
            pass
    else:
        logger.warning("No SMTP configured. Reset URL: %s", reset_url)

    return {"message": "If that email exists, a reset link has been sent."}


@router.post("/reset-password")
def reset_password(req: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(req.token, settings.secret_key, algorithms=[settings.algorithm])
        if payload.get("type") != "password_reset":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type")
        user_id = int(payload.get("sub", ""))
    except JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")

    if len(req.password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Password must be at least 6 characters")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    user.password = pwd_context.hash(req.password)
    db.commit()
    return {"message": "Password reset successful"}


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
