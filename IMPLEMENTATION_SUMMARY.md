# Profit Management System - Implementation Summary

## What Was Built

A complete profit management system that allows admins to control house profit margins dynamically. When betting payouts exceed the allocated winner pool, the system automatically reduces payouts proportionally to fit within the available pool.

## Key Features

### 1. Dynamic Profit Allocation
- Admin sets house profit % and winner pool % (must total 100%)
- Default: 20% house profit, 80% winner pool
- Example: $100,000 in bets → $20,000 house profit, $80,000 winner pool

### 2. Automatic Payout Adjustment
- Calculates all winner payouts based on odds
- If total payouts > winner pool, reduces ALL payouts proportionally
- Example: $90,000 calculated payouts vs $80,000 pool → 0.8889 reduction ratio
- All winners get: original_payout × 0.8889

### 3. Transparency & Audit
- Rounds with reduced payouts are flagged for review
- Every round records:
  - House profit amount
  - Winner pool amount
  - Total calculated payouts
  - Total actual payouts
  - Whether reduction occurred
  - Applied profit percentages

### 4. Admin Control
- Admin API to get/set profit settings
- View detailed profit breakdown for any round
- Settings change immediately for new rounds
- Historical settings preserved (not overwritten)

## Files Created/Modified

### New Files
1. **`app/services/profit_service.py`** - Core profit management logic
2. **`tests/unit/test_profit_service.py`** - Unit tests (11 tests, all passing)
3. **`PROFIT_MANAGEMENT.md`** - Complete documentation
4. **`alembic/versions/940e259016b0_add_profit_management_system.py`** - Database migration

### Modified Files
1. **`app/models/game.py`** - Added `ProfitSettings` model and profit fields to `GameRound`
2. **`app/services/game_engine.py`** - Updated `finalize_round()` to use profit management
3. **`app/schemas/admin.py`** - Added profit-related request/response schemas
4. **`app/api/admin.py`** - Added 3 new admin endpoints
5. **`CLAUDE.md`** - Updated with profit management information

## Database Changes

### New Table: `profit_settings`
```sql
- id (UUID)
- house_profit_percentage (0-100)
- winners_pool_percentage (0-100)
- is_active (boolean)
- created_at, updated_at
```

### Updated Table: `game_rounds`
```sql
+ total_payout_pool (Decimal)
+ house_profit (Decimal)
+ total_calculated_payouts (Decimal)
+ payout_reduced (Boolean)
+ applied_house_percentage (Decimal)
+ applied_winners_percentage (Decimal)
```

## API Endpoints

### 1. Get Current Profit Settings
```http
GET /api/v1/admin/profit-settings
Authorization: Bearer <admin-token>
```

Returns active profit configuration.

### 2. Update Profit Settings
```http
POST /api/v1/admin/profit-settings
Content-Type: application/json

{
  "house_profit_percentage": "25.00",
  "winners_pool_percentage": "75.00"
}
```

Creates new settings, deactivates old ones.

### 3. Get Round Profit Details
```http
GET /api/v1/admin/rounds/{round_id}/profit-details
```

Shows complete profit breakdown for a specific round.

## How It Works - Example

### Scenario: High Winning Bets

**Setup:**
- Admin sets: 20% house, 80% winners
- Total bets in round: $100,000
- House gets: $20,000
- Winner pool: $80,000

**Bets Placed:**
- 100 players bet on Green (2x odds)
- Total bet amount: $50,000
- Calculated payouts if Green wins: $100,000

**Green Wins - Payout Calculation:**
```
Total calculated payouts: $100,000
Available winner pool: $80,000
Exceeds pool by: $20,000

Reduction ratio: 80,000 / 100,000 = 0.80

All winners get 80% of their calculated payout:
- Player bet $500 → calculated win $1,000 → actual payout $800
- Player bet $1,000 → calculated win $2,000 → actual payout $1,600
```

**Round Result:**
- House profit: $20,000 (guaranteed)
- Total payouts: $80,000 (fits exactly in pool)
- `payout_reduced = true`
- `flagged_for_review = true`

### Scenario: Normal Winning Bets

**Setup:**
- Same settings (20% house, 80% winners)
- Total bets: $100,000
- Winner pool: $80,000

**Green Wins - Lower Volume:**
```
Total calculated payouts: $60,000
Available winner pool: $80,000
Fits within pool!

No reduction needed.
All winners get 100% of calculated payouts.
```

**Round Result:**
- House profit: $20,000
- Total payouts: $60,000
- Leftover pool: $20,000 (house keeps this too)
- `payout_reduced = false`
- `flagged_for_review = false`

## Business Logic

### Round Finalization Flow (Updated)

