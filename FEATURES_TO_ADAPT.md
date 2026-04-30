# Features to Adapt from 51Game WinGo Repository

After analyzing the 51Game WinGo repository, here are the specific features and patterns worth adapting to our Python implementation:

---

## ✅ High Priority - Implement These

### 1. **Big/Small Betting**
**What:** Bet on whether the winning number will be Big (5-9) or Small (0-4)

**Their Implementation:**
```javascript
// 2x payout for Big/Small bets
{ randomNumber: 7, isBig: true }   // Big: 5-9
{ randomNumber: 2, isBig: false }  // Small: 0-4
```

**How to Add to Ours:**
```python
# In app/services/payout_calculator.py
def _is_big_small_winner(bet_choice: str, winning_number: int) -> bool:
    """Determine if a big/small bet wins."""
    if bet_choice == "big":
        return winning_number >= 5  # 5,6,7,8,9
    elif bet_choice == "small":
        return winning_number <= 4  # 0,1,2,3,4
    return False

# In calculate_round_payouts()
if bet.color in ["big", "small"]:
    is_winner = _is_big_small_winner(bet.color, winning_number)
    if is_winner:
        big_small_odds = Decimal(str(odds.get("big_small", 2)))
        payout_amount = calculate_payout(bet.amount, big_small_odds)
```

**Effort:** 30 minutes
**Value:** ⭐⭐⭐⭐⭐ (Core game feature)

---

### 2. **Predictable Period Numbers (Issue Numbers)**
**What:** Generate deterministic period numbers based on date + time

**Their Implementation:**
```javascript
// Format: YYYYMMDD + 1000 + (50001 + period_index)
// Example: 20250428100051143
function formatIssueNumber(date, totalPeriods) {
    const year = date.getUTCFullYear();
    const month = String(date.getUTCMonth() + 1).padStart(2, '0');
    const day = String(date.getUTCDate()).padStart(2, '0');
    return `${year}${month}${day}1000${50001 + totalPeriods}`;
}

// Calculate period index for 1-minute intervals: 1440 per day
function calculateTotalPeriods(date, interval) {
    const hours = date.getUTCHours();
    const minutes = date.getUTCMinutes();
    const seconds = date.getUTCSeconds();
    
    if (interval === 30000) { // 30s
        return hours * 120 + minutes * 2 + Math.floor(seconds / 30);
    }
    if (interval === 60000) { // 1m
        return hours * 60 + minutes;
    }
    // etc...
}
```

**How to Add to Ours:**
```python
# In app/services/game_engine.py or new app/services/period_service.py
from datetime import datetime, timezone

def generate_period_number(
    created_at: datetime,
    interval_seconds: int
) -> str:
    """Generate deterministic period number.
    
    Format: YYYYMMDD + 1000 + (50001 + period_index)
    Example: 20250428100051143
    """
    utc_time = created_at.astimezone(timezone.utc)
    
    # Date part
    date_str = utc_time.strftime("%Y%m%d")
    
    # Calculate period index within the day
    seconds_since_midnight = (
        utc_time.hour * 3600 +
        utc_time.minute * 60 +
        utc_time.second
    )
    period_index = seconds_since_midnight // interval_seconds
    
    # Format: YYYYMMDD + 1000 + (50001 + index)
    period_number = f"{date_str}1000{50001 + period_index}"
    
    return period_number

# Usage in start_round()
game_round = GameRound(
    game_mode_id=game_mode_id,
    phase=RoundPhase.BETTING,
    betting_ends_at=betting_ends_at,
    period_number=generate_period_number(
        datetime.now(timezone.utc),
        game_mode.round_duration_seconds
    )
)
```

**Database Migration:**
```sql
ALTER TABLE game_rounds ADD COLUMN period_number VARCHAR(50) UNIQUE;
```

**Effort:** 1 hour
**Value:** ⭐⭐⭐⭐ (Better UX, easy to reference rounds)

---

### 3. **Sound Effects**
**What:** Audio feedback for betting actions and results

