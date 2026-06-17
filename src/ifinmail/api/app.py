import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from ifinmail.api.admin import router as admin_router
from ifinmail.api.ai_assistant import router as ai_assistant_router
from ifinmail.api.aliases import router as aliases_router
from ifinmail.api.analytics import router as analytics_router
from ifinmail.api.api_keys import router as api_keys_router
from ifinmail.api.attachments import router as attachments_router
from ifinmail.api.auth import decode_token
from ifinmail.api.auth import router as auth_router
from ifinmail.api.billing import router as billing_router
from ifinmail.api.config import settings
from ifinmail.api.contacts import router as contacts_router
from ifinmail.api.database import engine
from ifinmail.api.deps import _get_redis, get_redis
from ifinmail.api.domains import router as domains_router
from ifinmail.api.export_reports import router as export_reports_router
from ifinmail.api.filter_rules import router as filter_rules_router
from ifinmail.api.imap_import import router as imap_import_router
from ifinmail.api.intelligence import router as intelligence_router
from ifinmail.api.limiter import InMemoryRateLimitMiddleware
from ifinmail.api.logconf import RequestLogMiddleware, setup_logging
from ifinmail.api.mail import router as mail_router
from ifinmail.api.mail_scheduler import router as mail_scheduler_router
from ifinmail.api.mail_settings import router as mail_settings_router
from ifinmail.api.maintenance import MaintenanceMiddleware
from ifinmail.api.maintenance import is_enabled as maint_is_enabled
from ifinmail.api.metrics import MetricsMiddleware
from ifinmail.api.metrics import router as metrics_router
from ifinmail.api.organizations import router as organizations_router
from ifinmail.api.payments import router as payments_router
from ifinmail.api.push_routes import router as push_router
from ifinmail.api.sandbox import router as sandbox_router
from ifinmail.api.scheduler import start_scheduler, stop_scheduler
from ifinmail.api.spam import router as spam_router
from ifinmail.api.sso import router as sso_router
from ifinmail.api.templates import router as templates_router
from ifinmail.api.two_factor import router as two_factor_router
from ifinmail.api.verify import router as verify_router
from ifinmail.api.webhooks import router as webhooks_router
from ifinmail.api.ws_manager import connect as ws_connect
from ifinmail.api.ws_manager import disconnect as ws_disconnect
from ifinmail.db.models import Base

