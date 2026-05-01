# WebSocket Testing Procedure

## 🎯 Goal
Verify if WebSocket is actually connected when backend shows connection but frontend appears disconnected.

## 📋 Prerequisites

Make sure all services are running:

```bash
# Terminal 1 - Backend
uv run run_local.py
# Should see: Application startup complete.

# Terminal 2 - Celery Worker
start_celery.bat  # Windows
# or
./start_celery.sh  # Linux/Mac
# Should see: celery@HOSTNAME ready.

# Terminal 3 - Celery Beat (for timer_tick messages)
# This is included in start_celery.bat/sh
# Should see: beat: Starting...

# Terminal 4 - Frontend
cd frontend
npm run dev
# Should see: Ready in X.Xms
```

## 🧪 Test 1: Python Backend Test (Definitive)

This tests the WebSocket directly, bypassing the frontend entirely.

```bash
# Install websockets if needed
pip install websockets

# Run the test
python test_websocket_detailed.py
```

**Expected Output:**
```
[HH:MM:SS] ==========================================
[HH:MM:SS] WebSocket Connection Test
[HH:MM:SS] ==========================================
[HH:MM:SS] Testing backend health...
[HH:MM:SS] ✅ Backend health: {'status': 'ok', 'db': 'ok', 'redis': 'ok'}
[HH:MM:SS] 
[HH:MM:SS] Getting authentication token...
[HH:MM:SS] ✅ Got token: eyJhbGciOiJIUzI1NiIsInR5cCI...
[HH:MM:SS] 
[HH:MM:SS] Fetching active round ID...
[HH:MM:SS] ✅ Active round: 7ee46579-932d-458b-9bb6-87e15f307ca4 (mode: Win Go 3Min)
[HH:MM:SS] 
[HH:MM:SS] Connecting to WebSocket...
[HH:MM:SS] URL: ws://localhost:8000/ws/game/7ee46579-932d-458b-9bb6...?token=***
[HH:MM:SS] ✅ WebSocket connection ESTABLISHED
[HH:MM:SS] Waiting for messages (10 seconds)...
[HH:MM:SS] 📩 Received message #1: type=round_state
[HH:MM:SS]    Phase: betting, Timer: 28s, Players: 5
[HH:MM:SS] 📩 Received message #2: type=timer_tick
[HH:MM:SS]    Remaining: 27s
[HH:MM:SS] 📩 Received message #3: type=timer_tick
[HH:MM:SS]    Remaining: 26s
[HH:MM:SS] ✅ Received 3 messages total
```

### Interpreting Results:

**✅ If you see messages:**
- Backend WebSocket **IS working**
- Celery **IS sending** timer_tick messages
- Problem is in the frontend

**❌ If connection rejected (401):**
- Token issue
- Create test user: `python -m scripts.create_admin --email test@example.com --password testpassword`

**⚠️ If no messages received:**
- Celery is not running or not broadcasting
- Start Celery Beat: It broadcasts timer_tick every second

## 🧪 Test 2: Frontend Debug Dashboard

Navigate to: **http://localhost:3000/debug**

This shows the real-time state of all stores.

### What to Check:

1. **Authentication Section**
   - Is Authenticated: Should show `✅ Yes`
   - Has Access Token: Should show `✅ Yes`
   - If both No → Go to `/login` and login first

2. **WebSocket Section**
   - Connection Status: Should show `✅ Connected`
   - If `❌ Disconnected` → WebSocket not connecting
   - If `⏳ Connecting...` → Stuck connecting (backend issue)
   - If `🔄 Reconnecting...` → Connection dropped, retrying

3. **Game State Section**
   - Game Modes Loaded: Should show `4 modes` or similar
   - Active Mode: Should show mode name (e.g., "Win Go 30s")
   - Active Round ID: Should show a UUID
   - Timer Remaining: Should count down (28, 27, 26...)
   - If Timer shows `0` → Not receiving timer_tick messages

4. **Environment Section**
   - NEXT_PUBLIC_WS_URL: Should show `ws://localhost:8000`
   - If shows `❌ Not set` → Restart frontend dev server

### Comparison Matrix:

| Backend Logs | Frontend Debug | Diagnosis |
|--------------|----------------|-----------|
| "Player connected" | Connection: Disconnected | Frontend not updating status |
| "Player connected" | Connection: Connected, Timer: 0 | Not receiving messages |
| "Player connected" | Connection: Connected, Timer: counting | ✅ Working perfectly |
| No connection logs | Connection: Connecting... | WebSocket can't reach backend |

## 🧪 Test 3: Browser Console Inspection

Open game page: **http://localhost:3000/game**

Open DevTools: **F12** → **Console** tab

### Expected Logs:

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
[ws-client] ✅ WebSocket connection OPENED    ← KEY LOG
[ws-client] 📩 Received message: round_state  ← KEY LOG
[ws-client] 📩 Received message: timer_tick   ← KEY LOG (repeats every second)
```

### Red Flags:

**❌ `[ws-client] ❌ WebSocket ERROR`**
- Connection attempt failed
- Check if `NEXT_PUBLIC_WS_URL` is correct
- Check if backend is running: `curl http://localhost:8000/api/v1/health`

