# How to Place Bets - Complete Guide

## Problem Solved ✅

**Issue**: Unable to place bets because no game rounds existed.

**Root Cause**: Celery Beat (the task scheduler) was not running. Celery Beat is responsible for:
- Creating new rounds
- Advancing round phases (BETTING → RESOLUTION → RESULT)
- Resolving rounds and determining winners

**Solution**: Created rounds manually using `scripts/start_rounds.py`

---

## Quick Start (Betting Now!)

### Step 1: Rounds Are Ready
I've already created 4 rounds for you:
- ✅ Win Go 30s - Ready for betting
- ✅ Win Go 1Min - Ready for betting
- ✅ Win Go 3Min - Ready for betting
- ✅ Win Go 5Min - Ready for betting

### Step 2: Refresh the Game Page
1. Go to `http://localhost:3000/game`
2. Press **Ctrl+Shift+R** (hard refresh) or **F5**
3. You should now see:
   - Countdown timer (30s, 60s, 180s, or 300s)
   - Period number (e.g., "202604301000000001")
   - Bet buttons are enabled (not grayed out)

### Step 3: Place a Bet
1. **Select a bet type**:
   - Click **Green**, **Red**, or **Violet** button
   - OR click a **Number** (0-9)
   - OR click **Big** or **Small**

2. **Bet Confirmation Sheet appears**:
   - Shows your selection
   - Shows available balance
   - Choose bet amount (₹1, ₹10, ₹100, ₹1000)
   - Or enter custom amount
   - Select quantity (1x, 5x, 10x, etc.)

3. **Confirm bet**:
   - Click "Confirm" button
   - Balance is deducted immediately
   - Bet is placed

4. **Wait for round to end**:
   - Timer counts down to 0
   - Round enters RESOLUTION phase
   - Winning number and color displayed
   - If you win, balance is credited automatically

---

## Important Notes

### ⚠️ Manual Round Creation

The rounds I created will **NOT auto-advance** because Celery Beat is not running. This means:

**What Works:**
- ✅ You can place bets during the betting phase
- ✅ Balance is deducted when you bet
- ✅ Timer counts down

**What Doesn't Work (without Celery):**
- ❌ Rounds won't auto-resolve when timer hits 0
- ❌ Winners won't be determined
- ❌ New rounds won't be created
- ❌ No automatic payouts

### Solution: Start Celery Beat

For full functionality, you need to run Celery Beat:

```bash
# Terminal 3 (separate from backend and frontend)
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning"
celery -A app.celery_app beat --loglevel=info
```

**AND** Celery Worker:

```bash
# Terminal 4
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning"
celery -A app.celery_app worker --loglevel=info --queues=game,wallet,email,reports,maintenance,analytics
```

---

## Full Production Setup

### Required Services

1. **Backend** (Port 8000)
   ```bash
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

2. **Frontend** (Port 3000)
   ```bash
   cd frontend
   npm run dev
   ```

3. **Celery Beat** (Scheduler)
   ```bash
   celery -A app.celery_app beat --loglevel=info
   ```

4. **Celery Worker** (Task Processor)
   ```bash
   celery -A app.celery_app worker --loglevel=info --queues=game,wallet,email,reports,maintenance,analytics
   ```

5. **Redis** (Required for Celery)
   - Already configured in your `.env`
   - Using Upstash Redis (cloud)

6. **PostgreSQL** (Database)
   - Already configured in your `.env`
   - Using Supabase (cloud)

---

## Testing Without Celery (Development)

If you don't want to run Celery right now, you can manually manage rounds:

### Create Rounds
```bash
python -m scripts.start_rounds
```

### Check Round Status
```bash
python -c "
import asyncio
from sqlalchemy import select
from app.models.base import async_session_factory
from app.models.game import GameRound

