# Admin Dashboard Guide

This guide explains how to access and use the admin dashboard for the Color Prediction Game.

## Prerequisites

- Backend server running (`python -m uvicorn app.main:app --reload`)
- Frontend running (`npm run dev` in the `frontend` directory)
- PostgreSQL database connected
- Redis server running (for production)

## Creating an Admin Account

### Method 1: Using the create_admin script (Recommended)

```bash
# With custom credentials
python -m scripts.create_admin --email admin@example.com --username admin --password yourpassword

# Or use defaults (email: admin@example.com, password: admin123)
python -m scripts.create_admin
```

The script will:
- Create a new admin user with `is_admin=True`
- Create a wallet with $10,000 starting balance
- Or upgrade an existing user to admin if they already exist

### Method 2: Manually via database

If you already have a user account, you can upgrade it to admin:

```sql
UPDATE players SET is_admin = true WHERE email = 'your-email@example.com';
```

### Method 3: Using environment variables

Set environment variables and run the script:

```bash
export ADMIN_EMAIL=admin@example.com
export ADMIN_USERNAME=admin
export ADMIN_PASSWORD=yourpassword
python -m scripts.create_admin
```

## Accessing the Admin Dashboard

1. **Start the application**:
   ```bash
   # Terminal 1: Backend
   python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   
   # Terminal 2: Frontend
   cd frontend && npm run dev
   ```

2. **Login with admin credentials**:
   - Go to `http://localhost:3000/login`
   - Enter your admin email and password
   - Click "Sign In"

3. **Access the admin dashboard**:
   - Navigate to `http://localhost:3000/admin`
   - You'll be automatically redirected if not logged in or not an admin

## Admin Dashboard Features

### 1. Dashboard Overview (`/admin`)

**Metrics displayed:**
- **Active Players**: Number of players who have placed bets in the selected period
- **Total Bets**: Sum of all bets placed
- **Total Payouts**: Sum of all payouts distributed to winners
- **Revenue**: House profit (bets minus payouts)

**Time periods:**
- Daily
- Weekly
- Monthly
- All Time

**API Endpoint**: `GET /api/v1/admin/dashboard?period=daily`

### 2. Game Configuration (`/admin/config`)

Update game mode settings:
- **Odds**: Multipliers for color, number, big/small bets
- **Bet Limits**: Minimum and maximum bet amounts
- **Round Duration**: Length of betting phase in seconds
- **Game Mode Status**: Enable/disable specific game modes

**Note**: Changes apply to the next round, not the current one.

**API Endpoint**: `PUT /api/v1/admin/game-config/{mode_id}`

### 3. Player Management (`/admin/players`)

Manage player accounts:
- **Suspend Player**: Temporarily prevent a player from betting
- **Ban Player**: Permanently disable a player account
- **View Player History**: See bet history and transaction records
- **Wallet Management**: View balance and transaction history

**API Endpoints**:
- `POST /api/v1/admin/players/{player_id}/suspend`
- `POST /api/v1/admin/players/{player_id}/ban`

### 4. RNG Audit Log (`/admin/rng-audit`)

View the Random Number Generator audit trail:
- **Round ID**: Which round the RNG was used for
- **Winning Number**: Generated number (0-9)
- **Winning Color**: Derived color (green/red/violet)
- **Timestamp**: When the number was generated
- **Algorithm**: RNG algorithm used (e.g., `secrets.randbelow`)

**Purpose**: Compliance, fairness verification, dispute resolution

**API Endpoint**: `GET /api/v1/admin/rng-audit`

### 5. Audit Logs (`/admin/audit`)

View all system audit events:
- Authentication attempts (login, failed login, logout)
- Wallet transactions (deposit, withdrawal, bet, payout)
- Admin actions (config changes, player suspensions)
- Game events (round start, round end, bet placement)

**API Endpoint**: `GET /api/v1/admin/audit-logs`

### 6. Profit Settings (API only)

Configure house profit margin:

```bash
# Get current settings
curl http://localhost:8000/api/v1/admin/profit-settings \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN"

# Update settings
curl -X PUT http://localhost:8000/api/v1/admin/profit-settings \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"house_profit_percentage": 20, "winner_pool_percentage": 80}'
```

**Default**: 20% house profit, 80% winner pool

## Security

### Admin Guard

