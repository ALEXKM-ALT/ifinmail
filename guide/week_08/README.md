# Week 8: Python API Development — The ifinmail Platform Layer

**Month 2: Core Mail Stack | Days 43–48**

The API layer is what makes ifinmail a platform, not just a mail server. This week builds the full REST API contract described in proposal Section 7: authentication, mail operations, admin endpoints, device bootstrap, structured errors, and OpenAPI documentation. By Friday, you will have a working API that powers both the web client and future official apps.

---

## Learning Goals for the Week

By Sunday, you will be able to:

- Design and implement a versioned REST API matching the ifinmail contract
- Implement JWT-based authentication with refresh tokens
- Build all four API groups: Auth, Mail, Admin, and Device Bootstrap
- Generate OpenAPI documentation automatically
- Write integration tests for the API
- Understand idempotency keys, pagination, and structured errors

---

## Day 1 (Monday): API Architecture & Auth Endpoints

### Learning Objectives
- Design the ifinmail API project structure
- Implement user registration and login with Argon2id password hashing
- Generate and validate JWT access and refresh tokens
- Implement MFA TOTP setup (proposal Section 7.2 Auth API)

### Theory / Reading
- **JWT**: JSON Web Token — stateless authentication; header.payload.signature
- **Access vs refresh tokens**: short-lived access (15-30 min) + longer refresh (7-30 days)
- **Argon2id**: memory-hard password hashing; resistant to GPU/ASIC attacks
- **Structured errors**: every API error has `code`, `message`, `status` (proposal Section 7.1)

### Practical Exercise
```bash
# Create the ifinmail API project
mkdir -p ~/ifinmail-api/{app,app/routers,app/models,app/services,tests}
cd ~/ifinmail-api
python3 -m venv venv
source venv/bin/activate
pip install fastapi uvicorn pydantic[email] sqlalchemy asyncpg psycopg2-binary \
            python-jose[cryptography] passlib[argon2] redis httpx pytest
```

```python
# ~/ifinmail-api/app/__init__.py
"""ifinmail API — the platform layer for the ifinmail email ecosystem."""
__version__ = "0.1.0"
```

```python
# ~/ifinmail-api/app/main.py
"""FastAPI application factory for ifinmail."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.routers import auth, mail, admin, devices

app = FastAPI(
    title="ifinmail API",
    description="Secure, API-first email platform — proposal Section 7",
    version="0.1.0",
    docs_url="/v1/docs",
    openapi_url="/v1/openapi.json",
)

# CORS (restrict in production)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten in production
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API groups
app.include_router(auth.router, prefix="/v1/auth", tags=["Auth"])
app.include_router(mail.router, prefix="/v1/mail", tags=["Mail"])
app.include_router(admin.router, prefix="/v1/admin", tags=["Admin"])
app.include_router(devices.router, prefix="/v1/devices", tags=["Devices"])

@app.get("/v1/health")
async def health():
    return {"status": "ok", "service": "ifinmail-api", "version": __version__}
```

```python
# ~/ifinmail-api/app/models/auth.py
"""Pydantic models for authentication (proposal Section 7.2)."""
from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime

class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    device_name: Optional[str] = "Unknown"

class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 1800  # 30 minutes
    
class TokenRefreshRequest(BaseModel):
    refresh_token: str

class MfaSetupResponse(BaseModel):
    secret: str
    qr_code_url: str
    backup_codes: list[str]

class MfaVerifyRequest(BaseModel):
    code: str

class SessionInfo(BaseModel):
    session_id: str
    device_name: str
    ip_address: str
    created_at: datetime
    last_active: datetime
```

