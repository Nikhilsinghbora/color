# WebSocket Not Connecting - Complete Fix Guide

## 🔴 Problem
Frontend is not connecting to WebSocket even though backend shows it should work.

## 🎯 Root Cause Analysis

There are typically **3 main reasons** why WebSocket doesn't connect in the browser:

### 1. Environment Variable Not Loaded ⚠️ **MOST COMMON**
The `NEXT_PUBLIC_WS_URL` environment variable might not be loaded because:
- The dev server wasn't restarted after adding `.env.local`
- The variable name is incorrect
- Next.js caches environment variables

### 2. Wrong WebSocket URL
If `NEXT_PUBLIC_WS_URL` isn't set, the code falls back to `ws://localhost:3000` (the frontend server) instead of `ws://localhost:8000` (the backend server).

### 3. Timing Issues
The WebSocket tries to connect before:
- The auth token is available
- The game mode data is fetched
- The round ID is set

## ✅ Step-by-Step Fix

### Step 1: Verify Environment Variables

**Option A: Check via Diagnostic Page**
1. Navigate to: http://localhost:3000/env-check
2. Look for:
   - `NEXT_PUBLIC_API_URL: http://localhost:8000/api/v1` ✅
   - `NEXT_PUBLIC_WS_URL: ws://localhost:8000` ✅
3. If either shows "❌ Not set", proceed to Step 2

**Option B: Check via Console**
1. Open browser DevTools (F12)
2. Go to Console tab
3. Type: `console.log(process.env.NEXT_PUBLIC_WS_URL)`
4. Press Enter
5. Should show: `ws://localhost:8000`

### Step 2: Restart Frontend Dev Server (CRITICAL!)

**Windows:**
```bash
# Terminal running frontend
Ctrl+C  (to stop)
cd frontend
npm run dev
```

**Linux/Mac:**
```bash
# Terminal running frontend
Ctrl+C  (to stop)
cd frontend
npm run dev
```

**Why?** Next.js only loads `.env.local` when the dev server starts. If you added/changed environment variables, you MUST restart.

### Step 3: Verify .env.local File

Check: `frontend/.env.local`

Should contain:
```env
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

**Important:**
- No quotes needed
- No spaces around `=`
- Must start with `NEXT_PUBLIC_` to be available in browser
- File must be named exactly `.env.local` (not `.env` or `env.local`)

### Step 4: Clear Browser Cache

Sometimes the browser caches old JavaScript:

**Method 1: Hard Refresh**
- Windows: `Ctrl + Shift + R` or `Ctrl + F5`
- Mac: `Cmd + Shift + R`

**Method 2: Clear Cache via DevTools**
1. Open DevTools (F12)
2. Right-click the refresh button
3. Select "Empty Cache and Hard Reload"

### Step 5: Check Console Logs

Open browser DevTools (F12) → Console tab

**You should see:**
```
[GamePage] Fetching game modes...
[GamePage] Fetched game modes: 4 active modes
[GamePage] Setting active mode to: Win Go 30s with round: [UUID]
[GamePage] Round ID updated: [UUID] Active mode: Win Go 30s
[useWebSocket] Effect triggered with roundId: [UUID]
[useWebSocket] Auth state - isAuthenticated: true hasToken: true
[useWebSocket] Connecting with roundId: [UUID] token: eyJhbGc...
[ws-client] Using NEXT_PUBLIC_WS_URL: ws://localhost:8000
[ws-client] Built WebSocket URL: ws://localhost:8000/ws/game/[UUID]?token=***
[ws-client] Creating WebSocket instance...
[ws-client] ✅ WebSocket connection OPENED
[ws-client] 📩 Received message: round_state
[ws-client] 📩 Received message: timer_tick
```

**If you see errors like:**
```
[ws-client] ❌ WebSocket ERROR: ...
[ws-client] 🔌 WebSocket connection CLOSED: code=1006
```

This means the connection is being attempted but failing. Check:
- Is backend running on port 8000?
- Is the backend WebSocket endpoint registered?
- Is there a firewall blocking port 8000?

### Step 6: Verify Backend is Running

```bash
# Test backend health
curl http://localhost:8000/api/v1/health

