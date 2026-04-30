# Testing WebSocket and Balance Issues

## Issues Fixed

1. **Balance not showing** - Added `fetchBalance()` call on game page mount
2. **WebSocket not connecting** - Created `.env.local` file in frontend directory with correct URLs

## How to Test

### Step 1: Stop Both Servers

```bash
# Stop frontend (Ctrl+C in terminal)
# Stop backend (Ctrl+C in terminal)
```

### Step 2: Verify Environment Files

**Root `.env`** (already exists):
```
APP_DATABASE_URL=your_database_url
APP_REDIS_URL=your_redis_url
APP_JWT_SECRET_KEY=your_secret_key
```

**Frontend `.env.local`** (newly created):
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

### Step 3: Start Backend

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Wait for:
```
INFO:     Database tables verified (created if missing)
INFO:     Redis connection pool initialised
INFO:     WebSocket manager started
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 4: Start Frontend

```bash
cd frontend
npm run dev
```

Wait for:
```
  ▲ Next.js 16.2.4
  - Local:        http://localhost:3000
```

### Step 5: Test Balance

1. Go to `http://localhost:3000/login`
2. Login with:
   - Email: `admin@boranikhilsingh.com`
   - Password: `Nikhil@123`
3. You should be redirected to `/game`
4. **Check**: Top of page should show "Balance: ₹1,010,000.00" (or your balance)

**If balance still shows ₹0.00:**
- Open browser console (F12)
- Check for errors
- Look for network request to `/api/v1/wallet/balance`
- Verify response shows correct balance

### Step 6: Test WebSocket

1. After logging in and seeing the game page
2. Open browser console (F12)
3. Look for console logs:
   ```
   [useWebSocket] Connecting with roundId: xxx token: eyJ...
   ```
4. Check Network tab → WS (WebSocket) connections
5. Should see connection to `ws://localhost:8000/ws/game/{round_id}?token=...`
6. Status should be "101 Switching Protocols" (green)

**If WebSocket not connecting:**
- Check console for error messages
- Verify backend is running on port 8000
- Check `NEXT_PUBLIC_WS_URL` in `.env.local`
- Restart frontend dev server

### Step 7: Test Round Updates

1. Once connected, the page should show:
   - Countdown timer (30s, 60s, etc.)
   - Current period number
   - "Players: X" and "Pool: $X"
2. Wait for timer to reach 0
3. You should see:
   - Phase change to "RESOLUTION"
   - Result displayed (winning number and color)
   - Timer resets for new round

## Troubleshooting

### Balance Shows ₹0.00

**Check 1: API Call**
```bash
# Test API directly
curl http://localhost:8000/api/v1/wallet/balance \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"
```

**Check 2: Database**
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
        wallet = result.scalar_one_or_none()
        if wallet:
            print(f'Balance: {wallet.balance}')
        else:
            print('No wallet found')

asyncio.run(check())
"
```

**Check 3: Frontend State**
- Open browser console
- Type: `useWalletStore.getState().balance`
- Should show your balance

### WebSocket Not Connecting

**Check 1: Backend WebSocket Route**
```bash
# Check if route is registered
curl http://localhost:8000/api/docs
# Look for "/ws/game/{round_id}" endpoint
```

**Check 2: Token**
- Open browser console
- Type: `useAuthStore.getState().accessToken`
- Should show a JWT token (not null)

**Check 3: Round ID**
- Open browser console
- Type: `useGameStore.getState().currentRound?.roundId`
- Should show a round ID

**Check 4: WebSocket Manager**
- Check backend logs for:
  ```
  INFO:     WebSocket manager started
  ```

### Frontend Not Loading .env.local

**Restart Required:**
Next.js only loads environment variables on startup. If you just created `.env.local`, you MUST restart the dev server:

```bash
# In frontend directory
# Press Ctrl+C to stop
npm run dev  # Start again
```

### "Module not found" Errors

```bash
# Reinstall dependencies
cd frontend
rm -rf node_modules package-lock.json
npm install
```

## Expected Behavior

### On Login
1. User logs in → tokens saved to localStorage
2. Redirected to `/game`
3. `fetchBalance()` called automatically
4. Balance loaded and displayed
5. Game modes fetched
6. Round ID determined
7. WebSocket connects with token
8. Real-time updates start flowing

### During Game
1. Timer counts down
2. Player places bet
3. Balance updates immediately (from API response)
4. Timer reaches 0
5. Backend resolves round (via Celery)
6. WebSocket receives "result" message
7. Result displayed on screen
8. If player wins, balance refetched
9. New round starts automatically

## Files Modified

1. `frontend/src/app/game/page.tsx` - Added balance fetch on mount
2. `frontend/.env.local` - Created with WS URL
3. `frontend/src/hooks/useWebSocket.ts` - Added debug logging

## Next Steps

If everything works:
1. Remove debug console.log statements from `useWebSocket.ts`
2. Consider adding loading states for balance
3. Add error handling for failed balance fetch
4. Add reconnection UI feedback

If issues persist:
1. Check backend logs for errors
2. Check frontend console for errors
3. Verify network requests in browser DevTools
4. Test with curl/Postman first
