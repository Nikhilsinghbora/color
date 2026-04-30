# Implementation Plan: Color Prediction Game

## Overview

This plan implements a production-grade Color Prediction Game platform using Python/FastAPI, PostgreSQL, Redis, Celery, and WebSockets. Tasks are ordered to build foundational layers first (project structure, database, auth) then layer on game logic, real-time features, social/leaderboard systems, responsible gambling controls, admin tools, and security hardening. Each task builds incrementally on previous work.

## Tasks

- [x] 1. Project scaffolding and configuration
  - [x] 1.1 Create project directory structure and core configuration
    - Create `app/` package with `__init__.py`, `main.py` (FastAPI app factory), `config.py` (Pydantic Settings for DB, Redis, JWT, Stripe, email, CORS)
    - Create `app/api/`, `app/services/`, `app/models/`, `app/schemas/`, `app/middleware/`, `app/tasks/` packages
    - Create `tests/`, `tests/unit/`, `tests/integration/`, `tests/properties/`, `tests/smoke/` directories
    - Set up `pyproject.toml` or `requirements.txt` with dependencies: fastapi, uvicorn, sqlalchemy[asyncio], asyncpg, redis, celery, python-jose, passlib[bcrypt], pydantic, stripe, hypothesis, pytest, pytest-asyncio, httpx
    - Create `alembic.ini` and `alembic/` directory for database migrations
    - _Requirements: 13.1, 13.5, 13.6_

  - [x] 1.2 Create Docker and infrastructure configuration
    - Create `Dockerfile` for FastAPI application
    - Create `docker-compose.yml` with services: app, postgres, redis, celery-worker, celery-beat, nginx
    - Create `nginx.conf` with reverse proxy, TLS termination placeholder, and WebSocket upgrade support
    - _Requirements: 12.1, 13.3_

- [x] 2. Database models and migrations
  - [x] 2.1 Implement SQLAlchemy base and all database models
    - Create `app/models/base.py` with async engine setup, session factory, and `Base` declarative base
    - Implement `Player`, `Wallet`, `Transaction`, `TransactionType` models in `app/models/player.py`
    - Implement `GameMode`, `GameRound`, `RoundPhase`, `Bet`, `Payout` models in `app/models/game.py`
    - Implement `RNGAuditLog` model in `app/models/rng.py`
    - Implement `DepositLimit`, `LimitPeriod`, `SelfExclusion`, `SessionLimit` models in `app/models/responsible_gambling.py`
    - Implement `AuditTrail`, `AuditEventType` model in `app/models/audit.py`
    - Implement `FriendLink` model in `app/models/social.py`
    - Include all constraints: `wallet_non_negative_balance`, `bet_positive_amount`, `uq_player_deposit_limit_period`
    - _Requirements: 2.1, 2.5, 3.1, 5.3, 10.1, 12.5_

  - [x] 2.2 Create Alembic migration for initial schema
    - Generate and verify Alembic migration from all models
    - Ensure migration creates all tables, indexes, constraints, and enums
    - _Requirements: 2.1_

- [x] 3. Pydantic schemas and error handling
  - [x] 3.1 Create Pydantic request/response schemas
    - Create `app/schemas/auth.py`: `RegisterRequest`, `LoginRequest`, `TokenResponse`, `PasswordResetRequest`
    - Create `app/schemas/wallet.py`: `DepositRequest`, `WithdrawRequest`, `TransactionResponse`, `WalletResponse`
    - Create `app/schemas/game.py`: `PlaceBetRequest`, `RoundStateResponse`, `BetResponse`, `GameModeResponse`
    - Create `app/schemas/leaderboard.py`: `LeaderboardResponse`, `PlayerRankResponse`
    - Create `app/schemas/social.py`: `FriendRequest`, `InviteCodeResponse`, `ProfileResponse`
    - Create `app/schemas/responsible_gambling.py`: `DepositLimitRequest`, `SessionLimitRequest`, `SelfExclusionRequest`
    - Create `app/schemas/admin.py`: `DashboardResponse`, `GameConfigUpdateRequest`, `PlayerActionRequest`
    - All schemas must enforce strict validation (email format, password complexity, positive amounts, string length limits)
    - _Requirements: 1.7, 12.6_

  - [x] 3.2 Implement error handling middleware and domain exceptions
    - Create `app/exceptions.py` with domain exceptions: `InsufficientBalanceError`, `BettingClosedError`, `AccountLockedError`, `DepositLimitExceededError`, `SelfExcludedError`, `RateLimitExceededError`
    - Create `app/middleware/error_handler.py` with FastAPI exception handlers mapping domain exceptions to consistent JSON error responses with appropriate HTTP status codes
    - _Requirements: 2.4, 4.3, 4.6, 10.2_