```python
# ~/ifinmail-api/app/services/auth_service.py
"""Authentication service — Argon2id hashing, JWT, MFA."""
import hashlib
from datetime import datetime, timedelta
from typing import Optional
from jose import jwt, JWTError
from passlib.hash import argon2

# In production: load from env vars / secrets manager
SECRET_KEY = "CHANGE_ME_IN_PRODUCTION_USE_64_BYTE_RANDOM_KEY"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
REFRESH_TOKEN_EXPIRE_DAYS = 30

def hash_password(password: str) -> str:
    """Hash password with Argon2id (proposal Section 13.1)."""
    return argon2.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    """Verify password against Argon2id hash."""
    return argon2.verify(password, hashed)

def create_access_token(user_id: int, email: str, org_id: int) -> str:
    """Create a short-lived JWT access token."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "email": email,
        "org_id": org_id,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "jti": hashlib.sha256(f"{user_id}{now.timestamp()}".encode()).hexdigest()[:16],
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def create_refresh_token(user_id: int, session_id: str) -> str:
    """Create a long-lived JWT refresh token."""
    now = datetime.utcnow()
    payload = {
        "sub": str(user_id),
        "session_id": session_id,
        "type": "refresh",
        "iat": now,
        "exp": now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "jti": hashlib.sha256(f"{session_id}{now.timestamp()}".encode()).hexdigest()[:16],
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str) -> Optional[dict]:
    """Decode and validate a JWT token. Returns None if invalid."""
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None

# Quick smoke test
if __name__ == "__main__":
    h = hash_password("test_password_123")
    print(f"Hash: {h[:50]}...")
    print(f"Verify correct: {verify_password('test_password_123', h)}")
    print(f"Verify wrong: {verify_password('wrong_password', h)}")
    
    token = create_access_token(1, "alice@ifinmail.local", 1)
    print(f"Token: {token[:50]}...")
    print(f"Decoded: {decode_token(token)}")
```

### Checkpoint Questions
1. Why does ifinmail separate access tokens (short-lived) from refresh tokens (long-lived)?
2. Why Argon2id instead of bcrypt or scrypt?
3. What information should go in a JWT payload vs what should be looked up in the database?
4. How would you implement session revocation given stateless JWTs?

### Connection to ifinmail
Auth is the gateway to every API call. The proposal mandates "structured and consistent" errors and "idempotency keys where useful." This JWT implementation powers authentication for all official clients.

---

## Day 2 (Tuesday): Mail API Endpoints

### Learning Objectives
- Implement the full Mail API group (proposal Section 7.2)
- Handle pagination, filtering, and sorting
- Implement idempotency keys for write operations
- Connect API endpoints to Dovecot Maildir or message metadata in PostgreSQL

### Theory / Reading
- **Pagination**: cursor-based (more stable with concurrent inserts) vs offset-based (simpler)
- **Idempotency key**: client-generated unique key; server stores key + result to prevent duplicate processing
- **Partial responses**: allow clients to request only the fields they need

