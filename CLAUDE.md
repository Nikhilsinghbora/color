# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Color Prediction Game Backend — a FastAPI-based real-time gaming platform with WebSocket synchronization, Celery task scheduling, and Redis pub/sub for horizontal scaling.

**Stack**: FastAPI + SQLAlchemy 2.0 (async) + Celery + Redis + PostgreSQL

## Development Commands

### Local Development (No Docker Required)
```bash
# Install dependencies
uv sync --all-extras

# Run local server (uses SQLite + fakeredis)
uv run run_local.py

# Access API docs
# http://localhost:8000/api/docs
```

### Testing
```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/unit/test_game_engine.py

# Run with coverage
uv run pytest --cov=app --cov-report=html

# Run property-based tests only
uv run pytest tests/properties/

# Run integration tests (requires Redis/PostgreSQL)
uv run pytest tests/integration/
```

### Database Migrations
```bash
# Create a new migration
uv run alembic revision --autogenerate -m "description"

# Apply migrations
uv run alembic upgrade head

# Rollback one migration
uv run alembic downgrade -1

# Show current migration
uv run alembic current
```

### Docker Deployment
```bash
# Start all services (FastAPI + Celery + PostgreSQL + Redis)
docker-compose up -d

# View logs
docker-compose logs -f app

# Restart specific service
docker-compose restart celery-worker

# Stop all services
docker-compose down
```

### Celery Workers
```bash
# Start Celery worker manually (requires Redis)
celery -A app.celery_app worker --loglevel=info --queues=game,wallet,email,reports,maintenance,analytics

# Start Celery Beat scheduler
celery -A app.celery_app beat --loglevel=info

# Monitor Celery events
celery -A app.celery_app events
```

## Architecture

### Core Components

**1. FastAPI Application** (`app/main.py`)
- Entry point creates app with lifespan management
- Initializes Redis connection pool and WebSocket manager on startup
- Registers middleware (CORS, rate limiting, auth), routers, and exception handlers

**2. Game Engine** (`app/services/game_engine.py`)
- Implements round state machine: BETTING → RESOLUTION → RESULT
- Functions: `start_round()`, `place_bet()`, `resolve_round()`, `finalize_round()`
- Validates transitions, enforces bet limits, manages wallet debits/credits

**3. WebSocket Manager** (`app/services/ws_manager.py`)
- Singleton managing per-player, per-round WebSocket connections
- Subscribes to Redis pub/sub channels (`channel:round:{round_id}`)
- Provides heartbeat monitoring and stale connection cleanup
- Fan-out pattern: Celery publishes to Redis → all FastAPI instances broadcast to connected clients

**4. Celery Tasks** (`app/tasks/game_tasks.py`)
- `advance_game_round()`: periodic task (every 3s) drives round lifecycle
  - Resolves BETTING rounds whose timer expired
  - Finalizes RESOLUTION rounds and auto-starts new rounds
- Publishes state changes to Redis pub/sub after each transition

**5. Payout Calculator** (`app/services/payout_calculator.py`)
- Uses `Decimal` (never float) for fixed-point arithmetic
- `calculate_round_payouts()`: determines winners based on winning number
- Number-to-color mapping:
  - Green: {0,1,3,5,7,9}
  - Red: {2,4,6,8}
  - Violet: {0,5} (dual payouts possible for 0 and 5)

**6. Profit Service** (`app/services/profit_service.py`)
- Manages house profit margin and winner pool distribution
- Default: 20% house profit, 80% winner pool (configurable by admin)
- When calculated payouts exceed winner pool, reduces proportionally
- `calculate_profit_allocation()`: splits total bets into house/winner pools
- `adjust_payouts_to_pool()`: applies reduction ratio if needed
- Rounds with reduced payouts are flagged for review

**7. RNG Engine** (`app/services/rng_engine.py`)
- Generates winning number (0-9) and color
- Creates audit trail in `rng_audit` table for compliance

### Data Flow

**Placing a Bet**:
1. Client → POST `/api/v1/game/rounds/{round_id}/bet`
2. Validate round is in BETTING phase
3. Check bet limits (min_bet/max_bet from game mode)
4. Validate wallet balance
5. Debit wallet atomically
6. Create Bet record with `odds_at_placement`
7. Update `round.total_bets`

**Round Lifecycle** (driven by Celery Beat every 3s):
1. BETTING → RESOLUTION (when `betting_ends_at` expires)
   - Invoke RNG, set `winning_color` and `winning_number`
   - Publish to Redis: `channel:round:{round_id}` with phase=RESOLUTION
2. RESOLUTION → RESULT (immediately after)
   - Calculate profit allocation (house profit vs winner pool)
   - Calculate all winner payouts based on odds
   - If payouts exceed winner pool, reduce proportionally
   - Credit winners with adjusted amounts
   - Record profit details in round (`house_profit`, `total_payout_pool`, `payout_reduced`)
   - Flag round for review if payouts were reduced
   - Create Payout records
   - Publish to Redis: phase=RESULT
