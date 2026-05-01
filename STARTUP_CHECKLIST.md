# 🚀 Startup Checklist - Color Prediction Game

All code fixes are complete. If you're still seeing "0 game modes" or "Disconnected" status, follow this checklist to ensure all services are running correctly.

## ✅ Step-by-Step Startup Guide

### 1️⃣ Backend Setup

```bash
# Terminal 1: Start FastAPI backend
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning"
uv run run_local.py
```

**Expected output:**
```
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

**Test it:**
- Open http://localhost:8000/api/docs
- You should see the Swagger API documentation

---

### 2️⃣ Celery Worker & Beat

```bash
# Terminal 2: Start Celery (CRITICAL for game rounds and timers)
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning"
start_celery.bat
```

**Expected output:**
```
[tasks]
  . app.tasks.game_tasks.advance_game_round
  . app.tasks.game_tasks.broadcast_timer_updates
  
celery@HOSTNAME ready.
```

**Verify Beat is running:**
- Look for: `[beat] Scheduler: Sending due task broadcast-timer-updates`
- This should appear **every 1 second**

⚠️ **CRITICAL**: If Celery is not running, the following will NOT work:
- Round timers will not count down
- Rounds will not advance
- Bots will not appear
- Winners will not be calculated

---

### 3️⃣ Frontend Setup

```bash
# Terminal 3: Start Next.js frontend (MUST RESTART to load env vars)
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning\frontend"

# First, verify environment variables are set:
type .env.local

# Should show:
# NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
# NEXT_PUBLIC_WS_URL=ws://localhost:8000

# NOW start the dev server:
npm run dev
```

**Expected output:**
```
- Local:        http://localhost:3000
- Ready in 2.3s
```

**Why restart is needed:**
- `NEXT_PUBLIC_*` environment variables are compiled at build time
- If you added/changed `.env.local` while dev server was running, it won't pick them up
- You **MUST** stop (Ctrl+C) and restart `npm run dev`

---

### 4️⃣ Verify Connectivity

Visit: http://localhost:3000/connectivity-test

Click **"Run Connectivity Tests"** and check all 5 tests pass:

1. ✅ Direct fetch to backend health endpoint
2. ✅ Environment variables (both should show URLs, not "Not set")
3. ✅ Fetch using NEXT_PUBLIC_API_URL
4. ✅ CORS check (should show Access-Control headers)
5. ✅ Authenticated request (if logged in)

---

### 5️⃣ Test Login & Game Page

1. **Clear browser cache** (Ctrl+Shift+Delete → Cached images and files)
2. Navigate to http://localhost:3000/login
3. Login with your credentials
4. You should be redirected to http://localhost:3000/game

**Check Browser Console (F12):**

✅ **Good signs:**
```
[api-client] Using BASE_URL: http://localhost:8000/api/v1
[ws-client] Using NEXT_PUBLIC_WS_URL: ws://localhost:8000
[ws-client] ✅ WebSocket connection OPENED
[ws-client] 📩 Received message: round_state
[ws-client] 📩 Received message: timer_tick
```

❌ **Bad signs (means environment not loaded):**
```
[api-client] NEXT_PUBLIC_API_URL from env: NOT SET
[ws-client] ⚠️ NEXT_PUBLIC_WS_URL not set, using fallback
AxiosError: Network Error
```

**Solution:** Stop frontend (Ctrl+C) and restart `npm run dev`

---

### 6️⃣ Verify Real-Time Features

Once logged in at `/game`:

1. **Timer Countdown**: Should count down from 30/60/180/300 seconds
2. **Total Players**: Should show 3-8 (bots generated automatically)
3. **Betting**: Place a bet, see total pool increase immediately
4. **Round Transitions**: Watch timer reach 0, see winning number appear
5. **New Round**: New round should start within 5 seconds

---

## 🔧 Troubleshooting

### Problem: "0 game modes loaded"

**Cause:** Frontend dev server not restarted after `.env.local` changes

**Fix:**
```bash
cd frontend
# Stop dev server: Ctrl+C
npm run dev  # Start fresh
```

---

### Problem: "WebSocket: Disconnected"

**Cause:** Either backend not running OR frontend can't find WebSocket URL

**Fix:**
1. Check backend is running: http://localhost:8000/api/docs
2. Check Celery is running: Look for "celery@HOSTNAME ready"
3. Check browser console for WebSocket errors
4. Restart frontend dev server (see above)

---

### Problem: Timer stuck at 0

**Cause:** Celery Beat not running (timer_tick broadcasts not happening)

**Fix:**
1. Stop Celery: Ctrl+C in Terminal 2
2. Restart: `start_celery.bat`
3. Look for: `[beat] Scheduler: Sending due task broadcast-timer-updates`
4. This should appear **every 1 second**

---

### Problem: No bots visible

**Cause:** Celery worker not running OR no active rounds

**Fix:**
1. Ensure Celery is running (see above)
2. Backend logs should show: "Generated X bots for round"
3. If no rounds exist, seed game modes: `python -m scripts.seed_data`

---

## 📊 Monitoring

### Backend Health
```bash
curl http://localhost:8000/api/v1/health
```

Should return:
```json
{"status":"ok","database":"ok","redis":"ok"}
```

### WebSocket Test (Python)
```bash
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning"
python test_websocket_detailed.py
```

Should show:
```
✅ Connected to WebSocket!
📩 Received message: round_state
📩 Received message: timer_tick
```

---

## 🎯 Quick Start (All Commands)

Copy-paste this to start everything fresh:

```bash
# Terminal 1 - Backend
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning"
uv run run_local.py

# Terminal 2 - Celery (NEW WINDOW)
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning"
start_celery.bat

# Terminal 3 - Frontend (NEW WINDOW)
cd "C:\Users\Nikhil\OneDrive\Desktop\Project Planning\frontend"
npm run dev
```

Then visit: http://localhost:3000/login

---

## ✨ What's Fixed

All code issues from the bug report are now resolved:

1. ✅ **Login page flash on reload** - Added hydration check in `useAuthGuard`
2. ✅ **No bots visible** - Bots generate automatically, `broadcast_bet_update` shows player count
3. ✅ **Timer stuck at 0** - Removed conflicting countdown hook, use WebSocket timer directly
4. ✅ **Bet UI not updating** - Backend broadcasts `bet_update` after each bet placed

The only remaining issue is **environmental** - ensure all 3 services are running and frontend dev server was restarted after `.env.local` changes.