- [x] 4. Authentication service and endpoints
  - [x] 4.1 Implement authentication service
    - Create `app/services/auth_service.py` with `register_player`, `authenticate`, `refresh_token`, `request_password_reset`, `reset_password`, `check_account_lock`
    - Use passlib bcrypt with cost factor 12 for password hashing
    - Use python-jose for JWT access token and refresh token generation/validation
    - Implement 3-attempt account locking with 15-minute lockout (tracked in Redis)
    - Implement 30-minute session inactivity timeout via JWT expiry
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [x] 4.2 Create authentication API endpoints
    - Create `app/api/auth.py` with routes: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `POST /api/v1/auth/refresh`, `POST /api/v1/auth/password-reset-request`, `POST /api/v1/auth/password-reset`
    - Create JWT authentication dependency in `app/api/deps.py` for protecting routes
    - All endpoints validate payloads via Pydantic schemas
    - _Requirements: 1.1, 1.2, 1.4, 1.7_


  - [x] 4.3 Write property tests for authentication
    - **Property 1: Registration input validation** — For any registration payload, invalid email/username/password is rejected; valid payloads succeed
    - **Validates: Requirements 1.1**
    - **Property 2: Password hash round-trip** — For any password, bcrypt hash + verify returns True; different password returns False
    - **Validates: Requirements 1.2, 1.5**
    - **Property 3: Input validation rejects malicious payloads** — SQL injection, XSS, malformed payloads rejected by Pydantic
    - **Validates: Requirements 1.7, 12.6**
    - Write tests in `tests/properties/test_auth_properties.py` using Hypothesis with `@settings(max_examples=100)`

  - [x] 4.4 Write unit tests for authentication service
    - Test login flow with valid/invalid credentials
    - Test account locking after 3 failed attempts and 15-minute lockout
    - Test password reset token generation and consumption
    - Test session timeout after 30 minutes of inactivity
    - Write tests in `tests/unit/test_auth_service.py`
    - _Requirements: 1.2, 1.3, 1.4, 1.6_

