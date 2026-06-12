import asyncio

from fastapi import WebSocket

_connections: dict[int, list[WebSocket]] = {}


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
