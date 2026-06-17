import os
import time
from collections.abc import Awaitable, Callable

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from redis import Redis
from starlette.middleware.base import BaseHTTPMiddleware

from ifinmail.api.deps import get_redis


def rate_limit(times: int, window: int, key_prefix: str = "rl", use_user: bool = False):
    def _dependency(request: Request, redis: Redis = Depends(get_redis)) -> None:
        try:
            if use_user:
                auth = request.headers.get("Authorization", "")
                if auth.startswith("Bearer "):
                    from jose import jwt

                    from ifinmail.api.config import settings

                    try:
                        payload = jwt.decode(auth[7:], settings.secret_key, algorithms=[settings.algorithm])
                        identifier = f"user:{payload.get('sub', 'unknown')}"
                    except Exception:
                        identifier = request.client.host if request.client else "unknown"
                else:
                    identifier = request.client.host if request.client else "unknown"
            else:
                identifier = request.client.host if request.client else "unknown"

            key = f"{key_prefix}:{identifier}"
            now = time.time()
            window_start = now - window

            pipe = redis.pipeline()
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(now): now})
            pipe.expire(key, window)
            results = pipe.execute()
            count = results[1]

            if count >= times:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                )
        except HTTPException:
            raise
        except Exception:
            pass

    return _dependency


# IP-based rate limiters
strict = Depends(rate_limit(10, 60, "rl:strict"))
default = Depends(rate_limit(60, 60, "rl:default"))

# User-based rate limiters (uses JWT user_id)
user_strict = Depends(rate_limit(30, 60, "rl:user:strict", use_user=True))
user_moderate = Depends(rate_limit(100, 60, "rl:user:moderate", use_user=True))
user_generous = Depends(rate_limit(300, 60, "rl:user:generous", use_user=True))

# Admin rate limiters
admin_strict = Depends(rate_limit(20, 60, "rl:admin:strict", use_user=True))


class InMemoryRateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, times: int = 200, window: int = 60):
        super().__init__(app)
        self.times = times
        self.window = window
        self._store: dict[str, list[float]] = {}

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        if os.environ.get("IFINMAIL_ENV") == "testing":
            return await call_next(request)
        if not request.url.path.startswith(("/auth/", "/mail/", "/admin/", "/billing/", "/domains/", "/webhooks/")):
            return await call_next(request)

        identifier = request.client.host if request.client else "unknown"
        now = time.time()
        window_start = now - self.window
        hits = self._store.setdefault(identifier, [])
        hits[:] = [t for t in hits if t > window_start]
        remaining = max(0, self.times - len(hits))
        reset_at = int(window_start + self.window)
        if len(hits) >= self.times:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"error": "Too many requests. Please try again later."},
                headers={
                    "X-RateLimit-Limit": str(self.times),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(reset_at),
                },
            )
        hits.append(now)
        response = await call_next(request)
        response.headers["X-RateLimit-Limit"] = str(self.times)
        response.headers["X-RateLimit-Remaining"] = str(remaining - 1)
        response.headers["X-RateLimit-Reset"] = str(reset_at)
        return response