- [x] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Wallet service and endpoints
  - [x] 6.1 Implement wallet service
    - Create `app/services/wallet_service.py` with `get_balance`, `deposit`, `withdraw`, `debit`, `credit`, `get_transactions`
    - Implement atomic wallet operations using `SELECT ... FOR UPDATE` and SQLAlchemy async sessions
    - Implement optimistic locking via `version` column on Wallet model
    - Use Redis cache for wallet balance with 30s TTL and DB fallback
    - Initialize wallet with zero balance on player registration
    - Record every transaction with unique ID, timestamp, amount, type, and resulting balance
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7_

  - [x] 6.2 Create wallet API endpoints
    - Create `app/api/wallet.py` with routes: `GET /api/v1/wallet/balance`, `POST /api/v1/wallet/deposit`, `POST /api/v1/wallet/withdraw`, `GET /api/v1/wallet/transactions`
    - Deposit endpoint processes Stripe payment and credits wallet
    - Withdrawal endpoint validates balance and enqueues Celery task
    - Transactions endpoint returns paginated history sorted by most recent first
    - Require re-authentication if JWT issued more than 10 minutes ago for wallet access
    - _Requirements: 2.2, 2.3, 2.6, 2.8, 12.4_

  - [x] 6.3 Implement Celery withdrawal task
    - Create `app/tasks/wallet_tasks.py` with `process_withdrawal` task
    - Process Stripe payout with retry logic (3 retries, exponential backoff: 2s, 4s, 8s)
    - Mark transaction as failed after retry exhaustion
    - _Requirements: 2.8_

  - [x] 6.4 Write property tests for wallet operations
    - **Property 4: Withdrawal balance guard** — Withdrawal > balance rejected; 0 < withdrawal ≤ balance accepted with correct resulting balance
    - **Validates: Requirements 2.3, 2.4**
    - **Property 5: Transaction record completeness** — Every wallet operation produces a Transaction with non-null ID, timestamp, amount, type, and correct balance_after
    - **Validates: Requirements 2.5**
    - **Property 6: Transaction history ordering** — Paginated history returns transactions sorted by created_at descending, each page ≤ page_size entries
    - **Validates: Requirements 2.6**
    - **Property 7: Wallet balance consistency** — For any sequence of operations from balance 0, final balance = sum(credits) - sum(debits), never negative at any step
    - **Validates: Requirements 2.7**
    - **Property 11: Wallet debit equals bet amount** — For valid bet amount A with balance B ≥ A, resulting balance = B - A exactly
    - **Validates: Requirements 4.4**
    - Write tests in `tests/properties/test_wallet_properties.py` using Hypothesis with `@settings(max_examples=100)`

  - [x] 6.5 Write unit tests for wallet service
    - Test wallet initialization with zero balance
    - Test deposit via Stripe mock (payment confirmation within 5 seconds)
    - Test withdrawal rejection when amount exceeds balance
    - Test concurrent wallet operations and deadlock handling
    - Write tests in `tests/unit/test_wallet_service.py`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.7_

- [x] 7. RNG engine and audit logging
  - [x] 7.1 Implement RNG engine service
    - Create `app/services/rng_engine.py` with `generate_outcome` and `create_audit_entry`
    - Use `secrets.randbelow(len(color_options))` for outcome generation
    - Record algorithm identifier, raw value, num_options, and selected color in append-only `rng_audit_logs` table
    - Each outcome generated independently with no dependency on previous rounds
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 7.2 Write property tests for RNG engine
    - **Property 12: RNG uniform distribution** — Over 10,000+ outcomes, frequency of each color does not deviate beyond chi-squared test at 99% confidence
    - **Validates: Requirements 5.2**
    - **Property 13: RNG audit log completeness** — Every resolved round has audit entry with algorithm="secrets.randbelow", raw_value, num_options, and selected_color = color_options[raw_value]
    - **Validates: Requirements 5.3**
    - **Property 14: RNG outcome independence** — Serial correlation coefficient between consecutive outcomes is not statistically significant (p > 0.01)
    - **Validates: Requirements 5.4**
    - Write tests in `tests/properties/test_rng_properties.py` using Hypothesis with `@settings(max_examples=100)`

- [x] 8. Payout calculator
  - [x] 8.1 Implement payout calculator service
    - Create `app/services/payout_calculator.py` with `calculate_payout`, `calculate_round_payouts`, `check_reserve_threshold`
    - Use `Decimal` fixed-point arithmetic with `quantize(Decimal("0.01"))` for all payout calculations — never use float
    - Flag rounds for admin review when total payouts exceed configured reserve threshold
    - _Requirements: 6.1, 6.4, 6.5_

  - [x] 8.2 Write property tests for payout calculator
    - **Property 15: Payout calculation correctness** — For any bet amount A and odds O, payout = (A * O).quantize(Decimal("0.01")) using Decimal arithmetic
    - **Validates: Requirements 6.1, 6.4**
    - **Property 16: Reserve threshold flagging** — Round flagged when total payouts > threshold T; not flagged when ≤ T
    - **Validates: Requirements 6.5**
    - Write tests in `tests/properties/test_payout_properties.py` using Hypothesis with `@settings(max_examples=100)`