**Their Assets:**
```
/assets/mp3/di1-0f3d86cb.mp3  - Betting click sound
/assets/mp3/di2-ad9aa8fb.mp3  - Win/result sound
```

**How to Add to Ours:**
```typescript
// In frontend/src/hooks/useGameAudio.ts
export function useGameAudio() {
  const betSound = new Audio('/sounds/bet-click.mp3');
  const winSound = new Audio('/sounds/win-result.mp3');
  const timerSound = new Audio('/sounds/timer-tick.mp3');
  
  const playBetSound = () => betSound.play();
  const playWinSound = () => winSound.play();
  const playTimerSound = () => timerSound.play();
  
  return { playBetSound, playWinSound, playTimerSound };
}

// In components/BettingControls.tsx
const { playBetSound } = useGameAudio();

const handleBet = async () => {
  playBetSound();
  await placeBet(...);
};
```

**Effort:** 2 hours (find/create sounds + implement)
**Value:** ⭐⭐⭐⭐ (Better UX)

---

### 4. **Client-Side Caching with TTL**
**What:** Cache API responses for 30 seconds to reduce server load

**Their Implementation:**
```javascript
const gameCache = new Map();
const CACHE_DURATION = 30000; // 30 seconds

async function prefetchGameData(gameData) {
  const cacheKey = `game_${gameData.typeId}`;
  const now = Date.now();
  const cached = gameCache.get(cacheKey);

  // Return cached data if valid
  if (cached && now - cached.timestamp < CACHE_DURATION) {
    return cached.data;
  }

  const response = await getGameIssue(params);
  gameCache.set(cacheKey, {
    data: response.data,
    timestamp: now
  });
  return response.data;
}

// Clean up expired cache periodically
setInterval(() => {
  const now = Date.now();
  for (const [key, value] of gameCache.entries()) {
    if (now - value.timestamp > CACHE_DURATION) {
      gameCache.delete(key);
    }
  }
}, CACHE_DURATION);
```

**How to Add to Ours:**
```typescript
// In frontend/src/lib/apiCache.ts
interface CacheEntry<T> {
  data: T;
  timestamp: number;
}

class APICache {
  private cache = new Map<string, CacheEntry<any>>();
  private ttl = 30000; // 30 seconds

  get<T>(key: string): T | null {
    const entry = this.cache.get(key);
    if (!entry) return null;
    
    if (Date.now() - entry.timestamp > this.ttl) {
      this.cache.delete(key);
      return null;
    }
    
    return entry.data;
  }

  set<T>(key: string, data: T): void {
    this.cache.set(key, {
      data,
      timestamp: Date.now()
    });
  }

  cleanup(): void {
    const now = Date.now();
    for (const [key, entry] of this.cache.entries()) {
      if (now - entry.timestamp > this.ttl) {
        this.cache.delete(key);
      }
    }
  }
}

export const apiCache = new APICache();
setInterval(() => apiCache.cleanup(), 30000);

// Usage in API calls
export async function getRoundState(roundId: string) {
  const cacheKey = `round:${roundId}`;
  const cached = apiCache.get(cacheKey);
  if (cached) return cached;

  const response = await fetch(`/api/v1/game/rounds/${roundId}`);
  const data = await response.json();
  apiCache.set(cacheKey, data);
  return data;
}
```

**Effort:** 1 hour
**Value:** ⭐⭐⭐⭐ (Reduces server load)

---

### 5. **Multiple Game Mode Tabs**
**What:** UI to switch between different interval modes (30s, 1m, 3m, 5m)

**Their Implementation:**
```javascript
const GAME_DETAILS = {
  "Win Go 30s": { typeId: 30, interval: 30000 },
  "Win Go 1Min": { typeId: 1, interval: 60000 },
  "Win Go 3Min": { typeId: 2, interval: 180000 },
  "Win Go 5Min": { typeId: 3, interval: 300000 },
};

// UI: Tabs to switch between modes
gameItems.forEach(item => {
  item.addEventListener('click', () => {
    const textContent = item.textContent.trim();
    handleGameItemClicked(textContent);
  });
});
```