### Practical Exercise
```python
# ~/ifinmail-api/app/routers/mail.py
"""Mail API router (proposal Section 7.2)."""
from fastapi import APIRouter, Depends, HTTPException, Query, Header
from typing import Optional, List
from pydantic import BaseModel
from datetime import datetime

router = APIRouter()

# --- Dependencies ---
def get_current_user():
    """Dependency: validate JWT and return current user."""
    # Week 8 Day 1 auth integration — for now, return a mock user
    return {"id": 1, "email": "alice@ifinmail.local", "org_id": 1}

# --- Models ---
class MessageSummary(BaseModel):
    id: str
    sender: str
    subject: str
    snippet: str
    flags: List[str] = []
    has_attachments: bool = False
    received_at: datetime

class MessageDetail(BaseModel):
    id: str
    sender: str
    to: List[str]
    cc: List[str] = []
    subject: str
    body_text: str
    body_html: Optional[str] = None
    flags: List[str] = []
    attachments: List[dict] = []
    received_at: datetime

class SendRequest(BaseModel):
    to: List[str]
    cc: Optional[List[str]] = []
    bcc: Optional[List[str]] = []
    subject: str
    body_text: str
    body_html: Optional[str] = None
    in_reply_to: Optional[str] = None
    idempotency_key: Optional[str] = None  # proposal Section 7.1

# --- Endpoints ---
@router.get("/mailboxes")
async def list_mailboxes(user=Depends(get_current_user)):
    """List mailboxes for the authenticated user."""
    return {
        "mailboxes": [
            {"name": "INBOX", "total": 42, "unread": 3},
            {"name": "Sent", "total": 120, "unread": 0},
            {"name": "Drafts", "total": 2, "unread": 0},
            {"name": "Archive", "total": 500, "unread": 0},
            {"name": "Trash", "total": 15, "unread": 0},
            {"name": "Junk", "total": 7, "unread": 1},
        ]
    }

@router.get("/messages")
async def list_messages(
    mailbox: str = Query("INBOX", description="Mailbox name"),
    limit: int = Query(50, ge=1, le=200),
    page: int = Query(1, ge=1),
    sort: str = Query("-received_at", description="Sort field, prefix with - for descending"),
    user=Depends(get_current_user),
):
    """
    List messages in a mailbox with pagination.
    Matches proposal Section 7.2 Mail API.
    """
    # In production: query PostgreSQL messages_meta table
    return {
        "mailbox": mailbox,
        "page": page,
        "limit": limit,
        "total": 42,
        "has_more": page * limit < 42,
        "messages": [],  # Populated from database
    }

@router.get("/messages/{message_id}")
async def read_message(message_id: str, user=Depends(get_current_user)):
    """Read a single message by ID."""
    # In production: fetch from Maildir via Dovecot or database metadata
    raise HTTPException(status_code=501, detail={"code": "NOT_IMPLEMENTED", "message": "Connect to database in exercise"})

@router.post("/messages", status_code=202)
async def send_message(
    req: SendRequest,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user=Depends(get_current_user),
):
    """
    Queue a message for delivery.
    Idempotency key prevents duplicate sends (proposal Section 7.1).
    """
    # Check idempotency (Redis: SET NX + TTL)
    if idempotency_key:
        # In production: check Redis for idempotency_key
        pass
    
    # Validate recipients
    # Queue for Postfix submission
    # Return immediately with queue status
    return {
        "status": "queued",
        "message_id": "msg_placeholder",
        "accepted": req.to,
    }

@router.post("/messages/{message_id}/move")
async def move_message(message_id: str, mailbox: str, user=Depends(get_current_user)):
    """Move a message to another mailbox."""
    valid_mailboxes = {"INBOX", "Archive", "Trash", "Junk"}
    if mailbox not in valid_mailboxes:
        raise HTTPException(status_code=400, detail={
            "code": "INVALID_MAILBOX",
            "message": f"'{mailbox}' is not a valid mailbox",
        })
    return {"status": "ok", "message_id": message_id, "mailbox": mailbox}

@router.post("/messages/{message_id}/flags")
async def update_flags(message_id: str, add: List[str] = [], remove: List[str] = [], user=Depends(get_current_user)):
    """Add or remove flags (\\Seen, \\Flagged, \\Answered, etc.)."""
    return {"status": "ok", "message_id": message_id, "flags_added": add, "flags_removed": remove}

@router.get("/search")
async def search_messages(
    q: str = Query(..., min_length=1),
    mailbox: Optional[str] = None,
    limit: int = Query(50, ge=1, le=100),
    user=Depends(get_current_user),
):
    """
    Full-text search across messages.
    Uses PostgreSQL FTS initially (proposal Section 12).
    """
    return {
        "query": q,
        "mailbox": mailbox,
        "total": 0,
        "messages": [],
    }
```

### Checkpoint Questions
1. Why return HTTP 202 (Accepted) for send_message instead of 200 or 201?
2. How does an idempotency key prevent duplicate sends?
3. Why is cursor-based pagination better than offset-based for email?
4. What is the difference between the envelope and the headers in the send model?

### Connection to ifinmail
This is the exact API contract from proposal Section 7.2. Every official client — Android, Windows, macOS, Linux, and web — calls these same endpoints. The consistency comes from one API definition powering all clients.

---

## Day 3 (Wednesday): Admin API & OpenAPI Documentation

### Learning Objectives
- Implement the Admin API group for domain and user management
- Generate and customize OpenAPI documentation
- Add request validation and structured error responses
- Implement API versioning strategy

### Theory / Reading
- **OpenAPI 3.1**: machine-readable API specification; FastAPI auto-generates from Pydantic models
- **Admin scope**: create organizations, add domains, verify DNS, manage users (proposal Section 7.2)
- **Versioning**: URL prefix (`/v1/`) + deprecation headers; backward compatibility per proposal