All admin routes are protected by:
1. **Authentication**: Must be logged in (`isAuthenticated = true`)
2. **Authorization**: Must be admin (`isAdmin = true`)

If either check fails:
- Not authenticated → Redirect to `/login`
- Not admin → Redirect to `/game`

### Backend Validation

All admin API endpoints verify `is_admin=True` on the player record:

```python
async def _require_admin(
    db: AsyncSession = Depends(get_db),
    player_id: UUID = Depends(get_current_player_id),
) -> UUID:
    """Verify the requesting player has admin privileges."""
    result = await db.execute(select(Player).where(Player.id == player_id))
    player = result.scalar_one_or_none()
    if player is None or not player.is_admin:
        raise HTTPException(status_code=403, detail="Admin access required")
    return player_id
```

### Audit Trail

All admin actions are logged to the audit trail with:
- Admin player ID
- Timestamp
- Action type
- Target (player, game mode, etc.)
- Details (reason, changes made, etc.)

## API Reference

### Admin Endpoints

All endpoints require `Authorization: Bearer <access_token>` header with admin token.

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/admin/dashboard` | Dashboard metrics |
| PUT | `/api/v1/admin/game-config/{mode_id}` | Update game mode |
| POST | `/api/v1/admin/players/{player_id}/suspend` | Suspend player |
| POST | `/api/v1/admin/players/{player_id}/ban` | Ban player |
| GET | `/api/v1/admin/audit-logs` | Audit trail |
| GET | `/api/v1/admin/rng-audit` | RNG audit log |
| GET | `/api/v1/admin/profit-settings` | Get profit settings |
| PUT | `/api/v1/admin/profit-settings` | Update profit settings |
| GET | `/api/v1/admin/rounds/{round_id}/profit` | Get round profit details |

### Example: Suspend a Player

```bash
curl -X POST http://localhost:8000/api/v1/admin/players/550e8400-e29b-41d4-a716-446655440000/suspend \
  -H "Authorization: Bearer YOUR_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason": "Suspected bot activity"}'
```

## Troubleshooting

### "Admin access required" error

**Problem**: Getting 403 Forbidden when accessing admin routes.

**Solutions**:
1. Verify your account has `is_admin=True`:
   ```sql
   SELECT email, username, is_admin FROM players WHERE email = 'your-email@example.com';
   ```
2. Re-login to get a fresh token with admin claims
3. Check the JWT token payload includes `"is_admin": true`

### Can't access `/admin` route

**Problem**: Redirected to `/login` or `/game`.

**Solutions**:
1. Ensure you're logged in
2. Check that your account is an admin (see above)
3. Clear browser localStorage and re-login
4. Check browser console for errors

### Admin dashboard shows no data

**Problem**: Dashboard metrics show zeros or "No data".

**Solutions**:
1. Verify the backend is running and connected to the database
2. Check that game modes are seeded: `python -m scripts.seed_data`
3. Place some test bets to generate data
4. Check the backend logs for errors

### Script fails with "Module not found"

**Problem**: `python -m scripts.create_admin` fails.

**Solutions**:
1. Ensure you're in the project root directory
2. Activate your virtual environment
3. Install dependencies: `pip install -e ".[dev]"` or `uv sync --all-extras`

## Best Practices

1. **Use strong passwords** for admin accounts
2. **Don't use the default credentials** (`admin@example.com` / `admin123`) in production
3. **Audit regularly**: Review the audit logs for suspicious activity
4. **Test configuration changes** in a staging environment first
5. **Document player actions**: Always provide a reason when suspending/banning players
6. **Monitor profit margins**: Check flagged rounds where payouts were reduced
7. **Backup the database** before making bulk configuration changes

## Development

To add new admin features:

1. **Backend**: Add route to `app/api/admin.py` with `_require_admin` dependency
2. **Frontend**: Add page to `frontend/src/app/admin/` with `useAdminGuard()` hook
3. **Types**: Update `frontend/src/types/admin.ts` with new response types
4. **Tests**: Add tests to `tests/unit/test_admin.py` and `frontend/src/app/admin/*.test.tsx`

## Support

For issues or questions:
- Check the [main README](./README.md)
- Review [CLAUDE.md](./CLAUDE.md) for architecture details
- File an issue at: https://github.com/anthropics/claude-code/issues
