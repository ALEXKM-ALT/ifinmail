import time

from fastapi import Depends, HTTPException, Request, status
from redis import Redis

from ifinmail.api.deps import get_redis


def rate_limit(times: int, window: int, key_prefix: str = "rl"):
    def _dependency(request: Request, redis: Redis = Depends(get_redis)) -> None:
        try:
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
        except Exception:
            pass

    return _dependency


strict = Depends(rate_limit(10, 60, "rl:strict"))
default = Depends(rate_limit(60, 60, "rl:default"))