3. Auto-start new round for same game mode

**WebSocket Broadcast**:
- Celery publishes state to Redis pub/sub
- All FastAPI instances have Redis subscribers per active round
- WebSocketManager fans out to connected clients for that round

### Directory Structure

```
app/
├── api/          # FastAPI route handlers
├── middleware/   # CORS, rate limiting, auth, error handling
├── models/       # SQLAlchemy ORM models
├── schemas/      # Pydantic request/response schemas
├── services/     # Business logic (game_engine, wallet_service, ws_manager, etc.)
├── tasks/        # Celery tasks (game_tasks, wallet_tasks, email_tasks, etc.)
├── config.py     # Pydantic settings (loads from env vars with APP_ prefix)
├── exceptions.py # Custom exception classes
├── celery_app.py # Celery config with task routing and Beat schedule
└── main.py       # Application factory

tests/
├── unit/         # Unit tests (mock external dependencies)
├── integration/  # Integration tests (Redis, PostgreSQL, Celery)
├── properties/   # Property-based tests using Hypothesis
└── smoke/        # Infrastructure smoke tests
```

## Key Conventions

### Decimal Arithmetic
All monetary calculations use Python's `Decimal` type, never float. Always quantize to `Decimal("0.01")` for two-decimal precision.

### Database Sessions
- Use `async_session_factory` from `app/models/base` for async context managers
- Never share sessions across requests
- Explicit `await session.commit()` or `await session.rollback()` for transactions

### Wallet Operations
- `wallet_service.debit()` / `wallet_service.credit()` are atomic
- Always pass `reference_id` (usually `round_id` or `bet_id`) for audit trail
- Check balance before debit to provide user-friendly error messages

### State Transitions
- Game round transitions are strictly enforced via `VALID_TRANSITIONS` map
- Invalid transitions raise `InvalidTransitionError`
- Never manually set phase without validating transition

### WebSocket Events
- Celery publishes state changes to Redis: `channel:round:{round_id}`
- FastAPI instances subscribe and broadcast to clients
- Do NOT have FastAPI publish directly to Redis (that's Celery's job)

### Testing
- Unit tests use `pytest-asyncio` with `asyncio_mode = "auto"`
- Integration tests require real Redis/PostgreSQL (use Docker or separate instances)
- Property tests use Hypothesis for generative testing
- Mock external services (Stripe, email) in unit tests

### Configuration
- All settings in `app/config.py` load from environment variables with `APP_` prefix
- For local dev: `run_local.py` uses SQLite (`sqlite+aiosqlite:///:memory:`) and fakeredis
- For Docker: set `APP_DATABASE_URL` and `APP_REDIS_URL` in docker-compose.yml

### Celery Task Routing
Tasks are routed to dedicated queues (see `app/celery_app.py`):
- `game` queue: game round lifecycle
- `wallet` queue: wallet operations
- `email` queue: email notifications
- `reports` queue: analytics reports
- `maintenance` queue: cleanup tasks
- `analytics` queue: leaderboard updates

### Error Handling
- Custom exceptions in `app/exceptions.py` (e.g., `BettingClosedError`, `InsufficientBalanceError`)
- Middleware (`app/middleware/error_handler.py`) converts to proper HTTP responses
- Always provide user-friendly error messages with error codes

## Common Gotchas

- **Betting Phase Check**: Always validate `round.phase == RoundPhase.BETTING` before accepting bets
- **Odds Snapshot**: Bets store `odds_at_placement` (not dynamic) for fairness
- **Number Bets**: Single digit strings "0"–"9" are valid bet choices alongside color names
- **Dual Payouts**: Numbers 0 and 5 trigger both violet and green payouts
- **Profit Management**: Winners may receive less than calculated payouts if total exceeds winner pool
- **Payout Reduction**: Reductions are proportional (all winners get same reduction ratio)
- **Flagged Rounds**: Rounds with `payout_reduced=true` are automatically flagged for review
- **Redis Pool**: Access via `get_redis_pool()` from `app/main.py` (don't create new pools)
- **Celery Context**: Use `_run_async()` helper in Celery tasks to run async functions
- **Migration Autogenerate**: Always review generated migrations; Alembic can't detect all schema changes

## Debugging

### Check Round State
```python
from app.services import game_engine
state = await game_engine.get_round_state(session, round_id)
print(f"Phase: {state.phase}, Winning Color: {state.winning_color}")
```

### Inspect Celery Beat Schedule
```bash
celery -A app.celery_app inspect scheduled
```

### Monitor Redis Pub/Sub
```bash
redis-cli
> SUBSCRIBE channel:round:*
```

### Check Database Connections
```bash
# Visit health check endpoint
curl http://localhost:8000/api/v1/health
```