**❌ `[ws-client] 🔌 WebSocket connection CLOSED: code=1006`**
- Connection established then immediately dropped
- Code 1006 = Abnormal closure (no close frame sent)
- Usually means backend rejected the connection
- Check backend logs for errors

**❌ `[useWebSocket] ⚠️ No access token available`**
- Not logged in
- Go to `/login`

**✅ `[ws-client] ✅ WebSocket connection OPENED`**
- Connection successful!
- Should see timer_tick messages every second
- If you see this but timer isn't counting → Check game store updates

## 🧪 Test 4: Network Tab Inspection

1. Open DevTools: **F12**
2. Go to **Network** tab
3. Click **WS** filter button (filters to WebSocket only)
4. **Refresh the page** (F5)
5. Click on the WebSocket connection

### What to Check:

**Headers Tab:**
- Request URL: Should be `ws://localhost:8000/ws/game/[UUID]?token=...`
- Status: Should be `101 Switching Protocols`

**Messages Tab:**
- Shows all messages sent/received
- Should see `round_state` message on connect
- Should see `timer_tick` messages every second
- Click on a message to see its contents

### Message Flow:

```
↓ round_state   (on connect)
  - Contains: phase, timer, total_players, total_pool
  
↓ timer_tick    (every 1 second)
  - Contains: remaining (countdown)
  
↓ bet_update    (when someone places bet)
  - Contains: total_players, total_pool
  
↓ phase_change  (when round transitions)
  - Contains: phase (betting → resolution → result)
  
↓ result        (when round ends)
  - Contains: winning_color, winning_number, payouts
  
↓ new_round     (when new round starts)
  - Contains: round_id, timer
```

## 🔍 Diagnosis Decision Tree

### Scenario 1: Backend shows "Player connected", Frontend shows "Disconnected"

**Possible causes:**
1. Frontend is checking wrong connection status
2. Status polling interval issue (should poll every 500ms)
3. Game store not updating properly

**Test:**
- Check debug dashboard (`/debug`) for real connection status
- Check console for `[ws-client] ✅ WebSocket connection OPENED`
- If console shows connected → Frontend state update issue

### Scenario 2: Backend shows "Player connected", Timer not counting down

**Possible causes:**
1. Not receiving `timer_tick` messages
2. Celery Beat not running
3. Game store timer not updating

**Test:**
- Check console for `📩 Received message: timer_tick` logs
- If NO timer_tick logs → Celery Beat not running
- If YES timer_tick logs → Game store update issue
- Run Python test to verify backend is sending messages

### Scenario 3: Connection established but closes immediately

**Console shows:**
```
[ws-client] ✅ WebSocket connection OPENED
[ws-client] 🔌 WebSocket connection CLOSED: code=1006
```

**Possible causes:**
1. Backend authentication rejection (delayed)
2. Round ID invalid
3. Backend websocket handler crash

**Test:**
- Check backend terminal for errors
- Verify round ID exists: `curl http://localhost:8000/api/v1/game/rounds/[ROUND_ID]`
- Check if token is valid

### Scenario 4: No connection attempt at all

**Console shows:**
```
[useWebSocket] No roundId, skipping connection
```

**Possible causes:**
1. Game modes not loaded
2. No active round for game mode
3. API call to /game/modes failed

**Test:**
- Check debug dashboard - "Game Modes Loaded" should show > 0
- Check console for "Fetching game modes..." log
- Manually test: `curl http://localhost:8000/api/v1/game/modes`

## ✅ Success Criteria

WebSocket is **definitively connected** when ALL of these are true:

1. ✅ Python test shows: "✅ WebSocket connection ESTABLISHED"
2. ✅ Python test receives messages (timer_tick every second)
3. ✅ Browser console shows: `[ws-client] ✅ WebSocket connection OPENED`
4. ✅ Browser console shows: `📩 Received message: timer_tick` (repeating)
5. ✅ Debug dashboard shows: Connection Status: `✅ Connected`
6. ✅ Debug dashboard shows: Timer counting down (28, 27, 26...)
7. ✅ Network tab → WS filter shows active connection with messages
8. ✅ Backend logs show: "Player [UUID] connected to round [UUID]"

If **ANY** of these fail, the connection is not fully working.

## 🆘 Still Having Issues?

After running all tests:

1. **Collect evidence:**
   - Screenshot of debug dashboard (`/debug`)
   - Copy console logs (all `[ws-client]` and `[useWebSocket]` logs)
   - Copy Python test output
   - Copy last 20 lines from backend terminal

2. **Check the usual suspects:**
   - Backend running? `curl http://localhost:8000/api/v1/health`
   - Celery running? `celery -A app.celery_app inspect active`
   - Redis running? `redis-cli ping`
   - Logged in? Check debug dashboard authentication section

3. **Try clean restart:**
   - Stop all servers (Ctrl+C in each terminal)
   - Clear browser cache (Ctrl+Shift+Delete)
   - Start backend → Start Celery → Start frontend
   - Login → Navigate to /game
   - Open console BEFORE navigating

---

**Last Updated:** 2026-05-01
**For:** Diagnosing WebSocket connection discrepancies
