# Testing Checklist - WebSocket & UI Fixes

## ✅ What We Fixed

1. **Auth Guard Issue** - Waits for localStorage rehydration before redirecting
2. **Timer Countdown** - Properly initializes and counts down
3. **Bet Updates Broadcasting** - Backend now sends `bet_update` messages
4. **WebSocket Timer Sync** - Frontend properly initializes timer on connection

## 🧪 How to Test

### Prerequisites
Make sure both servers are running:
```bash
# Terminal 1 - Backend
uv run run_local.py

# Terminal 2 - Celery worker (IMPORTANT!)
start_celery.bat   # or ./start_celery.sh on Linux/Mac

# Terminal 3 - Frontend
cd frontend
npm run dev
```

### Test 1: Login Persistence (Fixed Bug #1)
1. Login to the app at http://localhost:3000/login
2. Navigate to the game page
3. **Refresh the browser (F5 or Ctrl+R)**
4. ✅ **Expected**: Should stay on the game page (no login flash)
5. ❌ **Before fix**: Would briefly show login page

### Test 2: Countdown Timer (Fixed Bug #2)
1. Go to http://localhost:3000/game
2. Open browser DevTools (F12) → Console tab
3. Look for logs like: `[GamePage] Round ID updated: ...`
4. Watch the circular countdown timer
5. ✅ **Expected**: Timer counts down from 30 (or 60, 180, 300 depending on mode)
6. ❌ **Before fix**: Timer stuck at 0

### Test 3: Players & Pool Updates (Fixed Bug #3)
1. Open the game in **TWO browser windows** side-by-side
2. In the first window, place a bet (e.g., $10 on Green)
3. Watch the second window
4. ✅ **Expected**: 
   - "Players: X" increases in the second window
   - "Pool: $Y" increases by $10 in the second window
5. ❌ **Before fix**: Players showed "1", Pool showed "$0.00"

**Note**: Players count includes bots (3-8 per round), so you might see:
- Before your bet: "Players: 5" (all bots)
- After your bet: "Players: 6" (5 bots + you)

### Test 4: WebSocket Connection
1. Open browser DevTools (F12) → Console tab
2. Navigate to http://localhost:3000/game
3. Look for these logs:
   ```
   [GamePage] Fetching game modes...
   [GamePage] Fetched game modes: 4 active modes
   [GamePage] Setting active mode to: Win Go 30s with round: [UUID]
   [GamePage] Round ID updated: [UUID]
   [useWebSocket] Effect triggered with roundId: [UUID]
   [useWebSocket] Auth state - isAuthenticated: true hasToken: true
   [useWebSocket] Connecting with roundId: [UUID] token: [first 20 chars]...
   ```
4. ✅ **Expected**: See all these logs, no errors
5. To see WebSocket in Network tab:
   - Go to DevTools → Network tab
   - Look for "WS" filter button (next to "All", "Fetch/XHR", etc.)
   - Click WS to filter only WebSocket connections
   - You should see a connection to `ws://localhost:8000/ws/game/[roundId]`

### Test 5: Backend Terminal Confirmation
If your backend terminal shows:
```
INFO: Player [UUID] connected to round [UUID] (X total in round)
```
Then the WebSocket **IS** connected! ✅

## 🔍 Troubleshooting

### Timer still at 0?
- Check console for `[useWebSocket]` logs - is it connecting?
- Check if Celery is running - it broadcasts timer ticks every second
- Run: `celery -A app.celery_app inspect active` to check Celery tasks

### Players/Pool not updating?
- Check console for errors when placing bet
- Verify the backend logs show: "Published state ... to channel:round:[UUID]"
- Check Redis is running: `redis-cli ping` should return `PONG`

### WebSocket not connecting?
- Check `[useWebSocket]` logs in console
- If it says "No token available" → Login again
- If it says "No roundId" → Wait for game modes to load (check `[GamePage]` logs)
- Navigate to http://localhost:3000/ws-test for detailed diagnostics

## 📊 Expected Behavior

**On Page Load:**
1. Game modes fetch (2-4 modes returned)
2. First mode becomes active (e.g., "Win Go 30s")
3. WebSocket connects with the active round ID
4. Initial `round_state` message received
5. Timer starts counting down
6. Players count shows (including bots)
7. Pool shows total bets

**During Betting Phase:**
1. You can click color/number buttons
2. Bet confirmation sheet appears
3. After confirming bet:
   - Your wallet balance decreases
   - "Bet placed: $X on [color]" toast appears
   - Players count increases (in all connected clients)
   - Pool amount increases (in all connected clients)

**When Round Ends:**
1. Timer reaches 0
2. Shows "Resolving..." spinner
3. Result appears (winning number & color)
4. If you won: Win dialog shows with bonus amount
5. If you lost: Loss dialog shows
6. New round starts automatically
7. Timer resets and counts down again

## 🐛 Still Having Issues?

If things still aren't working after these tests:
1. Share the console logs (copy from DevTools Console)
2. Share the backend terminal output (last 20-30 lines)
3. Describe exactly what you see vs. what's expected
4. Use the test page at http://localhost:3000/ws-test for detailed diagnostics
