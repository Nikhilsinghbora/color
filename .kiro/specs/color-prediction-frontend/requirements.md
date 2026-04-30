# Requirements Document

## Introduction

This document defines the requirements for the React/Next.js frontend of the Color Prediction Game platform. The frontend integrates with an existing Python/FastAPI backend that provides authentication, wallet management, game engine, leaderboards, social features, responsible gambling controls, and admin functionality via REST API endpoints and WebSocket connections. The frontend delivers a responsive, accessible, real-time gaming experience across desktop and mobile devices, handling JWT-based authentication flows, Stripe payment integration, WebSocket-driven game state updates, and comprehensive admin tooling.

## Glossary

- **Frontend**: The React/Next.js client application that renders the Color Prediction Game user interface
- **API_Client**: The HTTP client module that communicates with the FastAPI backend REST endpoints
- **Auth_Store**: The client-side state management module that stores JWT tokens and manages authentication state
- **WS_Client**: The WebSocket client module that maintains persistent connections to the backend for real-time game updates and chat
- **Game_View**: The primary UI component that displays the active Game_Round, color options, betting controls, and results
- **Wallet_Panel**: The UI component that displays wallet balance, deposit/withdrawal forms, and transaction history
- **Leaderboard_View**: The UI component that renders ranked player listings with filtering by metric and time period
- **Admin_Dashboard**: The protected UI section accessible only to Admin users for platform management
- **Toast_Notification**: A transient UI message displayed to inform the Player of events such as bet confirmation, payout receipt, or errors
- **Color_Chip**: A clickable UI element representing a single Color_Option that a Player can select for a Prediction
- **Countdown_Timer**: A visual timer component synchronized with the backend Betting_Phase duration via WebSocket
- **Player**: A registered user who interacts with the Frontend
- **Admin**: A privileged user who accesses the Admin_Dashboard
- **Session**: An authenticated period of Frontend activity backed by valid JWT tokens in the Auth_Store

## Requirements

### Requirement 1: Authentication UI and Token Management

**User Story:** As a player, I want to register, log in, and manage my account through intuitive forms, so that I can securely access the platform.

#### Acceptance Criteria

1. WHEN a visitor navigates to the registration page, THE Frontend SHALL display a form requesting email, username, and password with client-side validation for email format, username length (1–50 characters), and password complexity before submission
2. WHEN a visitor submits a valid registration form, THE Frontend SHALL send a POST request to `/api/v1/auth/register` and display a success message instructing the visitor to verify the email address
3. WHEN a Player submits valid credentials on the login page, THE Frontend SHALL send a POST request to `/api/v1/auth/login`, store the returned JWT access token and refresh token in the Auth_Store, and redirect the Player to the Game_View
4. WHEN the API_Client receives a 401 response with an expired token error, THE Auth_Store SHALL automatically attempt to refresh the token by calling `/api/v1/auth/refresh` with the stored refresh token before retrying the original request
5. IF the token refresh fails, THEN THE Frontend SHALL clear the Auth_Store, redirect the Player to the login page, and display a session expired message
6. WHEN a Player clicks the "Forgot Password" link, THE Frontend SHALL display a form to enter the registered email and send a POST request to `/api/v1/auth/password-reset-request`
7. WHEN a Player navigates to the password reset URL with a valid token, THE Frontend SHALL display a form to enter and confirm a new password and send a POST request to `/api/v1/auth/password-reset`
8. THE Frontend SHALL protect all authenticated routes using a route guard that checks for a valid token in the Auth_Store and redirects unauthenticated visitors to the login page
9. IF the backend returns a 423 account locked response, THEN THE Frontend SHALL display a message indicating the account is locked and the remaining lockout duration

### Requirement 2: Wallet UI and Payment Integration

**User Story:** As a player, I want to view my balance, deposit funds, and withdraw winnings through a clear interface, so that I can manage my credits easily.

#### Acceptance Criteria

