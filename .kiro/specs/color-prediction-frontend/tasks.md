# Implementation Plan: Color Prediction Game Frontend

## Overview

Build a Next.js App Router frontend for the Color Prediction Game platform. The implementation proceeds in layers: project scaffolding → type definitions → service layer (API client, WebSocket client) → Zustand stores → custom hooks → page components (auth, game, wallet, leaderboard, social, responsible gambling, admin) → navigation shell → responsive/accessible styling → error handling and offline resilience. Each task builds on the previous, with property-based tests and unit tests woven in close to the code they validate.

## Tasks

- [x] 1. Project scaffolding and configuration
  - [x] 1.1 Initialize Next.js project with App Router, Tailwind CSS, and TypeScript
    - Create Next.js app with `app/` directory structure
    - Configure Tailwind CSS with dark/light theme CSS custom properties
    - Install dependencies: `zustand`, `axios`, `@stripe/react-stripe-js`, `@stripe/stripe-js`, `fast-check`, `decimal.js`
    - Configure Jest/Vitest with TypeScript support and fast-check
    - Set up path aliases (`@/lib`, `@/stores`, `@/components`, `@/hooks`, `@/types`)
    - _Requirements: 10.7_

  - [x] 1.2 Create shared type definitions (`types/index.ts`)
    - Define all Auth, Wallet, Game, Leaderboard, Social, Responsible Gambling, Admin, and API Error types from the design document
    - Define WebSocket message types (`WSIncomingMessage`, `WSOutgoingMessage`)
    - Define store state interfaces (`AuthState`, `WalletState`, `GameState`, `UIState`)
    - _Requirements: All (shared foundation)_

- [x] 2. Service layer — API Client and WebSocket Client
  - [x] 2.1 Implement API Client with JWT interceptors (`lib/api-client.ts`)
    - Create Axios instance with base URL configuration
    - Implement request interceptor to attach `Authorization: Bearer <token>` from Auth Store
    - Implement response interceptor: on 401 `TOKEN_EXPIRED`, queue request, call `/api/v1/auth/refresh`, retry with new token
    - On refresh failure, clear Auth Store and redirect to `/login`
    - Implement consistent error response parsing for `{ error: { code, message, details } }` structure
    - _Requirements: 1.4, 1.5, 11.1_

  - [x] 2.2 Write property tests for API Client error parsing and token refresh
    - **Property 2: Token refresh interceptor** — verify 401 triggers exactly one refresh attempt and retries with new token
    - **Property 9: API error response parsing** — verify error codes are extracted and mapped to human-readable messages
    - **Validates: Requirements 1.4, 11.1**

  - [x] 2.3 Implement WebSocket Client (`lib/ws-client.ts`)
    - Create WebSocket wrapper with `connect`, `disconnect`, `send`, `onMessage`, `getStatus` methods
    - Implement typed message handling for all `WSIncomingMessage` variants
    - Implement exponential backoff reconnection: `min(2^(N-1) * 1000, 30000)` ms
    - Handle auth token expiry during WS session (close, refresh, reconnect)
    - _Requirements: 3.1, 3.7_

  - [x] 2.4 Write property test for WebSocket reconnection backoff
    - **Property 8: WebSocket reconnection backoff calculation** — verify delay = `min(2^(N-1) * 1000, 30000)` for any attempt N ≥ 1
    - **Validates: Requirements 3.7**

  - [x] 2.5 Implement utility functions (`lib/utils.ts`)
    - Implement `calculatePotentialPayout(amount: string, odds: string): string` using `decimal.js` for string-based decimal arithmetic, rounded to 2 decimal places
    - Implement registration validation functions: email format, username length (1–50), password complexity
    - Implement error code to human-readable message mapping
    - _Requirements: 4.8, 1.1, 11.1_

  - [x] 2.6 Write property tests for utility functions
    - **Property 1: Registration input validation** — verify email, username, password validators classify all inputs correctly
    - **Property 10: Potential payout calculation** — verify payout = amount × odds rounded to 2 decimal places using decimal arithmetic
    - **Property 17: Validation error field mapping** — verify field-level errors map to corresponding form inputs
    - **Validates: Requirements 1.1, 4.8, 11.5**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. State management — Zustand Stores
  - [x] 4.1 Implement Auth Store (`stores/auth-store.ts`)
    - Create Zustand store with `accessToken`, `refreshToken`, `player`, `isAuthenticated`, `isAdmin` state
    - Implement `setTokens`, `clearTokens`, `setPlayer`, `decodeAndSetPlayer` actions
    - Tokens stored in memory only (not localStorage) to prevent XSS token theft
    - _Requirements: 1.3, 1.4, 1.5, 1.8_

  - [x] 4.2 Write property test for Auth route guard logic
    - **Property 3: Auth route guard** — verify redirect to `/login` when no token, allow access when token present
    - **Validates: Requirements 1.8**

  - [x] 4.3 Implement Wallet Store (`stores/wallet-store.ts`)
    - Create Zustand store with `balance`, `transactions`, pagination state, and `isLoading`
    - Implement `fetchBalance`, `updateBalance`, `fetchTransactions`, `deposit`, `withdraw` actions using API Client
    - _Requirements: 2.1, 2.6, 2.7_

  - [x] 4.4 Implement Game Store (`stores/game-store.ts`)
    - Create Zustand store with `currentRound`, `phase`, `timerRemaining`, `colorOptions`, `selectedBets`, `placedBets`, `result`, `connectionStatus`
    - Implement all actions: `setRoundState`, `setPhase`, `updateTimer`, `setBetSelection`, `removeBetSelection`, `addPlacedBet`, `setResult`, `resetRound`, `setConnectionStatus`
    - _Requirements: 3.2, 3.3, 3.4, 3.5, 3.6, 3.8_

  - [x] 4.5 Write property tests for Game Store state transitions
    - **Property 5: Betting controls follow game phase** — verify betting enabled only during `betting` phase
    - **Property 6: Game store reflects WebSocket state updates** — verify timer, total_players, total_pool match received WS values
    - **Property 7: Game state full reset on new round** — verify all state cleared on `new_round` message
    - **Validates: Requirements 3.2, 3.3, 3.4, 3.6, 3.8**

  - [x] 4.6 Implement UI Store (`stores/ui-store.ts`)
    - Create Zustand store with `theme`, `isChatOpen`, `unreadChatCount`, `isOffline`, `sessionStartTime`, `sessionLimitMinutes`
    - Implement theme toggle with localStorage persistence
    - Implement session timer tracking actions
    - _Requirements: 10.7, 7.6, 8.5, 11.4_

