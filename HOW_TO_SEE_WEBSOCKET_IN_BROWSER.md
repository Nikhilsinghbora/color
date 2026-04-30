# How to See WebSocket Connections in Browser DevTools

## 🔍 Finding WebSocket Connections in Chrome/Edge DevTools

### Method 1: Network Tab with WS Filter
1. Open the game page: http://localhost:3000/game
2. Open DevTools: **F12** or **Ctrl+Shift+I**
3. Click the **Network** tab
4. Look for the filter buttons at the top (All, Fetch/XHR, JS, CSS, etc.)
5. Click **WS** button (WebSocket filter)
   - If you don't see WS button, the connection hasn't been made yet
6. **Refresh the page (F5)** while Network tab is open
7. You should see: `game/[UUID]` with status `101 Switching Protocols`

### Method 2: Check Before Page Load
WebSocket connections **only appear in the Network tab if the tab was open when the connection was made**!

**Wrong way:**
1. Load the page
2. Open DevTools
3. Go to Network tab
4. ❌ WebSocket not shown (it connected before you opened DevTools)

**Right way:**
1. Open DevTools **first** (F12)
2. Go to Network tab
3. **Then** load/refresh the page (F5)
4. ✅ WebSocket connection appears

### Method 3: Console Inspection
1. Open DevTools (F12)
2. Go to **Console** tab
3. Type this and press Enter:
```javascript
// Check game store connection status
useGameStore.getState().connectionStatus
```
4. Should return: `"connected"` if WebSocket is working

### Method 4: Live Message Monitoring
1. Open DevTools (F12) → Console tab
2. Paste this code and press Enter:
```javascript
// Monitor WebSocket messages in real-time
const originalLog = console.log;
console.log = function(...args) {
  originalLog.apply(console, args);
  if (args[0] && typeof args[0] === 'string' && args[0].includes('useWebSocket')) {
    originalLog('%c📡 WebSocket Event', 'color: cyan; font-weight: bold', ...args);
  }
};
originalLog('✅ WebSocket monitoring enabled - watch for cyan logs');
```
3. You should see cyan-colored logs for all WebSocket events

## 🎯 What You Should See

### Backend Terminal (Your Terminal Shows This Already!)
```
INFO: Player 45365d88-a343-479a-ac6a-8237dee20c46 connected to round 7ee46579-932d-458b-9bb6-87e15f307ca4 (1 total in round)
```
✅ **This means the WebSocket IS connected!**

### Browser Console Logs
```
[GamePage] Fetching game modes...
[GamePage] Fetched game modes: 4 active modes  
[GamePage] Setting active mode to: Win Go 3Min with round: 7ee46579-932d-458b-9bb6-87e15f307ca4
[useWebSocket] Effect triggered with roundId: 7ee46579-932d-458b-9bb6-87e15f307ca4
[useWebSocket] Auth state - isAuthenticated: true hasToken: true
[useWebSocket] Connecting with roundId: 7ee46579-932d-458b-9bb6-87e15f307ca4 token: eyJhbGciOiJIUzI1NiIs...
```

### Browser Network Tab (WS Filter)
```
Name                  Status    Type        Size
game/[UUID]          101       websocket   [live]
```

Click on it to see:
- **Headers** tab: Request URL, Protocol Upgrade details
- **Messages** tab: All messages sent/received (timer_tick, bet_update, etc.)
- **Timing** tab: Connection timing

## 🚨 Common Misconceptions

### "I don't see WebSocket in Network tab"
This could mean:
1. ✅ **Network tab wasn't open when connection was made** (Most common!)
   - Solution: Open Network tab, then refresh (F5)
2. ✅ **The connection is there but not filtered**
   - Solution: Click the "WS" filter button
3. ❌ **Actually not connecting** (Rare if backend shows connection)
   - Check console for errors

### Backend Shows Connection But Browser Doesn't?
**This is NORMAL!** The browser's Network tab only shows connections made **after** you opened the tab. Your WebSocket IS working if:
- Backend terminal shows "Player connected"  
- Timer is counting down
- You can place bets
- Players/Pool numbers update

The Network tab is just a **monitoring tool**, not a requirement for WebSocket to work!

## 🔧 Quick Debug Commands

Run these in the browser Console (F12) to check WebSocket status:

```javascript
// 1. Check connection status
useGameStore.getState().connectionStatus
// Should return: "connected"

// 2. Check current round state
useGameStore.getState().currentRound
// Should show: { roundId: "...", phase: "betting", timer: 28, ... }

// 3. Check timer
useGameStore.getState().timerRemaining
// Should show: number between 0-30 (or 60, 180, 300)

// 4. Check auth
useAuthStore.getState().isAuthenticated
// Should return: true

// 5. Force refresh game state (if needed)
window.location.reload()
```

## ✅ Verification Checklist

If you see ANY of these, WebSocket is working:
- [ ] Backend terminal shows "Player connected to round"
- [ ] Browser console shows "[useWebSocket] Connecting with roundId"
- [ ] Timer counts down from 30/60/180/300
- [ ] Players count shows a number > 0
- [ ] Pool amount updates when you place a bet
- [ ] You can place bets and see confirmation
- [ ] Result appears when round ends

If you see ALL of these ✅, then **WebSocket is working perfectly** even if you don't see it in the Network tab!

## 📱 Pro Tip: Watch Messages Live

1. Open DevTools → Network → WS filter
2. Refresh page (F5)
3. Click on the WebSocket connection
4. Click **Messages** tab
5. Watch live messages:
   - `timer_tick` every second (remaining: 29, 28, 27...)
   - `bet_update` when someone places a bet
   - `phase_change` when round transitions
   - `result` when round completes
   - `new_round` when new round starts

This is the best way to debug WebSocket issues!