STATIC_DIR = Path(__file__).resolve().parents[2] / "ifinmail" / "web" / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator:
    settings.validate()
    setup_logging(os.environ.get("IFINMAIL_LOG_LEVEL", "INFO"))
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import inspect as sa_inspect

    inspector = sa_inspect(engine)
    tables = inspector.get_table_names()
    if "messages" in tables:
        msg_cols = [c["name"] for c in inspector.get_columns("messages")]
        if "previous_folder" not in msg_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN previous_folder VARCHAR(32)"))
                conn.commit()
        if "labels" not in msg_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN labels TEXT"))
                conn.commit()
        if "undo_deadline" not in msg_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN undo_deadline TIMESTAMP"))
                conn.commit()
        if "snoozed_until" not in msg_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN snoozed_until TIMESTAMP"))
                conn.commit()
        if "priority_score" not in msg_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN priority_score FLOAT DEFAULT 0.0"))
                conn.commit()
        if "read_receipt_requested" not in msg_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE messages ADD COLUMN read_receipt_requested INTEGER DEFAULT 0 NOT NULL"))
                conn.commit()
    if "mailboxes" in tables:
        mb_cols = [c["name"] for c in inspector.get_columns("mailboxes")]
        if "plan" not in mb_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE mailboxes ADD COLUMN plan VARCHAR(32)"))
                conn.commit()
        if "signature" not in mb_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE mailboxes ADD COLUMN signature TEXT"))
                conn.commit()
        if "signature_enabled" not in mb_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE mailboxes ADD COLUMN signature_enabled INTEGER DEFAULT 0 NOT NULL"))
                conn.commit()
    if "users" in tables:
        user_cols = [c["name"] for c in inspector.get_columns("users")]
        if "first_name" not in user_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE users ADD COLUMN first_name VARCHAR(255)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN last_name VARCHAR(255)"))
                conn.execute(text("ALTER TABLE users ADD COLUMN last_login TIMESTAMP"))
                conn.execute(text("ALTER TABLE users ADD COLUMN storage_limit BIGINT DEFAULT 0 NOT NULL"))
                conn.execute(text("ALTER TABLE users ADD COLUMN quota_warning_sent INTEGER DEFAULT 0 NOT NULL"))
                conn.commit()
    if "organization_members" in tables:
        om_cols = [c["name"] for c in inspector.get_columns("organization_members")]
        if "first_name" not in om_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE organization_members ADD COLUMN first_name VARCHAR(100)"))
                conn.execute(text("ALTER TABLE organization_members ADD COLUMN last_name VARCHAR(100)"))
                conn.commit()
    if "organization_invites" in tables:
        oi_cols = [c["name"] for c in inspector.get_columns("organization_invites")]
        if "first_name" not in oi_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE organization_invites ADD COLUMN first_name VARCHAR(100)"))
                conn.execute(text("ALTER TABLE organization_invites ADD COLUMN last_name VARCHAR(100)"))
                conn.commit()
    if "organization_invites" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS organization_invites (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    email VARCHAR(255) NOT NULL,
                    token VARCHAR(64) NOT NULL UNIQUE,
                    role VARCHAR(32) NOT NULL DEFAULT 'member',
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    accepted INTEGER NOT NULL DEFAULT 0
                )
            """)
            )
            conn.execute(
                text("CREATE INDEX IF NOT EXISTS ix_organization_invites_token ON organization_invites(token)")
            )
            conn.commit()
    if "org_contacts" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS org_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    email VARCHAR(255) NOT NULL,
                    name VARCHAR(255),
                    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.commit()
    if "organizations" in tables:
        org_cols = [c["name"] for c in inspector.get_columns("organizations")]
        if "email" not in org_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE organizations ADD COLUMN email VARCHAR(255)"))
                conn.commit()
    if "domains" in tables:
        dom_cols = [c["name"] for c in inspector.get_columns("domains")]
        if "dkim_private_key" not in dom_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE domains ADD COLUMN dkim_private_key TEXT"))
                conn.execute(text("ALTER TABLE domains ADD COLUMN dkim_selector VARCHAR(64)"))
                conn.commit()
    if "spam_reports" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS spam_reports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id INTEGER NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    report_type VARCHAR(8) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_spam_reports_message ON spam_reports(message_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_spam_reports_user ON spam_reports(user_id)"))
            conn.commit()
    if "contact_groups" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS contact_groups (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    name VARCHAR(128) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_contact_groups_user ON contact_groups(user_id)"))
            conn.commit()
    if "contact_group_members" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS contact_group_members (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    group_id INTEGER NOT NULL REFERENCES contact_groups(id) ON DELETE CASCADE,
                    contact_id INTEGER NOT NULL REFERENCES contacts(id) ON DELETE CASCADE,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(group_id, contact_id)
                )
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cgm_group ON contact_group_members(group_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_cgm_contact ON contact_group_members(contact_id)"))
            conn.commit()
    if "two_factor" in tables:
        tf_cols = [c["name"] for c in inspector.get_columns("two_factor")]
        if "recovery_codes" not in tf_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE two_factor ADD COLUMN recovery_codes TEXT"))
                conn.commit()
    if "scheduled_messages" in tables:
        sm_cols = [c["name"] for c in inspector.get_columns("scheduled_messages")]
        if "repeat_interval" not in sm_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE scheduled_messages ADD COLUMN repeat_interval VARCHAR(16)"))
                conn.execute(text("ALTER TABLE scheduled_messages ADD COLUMN repeat_until TIMESTAMP"))
                conn.commit()
    if "vacation_responders" in tables:
        vr_cols = [c["name"] for c in inspector.get_columns("vacation_responders")]
        if "start_date" not in vr_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE vacation_responders ADD COLUMN start_date TIMESTAMP"))
                conn.execute(text("ALTER TABLE vacation_responders ADD COLUMN end_date TIMESTAMP"))
                conn.execute(
                    text("ALTER TABLE vacation_responders ADD COLUMN only_contacts INTEGER DEFAULT 0 NOT NULL")
                )
                conn.commit()
    if "user_sessions" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS user_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    token_hash VARCHAR(128) NOT NULL UNIQUE,
                    ip_address VARCHAR(45),
                    user_agent VARCHAR(512),
                    device_name VARCHAR(128),
                    last_used_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_user_sessions_user ON user_sessions(user_id)"))
            conn.commit()
    if "imap_imports" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS imap_imports (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
                    host VARCHAR(255) NOT NULL DEFAULT 'imap.gmail.com',
                    port INTEGER NOT NULL DEFAULT 993,
                    username VARCHAR(255) NOT NULL,
                    password TEXT NOT NULL,
                    use_ssl INTEGER NOT NULL DEFAULT 1,
                    folder VARCHAR(64) NOT NULL DEFAULT 'INBOX',
                    last_run_at TIMESTAMP,
                    last_run_status VARCHAR(32),
                    last_run_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.commit()
    if "push_subscriptions" not in tables:
        with engine.connect() as conn:
            conn.execute(
                text("""
                CREATE TABLE IF NOT EXISTS push_subscriptions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    endpoint TEXT NOT NULL,
                    p256dh_key VARCHAR(255) NOT NULL,
                    auth_key VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_push_subscriptions_user ON push_subscriptions(user_id)"))
            conn.commit()
    from ifinmail.api.vapid import get_vapid_public_key_b64

    try:
        get_vapid_public_key_b64()
    except Exception:
        pass
    if settings.smtp_host:
        await start_scheduler()
    yield
    await stop_scheduler()
    engine.dispose()
    r = _get_redis()
    if r is not None:
        r.close()