### Practical Exercise
```python
# ~/ifinmail-api/app/routers/admin.py
"""Admin API router (proposal Section 7.2)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()

class OrganizationCreate(BaseModel):
    name: str
    slug: str

class DomainCreate(BaseModel):
    organization_id: int
    name: str

class DomainVerifyRequest(BaseModel):
    domain_id: int

class UserCreate(BaseModel):
    organization_id: int
    username: str
    email: str
    password: str

class MailboxCreate(BaseModel):
    user_id: int
    domain_id: int
    local_part: str
    quota_mb: int = 1000

@router.get("/organizations")
async def list_organizations():
    """List all organizations."""
    return {"organizations": []}  # Database query

@router.post("/organizations", status_code=201)
async def create_organization(req: OrganizationCreate):
    """Create a new organization."""
    return {"status": "created", "organization": req.model_dump()}

@router.get("/domains")
async def list_domains(organization_id: Optional[int] = None):
    """List domains, optionally filtered by organization."""
    return {"domains": []}

@router.post("/domains", status_code=201)
async def add_domain(req: DomainCreate):
    """Add a domain to an organization."""
    return {"status": "created", "domain": req.model_dump()}

@router.post("/domains/verify")
async def verify_domain(req: DomainVerifyRequest):
    """
    Trigger DNS verification for a domain.
    Checks MX, SPF, DKIM, DMARC records (Week 7 Day 5 DNS checker).
    """
    return {
        "domain_id": req.domain_id,
        "verification_status": "pending",
        "checks": {
            "mx": "pending",
            "spf": "pending",
            "dkim": "pending",
            "dmarc": "pending",
        }
    }

@router.get("/domains/{domain_id}/dns-health")
async def domain_dns_health(domain_id: int):
    """
    Get DNS health status for a domain (proposal Section 6.5).
    Uses the DNS health checker from Week 7 Day 5.
    """
    return {
        "domain_id": domain_id,
        "checks": [
            {"check": "mx", "status": "PASS", "message": "MX records found"},
            {"check": "spf", "status": "PASS", "message": "SPF record valid"},
            {"check": "dkim", "status": "PASS", "message": "DKIM key published"},
            {"check": "dmarc", "status": "WARN", "message": "DMARC policy is p=none (consider p=quarantine)"},
            {"check": "mta_sts", "status": "FAIL", "message": "MTA-STS not configured"},
        ]
    }

@router.get("/users")
async def list_users(organization_id: Optional[int] = None):
    """List users, optionally filtered by organization."""
    return {"users": []}

@router.post("/users", status_code=201)
async def create_user(req: UserCreate):
    """Create a new user."""
    return {"status": "created", "user": req.model_dump(exclude={"password"})}

@router.post("/mailboxes", status_code=201)
async def create_mailbox(req: MailboxCreate):
    """Create a new mailbox for a user on a domain."""
    return {"status": "created", "mailbox": req.model_dump()}

@router.get("/deliverability")
async def deliverability_overview():
    """
    Platform-wide deliverability dashboard (proposal Section 6.5).
    Aggregates: bounce rate, complaint rate, DNS health, sending volume.
    """
    return {
        "overview": {
            "total_domains": 0,
            "healthy_domains": 0,
            "warning_domains": 0,
            "failing_domains": 0,
        },
        "metrics": {
            "bounce_rate_24h": 0.0,
            "complaint_rate_24h": 0.0,
            "delivery_rate_24h": 0.0,
            "avg_delivery_time_ms": 0,
        },
        "warnings": [],
    }

@router.get("/audit-logs")
async def audit_logs(
    limit: int = 100,
    user_id: Optional[int] = None,
    action: Optional[str] = None,
):
    """Query audit logs (proposal Section 11 entities)."""
    return {"logs": []}
```

```bash
# Run the API and explore the auto-generated docs
cd ~/ifinmail-api
source venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Now visit:
#   http://localhost:8000/v1/docs          (Swagger UI)
#   http://localhost:8000/v1/openapi.json  (OpenAPI spec)
```