- [x] 5. Custom hooks
  - [x] 5.1 Implement custom hooks (`hooks/`)
    - `useWebSocket(roundId)` — manages WS lifecycle, dispatches messages to Game Store, handles reconnection
    - `useCountdown(initialSeconds)` — client-side countdown synced with WS timer ticks
    - `useAuthGuard()` — redirects to `/login` if not authenticated
    - `useAdminGuard()` — redirects to `/game` if not admin
    - `useOnlineStatus()` — monitors `navigator.onLine`, dispatches to UI Store
    - `useSessionTimer()` — tracks session duration, triggers warning at limit
    - `useWalletSync()` — listens for bet/payout WS messages, updates Wallet Store balance
    - _Requirements: 3.1, 3.3, 1.8, 9.1, 11.4, 8.5, 2.7_

  - [x] 5.2 Write property tests for session timer and admin guard
    - **Property 14: Session timer notification trigger** — verify notification triggers at or after limit, not before
    - **Property 16: Admin route guard** — verify non-admin redirected to `/game`, admin allowed access
    - **Validates: Requirements 8.5, 9.1**

- [x] 6. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 7. Authentication pages
  - [x] 7.1 Implement Login page (`app/login/page.tsx`)
    - Login form with email/password fields, client-side validation
    - Submit to `POST /api/v1/auth/login`, store tokens in Auth Store, redirect to `/game`
    - Display error messages for invalid credentials, account locked (423)
    - Links to register and forgot password pages
    - _Requirements: 1.3, 1.9_

  - [x] 7.2 Implement Register page (`app/register/page.tsx`)
    - Registration form with email, username, password fields
    - Client-side validation: email format, username 1–50 chars, password complexity
    - Submit to `POST /api/v1/auth/register`, display success message for email verification
    - _Requirements: 1.1, 1.2_

  - [x] 7.3 Implement Forgot Password and Reset Password pages
    - `app/forgot-password/page.tsx` — email input, submit to `POST /api/v1/auth/password-reset-request`
    - `app/reset-password/[token]/page.tsx` — new password + confirm form, submit to `POST /api/v1/auth/password-reset`
    - _Requirements: 1.6, 1.7_

  - [x] 7.4 Write unit tests for authentication pages
    - Test login submission, error display, redirect on success
    - Test registration validation, submission, success message
    - Test password reset flows
    - _Requirements: 1.1, 1.2, 1.3, 1.6, 1.7_

