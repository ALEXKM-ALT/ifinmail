import threading
import time
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Request, Response
from fastapi.responses import PlainTextResponse
from sqlalchemy import func as sa_func
from sqlalchemy.orm import Session

from ifinmail.api.database import SessionLocal
from ifinmail.api.deps import get_redis
from ifinmail.db.models import Domain, Mailbox, Message, User, UserSession

router = APIRouter(tags=["metrics"])

# ── Manual Prometheus metric collectors (no prometheus_client dependency) ──

_lock = threading.Lock()


class Counter:
    __slots__ = ("_name", "_help", "_labels", "_value")

    def __init__(self, name: str, help_text: str, labels: tuple[str, ...] = ()) -> None:
        self._name = name
        self._help = help_text
        self._labels = labels
        self._value: dict[tuple[str, ...], float] = defaultdict(float)

    def inc(self, values: tuple[str, ...] = (), count: float = 1) -> None:
        with _lock:
            self._value[values] += count

    def collect(self) -> str:
        parts = [f"# HELP {self._name} {self._help}", f"# TYPE {self._name} counter"]
        with _lock:
            for label_vals, val in sorted(self._value.items()):
                if label_vals:
                    labels = ",".join(f'{k}="{v}"' for k, v in zip(self._labels, label_vals, strict=False))
                    parts.append(f"{self._name}{{{labels}}} {val}")
                else:
                    parts.append(f"{self._name} {val}")
        return "\n".join(parts) + "\n"


class Gauge:
    __slots__ = ("_name", "_help", "_labels", "_value")

    def __init__(self, name: str, help_text: str, labels: tuple[str, ...] = ()) -> None:
        self._name = name
        self._help = help_text
        self._labels = labels
        self._value: dict[tuple[str, ...], float] = defaultdict(float)

    def set(self, val: float, values: tuple[str, ...] = ()) -> None:
        with _lock:
            self._value[values] = val

    def collect(self) -> str:
        parts = [f"# HELP {self._name} {self._help}", f"# TYPE {self._name} gauge"]
        with _lock:
            for label_vals, val in sorted(self._value.items()):
                if label_vals:
                    labels = ",".join(f'{k}="{v}"' for k, v in zip(self._labels, label_vals, strict=False))
                    parts.append(f"{self._name}{{{labels}}} {val}")
                else:
                    parts.append(f"{self._name} {val}")
        return "\n".join(parts) + "\n"


class Histogram:
    __slots__ = ("_name", "_help", "_buckets", "_counts", "_sum", "_lock")

    def __init__(self, name: str, help_text: str, buckets: tuple[float, ...] = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)) -> None:
        self._name = name
        self._help = help_text
        self._buckets = buckets
        self._counts: dict[tuple[str, ...], list[int]] = defaultdict(lambda: [0] * (len(buckets) + 1))
        self._sum: dict[tuple[str, ...], float] = defaultdict(float)
        self._lock = threading.Lock()

    def observe(self, val: float, values: tuple[str, ...] = ()) -> None:
        with self._lock:
            self._sum[values] += val
            for i, b in enumerate(self._buckets):
                if val <= b:
                    self._counts[values][i] += 1
            self._counts[values][-1] += 1

    def collect(self) -> str:
        parts = [
            f"# HELP {self._name} {self._help}",
            f"# TYPE {self._name} histogram",
        ]
        suffix = self._name.replace("_seconds", "")
        with self._lock:
            for label_vals in sorted(set(list(self._counts.keys()) + list(self._sum.keys()))):
                labels_str = ""
                if label_vals:
                    labels_str = ",".join(f'{k}="{v}"' for k, v in zip(("method", "path", "status"), label_vals, strict=False))
                le = 0.0
                for i, b in enumerate(self._buckets):
                    le += self._counts[label_vals][i]
                    parts.append(f"{self._name}_bucket{{{labels_str},le=\"{b}\"}} {le}")
                total = self._counts[label_vals][-1]
                parts.append(f"{self._name}_bucket{{{labels_str},le=\"+Inf\"}} {total}")
                parts.append(f"{self._name}_count{{{labels_str}}} {total}")
                parts.append(f"{self._name}_sum{{{labels_str}}} {self._sum[label_vals]}")
        return "\n".join(parts) + "\n"


# ── Pre-defined metrics ──

http_requests_total = Counter(
    "ifinmail_http_requests_total",
    "Total HTTP requests by method, path, and status",
    ("method", "path", "status"),
)

http_request_duration_seconds = Histogram(
    "ifinmail_http_request_duration_seconds",
    "HTTP request duration in seconds",
)

emails_sent_total = Counter(
    "ifinmail_emails_sent_total",
    "Total emails sent by status",
    ("status",),
)

failed_logins_total = Counter(
    "ifinmail_failed_logins_total",
    "Total failed login attempts",
)

active_sessions_gauge = Gauge(
    "ifinmail_active_sessions",
    "Number of active user sessions",
)


class MetricsMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Callable, send: Callable) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = scope.get("method", "UNKNOWN")
        path = scope.get("path", "/")
        start = time.monotonic()
        status = [200]

        async def _send(message: dict) -> None:
            if message.get("type") == "http.response.start":
                status[0] = message.get("status", 200)
            await send(message)

        try:
            await self.app(scope, receive, _send)
        except Exception:
            status[0] = 500
            raise
        finally:
            duration = time.monotonic() - start
            http_requests_total.inc((method, path, str(status[0])))
            http_request_duration_seconds.observe(duration, (method, path, str(status[0])))


@router.get("/metrics")
async def metrics():
    db = SessionLocal()
    try:
        user_count = db.query(sa_func.count(User.id)).scalar() or 0
        domain_count = db.query(sa_func.count(Domain.id)).scalar() or 0
        mailbox_count = db.query(sa_func.count(Mailbox.id)).scalar() or 0
        message_count = db.query(sa_func.count(Message.id)).scalar() or 0
        session_count = db.query(sa_func.count(UserSession.id)).scalar() or 0
    finally:
        db.close()

    active_sessions_gauge.set(float(session_count))

    db_ok = 1
    redis_ok = 1
    try:
        r = get_redis()
        r.ping()
    except Exception:
        redis_ok = 0

    lines = [
        "# HELP ifinmail_users_total Total registered users",
        "# TYPE ifinmail_users_total gauge",
        f"ifinmail_users_total {user_count}",
        "",
        "# HELP ifinmail_domains_total Total domains",
        "# TYPE ifinmail_domains_total gauge",
        f"ifinmail_domains_total {domain_count}",
        "",
        "# HELP ifinmail_mailboxes_total Total mailboxes",
        "# TYPE ifinmail_mailboxes_total gauge",
        f"ifinmail_mailboxes_total {mailbox_count}",
        "",
        "# HELP ifinmail_messages_total Total stored messages",
        "# TYPE ifinmail_messages_total gauge",
        f"ifinmail_messages_total {message_count}",
        "",
        "# HELP ifinmail_up Database and Redis health (1=up, 0=down)",
        "# TYPE ifinmail_up gauge",
        f"ifinmail_up{{component=\"database\"}} {db_ok}",
        f"ifinmail_up{{component=\"redis\"}} {redis_ok}",
        "",
        http_requests_total.collect().rstrip(),
        http_request_duration_seconds.collect().rstrip(),
        emails_sent_total.collect().rstrip(),
        failed_logins_total.collect().rstrip(),
        active_sessions_gauge.collect().rstrip(),
    ]
    return PlainTextResponse(
        "\n".join(lines),
        headers={"Content-Type": "text/plain; version=0.0.4"},
    )