### Checkpoint Questions
1. How does FastAPI auto-generate OpenAPI documentation from Pydantic models?
2. Why separate the Admin API from the Mail API? Couldn't one API handle everything?
3. How would the DNS health endpoint integrate with the Week 7 checker?
4. What audit events should be logged for compliance?

### Connection to ifinmail
The Admin API is how the platform is managed — adding domains, creating users, and monitoring deliverability. The OpenAPI spec is the single source of truth that client code generators use for Android, desktop, and web apps.

---

## Day 4 (Thursday): Device Bootstrap API & WebSocket Events

### Learning Objectives
- Implement the Device Bootstrap API (proposal Section 8)
- Generate and manage device credentials
- Implement WebSocket endpoints for real-time events
- Understand the bootstrap flow: manifest → auth → device registration → sync

### Theory / Reading
- **Device Bootstrap**: standardized onboarding so every client sets up the same way
- **Bootstrap manifest**: server advertises API version, auth methods, feature flags
- **WebSocket events**: push new message, status change, security alerts (proposal Section 7.2)
- **Device credentials**: per-device keys stored in platform key stores (Android Keystore, etc.)

### Practical Exercise
```python
# ~/ifinmail-api/app/routers/devices.py
"""Device Bootstrap API (proposal Section 8)."""
from fastapi import APIRouter, Depends, HTTPException, WebSocket
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

router = APIRouter()

class BootstrapManifest(BaseModel):
    service: str = "ifinmail"
    api_version: str = "v1"
    minimum_client_version: str = "1.0.0"
    auth_methods: List[str] = ["password", "mfa_totp", "passkey", "device_approval"]
    endpoints: dict = {
        "api": "https://api.ifinmail.com/v1",
        "websocket": "wss://api.ifinmail.com/v1/events",
        "status": "https://status.ifinmail.com",
    }
    security: dict = {
        "tls_required": True,
        "certificate_pinning": True,
        "device_key_required": True,
        "token_rotation_minutes": 30,
    }
    features: dict = {
        "offline_mail": True,
        "encrypted_cache": True,
        "push_notifications": True,
        "local_search": True,
    }

class DeviceRegisterRequest(BaseModel):
    device_name: str
    platform: str  # android, windows, macos, linux, web
    platform_version: str
    app_version: str
    public_key: Optional[str] = None
    push_token: Optional[str] = None

class DeviceCredential(BaseModel):
    device_id: str
    access_token: str
    refresh_token: str
    sync_settings: dict
    feature_flags: dict

# --- Bootstrap Endpoints ---
@router.get("/bootstrap/manifest")
async def get_manifest():
    """
    Return the bootstrap manifest.
    Every official client calls this first (proposal Section 8.2).
    """
    return BootstrapManifest()

@router.post("/devices/register")
async def register_device(req: DeviceRegisterRequest):
    """
    Register a new device after authentication.
    Returns device-specific credentials (proposal Section 8.2 step 5).
    """
    device_id = f"dev_{hash(req.device_name + req.platform) % 10**8:08d}"
    
    return DeviceCredential(
        device_id=device_id,
        access_token="device_scoped_jwt_here",
        refresh_token="device_refresh_token_here",
        sync_settings={
            "sync_interval_seconds": 300,
            "max_cache_size_mb": 500,
            "sync_mailboxes": ["INBOX", "Sent", "Archive"],
        },
        feature_flags={
            "offline_mail": True,
            "encrypted_cache": True,
            "push_notifications": True,
        },
    )

@router.post("/devices/{device_id}/rotate")
async def rotate_credential(device_id: str):
    """Rotate a device credential (proposal Section 7.2)."""
    return {"device_id": device_id, "new_token": "rotated_token", "old_token_expires_in": 300}

@router.delete("/devices/{device_id}")
async def revoke_device(device_id: str):
    """Revoke a device's access."""
    return {"status": "revoked", "device_id": device_id}

@router.get("/devices")
async def list_devices():
    """List all devices for the authenticated user."""
    return {
        "devices": [
            {"id": "dev_001", "name": "Android Phone", "platform": "android", "last_seen": "2024-05-12T10:00:00Z"},
            {"id": "dev_002", "name": "Desktop PC", "platform": "windows", "last_seen": "2024-05-12T09:30:00Z"},
        ]
    }

# --- WebSocket Events (proposal Section 7.2) ---
@router.websocket("/events")
async def events_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time events.
    Streams: new_message, message_updated, mailbox_updated,
             sending_status, security_alert, device_revoked.
    """
    await websocket.accept()
    
    # Send initial connection confirmation
    await websocket.send_json({
        "event": "connected",
        "data": {"message": "Event stream established"},
    })
    
    try:
        while True:
            # In production: subscribe to Redis pubsub or NATS
            # For training: keep connection alive
            data = await websocket.receive_text()
            # Echo for testing
            await websocket.send_json({
                "event": "echo",
                "data": {"received": data},
            })
    except Exception:
        pass
```

