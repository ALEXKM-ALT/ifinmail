import asyncio
import threading

from fastapi import WebSocket

_connections: dict[int, list[WebSocket]] = {}
_PUSH_EVENTS = {"new_mail", "mail.sent", "autoreply.sent"}


async def connect(user_id: int, ws: WebSocket) -> None:
    await ws.accept()
    _connections.setdefault(user_id, []).append(ws)


def disconnect(user_id: int, ws: WebSocket) -> None:
    conns = _connections.get(user_id, [])
    if ws in conns:
        conns.remove(ws)


async def notify_user(user_id: int, event: str, data: dict | None = None) -> None:
    conns = _connections.get(user_id, [])
    for ws in conns[:]:
        try:
            await ws.send_json({"event": event, "data": data or {}})
        except Exception:
            conns.remove(ws)


def fire_notification(user_id: int, event: str, data: dict | None = None) -> None:
    """Fire-and-forget async notification from a sync context."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(notify_user(user_id, event, data))
    except RuntimeError:
        try:
            asyncio.run(notify_user(user_id, event, data))
        except Exception:
            pass
    if event in _PUSH_EVENTS:
        threading.Thread(target=_push_notify, args=(user_id, event, data), daemon=True).start()


def _push_notify(user_id: int, event: str, data: dict | None = None) -> None:
    try:
        from ifinmail.api.push import notify_user as push_notify

        push_notify(user_id, event, data)
    except Exception:
        import logging

        logging.getLogger("ifinmail.ws_manager").exception("push_notify failed")