**How to Add to Ours:**
```typescript
// In frontend/src/components/GameModeTabs.tsx
const GAME_MODES = [
  { id: '30s', name: '30 Sec', interval: 30 },
  { id: '1m', name: '1 Min', interval: 60 },
  { id: '3m', name: '3 Min', interval: 180 },
  { id: '5m', name: '5 Min', interval: 300 },
];

export function GameModeTabs() {
  const [activeMode, setActiveMode] = useState('1m');
  const { data: gameModes } = useQuery('/api/v1/game/modes');

  return (
    <div className="flex gap-2 mb-4">
      {GAME_MODES.map(mode => (
        <button
          key={mode.id}
          className={`px-4 py-2 rounded ${
            activeMode === mode.id ? 'bg-primary text-white' : 'bg-gray-200'
          }`}
          onClick={() => setActiveMode(mode.id)}
        >
          {mode.name}
        </button>
      ))}
    </div>
  );
}
```

**Backend:**
Already supported! Just need to seed game modes:
```sql
INSERT INTO game_modes (name, mode_type, round_duration_seconds, ...) VALUES
  ('Win Go 30s', 'wingo', 30, ...),
  ('Win Go 1 Min', 'wingo', 60, ...),
  ('Win Go 3 Min', 'wingo', 180, ...),
  ('Win Go 5 Min', 'wingo', 300, ...);
```

**Effort:** 2 hours
**Value:** ⭐⭐⭐⭐⭐ (Better UX, more game options)

---

### 6. **Progressive Retry with Exponential Backoff**
**What:** Retry failed API calls with increasing delays

**Their Implementation:**
```javascript
async function startNewGameCycle(gameData, retryCount = 0) {
  try {
    apiResponse = await Promise.race([
      getGameIssue(params),
      new Promise((_, reject) => 
        setTimeout(() => reject(new Error('Timeout')), 3000)
      )
    ]);
  } catch (error) {
    // Progressive retry with backoff
    const retryDelay = Math.min(1000 * Math.pow(1.5, retryCount), 5000);
    setTimeout(() => {
      startNewGameCycle(gameData, retryCount + 1);
    }, retryDelay);
  }
}
```

**How to Add to Ours:**
```typescript
// In frontend/src/lib/apiClient.ts
async function fetchWithRetry<T>(
  url: string,
  options: RequestInit = {},
  maxRetries = 3
): Promise<T> {
  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 3000);

      const response = await fetch(url, {
        ...options,
        signal: controller.signal
      });

      clearTimeout(timeout);

      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      return await response.json();

    } catch (error) {
      if (attempt === maxRetries) throw error;

      // Exponential backoff: 1s, 1.5s, 2.25s, ...
      const delay = Math.min(1000 * Math.pow(1.5, attempt), 5000);
      await new Promise(resolve => setTimeout(resolve, delay));
    }
  }
  throw new Error('Max retries exceeded');
}
```

**Effort:** 1 hour
**Value:** ⭐⭐⭐ (Better reliability)

---

## ⚠️ Medium Priority - Consider These

### 7. **Prefetch Next Round Data**
**What:** Load next round data before current round ends

**Their Implementation:**
```javascript
// Start prefetching 3 seconds before round ends
setTimeout(() => {
  prefetchGameData(gameData).catch(console.error);
}, Math.max(100, gameData.interval - 3000));
```

**How to Add to Ours:**
```typescript
// In frontend/src/hooks/useRoundPrefetch.ts
export function useRoundPrefetch(currentRound: GameRound) {
  useEffect(() => {
    const timeUntilEnd = new Date(currentRound.betting_ends_at).getTime() - Date.now();
    const prefetchDelay = Math.max(0, timeUntilEnd - 3000);

    const timer = setTimeout(() => {
      // Prefetch next round (will be auto-created by backend)
      queryClient.prefetchQuery(['round', 'next'], fetchNextRound);
    }, prefetchDelay);

    return () => clearTimeout(timer);
  }, [currentRound]);
}
```

