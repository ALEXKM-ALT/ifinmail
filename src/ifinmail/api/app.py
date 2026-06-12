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
from ifinmail.api.organizations import router as organizations_router
from ifinmail.api.payments import router as payments_router
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
    if "mailboxes" in tables:
        mb_cols = [c["name"] for c in inspector.get_columns("mailboxes")]
        if "plan" not in mb_cols:
            with engine.connect() as conn:
                conn.execute(text("ALTER TABLE mailboxes ADD COLUMN plan VARCHAR(32)"))
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
    if "organization_invites" not in tables:
        with engine.connect() as conn:
            conn.execute(text("""
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
            """))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_organization_invites_token ON organization_invites(token)"))
            conn.commit()
    if "org_contacts" not in tables:
        with engine.connect() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS org_contacts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    organization_id INTEGER NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
                    email VARCHAR(255) NOT NULL,
                    name VARCHAR(255),
                    created_by INTEGER REFERENCES users(id) ON DELETE SET NULL,
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """))
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
    if "imap_imports" not in tables:
        with engine.connect() as conn:
            conn.execute(text("""
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
            """))
            conn.commit()
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
    description="A secure, API-first email hosting platform. Provides email management, admin controls, billing, and real-time notifications.",
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
app.include_router(mail_router)
app.include_router(mail_settings_router)
app.include_router(attachments_router)
app.include_router(webhooks_router)
app.include_router(sandbox_router)
app.include_router(intelligence_router)
app.include_router(organizations_router)
app.include_router(sso_router)
app.include_router(ai_assistant_router)
app.include_router(payments_router)
app.include_router(export_reports_router)
app.include_router(mail_scheduler_router)
app.include_router(filter_rules_router)
app.include_router(imap_import_router)

# API versioning - expose under /v1 prefix too
for router in [
    auth_router,
    admin_router,
    analytics_router,
    api_keys_router,
    billing_router,
    contacts_router,
    domains_router,
    mail_router,
    templates_router,
    verify_router,
    two_factor_router,
    spam_router,
    mail_settings_router,
    attachments_router,
    webhooks_router,
    sandbox_router,
    intelligence_router,
    organizations_router,
    sso_router,
    ai_assistant_router,
    payments_router,
    export_reports_router,
    mail_scheduler_router,
    filter_rules_router,
    imap_import_router,
    aliases_router,
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
    }


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/sso-callback")
    async def sso_callback_page():
        return FileResponse(str(STATIC_DIR / "index.html"))

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(str(STATIC_DIR / "index.html"))
