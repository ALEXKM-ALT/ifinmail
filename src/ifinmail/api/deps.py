from collections.abc import Generator

from redis import Redis
from sqlalchemy.orm import Session

from ifinmail.api.config import settings
from ifinmail.api.database import SessionLocal
from ifinmail.db.models import User

_redis: Redis | None = None


def _get_redis() -> Redis | None:
    global _redis
    return _redis


def get_redis() -> Redis:
    global _redis
    if _redis is None:
        _redis = Redis.from_url(settings.redis_url, decode_responses=True)
    return _redis


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(db: Session, user_id: int) -> User | None:
    return db.query(User).filter(User.id == user_id).first()
