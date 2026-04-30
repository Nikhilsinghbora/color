"""Local development runner with Celery — uses SQLite + fakeredis.

Runs:
1. FastAPI backend (uvicorn)
2. Celery worker (for tasks)
3. Celery beat (for periodic tasks like round advancement)

All services run in the same process using multiprocessing.
"""

import asyncio
import multiprocessing
import sys
import time

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
    print("✓ Database tables created.")


def run_uvicorn():
    """Run the FastAPI backend."""
    import uvicorn
    print("\n🚀 Starting FastAPI backend at http://localhost:8000")
    print("   API docs at http://localhost:8000/api/docs\n")
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=False)


def run_celery_worker():
    """Run the Celery worker."""
    from celery.bin import worker as celery_worker
    from app.celery_app import celery_app

    print("\n⚙️  Starting Celery worker...")
    worker = celery_worker.worker(app=celery_app)
    options = {
        "loglevel": "INFO",
        "traceback": True,
        "queues": ["game", "wallet", "email", "reports", "maintenance", "analytics"],
    }
    worker.run(**options)


def run_celery_beat():
    """Run the Celery beat scheduler."""
    from celery.bin import beat as celery_beat
    from app.celery_app import celery_app

    print("\n⏰ Starting Celery beat scheduler...")
    beat = celery_beat.beat(app=celery_app)
    options = {
        "loglevel": "INFO",
    }
    beat.run(**options)


def main():
    """Initialize database and start all services."""
    # Initialize DB tables
    print("Initializing database...")
    asyncio.run(init_db())

    # Start services in separate processes
    processes = []

    # Start Celery beat (scheduler)
    beat_process = multiprocessing.Process(target=run_celery_beat)
    beat_process.start()
    processes.append(beat_process)
    time.sleep(2)  # Let beat start first

    # Start Celery worker
    worker_process = multiprocessing.Process(target=run_celery_worker)
    worker_process.start()
    processes.append(worker_process)
    time.sleep(2)  # Let worker start

    # Start FastAPI (in main process for reload support)
    try:
        run_uvicorn()
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down...")
        for proc in processes:
            proc.terminate()
            proc.join(timeout=5)
            if proc.is_alive():
                proc.kill()
        print("✓ All services stopped.")
        sys.exit(0)


if __name__ == "__main__":
    multiprocessing.set_start_method('spawn', force=True)
    main()