1. WHEN a Player opens the Wallet_Panel, THE Frontend SHALL fetch the current balance from `GET /api/v1/wallet/balance` and display it prominently
2. WHEN a Player initiates a deposit, THE Frontend SHALL render a Stripe Elements payment form, collect payment details, and send the Stripe token with the deposit amount to `POST /api/v1/wallet/deposit`
3. WHEN the deposit API returns a success response, THE Frontend SHALL update the displayed Wallet balance and show a Toast_Notification confirming the deposit amount
4. WHEN a Player initiates a withdrawal, THE Frontend SHALL display a form to enter the withdrawal amount and send a POST request to `POST /api/v1/wallet/withdraw`
5. IF the withdrawal API returns an insufficient balance error, THEN THE Frontend SHALL display the current available balance and a descriptive error message
6. WHEN a Player views the transaction history, THE Frontend SHALL fetch paginated transactions from `GET /api/v1/wallet/transactions` and display them in a scrollable list sorted by most recent first, with transaction type, amount, and timestamp for each entry
7. THE Frontend SHALL display the Wallet balance in the application header on all authenticated pages, updating it in real-time when bet debits or payout credits occur

### Requirement 3: Game View and Real-Time Round Display

**User Story:** As a player, I want to see the current game round with live updates, so that I know when to bet and what the outcome is.

#### Acceptance Criteria

1. WHEN a Player enters the Game_View, THE WS_Client SHALL establish a WebSocket connection to `ws/game/{round_id}` and subscribe to round state updates
2. WHILE the Game_Round is in Betting_Phase, THE Frontend SHALL display all available Color_Chips with their corresponding Odds and enable the betting controls
3. THE Frontend SHALL display a Countdown_Timer synchronized with the backend Betting_Phase duration, updating every second based on WebSocket tick messages
4. WHEN the WS_Client receives a phase transition message to Resolution_Phase, THE Frontend SHALL disable all betting controls, hide the Countdown_Timer, and display a "Resolving..." animation
5. WHEN the WS_Client receives a Result_Phase message with the winning color, THE Frontend SHALL highlight the winning Color_Chip, display the result, and show the Player's Payout or loss amount via a Toast_Notification
6. WHEN the WS_Client receives a new round initiation message, THE Frontend SHALL reset the Game_View, re-enable betting controls, and start the Countdown_Timer for the new round
7. IF the WebSocket connection drops, THEN THE WS_Client SHALL attempt to reconnect with exponential backoff (1s, 2s, 4s, up to 30s maximum) and display a connection status indicator to the Player
8. THE Frontend SHALL display the current round number, total players in the round, and total bet pool amount, updated in real-time via WebSocket messages

### Requirement 4: Betting Interface

**User Story:** As a player, I want to select colors and place bets quickly and confidently, so that I can participate in each round without confusion.

#### Acceptance Criteria

1. WHILE the Game_Round is in Betting_Phase, THE Frontend SHALL allow the Player to click one or more Color_Chips to select Predictions
2. WHEN a Player selects a Color_Chip, THE Frontend SHALL visually highlight the selected Color_Chip and display a bet amount input field for that color
3. WHEN a Player enters a bet amount and confirms the bet, THE Frontend SHALL send a POST request to `/api/v1/game/bet` with the round ID, selected color, and bet amount
4. WHEN the bet API returns a success response, THE Frontend SHALL display a Toast_Notification confirming the bet, update the Wallet balance display, and mark the Color_Chip as "bet placed"
5. IF the bet API returns a validation error (amount below minimum, above maximum, or insufficient balance), THEN THE Frontend SHALL display the specific error message adjacent to the bet input field
6. IF the bet API returns a "betting closed" error, THEN THE Frontend SHALL disable all betting controls and display a message that the Betting_Phase has ended
7. THE Frontend SHALL display the configured minimum and maximum bet amounts for the current Game_Mode adjacent to the bet input field
8. THE Frontend SHALL display a summary of all bets placed by the Player in the current round, showing color, amount, and potential payout for each bet

### Requirement 5: Game Mode Selection

**User Story:** As a player, I want to browse and select different game modes, so that I can choose the gameplay experience I prefer.

#### Acceptance Criteria