- [x] 8. Game View and Betting Interface
  - [x] 8.1 Implement Game View page (`app/game/page.tsx`)
    - Display Color_Chips with odds, Countdown_Timer, round info (round number, total players, total pool)
    - Integrate `useWebSocket` hook for real-time updates
    - Handle phase transitions: betting → resolution ("Resolving..." animation) → result (highlight winner)
    - Display connection status indicator when WS is reconnecting
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8_

  - [x] 8.2 Implement Betting controls and bet summary
    - Color_Chip selection with visual highlight and bet amount input
    - Display min/max bet amounts for current Game_Mode
    - Place bet via `POST /api/v1/game/bet`, show Toast confirmation, update wallet balance
    - Display bet summary: color, amount, potential payout for each placed bet
    - Handle validation errors inline (below min, above max, insufficient balance, betting closed)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7, 4.8_

  - [x] 8.3 Implement Game Modes page (`app/game/modes/page.tsx`)
    - Fetch modes from `GET /api/v1/game/modes`, display name, description, status
    - Show rules, color options, odds, betting limits, round duration per mode
    - Distinct visual styling for Classic, Timed_Challenge, Tournament modes
    - Navigate to Game_View on mode selection
    - _Requirements: 5.1, 5.2, 5.3, 5.4_

  - [x] 8.4 Write property test for loss warning blocking bets
    - **Property 15: Loss warning blocks betting** — verify bet submission blocked when loss warning unacknowledged, permitted after acknowledgment
    - **Validates: Requirements 8.7**

  - [x] 8.5 Write unit tests for Game View and Betting
    - Test color chip selection, bet placement, result display, round transitions
    - Test mode listing, mode selection, rules display
    - _Requirements: 3.1–3.8, 4.1–4.8, 5.1–5.4_

- [x] 9. Wallet page with Stripe integration
  - [x] 9.1 Implement Wallet page (`app/wallet/page.tsx`)
    - Display current balance prominently
    - Render Stripe Elements payment form for deposits, collect payment details, submit to `POST /api/v1/wallet/deposit`
    - Withdrawal form with amount input, submit to `POST /api/v1/wallet/withdraw`
    - Display insufficient balance error with current balance
    - Paginated transaction history list: type, amount, timestamp, sorted most recent first
    - Toast notifications for deposit/withdrawal success
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6_

  - [x] 9.2 Write property test for transaction rendering
    - **Property 4: Transaction rendering completeness** — verify all required fields (type, amount, timestamp) rendered for any transaction
    - **Validates: Requirements 2.6**

  - [x] 9.3 Write unit tests for Wallet page
    - Test balance display, deposit with Stripe mock, withdrawal form, insufficient balance error
    - _Requirements: 2.1–2.7_

- [x] 10. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 11. Leaderboard, Social, and Responsible Gambling pages
  - [x] 11.1 Implement Leaderboard page (`app/leaderboard/page.tsx`)
    - Fetch from `GET /api/v1/leaderboard/{metric}`, display top 100 with rank, username, metric value
    - Filter controls for metric (total winnings, win rate, win streak) and period (daily, weekly, monthly, all-time)
    - Highlight viewing player's row, scroll to player's position
    - Update display on filter change without full page reload
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [x] 11.2 Write property test for leaderboard rendering
    - **Property 11: Leaderboard entry rendering completeness** — verify rank, username, metric_value all rendered for any entry
    - **Validates: Requirements 6.1**

  - [x] 11.3 Implement Social pages
    - `app/social/page.tsx` — friends list, friend search via `POST /api/v1/social/friends`, invite code entry via `POST /api/v1/social/join`
    - `app/social/profile/[id]/page.tsx` — public profile with total games, win rate, leaderboard rank from `GET /api/v1/social/profile/{player_id}`
    - Chat panel component with WS message send/receive, unread indicator when collapsed
    - Copy-to-clipboard for invite codes
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6_

  - [x] 11.4 Write property tests for social features
    - **Property 12: Chat message rendering completeness** — verify sender and message content rendered for any chat message
    - **Property 13: Player profile rendering completeness** — verify total_games, win_rate, leaderboard_rank all rendered
    - **Validates: Requirements 7.3, 7.5**

  - [x] 11.5 Implement Responsible Gambling pages
    - `app/settings/responsible-gambling/page.tsx` — deposit limit forms (daily/weekly/monthly), session limit form, self-exclusion with confirmation dialog
    - Fetch current limits from `GET /api/v1/responsible-gambling/deposit-limit`
    - Submit limits/exclusion to respective POST endpoints
    - Responsible gambling link in footer on all betting pages
    - Loss warning modal that blocks betting until acknowledged
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6, 8.7_

  - [x] 11.6 Write unit tests for Leaderboard, Social, and Responsible Gambling
    - Test filter switching, player highlight, chat send/receive, invite code, deposit limit forms, session timer, self-exclusion dialog, loss warning modal
    - _Requirements: 6.1–6.4, 7.1–7.6, 8.1–8.7_

