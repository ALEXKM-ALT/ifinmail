import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from ifinmail.api.admin import router as admin_router
from ifinmail.api.attachments import router as attachments_router
from ifinmail.api.auth import decode_token
from ifinmail.api.auth import router as auth_router
from ifinmail.api.billing import router as billing_router
from ifinmail.api.config import settings
from ifinmail.api.database import engine
from ifinmail.api.deps import _get_redis, get_redis
from ifinmail.api.domains import router as domains_router
from ifinmail.api.logconf import RequestLogMiddleware, setup_logging
from ifinmail.api.mail import router as mail_router
from ifinmail.api.mail_settings import router as mail_settings_router
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
    msg_cols = [c["name"] for c in inspector.get_columns("messages")]
    if "previous_folder" not in msg_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE messages ADD COLUMN previous_folder VARCHAR(32)"))
            conn.commit()
    if "labels" not in msg_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE messages ADD COLUMN labels TEXT"))
            conn.commit()
    mb_cols = [c["name"] for c in inspector.get_columns("mailboxes")]
    if "plan" not in mb_cols:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE mailboxes ADD COLUMN plan VARCHAR(32)"))
            conn.commit()
    yield
    engine.dispose()
    r = _get_redis()
    if r is not None:
        r.close()


app = FastAPI(
    title="ifinmail App API",
    version="0.1.0",
    description="A secure, API-first email platform",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLogMiddleware)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(billing_router)
app.include_router(domains_router)
app.include_router(mail_router)
app.include_router(mail_settings_router)
app.include_router(attachments_router)


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

    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        return FileResponse(str(STATIC_DIR / "index.html"))
