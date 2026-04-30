"""Local development runner — uses SQLite + fakeredis (no external services needed)."""

import asyncio
import sys

# Patch redis with fakeredis BEFORE any app imports
import fakeredis
import fakeredis.aioredis as fake_aioredis
import redis.asyncio as real_aioredis

# Monkey-patch redis.asyncio so the app uses fakeredis transparently
_fake_server = fakeredis.FakeServer()

_original_from_url = real_aioredis.from_url
_original_connection_pool_from_url = real_aioredis.ConnectionPool.from_url


def _patched_from_url(url, **kwargs):
    return fake_aioredis.FakeRedis(server=_fake_server, decode_responses=kwargs.get("decode_responses", False))


def _patched_pool_from_url(url, **kwargs):
    """Return a fake connection pool."""
    return _original_connection_pool_from_url(url, **kwargs) if False else type(
        "FakePool", (), {
            "aclose": lambda self: asyncio.sleep(0),
            "__aenter__": lambda self: self,
            "__aexit__": lambda self, *a: asyncio.sleep(0),
        }
    )()


real_aioredis.from_url = _patched_from_url
real_aioredis.ConnectionPool.from_url = _patched_pool_from_url

# Also patch Redis class
_OriginalRedis = real_aioredis.Redis


class PatchedRedis(_OriginalRedis):
    def __init__(self, *args, connection_pool=None, **kwargs):
        # Ignore the fake pool, create a fakeredis instance
        self._fake = fake_aioredis.FakeRedis(server=_fake_server, decode_responses=True)

    async def ping(self):
        return await self._fake.ping()

    async def publish(self, channel, message):
        return await self._fake.publish(channel, message)

    def pubsub(self, **kwargs):
        return self._fake.pubsub(**kwargs)


real_aioredis.Redis = PatchedRedis


async def init_db():
    """Create all tables in SQLite."""
    from app.models.base import Base, engine
    # Import all models so they register with Base
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("Database tables created.")


if __name__ == "__main__":
    # Initialize DB tables
    asyncio.run(init_db())

    # Run the app
    import uvicorn
    print("\n Starting backend at http://localhost:8000")
    print(" API docs at http://localhost:8000/api/docs\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