- [x] 12. Admin Dashboard
  - [x] 12.1 Implement Admin Dashboard pages
    - `app/admin/page.tsx` — metrics overview (active players, total bets, payouts, revenue) with period selector from `GET /api/v1/admin/dashboard`
    - `app/admin/config/page.tsx` — editable game config forms (betting limits, odds, color options, round duration) per mode, submit to `POST /api/v1/admin/game-config`
    - `app/admin/players/page.tsx` — searchable, paginated player list from `GET /api/v1/admin/players`, suspend/ban actions
    - `app/admin/audit/page.tsx` — paginated audit logs from `GET /api/v1/admin/audit-logs` with event type, date range, actor filters
    - `app/admin/rng-audit/page.tsx` — RNG audit entries from `GET /api/v1/admin/rng-audit` showing round ID, algorithm, raw value, options, selected color
    - Protect all admin routes with `useAdminGuard` hook
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6, 9.7_

  - [x] 12.2 Write unit tests for Admin Dashboard
    - Test metrics display, config forms, player management, audit logs
    - _Requirements: 9.1–9.7_

- [x] 13. Navigation shell, layout, and theme
  - [x] 13.1 Implement application shell and navigation
    - Root layout (`app/layout.tsx`) with Zustand providers, Stripe provider, theme class application
    - Persistent nav bar with links to Game, Wallet, Leaderboard, Social, Settings
    - Display player username and wallet balance in nav bar on authenticated pages
    - Account dropdown menu: profile settings, responsible gambling settings, logout
    - Logout action: clear Auth Store, close WebSocket connections, redirect to `/login`
    - Settings page (`app/settings/page.tsx`) with theme toggle
    - Next.js client-side routing for all navigation
    - _Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 10.7_

  - [x] 13.2 Implement responsive layout and accessibility
    - Responsive layout adapting from 320px to 1920px without horizontal scroll
    - Semantic HTML elements (`nav`, `main`, `section`, `article`, `button`) and ARIA attributes
    - Keyboard navigation (Tab, Enter, Escape) for all interactive elements
    - Minimum 4.5:1 contrast ratio for normal text, 3:1 for large text
    - Visible focus indicators on all interactive elements
    - Skeleton loading states and spinner indicators during API calls
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5, 10.6_

  - [x] 13.3 Implement Toast notification system and error handling UI
    - Reusable Toast component for success, error, warning, info notifications
    - Auto-dismiss with configurable duration
    - Error toast for API errors with human-readable messages
    - Rate limit handling: disable action for Retry-After duration, show "Too many requests"
    - 500/503 handling: "Something went wrong" with retry button
    - Inline form validation error display mapped to input fields
    - _Requirements: 11.1, 11.2, 11.3, 11.5_

  - [x] 13.4 Implement offline resilience
    - Monitor `navigator.onLine` and `online`/`offline` events via `useOnlineStatus` hook
    - Display persistent offline banner when disconnected
    - Disable API-dependent actions while offline
    - Queue pending actions in memory, retry on reconnection
    - Re-establish WebSocket connection on connectivity restore
    - _Requirements: 11.4_

  - [x] 13.5 Write unit tests for navigation, toast, and theme
    - Test nav links, balance display, account menu, logout
    - Test toast display, auto-dismiss, different types
    - Test theme toggle, localStorage persistence
    - _Requirements: 12.1–12.5, 10.7_

- [x] 14. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Integration and smoke tests
  - [x] 15.1 Write integration tests
    - Auth flow: login → token refresh → logout with mocked API
    - Betting flow: select mode → join round → place bet → receive result with mocked WS
    - Deposit flow: Stripe Elements → deposit → balance update with mocked Stripe and API
    - WebSocket lifecycle: connect → receive messages → disconnect → reconnect with mocked WS
    - Offline resilience: go offline → queue actions → come online → retry
    - _Requirements: 1.3–1.5, 3.1–3.6, 2.2–2.3, 3.7, 11.4_

  - [x] 15.2 Write smoke tests
    - Accessibility: axe-core audit on game view, wallet, leaderboard pages
    - Routing: all routes render without crash, auth guards redirect correctly
    - Responsive: key pages render at 320px, 768px, 1920px without overflow
    - _Requirements: 10.1–10.5_

- [x] 16. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document using fast-check
- Unit tests validate specific examples and edge cases
- All monetary values use string-based decimal arithmetic (`decimal.js`) to avoid floating-point issues
- TypeScript is used throughout as specified in the design document
