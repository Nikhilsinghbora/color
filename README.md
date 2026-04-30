# 🎮 WinGo Color Prediction Game

A full-stack color prediction game platform inspired by 51game WinGo. Players bet on colors (Green/Red/Violet), numbers (0–9), or Big/Small (5–9 / 0–4) with real-time WebSocket updates, multiple game modes, and a 2% service fee on winning payouts.

**Backend:** FastAPI + SQLAlchemy + Redis + Celery
**Frontend:** Next.js + React + Zustand + Tailwind CSS
**Database:** PostgreSQL (Supabase) | **Cache:** Redis (Upstash)

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Git

### 1. Clone the repo

```bash
git clone https://github.com/Nikhilsinghbora/color.git
cd color
```

### 2. Set up environment variables

```bash
cp .env.example .env
```

Edit `.env` with your credentials:

```env
# Database (Supabase PostgreSQL)
APP_DATABASE_URL=postgresql+asyncpg://postgres.YOUR_PROJECT:YOUR_PASSWORD@aws-0-region.pooler.supabase.com:5432/postgres

# Redis (Upstash or local)
APP_REDIS_URL=rediss://default:YOUR_TOKEN@your-host.upstash.io:6379

# JWT (change in production!)
APP_JWT_SECRET_KEY=your-secret-key-here

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000/ws
```

### 3. Install backend dependencies

```bash
pip install -e ".[dev]"
```

Or with [uv](https://github.com/astral-sh/uv):

```bash
uv sync --all-extras
```

### 4. Start the backend

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Tables are created automatically on first startup (if they don't exist).

### 5. Seed game modes

```bash
python -m scripts.seed_data
```

This creates 4 game modes: Win Go 30s, 1Min, 3Min, 5Min.

### 6. Install frontend dependencies

```bash
cd frontend
npm install
```

### 7. Start the frontend

```bash
npm run dev
```

Frontend runs on `http://localhost:3000`.

---

## API Endpoints

Once running, open the interactive API docs:

- **Swagger UI:** http://localhost:8000/api/docs
- **ReDoc:** http://localhost:8000/api/redoc
- **Health Check:** http://localhost:8000/api/v1/health

### Auth
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/auth/register` | Register a new player |
| POST | `/api/v1/auth/login` | Login and get JWT tokens |
| POST | `/api/v1/auth/refresh` | Refresh access token |

### Game
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/game/modes` | List all active game modes |
| GET | `/api/v1/game/modes/{id}` | Get a single game mode |
| GET | `/api/v1/game/rounds/{id}` | Get round state |
| POST | `/api/v1/game/rounds/{id}/bet` | Place a bet |
| GET | `/api/v1/game/history` | Paginated game history |
| GET | `/api/v1/game/my-history` | Player's bet history (auth required) |

### Wallet
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/wallet/balance` | Get wallet balance |
| POST | `/api/v1/wallet/deposit` | Deposit funds |
| POST | `/api/v1/wallet/withdraw` | Withdraw funds |
| GET | `/api/v1/wallet/transactions` | Transaction history |

### WebSocket
```
ws://localhost:8000/ws/game/{round_id}?token=JWT_TOKEN
```

**Incoming messages:** `round_state`, `timer_tick`, `phase_change`, `result`, `new_round`, `bet_update`, `chat_message`
**Outgoing messages:** `chat`, `pong`

---

## Running Tests

### Backend tests

```bash
# All tests
pytest

# Unit tests only
pytest tests/unit/

# Property-based tests
pytest tests/properties/

# With verbose output
pytest -v
```

### Frontend tests

```bash
cd frontend

# Run all tests
npm test

# Watch mode
npm run test:watch

# Run specific test file
npx vitest --run src/components/WalletCard.test.tsx
```

---

## Docker (Full Stack)

Run everything with Docker Compose (includes PostgreSQL, Redis, Celery, Nginx):

```bash
docker-compose up -d
```

This starts:
- **app** — FastAPI backend on port 8000
- **postgres** — PostgreSQL on port 5432
- **redis** — Redis on port 6379
- **celery-worker** — Background task processor
- **celery-beat** — Periodic task scheduler
- **nginx** — Reverse proxy on port 80

To stop:

```bash
docker-compose down
```

---

## Celery (Background Tasks)

The game round lifecycle (BETTING → RESOLUTION → RESULT → new round) is driven by Celery periodic tasks.

### Start Celery worker

```bash
celery -A app.celery_app worker --loglevel=info
```

### Start Celery beat (scheduler)

```bash
celery -A app.celery_app beat --loglevel=info
```

---

## Project Structure

```
├── app/
│   ├── api/              # FastAPI route handlers
│   ├── middleware/        # Auth, CORS, rate limiting
│   ├── models/           # SQLAlchemy models
│   ├── schemas/          # Pydantic request/response schemas
│   ├── services/         # Business logic (game engine, payouts, etc.)
│   ├── tasks/            # Celery background tasks
│   ├── config.py         # Settings from environment
│   └── main.py           # FastAPI app factory
├── frontend/
│   ├── src/
│   │   ├── app/          # Next.js pages
│   │   ├── components/   # React components
│   │   ├── hooks/        # Custom hooks (useWebSocket, etc.)
│   │   ├── stores/       # Zustand state stores
│   │   ├── lib/          # API client, sound manager, utils
│   │   └── types/        # TypeScript type definitions
│   └── package.json
├── tests/
│   ├── unit/             # Unit tests
│   ├── properties/       # Property-based tests (Hypothesis)
│   ├── integration/      # Integration tests
│   └── smoke/            # Smoke tests
├── alembic/              # Database migrations
├── scripts/              # Seed data, utilities
├── .env                  # Environment variables (not committed)
├── docker-compose.yml    # Full stack Docker setup
└── pyproject.toml        # Python project config
```

---

## Game Modes

| Mode | Duration | Prefix | Round Format |
|------|----------|--------|--------------|
| Win Go 30s | 30 seconds | 100 | `YYYYMMDD1000000001` |
| Win Go 1Min | 60 seconds | 101 | `YYYYMMDD1010000001` |
| Win Go 3Min | 180 seconds | 102 | `YYYYMMDD1020000001` |
| Win Go 5Min | 300 seconds | 103 | `YYYYMMDD1030000001` |

## Bet Types & Payouts

| Bet Type | Options | Payout | Example |
|----------|---------|--------|---------|
| Color | Green, Red, Violet | 2x, 2x, 4.8x | ₹100 on Green → ₹196 |
| Number | 0–9 | 9.6x | ₹100 on 7 → ₹940.80 |
| Big | 5, 6, 7, 8, 9 | 2x | ₹100 on Big → ₹196 |
| Small | 0, 1, 2, 3, 4 | 2x | ₹100 on Small → ₹196 |

> **Note:** A 2% service fee is deducted from winning payouts. Payout = (bet × 0.98) × odds.
