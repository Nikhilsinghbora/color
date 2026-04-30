# Complete Setup Guide

This guide will help you set up and run the Color Prediction Game with all features including the bot system.

## Prerequisites

- Python 3.11+ with `uv` package manager installed
- Node.js 18+ and npm
- Access to Supabase (PostgreSQL) and Upstash (Redis) - already configured in `.env`

## Quick Start

### 1. Backend Setup

```bash
# Install dependencies
uv sync --all-extras

# The .env file is already configured with:
# - Supabase PostgreSQL database
# - Upstash Redis (with SSL)
# - JWT secrets and game settings

# Run the backend server (Terminal 1)
uv run run_local.py
# Server will be at: http://localhost:8000
# API docs at: http://localhost:8000/api/docs
```

### 2. Start Celery Services

**IMPORTANT**: Celery is required for game rounds to advance automatically and for bots to work.

```bash
# Windows (Terminal 2)
start_celery.bat

# Linux/Mac (Terminal 2)
chmod +x start_celery.sh
./start_celery.sh

# Or manually start worker and beat:
# Terminal 2:
uv run celery -A app.celery_app worker --loglevel=info --pool=solo --queues=game,wallet,email,reports,maintenance,analytics

# Terminal 3:
uv run celery -A app.celery_app beat --loglevel=info
```

**Why Celery is Required:**
- Celery Beat runs periodic tasks every 3 seconds
- These tasks advance game rounds through their lifecycle (BETTING → RESOLUTION → RESULT)
- Bots are automatically generated when new rounds start
- Without Celery, rounds won't progress and no new rounds will be created

### 3. Seed Initial Data

```bash
# Create game modes (Win Go 30s, 1Min, 3Min, 5Min)
python -m scripts.seed_data

# This will create 4 game modes and start the first round for each
```

### 4. Create an Admin User (Optional)

```bash
# Create admin with custom credentials
python -m scripts.create_admin --email admin@example.com --username admin --password yourpassword

# Or use defaults (admin@example.com / admin / admin123)
python -m scripts.create_admin
```

### 5. Frontend Setup

```bash
# Navigate to frontend directory (Terminal 4)
cd frontend

# Install dependencies
npm install

# Start Next.js dev server
npm run dev
# Frontend will be at: http://localhost:3000
# Admin dashboard: http://localhost:3000/admin
```

## Features Overview

### Bot System

The bot system creates realistic player activity without saving bot data to the database:

**How It Works:**
1. When a new round starts, Celery automatically generates 3-8 bots
2. Each bot gets a unique name from a pool of 20 (LuckyPlayer, GameMaster, etc.)
3. Bots place random bets on:
   - Colors: green, red, violet
   - Numbers: 0-9
   - Big/Small: big (5-9), small (0-4)
4. Bet amounts: $10, $20, $50, $100, $200, $500
5. Bot bets are stored in memory only (not in database)
6. When round completes, winning bots are calculated with 2% service fee
7. Bot winners appear in the WebSocket broadcast and winner lists
8. Bot data is cleared after round completes to save memory

**Benefits:**
- Creates consistent player activity in all rounds
- Makes the game look active even with few real players
- No database pollution with fake data
- Real players see realistic competition
- Bot winners visible in UI for authenticity

### WebSocket Real-Time Updates

The WebSocket system provides live updates:

**Connection:**
- Frontend connects to: `ws://localhost:8000/ws/game/{round_id}`
- Authentication via JWT token in query parameter
- Automatic reconnection with exponential backoff

**Messages Received:**
- `round_state`: Full round state (phase, timer, players, pool)
- `timer_tick`: Countdown updates
- `phase_change`: BETTING → RESOLUTION → RESULT
- `result`: Winning number/color and all payouts (including bots)
- `new_round`: When a new round starts
- `bet_update`: When players (or bots) place bets

### Game Lifecycle

**BETTING Phase (30s/1min/3min/5min depending on mode):**
- Real players can place bets via UI
- Bots automatically have bets placed (generated at round start)
- Timer counts down
- Pool and player count updates in real-time

**RESOLUTION Phase (~1-2 seconds):**
- Celery task invokes RNG to determine winning number (0-9)
- Winning color derived from number
- WebSocket broadcasts winning result

**RESULT Phase (~1-2 seconds):**
- Celery calculates all winner payouts:
  - Real player payouts: credited to wallets and saved to DB
  - Bot payouts: calculated but not saved to DB
- Winners (both real and bot) broadcast via WebSocket
- Bot winners appear in UI winner list with their names
- New round automatically starts for the same game mode

**Repeat:**
- Cycle continues every 30s/1min/3min/5min
- Bots regenerated for each new round
- Consistent activity guaranteed

## Testing the System

### 1. Check Backend Health

```bash
curl http://localhost:8000/api/v1/health
# Should return: {"status":"ok","db":"ok","redis":"ok"}
```

### 2. Check Active Game Modes

```bash
curl http://localhost:8000/api/v1/game/modes | python -m json.tool
# Should show 4 game modes with active_round_id for each
```

### 3. Verify Celery is Running

Check Celery worker logs - you should see:
```
[2026-04-30 13:05:07,672: INFO/MainProcess] Connected to rediss://...
```

Check Celery beat logs - you should see:
```
celery beat v5.6.3 is starting.
DatabaseScheduler: Schedule changed.
```

### 4. Monitor Round Advancement