- [x] 9. Game engine and round lifecycle
  - [x] 9.1 Implement game engine service
    - Create `app/services/game_engine.py` with `start_round`, `place_bet`, `resolve_round`, `finalize_round`, `get_round_state`
    - Implement state machine: BETTING → RESOLUTION → RESULT, reject invalid transitions
    - Accept bets only during BETTING phase; reject with `BettingClosedError` otherwise
    - Validate bet amounts against game mode min_bet/max_bet limits
    - Validate bet amounts against player wallet balance
    - Allow multiple bets per player per round on different colors
    - Deduct bet from wallet via wallet_service.debit, invoke RNG via rng_engine, calculate payouts via payout_calculator, credit winners via wallet_service.credit
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 6.1, 6.2_

  - [x] 9.2 Implement game mode configuration
    - Create `app/services/game_mode_service.py` for CRUD operations on game modes
    - Support Classic, Timed_Challenge, and Tournament mode types
    - Each mode has independent color_options, odds, min_bet, max_bet, round_duration_seconds
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [x] 9.3 Create game API endpoints
    - Create `app/api/game.py` with routes: `GET /api/v1/game/modes`, `GET /api/v1/game/modes/{mode_id}`, `GET /api/v1/game/rounds/{round_id}`, `POST /api/v1/game/rounds/{round_id}/bet`
    - Display available color options with odds during betting phase
    - Display result summary (winning color, player prediction, bet amount, payout/loss) after result phase
    - _Requirements: 3.7, 4.1, 6.3, 7.4_

  - [x] 9.4 Implement Celery tasks for round lifecycle
    - Create `app/tasks/game_tasks.py` with `advance_game_round` periodic task
    - Transition rounds on timer expiry: BETTING → RESOLUTION → RESULT → new round (≤5s delay)
    - Publish state transitions to Redis pub/sub for all FastAPI instances
    - _Requirements: 3.3, 3.5, 3.6, 3.8_

  - [x] 9.5 Write property tests for game engine
    - **Property 8: Game round state machine validity** — Phase transitions only follow BETTING → RESOLUTION → RESULT; bets accepted only in BETTING phase
    - **Validates: Requirements 3.1, 3.2, 3.3, 4.6**
    - **Property 9: Bet amount within configured limits** — Bet rejected if amount < min_bet or > max_bet; accepted if within range
    - **Validates: Requirements 4.2**
    - **Property 10: Bet rejected when exceeding wallet balance** — Bet rejected with insufficient balance error when amount > wallet balance; balance unchanged
    - **Validates: Requirements 4.3**
    - Write tests in `tests/properties/test_game_engine_properties.py` using Hypothesis with `@settings(max_examples=100)`

  - [x] 9.6 Write property tests for game mode configuration
    - **Property 17: Game mode configuration display** — Response contains all configured values (color_options, odds, min_bet, max_bet, round_duration_seconds) matching stored config exactly
    - **Validates: Requirements 7.4**
    - Write tests in `tests/properties/test_game_mode_properties.py` using Hypothesis with `@settings(max_examples=100)`

  - [x] 9.7 Write unit tests for game engine
    - Test full round lifecycle: BETTING → RESOLUTION → RESULT → new round
    - Test RNG invocation during resolution phase
    - Test Classic, Timed_Challenge, and Tournament mode existence and configuration
    - Write tests in `tests/unit/test_game_engine.py` and `tests/unit/test_game_modes.py`
    - _Requirements: 3.1, 3.4, 3.5, 3.6, 7.1, 7.2, 7.3_