1. WHEN a Player navigates to the game mode selection page, THE Frontend SHALL fetch available game modes from `GET /api/v1/game/modes` and display each mode with its name, description, and status
2. WHEN a Player selects a Game_Mode, THE Frontend SHALL fetch the mode details and display the rules, available Color_Options with Odds, Betting_Limits (minimum and maximum), and round duration before the Player enters the Game_View
3. WHEN a Player confirms the Game_Mode selection, THE Frontend SHALL navigate to the Game_View configured for that mode and join the current active round
4. THE Frontend SHALL visually distinguish between Classic, Timed_Challenge, and Tournament Game_Modes using distinct icons or color themes

### Requirement 6: Leaderboard Display

**User Story:** As a player, I want to view leaderboards to see how I rank against others, so that I can track my progress and compete.

#### Acceptance Criteria

1. WHEN a Player navigates to the Leaderboard_View, THE Frontend SHALL fetch leaderboard data from `GET /api/v1/leaderboard/{metric}` and display the top 100 players with rank, username, and metric value
2. THE Frontend SHALL provide filter controls to switch between leaderboard metrics (total winnings, win rate, win streak) and time periods (daily, weekly, monthly, all-time)
3. WHEN a Player views a Leaderboard, THE Frontend SHALL highlight the viewing Player's own row with a distinct visual style and scroll to the Player's position if the Player is outside the visible viewport
4. WHEN a Player selects a different metric or time period filter, THE Frontend SHALL fetch the corresponding leaderboard data and update the display without a full page reload

### Requirement 7: Social Features UI

**User Story:** As a player, I want to invite friends, chat during games, and view profiles, so that the game feels social and engaging.

#### Acceptance Criteria

1. WHEN a Player creates a private round, THE Frontend SHALL display the generated invite code with a copy-to-clipboard button and a share link
2. WHEN a Player enters an invite code, THE Frontend SHALL send a request to `POST /api/v1/social/join` and navigate the Player to the corresponding private Game_Round on success
3. WHILE a Game_Round is active, THE Frontend SHALL display a chat panel that sends messages through the WebSocket connection and renders incoming messages from other Players in real-time
4. THE Frontend SHALL allow a Player to search for other Players by username and send friend requests via `POST /api/v1/social/friends`
5. WHEN a Player views a friend's profile, THE Frontend SHALL fetch and display the friend's public statistics (total games played, win rate, leaderboard rank) from `GET /api/v1/social/profile/{player_id}`
6. THE Frontend SHALL display an unread message indicator on the chat panel toggle when new chat messages arrive while the panel is collapsed

### Requirement 8: Responsible Gambling UI

**User Story:** As a player, I want easy access to responsible gambling tools, so that I can manage my gaming habits and spending limits.

#### Acceptance Criteria

1. THE Frontend SHALL display a responsible gambling information link in the footer of every page that contains betting functionality, linking to a dedicated responsible gambling information page
2. WHEN a Player navigates to the responsible gambling settings page, THE Frontend SHALL fetch current limits from `GET /api/v1/responsible-gambling/deposit-limit` and display forms to set or update daily, weekly, and monthly deposit limits
3. WHEN a Player sets a deposit limit, THE Frontend SHALL send a POST request to `/api/v1/responsible-gambling/deposit-limit` and display a confirmation Toast_Notification
4. WHEN a Player navigates to session limit settings, THE Frontend SHALL display a form to set a session time limit in minutes and send a POST request to `/api/v1/responsible-gambling/session-limit`
5. WHILE a Player's session time limit is active, THE Frontend SHALL display a session duration counter and show a mandatory reminder notification when the limit is reached
6. WHEN a Player requests self-exclusion, THE Frontend SHALL display a confirmation dialog explaining the consequences and available durations (24 hours, 7 days, 30 days, permanent), and send a POST request to `/api/v1/responsible-gambling/self-exclude` upon confirmation
7. IF the backend returns a loss threshold warning, THEN THE Frontend SHALL display a modal dialog requiring the Player to acknowledge the warning before any further betting actions are permitted


### Requirement 9: Admin Dashboard UI

**User Story:** As an admin, I want a comprehensive dashboard to monitor platform activity and manage configuration, so that I can ensure fair and compliant operation.

#### Acceptance Criteria