```python
async def finalize_round(session, round_id):
    # 1. Get round and game mode
    game_round = fetch_round(round_id)
    game_mode = fetch_game_mode(game_round.game_mode_id)
    
    # 2. Calculate profit allocation
    total_bets = game_round.total_bets  # e.g., $100,000
    profit_allocation = calculate_profit_allocation(total_bets)
    # house_profit: $20,000
    # winner_pool: $80,000
    
    # 3. Calculate all winner payouts (based on odds)
    payout_results = calculate_round_payouts(
        round_id, winning_color, odds
    )
    total_calculated = sum(pr.amount for pr in payout_results if pr.is_winner)
    # e.g., $90,000
    
    # 4. Adjust if needed
    adjustment = adjust_payouts_to_pool(total_calculated, winner_pool)
    # reduction_ratio: 0.8889
    # payout_reduced: True
    
    # 5. Credit winners with adjusted amounts
    for payout_result in payout_results:
        if payout_result.is_winner:
            adjusted = payout_result.amount * adjustment.reduction_ratio
            credit_wallet(payout_result.player_id, adjusted)
            create_payout_record(adjusted)
    
    # 6. Update round with profit details
    game_round.house_profit = profit_allocation.house_profit_amount
    game_round.total_payout_pool = profit_allocation.winner_pool_amount
    game_round.total_calculated_payouts = total_calculated
    game_round.total_payouts = sum(adjusted_payouts)
    game_round.payout_reduced = adjustment.payout_reduced
    game_round.flagged_for_review = adjustment.payout_reduced
```

## Testing

All tests pass successfully:

```bash
uv run pytest tests/unit/test_profit_service.py -v

✓ test_get_active_profit_settings_none
✓ test_get_active_profit_settings
✓ test_calculate_profit_allocation_default
✓ test_calculate_profit_allocation_custom
✓ test_adjust_payouts_no_reduction
✓ test_adjust_payouts_with_reduction
✓ test_adjust_payouts_exact_match
✓ test_create_profit_settings
✓ test_create_profit_settings_deactivates_old
✓ test_create_profit_settings_validation_sum
✓ test_create_profit_settings_validation_negative

11 passed in 1.61s
```

## Migration Steps

### 1. Apply Database Migration
```bash
uv run alembic upgrade head
```

### 2. Create Initial Profit Settings (Optional)
```bash
curl -X POST http://localhost:8000/api/v1/admin/profit-settings \
  -H "Authorization: Bearer <admin-token>" \
  -H "Content-Type: application/json" \
  -d '{
    "house_profit_percentage": "20.00",
    "winners_pool_percentage": "80.00"
  }'
```

If no settings are created, system uses default 20/80 split.

### 3. Monitor Results
Check rounds for profit details:
```bash
curl http://localhost:8000/api/v1/admin/rounds/{round_id}/profit-details \
  -H "Authorization: Bearer <admin-token>"
```

## Benefits

### For Platform
1. **Guaranteed Profit**: House always gets configured percentage
2. **Risk Management**: Payouts can never exceed allocated pool
3. **Flexibility**: Adjust margins anytime (promotions, events)
4. **Transparency**: Complete audit trail of all profit decisions

### For Players
1. **Fair Distribution**: If payouts are reduced, ALL winners affected equally
2. **Predictable**: Same reduction ratio for everyone
3. **Visibility**: (Can add UI to show house margin)

### For Admins
1. **Real-time Control**: Change settings instantly
2. **Detailed Reporting**: See exactly what happened in each round
3. **Flagged Rounds**: Automatic alerts for investigation
4. **Historical Data**: All settings changes preserved

## Future Enhancements

1. **Real-time Alerts**: Notify admins when payouts are reduced
2. **Dynamic Odds**: Adjust odds automatically to reduce reduction frequency
3. **Player Communication**: Show reduction info in payout notifications
4. **Analytics Dashboard**: Visualize profit trends, reduction frequency
5. **Per-Game-Mode Settings**: Different margins for different game types
6. **Maximum Reduction Cap**: Limit how much payouts can be reduced
7. **Progressive Pools**: Carry over unused winner pool to next round

## Security Considerations

1. **Admin Only**: All profit endpoints require `is_admin = true`
2. **Validation**: Percentages must sum to exactly 100
3. **Audit Trail**: All settings changes logged
4. **Decimal Precision**: Uses `Decimal` for exact calculations
5. **Atomicity**: Entire finalization process in one transaction

## Documentation

- **PROFIT_MANAGEMENT.md**: Complete guide with examples
- **CLAUDE.md**: Updated with profit management info
- **API docs**: Available at `/api/docs` (Swagger UI)
- **Code comments**: Detailed docstrings in all functions

## Rollback Plan

If needed, rollback the migration:
```bash
uv run alembic downgrade -1
```

This removes:
- `profit_settings` table
- New columns from `game_rounds`

Old behavior resumes (payouts not reduced, only flagged if exceed threshold).