- [x] 10. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. WebSocket manager and real-time features
  - [x] 11.1 Implement WebSocket manager service
    - Create `app/services/ws_manager.py` with `connect`, `disconnect`, `broadcast_round_state`, `broadcast_chat`, `send_personal`
    - Register WebSocket connections per player per round
    - Subscribe to Redis pub/sub channels `channel:round:{round_id}` and `channel:chat:{round_id}`
    - Fan out Redis pub/sub messages to all locally connected WebSocket clients
    - Implement heartbeat and stale connection cleanup
    - _Requirements: 3.5, 3.7, 3.8, 9.3, 9.6, 13.1_

  - [x] 11.2 Create WebSocket endpoint
    - Create `app/api/websocket.py` with `WS /ws/game/{round_id}` endpoint
    - Authenticate WebSocket connections via JWT token in query parameter
    - Handle game state broadcasts and chat messages
    - Deliver round state updates within 200ms under normal load
    - _Requirements: 3.5, 3.7, 9.3, 13.1_

  - [x] 11.3 Write integration tests for WebSocket
    - Test WebSocket connection and authentication
    - Test round state broadcast delivery to connected clients
    - Test chat message delivery via Redis pub/sub
    - Write tests in `tests/integration/test_websocket.py`
    - _Requirements: 3.5, 9.3, 9.6_

- [x] 12. Leaderboard service
  - [x] 12.1 Implement leaderboard service
    - Create `app/services/leaderboard_service.py` with `update_rankings`, `get_leaderboard`, `get_player_rank`
    - Use Redis sorted sets with keys `leaderboard:{metric}:{period}` for total_winnings, win_rate, win_streak
    - Support daily, weekly, monthly, and all-time periods
    - Update rankings within 10 seconds of round completion (via Celery task `update_leaderboards`)
    - Return top 100 players with rank, username, and metric value
    - Highlight viewing player's own rank and position
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [x] 12.2 Create leaderboard API endpoints
    - Create `app/api/leaderboard.py` with routes: `GET /api/v1/leaderboard/{metric}`, `GET /api/v1/leaderboard/{metric}/me`
    - Support query parameters for period (daily, weekly, monthly, all-time) and pagination
    - _Requirements: 8.3, 8.4, 8.5_

  - [x] 12.3 Write property tests for leaderboard
    - **Property 18: Leaderboard sorting correctness** — For any metric, leaderboard returns players sorted descending; entry[i].value >= entry[i+1].value
    - **Validates: Requirements 8.1**
    - Write tests in `tests/properties/test_leaderboard_properties.py` using Hypothesis with `@settings(max_examples=100)`

  - [x] 12.4 Write unit tests for leaderboard service
    - Test top 100 limit enforcement
    - Test player rank inclusion and highlighting
    - Test daily/weekly/monthly/all-time period filters
    - Write tests in `tests/unit/test_leaderboard.py`
    - _Requirements: 8.3, 8.4, 8.5_

- [x] 13. Multiplayer and social features
  - [x] 13.1 Implement social service
    - Create `app/services/social_service.py` with invite code generation, friend management, and profile display
    - Generate unique invite codes for private game rounds
    - Allow players to add friends by username
    - Display friend public statistics: total games played, win rate, leaderboard rank
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

  - [x] 13.2 Create social API endpoints
    - Create `app/api/social.py` with routes: `POST /api/v1/social/invite`, `POST /api/v1/social/join/{invite_code}`, `POST /api/v1/social/friends`, `GET /api/v1/social/friends`, `GET /api/v1/social/profile/{username}`
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

  - [x] 13.3 Write property tests for social features
    - **Property 19: Invite code uniqueness** — For any N private rounds created, all N invite codes are distinct
    - **Validates: Requirements 9.1**
    - Write tests in `tests/properties/test_social_properties.py` using Hypothesis with `@settings(max_examples=100)`

  - [x] 13.4 Write unit tests for social features
    - Test friend add by username
    - Test invite code join flow
    - Test profile display with public statistics
    - Write tests in `tests/unit/test_social.py`
    - _Requirements: 9.1, 9.2, 9.4, 9.5_