# Should return:
{
    "status": "ok",
    "db": "ok",
    "redis": "ok"
}
```

If this fails, start the backend:
```bash
uv run run_local.py
```

### Step 7: Check Backend Logs

When the frontend connects, backend should log:
```
INFO: Player [UUID] connected to round [UUID] (1 total in round)
```

If you see this in the backend but not in frontend console, the issue is on the frontend side (usually environment variables).

## 🧪 Testing the Fix

### Quick Test Checklist

1. ✅ Backend running: `curl http://localhost:8000/api/v1/health`
2. ✅ Celery running: `start_celery.bat` or `./start_celery.sh`
3. ✅ Frontend dev server restarted
4. ✅ Environment variables loaded: http://localhost:3000/env-check
5. ✅ Logged in to the app
6. ✅ Navigate to game page: http://localhost:3000/game
7. ✅ Open DevTools Console (F12)
8. ✅ See `[ws-client] ✅ WebSocket connection OPENED`
9. ✅ Timer counting down
10. ✅ Players/Pool showing numbers

### Detailed WebSocket Test

Use the diagnostic page:
1. Go to: http://localhost:3000/ws-test
2. Click "Test WebSocket Connection"
3. Watch the logs
4. Should see: "✅ WebSocket CONNECTED"
5. Should see incoming messages: "📩 Received: ..."

## 🔍 Common Error Messages

### "No token available, skipping connection"
**Problem:** Not logged in
**Fix:** Navigate to `/login` and login first

### "No roundId, skipping connection"
**Problem:** Game modes haven't loaded yet
**Fix:** Wait a few seconds, or check if backend is returning game modes

### "WebSocket connection CLOSED: code=1006"
**Problem:** Connection refused
**Possible causes:**
- Backend not running
- Wrong URL (check `NEXT_PUBLIC_WS_URL`)
- Firewall blocking connection
**Fix:** 
- Restart backend
- Verify environment variables
- Check if `ws://localhost:8000` is accessible

### "Using fallback: ws://localhost:3000"
**Problem:** `NEXT_PUBLIC_WS_URL` not loaded
**Fix:** Restart frontend dev server (this is the #1 issue)

## 🎬 Complete Restart Procedure

If nothing works, do a complete restart:

```bash
# Terminal 1 - Backend
Ctrl+C  (kill if running)
uv run run_local.py

# Terminal 2 - Celery
Ctrl+C  (kill if running)
start_celery.bat   # Windows
# or
./start_celery.sh  # Linux/Mac

# Terminal 3 - Frontend
Ctrl+C  (kill if running)
cd frontend
npm run dev
```

Then:
1. Clear browser cache (Ctrl+Shift+R)
2. Navigate to http://localhost:3000/env-check
3. Verify both environment variables show ✅
4. Navigate to http://localhost:3000/login
5. Login
6. Navigate to http://localhost:3000/game
7. Open DevTools Console
8. Look for `[ws-client] ✅ WebSocket connection OPENED`

## 📊 Success Indicators

You'll know it's working when:
- ✅ Console shows `[ws-client] ✅ WebSocket connection OPENED`
- ✅ Backend terminal shows `Player [UUID] connected to round [UUID]`
- ✅ Timer counts down from 30/60/180/300
- ✅ Players count shows > 0 (includes bots)
- ✅ Pool amount shows > $0.00
- ✅ Placing a bet updates Players and Pool in real-time
- ✅ Connection status (if displayed) shows "connected"

## 🆘 Still Not Working?

If you've tried everything above:

1. **Check the exact error message** in browser console
2. **Share the last 20 lines** from:
   - Browser console logs
   - Backend terminal output
3. **Verify these files exist and have correct content:**
   - `frontend/.env.local` (with `NEXT_PUBLIC_WS_URL=ws://localhost:8000`)
   - `app/api/websocket.py` (WebSocket endpoint)
   - `app/main.py` (registers `ws_router`)

4. **Try the standalone test:**
   - Open `test_websocket_connection.html` in browser
   - Get a real auth token from browser console: `useAuthStore.getState().accessToken`
   - Replace `YOUR_TOKEN_HERE` in the HTML file
   - Open the HTML file - should connect directly

## 💡 Pro Tips

- Always have DevTools Console open when debugging WebSocket
- The Network tab → WS filter only shows connections made AFTER opening DevTools
- Backend logs are more reliable than browser Network tab
- Environment variables are cached - always restart dev server after changes
- WebSocket connections happen immediately on page load (within 1-2 seconds)
- If you see timer counting down, WebSocket IS connected!

---

**Last Updated:** 2026-05-01
**Issue:** Frontend WebSocket not connecting
**Solution:** Restart frontend dev server to load NEXT_PUBLIC_WS_URL