async def check():
    async with async_session_factory() as session:
        result = await session.execute(select(GameRound))
        rounds = result.scalars().all()
        for r in rounds:
            print(f'Period: {r.period_number}, Phase: {r.phase.value}, Bets: {r.total_bets}')

asyncio.run(check())
"
```

---

## Troubleshooting

### "No rounds available" or bet buttons disabled

**Check if rounds exist:**
```bash
python -m scripts.start_rounds
```

**Refresh the page:**
- Hard refresh: **Ctrl+Shift+R**
- Or close and reopen browser tab

### Bet button shows but clicking does nothing

**Check browser console (F12):**
- Look for error messages
- Check network tab for failed API calls

**Verify balance:**
```bash
python -c "
import asyncio
from sqlalchemy import select
from app.models.base import async_session_factory
from app.models.player import Player, Wallet

async def check():
    async with async_session_factory() as session:
        result = await session.execute(
            select(Wallet).join(Player).where(Player.email == 'admin@boranikhilsingh.com')
        )
        wallet = result.scalar_one()
        print(f'Balance: {wallet.balance}')

asyncio.run(check())
"
```

### Timer reaches 0 but nothing happens

**This is expected without Celery Beat!**

You need to start Celery Beat for automatic round resolution.

**Manual workaround (NOT recommended for production):**
You can manually resolve rounds using Python, but it's complex. Just start Celery Beat instead.

### Celery won't start

**Common issues:**

1. **Redis not accessible:**
   ```bash
   # Test Redis connection
   python -c "
   import asyncio
   import redis.asyncio as aioredis
   
   async def test():
       from app.config import settings
       pool = aioredis.ConnectionPool.from_url(settings.redis_url)
       client = aioredis.Redis(connection_pool=pool)
       await client.ping()
       print('Redis OK')
       await pool.aclose()
   
   asyncio.run(test())
   "
   ```

2. **Wrong directory:**
   Make sure you're in the project root (where `app/` directory is)

3. **Module not found:**
   ```bash
   # Make sure dependencies are installed
   pip install celery redis
   # Or with uv
   uv sync --all-extras
   ```

---

## Docker Alternative (Easiest)

If Celery is too complicated, use Docker Compose to run everything:

```bash
docker-compose up -d
```

This starts ALL services automatically:
- FastAPI backend
- Celery Beat
- Celery Worker
- PostgreSQL
- Redis
- Nginx

---

## Current Status

- ✅ Backend running
- ✅ Frontend running
- ✅ Database connected
- ✅ Redis connected
- ✅ 4 game rounds created
- ✅ Can place bets NOW
- ❌ Celery Beat not running (rounds won't auto-advance)
- ❌ Celery Worker not running (bets won't be resolved)

## Recommended Next Steps

1. **Try betting now** (works without Celery):
   - Refresh game page
   - Place a bet
   - See balance deducted

2. **For full experience**, start Celery:
   ```bash
   # Terminal 3
   celery -A app.celery_app beat --loglevel=info
   
   # Terminal 4
   celery -A app.celery_app worker --loglevel=info --queues=game,wallet,email,reports,maintenance,analytics
   ```

3. **Watch it work**:
   - Place bet
   - Wait for timer to reach 0
   - See result announced
   - Balance updated if you win
   - New round starts automatically

---

## Quick Commands Reference

```bash
# Create/restart rounds
python -m scripts.start_rounds

# Check database rounds
python -c "from app.models.game import GameRound; from app.models.base import async_session_factory; from sqlalchemy import select, func; import asyncio; print(asyncio.run((lambda: async_session_factory().__aenter__()).__call__()).execute(select(func.count()).select_from(GameRound)).scalar())"

# Add balance to user
python -m scripts.add_currency --amount 100000 --email admin@boranikhilsingh.com --confirm

# Create admin
python -m scripts.create_admin --email admin@test.com --username admin2 --password test123

# Seed game modes
python -m scripts.seed_data
```

**You can now place bets! Just refresh the page! 🎰**