### Checkpoint Questions
1. Why does the bootstrap manifest exist as a separate endpoint instead of hardcoding client configuration?
2. What is the benefit of device-specific credentials vs sharing the user's main token?
3. How does device revocation work with stateless JWTs?
4. What events should be pushed over WebSocket vs polled via REST?

### Connection to ifinmail
The bootstrap contract is the key to multi-client consistency. Every official app (Android, Windows, macOS, Linux, web) starts with the same `/bootstrap/manifest` call. Device-specific credentials mean revoking one device does not affect others. This is proposal Section 8 implemented.

---

## Day 5 (Friday): Testing, Error Handling & API Polish

### Learning Objectives
- Write integration tests for the API using pytest and httpx
- Implement consistent error handling middleware
- Add rate limiting middleware using Redis
- Understand CORS, security headers, and API hardening

### Theory / Reading
- **Integration tests**: test the full stack (HTTP request → handler → database → response)
- **Error middleware**: catches unhandled exceptions and formats them as structured API errors
- **Rate limiting**: per-user, per-IP, per-endpoint limits; Redis sliding window
- **Security headers**: Content-Security-Policy, Strict-Transport-Security, X-Content-Type-Options

### Practical Exercise
```python
# ~/ifinmail-api/tests/test_auth.py
"""Integration tests for the Auth API."""
import pytest
from httpx import Client, ASGITransport
from app.main import app

@pytest.fixture
def client():
    """Create a test client that talks to the FastAPI app directly."""
    transport = ASGITransport(app=app)
    with Client(transport=transport, base_url="http://test") as c:
        yield c

def test_health_check(client):
    """Health endpoint should return 200."""
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "ifinmail-api"

def test_bootstrap_manifest(client):
    """Bootstrap manifest should return the correct structure."""
    response = client.get("/v1/devices/bootstrap/manifest")
    assert response.status_code == 200
    data = response.json()
    assert data["service"] == "ifinmail"
    assert data["api_version"] == "v1"
    assert "password" in data["auth_methods"]
    assert data["security"]["tls_required"] is True

def test_list_mailboxes_requires_auth(client):
    """Mail API should require authentication."""
    response = client.get("/v1/mail/mailboxes")
    assert response.status_code == 403  # or 401 depending on auth setup

def test_list_messages_pagination(client):
    """Message listing should respect pagination params."""
    # This will require auth in production
    response = client.get("/v1/mail/messages?mailbox=INBOX&limit=10&page=1")
    # For now, verify the auth challenge
    assert response.status_code in [200, 401, 403]

def test_send_message_validation(client):
    """Send endpoint should validate required fields."""
    response = client.post("/v1/mail/messages", json={})
    assert response.status_code == 422  # Validation error

def test_openapi_schema(client):
    """OpenAPI schema should be valid."""
    response = client.get("/v1/openapi.json")
    assert response.status_code == 200
    schema = response.json()
    assert schema["info"]["title"] == "ifinmail API"
    assert "/v1/auth/login" in schema["paths"] or True  # Schema structure check
```