app = FastAPI(
    title="ifinmail API",
    version="2.0.0",
    description=(
        "A secure, API-first email hosting platform. "
        "Provides email management, admin controls, billing, and real-time notifications."
    ),
    lifespan=lifespan,
    contact={
        "name": "ifinmail Support",
        "email": "support@ifinmail.com",
    },
    license_info={
        "name": "MIT",
    },
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)
app.add_middleware(InMemoryRateLimitMiddleware)
app.add_middleware(MetricsMiddleware)


class SecurityHeadersMiddleware:
    """Add security-related HTTP headers to every response."""

    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.jsdelivr.net https://fastapi.tiangolo.com; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com; "
        "img-src 'self' data: blob: https://fastapi.tiangolo.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' ws: wss: https://cdn.jsdelivr.net; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
    )

    HEADERS = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains; preload",
        "Referrer-Policy": "strict-origin-when-cross-origin",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=(), interest-cohort=()",
    }

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                headers = message.get("headers", [])
                header_names = {h[0] for h in headers}
                for name, value in self.HEADERS.items():
                    name_bytes = name.lower().encode("latin-1")
                    if name_bytes not in header_names:
                        headers.append((name_bytes, value.encode("latin-1")))
                csp_name = b"content-security-policy"
                if csp_name not in header_names:
                    headers.append((csp_name, self.CSP.encode("latin-1")))
                message["headers"] = headers
            await send(message)

        await self.app(scope, receive, send_wrapper)


app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(MaintenanceMiddleware)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(aliases_router)
app.include_router(analytics_router)
app.include_router(api_keys_router)
app.include_router(billing_router)
app.include_router(contacts_router)
app.include_router(domains_router)
app.include_router(templates_router)
app.include_router(verify_router)
app.include_router(two_factor_router)
app.include_router(spam_router)
app.include_router(mail_settings_router)
app.include_router(mail_scheduler_router)
app.include_router(filter_rules_router)
app.include_router(imap_import_router)
app.include_router(attachments_router)
app.include_router(mail_router)
app.include_router(webhooks_router)
app.include_router(sandbox_router)
app.include_router(intelligence_router)
app.include_router(organizations_router)
app.include_router(sso_router)
app.include_router(ai_assistant_router)
app.include_router(payments_router)
app.include_router(export_reports_router)
app.include_router(push_router)
app.include_router(metrics_router)

# API versioning - expose under /v1 prefix too
for router in [
    auth_router,
    admin_router,
    analytics_router,
    api_keys_router,
    billing_router,
    contacts_router,
    domains_router,
    mail_settings_router,
    mail_scheduler_router,
    filter_rules_router,
    imap_import_router,
    attachments_router,
    mail_router,
    templates_router,
    verify_router,
    two_factor_router,
    spam_router,
    webhooks_router,
    sandbox_router,
    intelligence_router,
    organizations_router,
    sso_router,
    ai_assistant_router,
    payments_router,
    export_reports_router,
    aliases_router,
    push_router,
]:
    app.include_router(router, prefix="/v1")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title="ifinmail API",
        version="2.0.0",
        description="A secure, API-first email hosting platform.",
        routes=app.routes,
    )
    schema["servers"] = [
        {"url": "https://api.ifinmail.com/v2", "description": "Production"},
        {"url": "http://localhost:8000", "description": "Development"},
    ]
    schema["components"]["securitySchemes"] = {
        "bearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
        }
    }
    schema["security"] = [{"bearerAuth": []}]
    schema["x-versions"] = {
        "versions": ["v1", "v2"],
        "current": "v2",
        "deprecated": ["v1"],
        "sunset_dates": {"v1": "2027-01-01"},
    }
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket, token: str = Query(...)):
    user_id = decode_token(token)
    if not user_id:
        await ws.close(code=4001)
        return
    await ws_connect(user_id, ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_disconnect(user_id, ws)
    except Exception:
        ws_disconnect(user_id, ws)


@app.get("/health")
async def health():
    db_ok = False
    redis_ok = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            db_ok = True
    except Exception:
        pass

    try:
        r = _get_redis()
        if r is None:
            r = get_redis()
        r.ping()
        redis_ok = True
    except Exception:
        pass

    ok = db_ok and redis_ok
    return {
        "status": "ok" if ok else "degraded",
        "database": "up" if db_ok else "down",
        "redis": "up" if redis_ok else "down",
        "maintenance_mode": maint_is_enabled(),
    }


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/sw.js")
    async def service_worker():
        from fastapi.responses import Response

        return Response(
            content=(STATIC_DIR / "sw.js").read_bytes(),
            media_type="application/javascript",
        )

    @app.get("/sso-callback")
    async def sso_callback_page():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(str(STATIC_DIR / "index.html"))
