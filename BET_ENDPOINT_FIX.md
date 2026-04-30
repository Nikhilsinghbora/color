# Bet Endpoint 404 Error - FIXED ✅

## Problem

Getting `404 Not Found` when trying to place a bet:
```
INFO: 127.0.0.1:61357 - "POST /api/v1/game/bet HTTP/1.1" 404 Not Found
```

## Root Cause

**Frontend-Backend API Mismatch**

**Frontend was calling:**
```typescript
POST /api/v1/game/bet
Body: {
  round_id: "xxx",
  color: "green",
  amount: "100"
}
```

**Backend expects:**
```python
POST /api/v1/game/rounds/{round_id}/bet
Body: {
  color: "green",
  amount: "100"
}
```

The `round_id` should be in the URL path, not the request body!

## Solution

### Fixed File
`frontend/src/app/game/page.tsx` - Line 204

**Before:**
```typescript
const { data } = await apiClient.post<BetResponse>('/game/bet', {
  round_id: effectiveRoundId,
  color,
  amount,
});
```

**After:**
```typescript
const { data } = await apiClient.post<BetResponse>(`/game/rounds/${effectiveRoundId}/bet`, {
  color,
  amount,
});
```

## How to Test

### Step 1: Restart Frontend
The frontend code has changed, so you need to restart:

```bash
cd frontend
# Press Ctrl+C to stop
npm run dev  # Start again
```

### Step 2: Clear Browser Cache
1. Open DevTools (F12)
2. Right-click refresh button → "Empty Cache and Hard Reload"
3. Or: Application → Clear storage → Clear site data

### Step 3: Test Betting
1. Go to `http://localhost:3000/game`
2. Click any bet button (Green/Red/Violet/Number)
3. Confirm bet
4. ✅ Should work now!

### Step 4: Verify in Console
Open browser console (F12) and check Network tab:
- Should see: `POST /api/v1/game/rounds/{uuid}/bet`
- Status should be: `200 OK` (not 404)
- Response should contain bet details

## Expected Behavior

### Successful Bet Response
```json
{
  "id": "bet-uuid",
  "player_id": "player-uuid",
  "round_id": "round-uuid",
  "color": "green",
  "amount": "100.00",
  "odds_at_placement": "2.00",
  "balance_after": "999900.00",
  "created_at": "2026-04-30T07:00:00Z"
}
```

### What Happens After Fix
1. ✅ Click bet button
2. ✅ Bet confirmation sheet opens
3. ✅ Confirm bet
4. ✅ API call succeeds (200 OK)
5. ✅ Balance decreases immediately
6. ✅ Bet appears in placed bets list
7. ✅ Toast notification: "Bet placed: $100 on green"

## Backend Endpoint Reference

```python
@router.post("/rounds/{round_id}/bet", response_model=BetResponse)
async def place_bet(
    round_id: UUID,              # From URL path
    body: PlaceBetRequest,       # From request body
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
):
    """Place a bet on a color for a given round."""
    ...
```

**PlaceBetRequest schema:**
```python
class PlaceBetRequest(BaseModel):
    color: str = Field(..., min_length=1, max_length=20)
    amount: Decimal = Field(..., gt=0, decimal_places=2)
```

## Troubleshooting

### Still getting 404?

**Check 1: Frontend restarted?**
```bash
# Must restart for code changes to take effect
cd frontend
npm run dev
```

**Check 2: Round ID valid?**
Open browser console and check:
```javascript
// Should show a valid UUID
useGameStore.getState().currentRound?.roundId
```

If `undefined`, no round is loaded. Run:
```bash
python -m scripts.start_rounds
```

**Check 3: API base URL correct?**
Check `frontend/.env.local`:
```
NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1
```

**Check 4: Backend running?**
```bash
# Should show backend is running
curl http://localhost:8000/api/v1/health
```

### Getting different errors?

**400 Bad Request - "INSUFFICIENT_BALANCE"**
- Your balance is too low
- Add more: `python -m scripts.add_currency --amount 100000 --email your@email.com --confirm`

**400 Bad Request - "BET_LIMIT_ERROR"**
- Amount is below minimum or above maximum
- Check game mode limits (usually min: ₹1, max: ₹10,000)

**409 Conflict - "BETTING_CLOSED"**
- Round is no longer in BETTING phase
- Wait for new round or refresh page

**401 Unauthorized - "TOKEN_EXPIRED"**
- Your session expired
- Log out and log back in

## Complete Setup Checklist

Before testing bets:
- ✅ Backend running on port 8000
- ✅ Frontend running on port 3000
- ✅ Database connected (Supabase)
- ✅ Redis connected (Upstash)
- ✅ Game modes seeded (`python -m scripts.seed_data`)
- ✅ Rounds created (`python -m scripts.start_rounds`)
- ✅ User has balance (check admin account: ₹1,010,000)
- ✅ Frontend restarted after code fix
- ✅ Browser cache cleared

## Summary

- ✅ **Issue**: Wrong API endpoint path in frontend
- ✅ **Fix**: Changed `/game/bet` to `/game/rounds/{round_id}/bet`
- ✅ **Action Required**: Restart frontend dev server
- ✅ **Test**: Place a bet and verify it works

**Betting should work now after frontend restart! 🎰**