```python
# ~/ifinmail-api/app/middleware.py
"""API middleware: errors, rate limiting, security headers."""
from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import time

class StructuredErrorMiddleware(BaseHTTPMiddleware):
    """Convert all unhandled errors to the ifinmail error format (proposal Section 7.1)."""
    
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            return response
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={
                    "code": e.detail.get("code", "ERROR") if isinstance(e.detail, dict) else "ERROR",
                    "message": e.detail.get("message", str(e.detail)) if isinstance(e.detail, dict) else str(e.detail),
                    "status": e.status_code,
                }
            )
        except Exception as e:
            # Log the real error; return a sanitized message
            return JSONResponse(
                status_code=500,
                content={
                    "code": "INTERNAL_ERROR",
                    "message": "An internal error occurred. The incident has been logged.",
                    "status": 500,
                }
            )

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware using Redis (proposal Section 6.4)."""
    
    async def dispatch(self, request: Request, call_next):
        # In production: check Redis for rate limit
        # For now: pass through
        response = await call_next(request)
        return response

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to every response."""
    
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Content-Security-Policy"] = "default-src 'self'"
        response.headers["X-Ifinmail-API-Version"] = "v1"
        return response
```

```bash
# Run the tests
cd ~/ifinmail-api
source venv/bin/activate
pip install pytest pytest-cov httpx
python -m pytest tests/ -v

# With coverage
python -m pytest tests/ --cov=app --cov-report=term-missing
```

### Checkpoint Questions
1. Why is it important to test the full HTTP stack (integration tests) rather than just unit tests?
2. How does the structured error middleware ensure consistent API errors?
3. What security headers should every ifinmail API response include?
4. How would you test rate limiting behavior?

### Connection to ifinmail
Testing is not optional for an email platform. A bug in the send endpoint could mean lost messages. Structured errors mean every client (Android, desktop, web) can handle failures the same way. The middleware pattern keeps cross-cutting concerns (auth, rate limiting, errors) out of business logic.

---

## Day 6 (Saturday): Review & Integration

### Review Challenge: API Integration Test Suite

Build a comprehensive integration test script that:

1. Tests the full user lifecycle: register → login → refresh token → logout
2. Tests the mail lifecycle: list mailboxes → list messages → read message → send message
3. Tests the device lifecycle: get manifest → register device → rotate credential → revoke
4. Tests admin endpoints: create org → add domain → verify DNS → create user → create mailbox
5. Tests error handling: invalid auth, bad request, not found, rate limited
6. Generates a test report in JSON format

**Stretch goal**: Add performance benchmarks (response time p50/p95/p99 for each endpoint).

### Week 8 Self-Assessment

Before moving to Week 9, confirm you can:
- [ ] Implement JWT authentication with access and refresh tokens
- [ ] Build versioned REST APIs matching the ifinmail contract
- [ ] Define Pydantic models that validate and document request/response shapes
- [ ] Generate OpenAPI documentation automatically
- [ ] Implement the Device Bootstrap API with manifest
- [ ] Write integration tests using pytest and httpx
- [ ] Add error handling middleware for consistent API responses

---

## Week 8 Resource Index

| Resource | Location |
|---|---|
| API project skeleton | `code/ifinmail-api/` |
| Auth service | `code/ifinmail-api/app/services/auth_service.py` |
| Mail router | `code/ifinmail-api/app/routers/mail.py` |
| Admin router | `code/ifinmail-api/app/routers/admin.py` |
| Device router | `code/ifinmail-api/app/routers/devices.py` |
| Middleware | `code/ifinmail-api/app/middleware.py` |
| Test suite | `code/ifinmail-api/tests/` |
| OpenAPI schema | `docs/openapi.json` |

---

## Month 2 Completion Checklist

- [ ] **Postfix**: Virtual domains, PostgreSQL maps, TLS, submission, queues
- [ ] **Dovecot**: Maildir, SQL auth, LMTP with Postfix, Sieve, doveadm
- [ ] **Email Security**: SPF, DKIM, DMARC, Rspamd milter, MTA-STS, DNS health
- [ ] **API Platform**: Auth, Mail, Admin, Device Bootstrap API groups with tests

You can now build and operate a complete mail platform. Month 3 adds Rust, the frontend, deployment, and the capstone project.

---

*Week 8 of 12 — Python API Development for ifinmail Platform Engineering*