1. THE Frontend SHALL restrict access to the Admin_Dashboard to users whose JWT token contains an admin role claim, redirecting non-admin users to the Game_View
2. WHEN an Admin opens the Admin_Dashboard, THE Frontend SHALL fetch and display key metrics from `GET /api/v1/admin/dashboard` including active player count, total bets placed, total payouts distributed, and platform revenue for a selectable time period
3. WHEN an Admin navigates to the game configuration page, THE Frontend SHALL fetch current settings from `GET /api/v1/admin/game-config` and display editable forms for Betting_Limits, Odds, number of Color_Options, and round duration per Game_Mode
4. WHEN an Admin submits a configuration change, THE Frontend SHALL send a POST request to `/api/v1/admin/game-config` and display a Toast_Notification confirming the change will take effect on the next Game_Round
5. WHEN an Admin navigates to the player management page, THE Frontend SHALL fetch and display a searchable, paginated list of players from `GET /api/v1/admin/players` with options to suspend or ban accounts
6. WHEN an Admin navigates to the audit log page, THE Frontend SHALL fetch and display paginated audit logs from `GET /api/v1/admin/audit-logs` with filters for event type, date range, and actor
7. WHEN an Admin navigates to the RNG audit page, THE Frontend SHALL fetch and display RNG audit entries from `GET /api/v1/admin/rng-audit` showing round ID, algorithm, raw value, number of options, and selected color for each entry

### Requirement 10: Responsive Layout and Accessibility

**User Story:** As a player, I want the game to work well on any device and be accessible, so that I can play comfortably regardless of my device or abilities.

#### Acceptance Criteria

1. THE Frontend SHALL render a responsive layout that adapts to viewport widths from 320px (mobile) to 1920px (desktop) without horizontal scrolling or content overflow
2. THE Frontend SHALL use semantic HTML elements (nav, main, section, article, button) and ARIA attributes to support screen reader navigation
3. THE Frontend SHALL ensure all interactive elements (Color_Chips, buttons, form inputs) are keyboard navigable using Tab, Enter, and Escape keys
4. THE Frontend SHALL maintain a minimum color contrast ratio of 4.5:1 for normal text and 3:1 for large text against background colors
5. THE Frontend SHALL provide visible focus indicators on all interactive elements when navigated via keyboard
6. WHILE the Frontend is loading data from the API, THE Frontend SHALL display skeleton loading states or spinner indicators to communicate loading progress to the Player
7. THE Frontend SHALL support both light and dark color themes, persisting the Player's preference in local storage

### Requirement 11: Error Handling and Offline Resilience

**User Story:** As a player, I want clear feedback when something goes wrong, so that I understand what happened and what to do next.

#### Acceptance Criteria

1. WHEN the API_Client receives an error response, THE Frontend SHALL parse the error code and message from the response body and display a human-readable Toast_Notification with the error description
2. IF the API_Client receives a 429 rate limit response, THEN THE Frontend SHALL display a "Too many requests" message and disable the triggering action for the duration specified in the Retry-After header
3. IF the API_Client receives a 500 or 503 response, THEN THE Frontend SHALL display a generic "Something went wrong" message with a retry button
4. WHEN the browser detects a loss of network connectivity, THE Frontend SHALL display a persistent banner indicating offline status and queue any pending actions for retry when connectivity is restored
5. THE Frontend SHALL display form-level validation errors inline adjacent to the relevant input fields, and API-returned validation errors mapped to the corresponding form fields

### Requirement 12: Navigation and Application Shell

**User Story:** As a player, I want intuitive navigation across all sections of the app, so that I can find what I need quickly.

#### Acceptance Criteria

1. THE Frontend SHALL display a persistent navigation bar containing links to Game_View, Wallet_Panel, Leaderboard_View, Social features, and account settings
2. THE Frontend SHALL display the Player's username and current Wallet balance in the navigation bar on all authenticated pages
3. WHEN a Player clicks the account menu, THE Frontend SHALL display a dropdown with links to profile settings, responsible gambling settings, and a logout action
4. WHEN a Player clicks logout, THE Frontend SHALL clear the Auth_Store, close any active WebSocket connections, and redirect to the login page
5. THE Frontend SHALL use Next.js client-side routing for navigation between pages to avoid full page reloads