- [x] 14. Responsible gambling controls
  - [x] 14.1 Implement responsible gambling service
    - Create `app/services/responsible_gambling_service.py` with `set_deposit_limit`, `check_deposit_limit`, `set_session_limit`, `check_loss_threshold`, `self_exclude`
    - Enforce daily/weekly/monthly deposit limits; reject deposits exceeding limit with remaining allowance and reset date
    - Implement session time limit with mandatory reminder notification
    - Implement self-exclusion for 24h, 7d, 30d, or permanent; prevent re-activation before period ends
    - Trigger mandatory warning when 24h cumulative losses exceed configurable threshold
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_

  - [x] 14.2 Create responsible gambling API endpoints
    - Create `app/api/responsible_gambling.py` with routes: `POST /api/v1/responsible-gambling/deposit-limit`, `GET /api/v1/responsible-gambling/deposit-limit`, `POST /api/v1/responsible-gambling/session-limit`, `POST /api/v1/responsible-gambling/self-exclude`
    - _Requirements: 10.1, 10.3, 10.4_

  - [x] 14.3 Implement Celery task for deposit limit resets
    - Create `app/tasks/maintenance_tasks.py` with `reset_deposit_limits` periodic task
    - Reset expired deposit limit counters based on period (daily/weekly/monthly)
    - _Requirements: 10.2_

  - [x] 14.4 Write property tests for responsible gambling
    - **Property 20: Deposit limit enforcement** — Deposit rejected when current_usage + deposit > limit; response includes remaining allowance and reset date
    - **Validates: Requirements 10.2**
    - **Property 21: Cumulative loss threshold warning** — Warning triggered when 24h losses > threshold; no warning when ≤ threshold
    - **Validates: Requirements 10.6**
    - Write tests in `tests/properties/test_responsible_gambling_properties.py` using Hypothesis with `@settings(max_examples=100)`

  - [x] 14.5 Write unit tests for responsible gambling
    - Test deposit limit CRUD and enforcement
    - Test session limit and reminder notification
    - Test self-exclusion for all durations (24h, 7d, 30d, permanent)
    - Write tests in `tests/unit/test_responsible_gambling.py`
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.6_

- [x] 15. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 16. Admin endpoints and compliance
  - [x] 16.1 Implement admin service and endpoints
    - Create `app/services/admin_service.py` for dashboard metrics, config management, player actions
    - Create `app/api/admin.py` with routes: `GET /api/v1/admin/dashboard`, `PUT /api/v1/admin/game-config/{mode_id}`, `POST /api/v1/admin/players/{player_id}/suspend`, `POST /api/v1/admin/players/{player_id}/ban`, `GET /api/v1/admin/audit-logs`, `GET /api/v1/admin/rng-audit`
    - Dashboard displays: active player count, total bets, total payouts, platform revenue for configurable time periods
    - Config changes apply starting from next game round; log change with admin ID and timestamp
    - Allow admin to suspend/ban player accounts with recorded reason
    - Expose RNG audit log for fairness verification
    - _Requirements: 11.1, 11.2, 11.3, 11.4, 5.5_

  - [x] 16.2 Implement Celery task for daily compliance reports
    - Create `app/tasks/report_tasks.py` with `generate_daily_report` scheduled task (daily at 00:00 UTC)
    - Report includes: total wagering volume, payout ratios, flagged game rounds, responsible gambling trigger events
    - _Requirements: 11.5_

  - [x] 16.3 Write unit tests for admin service
    - Test dashboard metrics aggregation
    - Test config change application and logging
    - Test player suspension and ban with reason recording
    - Write tests in `tests/unit/test_admin.py`
    - _Requirements: 11.1, 11.2, 11.3, 11.4_

