# Profit Management System

## Overview

The profit management system allows admins to control the house profit margin and winner pool distribution. When total payouts exceed the allocated winner pool, payouts are automatically reduced proportionally so winners share only the available pool.

## How It Works

### 1. Profit Allocation

Total bets are split into two pools:
- **House Profit**: Platform's revenue (e.g., 20%)
- **Winner Pool**: Available for winner payouts (e.g., 80%)

**Example**:
```
Total bets: $100,000
House profit (20%): $20,000
Winner pool (80%): $80,000
```

### 2. Payout Calculation

The system calculates winner payouts based on odds:
```
Player A bets $1,000 on Green (2x odds) → wins → $2,000 payout
Player B bets $500 on Green (2x odds) → wins → $1,000 payout
...
Total calculated payouts: $90,000
```

### 3. Payout Adjustment

If calculated payouts exceed the winner pool, they're reduced proportionally:

**Scenario 1: Payouts fit within pool**
```
Total calculated payouts: $70,000
Winner pool: $80,000
Result: Winners get full calculated amounts (no reduction)
```

**Scenario 2: Payouts exceed pool**
```
Total calculated payouts: $90,000
Winner pool: $80,000
Reduction ratio: 80,000 / 90,000 = 0.8889

Player A's adjusted payout: $2,000 × 0.8889 = $1,777.78
Player B's adjusted payout: $1,000 × 0.8889 = $888.89
...
Total actual payouts: $80,000 (fits exactly in pool)
```

### 4. Round Flagging

Rounds where payouts are reduced are automatically flagged for admin review (`flagged_for_review = true`).

## Database Schema

### New Table: `profit_settings`

Stores profit margin configurations:

```sql
CREATE TABLE profit_settings (
    id UUID PRIMARY KEY,
    house_profit_percentage NUMERIC(5,2) NOT NULL,  -- e.g., 20.00
    winners_pool_percentage NUMERIC(5,2) NOT NULL,  -- e.g., 80.00
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT total_percentage_is_100 CHECK (
        house_profit_percentage + winners_pool_percentage = 100
    )
);
```

### Updated Table: `game_rounds`

New fields track profit details for each round:

```sql
ALTER TABLE game_rounds ADD COLUMN total_payout_pool NUMERIC(14,2);
ALTER TABLE game_rounds ADD COLUMN house_profit NUMERIC(14,2);
ALTER TABLE game_rounds ADD COLUMN total_calculated_payouts NUMERIC(14,2);
ALTER TABLE game_rounds ADD COLUMN payout_reduced BOOLEAN DEFAULT FALSE;
ALTER TABLE game_rounds ADD COLUMN applied_house_percentage NUMERIC(5,2);
ALTER TABLE game_rounds ADD COLUMN applied_winners_percentage NUMERIC(5,2);
```

## API Endpoints

### Get Current Profit Settings

```http
GET /api/v1/admin/profit-settings
Authorization: Bearer <admin-token>
```

**Response**:
```json
{
  "id": "uuid",
  "house_profit_percentage": "20.00",
  "winners_pool_percentage": "80.00",
  "is_active": true,
  "created_at": "2026-04-28T...",
  "updated_at": "2026-04-28T..."
}
```

### Create/Update Profit Settings

```http
POST /api/v1/admin/profit-settings
Authorization: Bearer <admin-token>
Content-Type: application/json

{
  "house_profit_percentage": "25.00",
  "winners_pool_percentage": "75.00"
}
```

**Response** (201 Created):
```json
{
  "id": "uuid",
  "house_profit_percentage": "25.00",
  "winners_pool_percentage": "75.00",
  "is_active": true,
  "created_at": "2026-04-28T...",
  "updated_at": "2026-04-28T..."
}
```

### Get Round Profit Details

```http
GET /api/v1/admin/rounds/{round_id}/profit-details
Authorization: Bearer <admin-token>
```

**Response**:
```json
{
  "round_id": "uuid",
  "total_bets": "100000.00",
  "total_payout_pool": "80000.00",
  "house_profit": "20000.00",
  "total_calculated_payouts": "90000.00",
  "total_actual_payouts": "80000.00",
  "payout_reduced": true,
  "applied_house_percentage": "20.00",
  "applied_winners_percentage": "80.00",
  "flagged_for_review": true
}
```

## Configuration

### Default Settings

If no profit settings are configured, the system uses defaults:
- **House profit**: 20%
- **Winner pool**: 80%

### Changing Settings

1. Admin creates new settings via API
2. Old settings are automatically deactivated (`is_active = false`)
3. New settings apply to all future rounds
4. In-progress rounds use the settings active when they started

## Business Logic Flow

### During Round Finalization

```python
# 1. Calculate profit allocation
house_profit = total_bets × house_percentage
winner_pool = total_bets × winners_percentage

# 2. Calculate all winner payouts based on odds
total_calculated_payouts = sum(bet.amount × bet.odds for all winning bets)

# 3. Check if adjustment needed
if total_calculated_payouts > winner_pool:
    reduction_ratio = winner_pool / total_calculated_payouts
    
    # 4. Apply reduction to each winner
    for winner in winners:
        adjusted_payout = original_payout × reduction_ratio
        credit_wallet(winner, adjusted_payout)
    
    # 5. Flag round for review
    round.flagged_for_review = True
else:
    # 4. Pay full amounts
    for winner in winners:
        credit_wallet(winner, original_payout)
```

## Use Cases

### Use Case 1: Conservative Margin (Low House Profit)

**Settings**: 10% house, 90% winners

- Lower platform revenue
- Higher winner payouts
- Less likely to reduce payouts
- Better for player retention

### Use Case 2: Standard Margin

**Settings**: 20% house, 80% winners

- Balanced approach
- Moderate platform revenue
- Occasional payout reductions
- Industry standard

### Use Case 3: Aggressive Margin (High House Profit)

**Settings**: 30% house, 70% winners

- Higher platform revenue
- More frequent payout reductions
- May impact player satisfaction
- Better for profitability

### Use Case 4: Special Promotions

**Settings**: 5% house, 95% winners

- Temporary promotional period
- Minimal platform profit
- Maximum player payouts
- Good for marketing campaigns

## Monitoring

### Key Metrics to Track

1. **Payout Reduction Frequency**: % of rounds with `payout_reduced = true`
2. **Average Reduction Ratio**: Mean reduction when payouts are cut
3. **Flagged Rounds**: Count of rounds flagged for review
4. **House Profit vs Winner Payouts**: Actual revenue breakdown
5. **Player Impact**: How reduction affects player behavior

### Recommended Alerts

- Alert when payout reduction rate exceeds threshold (e.g., >10% of rounds)
- Alert when reduction ratio is severe (e.g., <0.75)
- Daily summary of house profit vs winner payouts

## Testing

Run profit management tests:

```bash
# Unit tests
uv run pytest tests/unit/test_profit_service.py

# Integration tests (if available)
uv run pytest tests/integration/ -k profit
```

## Migration

Apply the database migration:

```bash
# Run migration
uv run alembic upgrade head

# Verify migration
uv run alembic current
```

## Rollback

If needed, rollback the migration:

```bash
uv run alembic downgrade -1
```

## Best Practices

1. **Start Conservative**: Begin with 20/80 split and adjust based on data
2. **Monitor Closely**: Watch payout reduction frequency
3. **Communicate Changes**: Notify players of policy changes
4. **Review Flagged Rounds**: Investigate rounds with payout reductions
5. **Adjust Odds**: If reductions are frequent, consider lowering odds instead
6. **Seasonal Adjustments**: Use different margins for promotions
7. **Transparency**: Consider showing house margin in UI
