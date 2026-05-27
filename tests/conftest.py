from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from ifinmail.api.app import app
from ifinmail.api.deps import get_db
from ifinmail.api.deps import get_redis as deps_get_redis
from ifinmail.db.models import Base


class _FakeRedis:
    def __init__(self):
        self._string_store: dict[str, str] = {}
        self._zset_store: dict[str, dict[str, float]] = {}

    def get(self, key: str) -> str | None:
        return self._string_store.get(key)

    def setex(self, key: str, _time: int, value: str) -> None:
        self._string_store[key] = value

    def delete(self, *keys: str) -> int:
        count = 0
        for k in keys:
            if k in self._string_store:
                del self._string_store[k]
                count += 1
        return count

    def zremrangebyscore(self, key: str, _min, _max) -> int:
        zset = self._zset_store.get(key)
        if zset is None:
            return 0
        to_remove = [k for k, v in zset.items() if _min <= v <= _max]
        for k in to_remove:
            del zset[k]
        return len(to_remove)

    def zcard(self, key: str) -> int:
        zset = self._zset_store.get(key)
        return len(zset) if zset else 0

    def zadd(self, key: str, mapping: dict[str, float]) -> int:
        if key not in self._zset_store:
            self._zset_store[key] = {}
        added = 0
        for member, score in mapping.items():
            if member not in self._zset_store[key]:
                added += 1
            self._zset_store[key][member] = score
        return added

    def expire(self, key: str, _seconds: int) -> int:
        return 1

    def pipeline(self):
        return _FakePipeline(self)


class _FakePipeline:
    def __init__(self, redis: _FakeRedis):
        self._redis = redis
        self._commands: list[tuple[str, tuple, dict]] = []

    def zremrangebyscore(self, key: str, min_v, max_v):
        self._commands.append(("zremrangebyscore", (key, min_v, max_v), {}))
        return self

    def zcard(self, key: str):
        self._commands.append(("zcard", (key,), {}))
        return self

    def zadd(self, key: str, mapping: dict[str, float]):
        self._commands.append(("zadd", (key, mapping), {}))
        return self

    def expire(self, key: str, seconds: int):
        self._commands.append(("expire", (key, seconds), {}))
        return self

    def execute(self) -> list:
        results = []
        for name, args, _kwargs in self._commands:
            method = getattr(self._redis, name)
            results.append(method(*args))
        return results


@pytest.fixture(scope="session")
def engine():
    e = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(e)
    return e


@pytest.fixture
def db_session(engine):
    conn = engine.connect()
    tx = conn.begin()
    session = sessionmaker(bind=conn)()
    yield session
    session.close()
    tx.rollback()
    conn.close()


@pytest.fixture
def redis_mock():
    return _FakeRedis()


@pytest.fixture
def client(db_session, redis_mock):
    def _get_db_override():
        yield db_session

    app.dependency_overrides[get_db] = _get_db_override
    app.dependency_overrides[deps_get_redis] = lambda: redis_mock

    patches = [
        patch("ifinmail.api.auth.get_redis", return_value=redis_mock),
    ]
    for p in patches:
        p.start()

    with TestClient(app) as c:
        yield c

    for p in patches:
        p.stop()
    app.dependency_overrides.clear()