**Effort:** 1 hour
**Value:** ⭐⭐⭐ (Smoother UX)

---

### 8. **requestAnimationFrame for UI Updates**
**What:** Use browser's animation frame for smoother updates

**Their Implementation:**
```javascript
requestAnimationFrame(() => {
  if (period_number) period_number.innerHTML = issueNumber;
  startCountdown(new Date(endTime), params, issueNumber);
});
```

**How to Add to Ours:**
```typescript
// In frontend/src/components/CountdownTimer.tsx
export function CountdownTimer({ endTime }: Props) {
  const [timeLeft, setTimeLeft] = useState(0);
  const rafRef = useRef<number>();

  useEffect(() => {
    const updateTimer = () => {
      const now = Date.now();
      const end = new Date(endTime).getTime();
      const remaining = Math.max(0, end - now);

      setTimeLeft(remaining);

      if (remaining > 0) {
        rafRef.current = requestAnimationFrame(updateTimer);
      }
    };

    rafRef.current = requestAnimationFrame(updateTimer);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
    };
  }, [endTime]);

  return <div>{formatTime(timeLeft)}</div>;
}
```

**Effort:** 30 minutes
**Value:** ⭐⭐⭐ (Smoother animations)

---

## ❌ Low Priority - Already Have Better

### 9. ~~Offline Mode~~
**Why Skip:** We have real-time WebSocket updates and Celery-driven rounds. Their offline mode is a workaround for no backend.

### 10. ~~Client-side RNG~~
**Why Skip:** We have server-side cryptographically secure RNG with audit trail. Their client-side RNG is not provably fair.

### 11. ~~LocalStorage Balance~~
**Why Skip:** We have proper database-backed wallet system with atomic transactions.

---

## 🎨 UI/UX Elements to Adapt

### Visual Design Patterns
1. **Color-coded betting buttons** (Red/Green/Violet colors)
2. **Number grid layout** (0-9 in attractive grid)
3. **Big/Small indicator** on results
4. **Period number display** (prominent at top)
5. **Countdown timer** (large, visible)
6. **Win amount animation** (celebration effect)
7. **Recent results history** (colored dots showing last 10 results)

### Animations
1. **Bet placement feedback** (button press animation)
2. **Timer urgency** (pulse when <10 seconds left)
3. **Result reveal** (spinning animation to reveal number)
4. **Win celebration** (confetti/fireworks for big wins)

---

## Implementation Priority

### Sprint 1 (Week 1)
1. ✅ Big/Small betting logic (30 min)
2. ✅ Period number generation (1 hour)
3. ✅ Multiple game mode tabs UI (2 hours)

### Sprint 2 (Week 2)
4. ✅ Sound effects integration (2 hours)
5. ✅ Client-side caching with TTL (1 hour)
6. ✅ Progressive retry with backoff (1 hour)

### Sprint 3 (Week 3)
7. ✅ Prefetch next round data (1 hour)
8. ✅ requestAnimationFrame timers (30 min)
9. ✅ UI/UX polish (animations, sounds, colors)

---

## Summary

**Must Implement:**
- ✅ Big/Small betting (core feature)
- ✅ Period numbers (better UX)
- ✅ Game mode tabs (more options)
- ✅ Sound effects (engagement)

**Nice to Have:**
- ✅ Client-side caching (performance)
- ✅ Retry with backoff (reliability)
- ✅ Prefetch rounds (smooth UX)
- ✅ RAF animations (polish)

**Already Better:**
- ✅ Backend architecture
- ✅ Database persistence
- ✅ Real-time sync
- ✅ Profit management
- ✅ Security & auth

**Total Effort:** ~12 hours to implement all high-priority features
**Expected Impact:** Significant UX improvement + feature parity with 51Game