- [x] 17. Security middleware and audit trail
  - [x] 17.1 Implement security middleware
    - Create `app/middleware/rate_limiter.py` with rate limiting: 100 requests per minute per player session using Redis counter with 60s TTL
    - Create `app/middleware/cors.py` configuring CORS via FastAPI middleware, restricting allowed origins to frontend domain
    - Create `app/middleware/auth.py` with JWT re-authentication check (10-minute window) for sensitive endpoints
    - Validate and sanitize all inputs via Pydantic models (already in schemas)
    - _Requirements: 12.3, 12.4, 12.6, 12.7_

  - [x] 17.2 Implement audit trail service
    - Create `app/services/audit_service.py` for recording all auditable events (auth, wallet, admin actions)
    - Append-only audit trail in PostgreSQL `audit_trail` table — no updates or deletes
    - Record event_type, actor_id, target_id, details, ip_address, timestamp
    - Integrate audit logging into auth_service, wallet_service, and admin_service
    - _Requirements: 12.5_

  - [x] 17.3 Write property tests for security
    - **Property 22: Rate limiting enforcement** — More than 100 requests in 60s window returns 429; requests within limit processed normally
    - **Validates: Requirements 12.3**
    - **Property 23: Audit trail creation** — Every auditable event creates an immutable audit entry with event_type, actor_id, timestamp, and details
    - **Validates: Requirements 12.5**
    - Write tests in `tests/properties/test_security_properties.py` using Hypothesis with `@settings(max_examples=100)`

- [x] 18. Celery configuration and email tasks
  - [x] 18.1 Configure Celery app and implement email tasks
    - Create `app/celery_app.py` with Celery configuration, Redis broker, task routing to queues (wallet, email, game, analytics, reports, maintenance)
    - Create `app/tasks/email_tasks.py` with `send_verification_email`, `send_password_reset_email`, `send_notification_email` tasks
    - Implement retry logic for email delivery (3 retries, failure logged but non-blocking)
    - Create `app/tasks/maintenance_tasks.py` with `cleanup_expired_sessions` task (every 5 min)
    - Configure Celery Beat schedule for periodic tasks: `advance_game_round`, `reset_deposit_limits`, `generate_daily_report`, `cleanup_expired_sessions`
    - _Requirements: 1.1, 1.3, 1.4, 13.6_

- [x] 19. Wire FastAPI application together
  - [x] 19.1 Assemble FastAPI application
    - Update `app/main.py` to register all API routers (auth, wallet, game, leaderboard, social, responsible_gambling, admin, websocket)
    - Register all middleware (CORS, rate limiter, error handler)
    - Configure database session dependency injection
    - Configure Redis connection pool
    - Add startup/shutdown event handlers for DB and Redis connections
    - Add health check endpoint `GET /api/v1/health`
    - _Requirements: 13.1, 13.5_

- [x] 20. Integration and smoke tests
  - [x] 20.1 Write integration tests
    - Test Stripe deposit/withdrawal flow with Stripe test mode in `tests/integration/test_stripe.py`
    - Test Celery task dispatch and execution for withdrawals, emails, reports in `tests/integration/test_celery_tasks.py`
    - Test Redis pub/sub message delivery across simulated multi-instance setup in `tests/integration/test_redis_pubsub.py`
    - Test concurrent wallet operations and deadlock handling in `tests/integration/test_db_transactions.py`
    - _Requirements: 2.2, 2.7, 2.8, 3.8, 13.6_

  - [x] 20.2 Write smoke tests
    - Test bcrypt cost factor, CORS policy, connection pool settings in `tests/smoke/test_config.py`
    - Test Redis connectivity, Celery worker health, DB migrations applied in `tests/smoke/test_infrastructure.py`
    - _Requirements: 1.5, 12.7, 13.5_

- [x] 21. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints at tasks 5, 10, 15, and 21 ensure incremental validation
- Property tests validate the 23 universal correctness properties defined in the design document using Hypothesis
- Unit tests validate specific scenarios and edge cases
- All wallet operations use atomic transactions with `SELECT ... FOR UPDATE` to prevent double-spending
- All payout calculations use `Decimal` fixed-point arithmetic — never float
- WebSocket broadcasts coordinated via Redis pub/sub for horizontal scalability