Watch the backend logs - every 3 seconds you should see:
```
INFO: Resolved round {uuid}
INFO: Finalized round {uuid} with {n} bot winners
INFO: Started new round {uuid} for game mode {uuid} with {n} bots
```

### 5. Test Frontend

1. Open http://localhost:3000/game
2. Login or register
3. You should see:
   - Period number at top
   - Countdown timer
   - Player count (includes bots + real players)
   - Pool amount (includes bot bets + real bets)
4. Place a bet and watch it work
5. Wait for round to complete
6. See result with winning number/color
7. Check if you won (dialog will show)
8. See bot winners in the winner list

## Troubleshooting

### WebSocket Not Connecting

**Symptom:** Error in browser console about WebSocket connection failure

**Solution:**
1. Check backend is running on port 8000
2. Check `.env.local` in frontend:
   ```
   NEXT_PUBLIC_WS_URL=ws://localhost:8000
   ```
3. Verify game modes have active_round_id:
   ```bash
   curl http://localhost:8000/api/v1/game/modes | grep active_round_id
   ```
4. Make sure you're logged in (JWT token required for WebSocket)

### Rounds Not Advancing

**Symptom:** Timer stuck, no new rounds

**Solution:**
1. Check if Celery worker is running:
   ```bash
   ps aux | grep celery  # Linux/Mac
   tasklist | findstr celery  # Windows
   ```
2. Check if Celery beat is running (same commands)
3. Restart Celery services:
   ```bash
   # Kill existing processes
   pkill -f celery  # Linux/Mac
   taskkill /F /IM python.exe  # Windows (nuclear option)
   
   # Restart
   ./start_celery.sh  # or start_celery.bat
   ```

### No Bots in Rounds

**Symptom:** Player count is low, no activity

**Solution:**
1. Bots are only generated when NEW rounds start
2. Check Celery logs for:
   ```
   Generated {n} bot bets for round {uuid}
   ```
3. If not seeing this, check if game tasks are registered:
   ```bash
   uv run celery -A app.celery_app inspect registered
   ```
4. Should see `app.tasks.game_tasks.advance_game_round`

### Celery SSL Error

**Symptom:** `ValueError: A rediss:// URL must have parameter ssl_cert_reqs`

**Solution:**
This has been fixed in the latest commit. If you still see it:
1. Pull latest code
2. Check `app/celery_app.py` has SSL configuration
3. Restart Celery services

### Database Connection Error

**Symptom:** `asyncpg.exceptions.InvalidPasswordError` or connection refused

**Solution:**
1. Check Supabase is running and accessible
2. Verify `.env` has correct `APP_DATABASE_URL`
3. Test connection:
   ```bash
   uv run python -c "
   from app.models.base import async_session_factory
   import asyncio
   async def test():
       async with async_session_factory() as s:
           print('DB connection OK')
   asyncio.run(test())
   "
   ```

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                       Frontend (Next.js)                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Game UI  │  │ WebSocket│  │ Auth     │  │ Admin    │   │
│  │ Zustand  │  │ Client   │  │ Store    │  │ Dashboard│   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │           │
└───────┼─────────────┼─────────────┼─────────────┼───────────┘
        │             │             │             │
        │ HTTP        │ WS          │ JWT         │ HTTP
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    Backend (FastAPI)                         │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Game API │  │ WebSocket│  │ Auth API │  │ Admin API│   │
│  │ Routes   │  │ Manager  │  │ Routes   │  │ Routes   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │             │           │
│  ┌────┴─────────────┴─────────────┴─────────────┴─────┐   │
│  │              Services Layer                          │   │
│  │  • GameEngine    • WalletService  • BotService      │   │
│  │  • PayoutCalc    • ProfitService  • RNGEngine       │   │
│  └────┬─────────────────────────────────────┬──────────┘   │
│       │                                     │               │
└───────┼─────────────────────────────────────┼───────────────┘
        │                                     │
        ▼                                     ▼
┌───────────────┐                    ┌──────────────┐
│   PostgreSQL  │                    │    Redis     │
│   (Supabase)  │                    │  (Upstash)   │
│               │                    │              │
│  • Players    │                    │  • Sessions  │
│  • Rounds     │                    │  • Pub/Sub   │
│  • Bets       │                    │  • Cache     │
│  • Payouts    │                    │              │
└───────────────┘                    └──────┬───────┘
                                            │
                                            │ Subscribe
                                            ▼
                                   ┌──────────────────┐
                                   │  Celery Worker   │
                                   │  • Game Tasks    │
                                   │  • Bot Generator │
                                   │  • Payout Calc   │
                                   └────────▲─────────┘
                                            │
                                            │ Trigger
                                   ┌────────┴─────────┐
                                   │   Celery Beat    │
                                   │ (Every 3 seconds)│
                                   └──────────────────┘
```

## Summary

You now have a fully functional Color Prediction Game with:

✅ Real-time WebSocket updates  
✅ Automatic round advancement via Celery  
✅ Bot system for consistent activity  
✅ Real player betting and payouts  
✅ Admin dashboard for management  
✅ Secure authentication with JWT  
✅ Production-grade database (PostgreSQL)  
✅ Redis pub/sub for horizontal scaling  

**Next Steps:**
1. Customize bot names in `app/services/bot_service.py`
2. Adjust bot count (currently 3-8) in `generate_bots_for_round()`
3. Modify game mode durations in database
4. Configure profit margins in admin dashboard
5. Deploy to production (Docker Compose provided)

Enjoy your game! 🎰
