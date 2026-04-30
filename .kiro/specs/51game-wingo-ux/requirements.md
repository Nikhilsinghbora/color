# Requirements Document

## Introduction

This document defines the requirements for a comprehensive UI/UX overhaul of the Color Prediction Game to match the 51game WinGo platform interface. The overhaul spans both backend and frontend, adding Big/Small betting mechanics, game mode timer tabs, formatted period numbers, a bet confirmation bottom sheet, win/loss celebration dialogs, sound effects, a scrolling announcement bar, a "How to Play" rules modal, an enhanced game history table with pagination, a quick multiplier row, and a wallet card. The existing FastAPI backend, React/Next.js frontend, WebSocket real-time updates, and Zustand state management are extended — not replaced.

## Glossary

- **Game_View**: The primary frontend page component (`frontend/src/app/game/page.tsx`) that renders the active game round, betting controls, timer, and results
- **Game_Engine**: The backend service (`app/services/game_engine.py`) that orchestrates round lifecycle (start, resolve, finalize) and bet placement
- **Payout_Calculator**: The backend service (`app/services/payout_calculator.py`) that computes payouts for all bet types using Decimal arithmetic
- **Game_Store**: The Zustand store (`frontend/src/stores/game-store.ts`) managing client-side game state including round info, phase, timer, bets, and results
- **WS_Manager**: The backend WebSocket connection manager (`app/services/ws_manager.py`) that tracks per-round, per-player connections and handles Redis pub/sub fan-out
- **Advance_Task**: The Celery periodic task (`app/tasks/game_tasks.py:advance_game_round`) that drives round state transitions based on timer expiry
- **Bet_Confirmation_Sheet**: A bottom sheet modal that appears when a player taps a betting button, allowing them to configure bet amount, quantity, and multiplier before confirming
- **Win_Loss_Dialog**: A popup dialog shown after round results when the player had active bets, displaying the outcome with celebration or loss styling
- **Sound_Manager**: A frontend service that manages audio playback for countdown beeps, bet confirmations, and win celebrations, respecting user mute preferences
- **Announcement_Bar**: A horizontally scrolling marquee component displaying platform announcements below the wallet area
- **Period_Number**: A formatted identifier for game rounds using the pattern YYYYMMDD + mode_prefix + sequential_number (e.g., "20250429100051058")
- **Game_Mode_Tabs**: A horizontal tab bar allowing players to switch between game modes (30s, 1Min, 3Min, 5Min)
- **History_Table**: A paginated table component with three sub-tabs (Game history, Chart, My history) replacing the current HistoryTabs component
- **Wallet_Card**: A prominent card at the top of the Game_View displaying the player's balance with Withdraw and Deposit action buttons
- **Quick_Multiplier_Row**: A row of multiplier buttons (Random, X1, X5, X10, X20, X50, X100) that set the bet quantity multiplier
- **Rules_Modal**: A modal dialog explaining payout rules for all bet types including color, number, big/small, and service fee
- **Number_Color_Map**: The mapping of numbers 0–9 to colors: 0 and 5 are green+violet, 1/3/7/9 are green, 2/4/6/8 are red
- **Service_Fee**: A 2% deduction applied to all bet amounts before payout calculation (payout is calculated on 98% of the bet amount)
- **Big_Bet**: A bet type where the player wagers that the winning number will be 5, 6, 7, 8, or 9
- **Small_Bet**: A bet type where the player wagers that the winning number will be 0, 1, 2, 3, or 4

## Requirements

### Requirement 1: Big/Small Betting Backend Support

**User Story:** As a player, I want to place Big or Small bets predicting whether the winning number will be high (5–9) or low (0–4), so that I have an additional betting option with even odds.

#### Acceptance Criteria

1. WHEN a Player places a bet with the color field set to "big", THE Game_Engine SHALL accept the bet and store it with odds retrieved from `GameMode.odds["big"]` (default 2.0x)
2. WHEN a Player places a bet with the color field set to "small", THE Game_Engine SHALL accept the bet and store it with odds retrieved from `GameMode.odds["small"]` (default 2.0x)
3. WHEN a round is resolved and the winning number is 5, 6, 7, 8, or 9, THE Payout_Calculator SHALL mark all "big" bets as winners and calculate payout as `bet_amount × big_odds`, quantized to 2 decimal places
4. WHEN a round is resolved and the winning number is 0, 1, 2, 3, or 4, THE Payout_Calculator SHALL mark all "small" bets as winners and calculate payout as `bet_amount × small_odds`, quantized to 2 decimal places
5. WHEN a round is resolved and the winning number is 5, 6, 7, 8, or 9, THE Payout_Calculator SHALL mark all "small" bets as losers with payout of 0.00
6. WHEN a round is resolved and the winning number is 0, 1, 2, 3, or 4, THE Payout_Calculator SHALL mark all "big" bets as losers with payout of 0.00
7. IF a Player places a bet with a color field value that is not a valid color name, digit string "0"–"9", "big", or "small", THEN THE Game_Engine SHALL reject the bet with a validation error

### Requirement 2: Service Fee Deduction

**User Story:** As a platform operator, I want a 2% service fee deducted from all bets before payout calculation, so that the platform retains a consistent fee on every wager.

#### Acceptance Criteria

1. WHEN the Payout_Calculator calculates a winning payout, THE Payout_Calculator SHALL compute the effective bet amount as `bet_amount × 0.98` (deducting 2% service fee) before multiplying by odds
2. THE Payout_Calculator SHALL calculate the final payout as `(bet_amount × 0.98) × odds`, quantized to 2 decimal places
3. THE Service_Fee percentage SHALL be configurable via a settings constant (default 0.02) rather than hardcoded in the payout formula
4. WHEN a bet is placed, THE Game_Engine SHALL deduct the full bet amount from the player's wallet (the service fee is applied only during payout calculation, not during bet placement)

### Requirement 3: Big/Small Betting Frontend

**User Story:** As a player, I want Big and Small betting buttons displayed below the number grid, so that I can quickly place Big/Small bets from the game interface.

#### Acceptance Criteria

1. THE Game_View SHALL display two buttons labeled "Big" and "Small" arranged horizontally below the Number_Grid
2. THE "Big" button SHALL display the text "5-9" and the multiplier "x2.0" (or the configured big odds from the game mode)
3. THE "Small" button SHALL display the text "0-4" and the multiplier "x2.0" (or the configured small odds from the game mode)
4. WHEN a Player taps the "Big" button during the betting phase, THE Game_View SHALL open the Bet_Confirmation_Sheet with the bet type set to "big"
5. WHEN a Player taps the "Small" button during the betting phase, THE Game_View SHALL open the Bet_Confirmation_Sheet with the bet type set to "small"
6. WHILE the current round is not in the betting phase, THE Big/Small buttons SHALL be visually disabled with reduced opacity and SHALL NOT respond to tap or click events
7. WHEN a Player has placed a bet on "big" or "small", THE corresponding button SHALL display a visual indicator showing the bet has been placed

### Requirement 4: Game Mode Timer Tabs

**User Story:** As a player, I want to switch between different game modes (30s, 1Min, 3Min, 5Min) using tabs, so that I can choose my preferred round duration.

#### Acceptance Criteria

1. THE Game_View SHALL display a horizontal tab bar above the timer area with tabs for each active game mode, labeled as "Win Go 30s", "Win Go 1Min", "Win Go 3Min", "Win Go 5Min"
2. THE Game_Mode_Tabs SHALL highlight the currently active tab with distinct background color and text styling to differentiate it from inactive tabs
3. WHEN a Player taps an inactive game mode tab, THE Game_View SHALL switch the active game mode, disconnect from the current round's WebSocket, and connect to the active round for the selected game mode
4. WHEN a Player switches game modes, THE Game_Store SHALL reset the round state (phase, timer, bets, result) and load the new mode's round state from the initial WebSocket round_state message
5. THE Game_Mode_Tabs SHALL fetch the list of available game modes from the `GET /api/v1/game/modes` endpoint on initial load
6. WHILE a game mode tab is active, THE tab SHALL display the mode name and duration text

### Requirement 5: Period Number Display

**User Story:** As a player, I want to see a formatted period number instead of a UUID for each round, so that I can easily reference and track specific rounds.

#### Acceptance Criteria

1. THE Game_View SHALL display a formatted period number in the timer area, replacing the current UUID-based round identifier
2. THE Period_Number SHALL follow the format `YYYYMMDD` + mode_prefix (3 digits) + sequential_number (7 digits), producing strings like "20250429100051058"
3. WHEN a new round starts, THE backend SHALL generate the Period_Number based on the current UTC date, the game mode's assigned prefix, and an auto-incrementing sequence number scoped to the game mode and date
4. THE Period_Number SHALL be stored on the GameRound model and included in WebSocket round_state and new_round messages
5. THE History_Table SHALL display the Period_Number in the "Period" column instead of the round UUID
6. THE Win_Loss_Dialog SHALL display the Period_Number of the resolved round

### Requirement 6: Bet Confirmation Bottom Sheet

**User Story:** As a player, I want a confirmation bottom sheet when I tap a betting button, so that I can review and adjust my bet before placing it.

#### Acceptance Criteria

1. WHEN a Player taps any betting button (color, number, big, or small) during the betting phase, THE Game_View SHALL display the Bet_Confirmation_Sheet as a bottom sheet overlay instead of placing the bet immediately
2. THE Bet_Confirmation_Sheet SHALL display a header showing the game mode name and the selected bet type (e.g., "Win Go 1Min — Select Green")
3. THE Bet_Confirmation_Sheet SHALL display balance preset buttons with values ₹1, ₹10, ₹100, and ₹1000, and THE Player SHALL be able to select one preset at a time
4. THE Bet_Confirmation_Sheet SHALL display quantity controls with a minus button, a numeric input field (range 1–100), and a plus button
5. THE Bet_Confirmation_Sheet SHALL display a multiplier row with buttons X1, X5, X10, X20, X50, X100, and THE Player SHALL be able to select one multiplier at a time
6. THE Bet_Confirmation_Sheet SHALL display an "I agree with the pre-sale rules" checkbox that must be checked before the confirm button becomes active
7. THE Bet_Confirmation_Sheet SHALL display a footer with a Cancel button and a Confirm button showing "Total amount ₹X.XX" where the total equals `selected_balance × selected_quantity`
8. WHEN the Player taps the Confirm button, THE Game_View SHALL validate that the total amount does not exceed the player's wallet balance before sending the bet to the API
9. IF the total amount exceeds the player's wallet balance, THEN THE Bet_Confirmation_Sheet SHALL display an inline error message and SHALL NOT submit the bet
10. WHEN the Player taps the Cancel button, THE Bet_Confirmation_Sheet SHALL close without placing any bet

### Requirement 7: Win/Loss Celebration Dialog

**User Story:** As a player, I want to see a celebration popup after a round result when I had active bets, so that I know immediately whether I won or lost and by how much.

#### Acceptance Criteria

1. WHEN a round enters the result phase and the Player had placed bets in that round, THE Game_View SHALL display the Win_Loss_Dialog as a centered modal overlay
2. WHEN the Player won at least one bet, THE Win_Loss_Dialog SHALL display a "Congratulations" header with celebration styling (gold/green theme)
3. WHEN the Player lost all bets, THE Win_Loss_Dialog SHALL display a "Sorry" header with loss styling (muted/gray theme)
4. THE Win_Loss_Dialog SHALL display the lottery result: the winning number with its color indicator and a "Big" or "Small" label based on whether the winning number is >= 5 or <= 4
5. THE Win_Loss_Dialog SHALL display the total bonus amount (sum of all payouts for the player in that round) formatted with currency symbol
6. THE Win_Loss_Dialog SHALL display the Period_Number of the resolved round
7. THE Win_Loss_Dialog SHALL display a countdown timer starting at 3 seconds, and WHEN the countdown reaches zero, THE dialog SHALL auto-close
8. THE Win_Loss_Dialog SHALL display a close button that allows the Player to dismiss the dialog before the auto-close countdown expires

### Requirement 8: Sound Effects

**User Story:** As a player, I want audio feedback during key game moments (countdown, bet placement, win), so that the experience feels more engaging and immersive.

#### Acceptance Criteria

1. WHILE the betting phase countdown has 5 or fewer seconds remaining, THE Sound_Manager SHALL play a tick sound each second
2. WHEN the betting phase countdown reaches the final second (1 second remaining), THE Sound_Manager SHALL play a distinct "last second" sound different from the regular tick
3. WHEN a bet is successfully placed (API returns success), THE Sound_Manager SHALL play a bet confirmation sound
4. WHEN the Win_Loss_Dialog displays a win result, THE Sound_Manager SHALL play a win celebration sound
5. THE Game_View SHALL display a sound toggle button in the header area that allows the Player to mute or unmute all game sounds
6. THE Sound_Manager SHALL persist the mute/unmute preference in localStorage so the setting survives page reloads
7. THE Sound_Manager SHALL NOT autoplay any sounds until the Player has interacted with the page (click, tap, or keypress), complying with browser autoplay policies

### Requirement 9: Scrolling Announcement Bar

**User Story:** As a player, I want to see platform announcements in a scrolling marquee, so that I stay informed about promotions and notices without leaving the game.

#### Acceptance Criteria

1. THE Game_View SHALL display the Announcement_Bar below the Wallet_Card area as a horizontally scrolling marquee
2. THE Announcement_Bar SHALL display a speaker/megaphone icon on the left side and a "Detail" button on the right side
3. THE Announcement_Bar SHALL scroll the announcement text continuously from right to left at a readable pace
4. THE Announcement_Bar text content SHALL be configurable via a frontend configuration constant or fetched from an API endpoint
5. WHEN the Player taps the "Detail" button, THE Game_View SHALL navigate to an announcements detail page or display a modal with the full announcement content

### Requirement 10: How to Play Rules Modal

**User Story:** As a player, I want to access a "How to Play" modal explaining payout rules, so that I understand the game mechanics before betting.

#### Acceptance Criteria

1. THE Game_View SHALL display a "How to Play" button (or question mark icon) in the timer area near the period number
2. WHEN the Player taps the "How to Play" button, THE Game_View SHALL display the Rules_Modal as a centered overlay
3. THE Rules_Modal SHALL explain color bet payouts: Green pays 2x, Red pays 2x, Violet pays 4.8x
4. THE Rules_Modal SHALL explain number bet payouts: matching a specific number pays 9.6x
5. THE Rules_Modal SHALL explain Big/Small bet payouts: Big (5–9) pays 2x, Small (0–4) pays 2x
6. THE Rules_Modal SHALL explain the 2% service fee deduction applied to all winning payouts
7. THE Rules_Modal SHALL display a close button at the bottom that dismisses the modal

### Requirement 11: Enhanced Game History Table

**User Story:** As a player, I want a detailed game history table with pagination and multiple views, so that I can analyze past results and track my betting performance.

#### Acceptance Criteria

1. THE Game_View SHALL replace the current HistoryTabs component with the History_Table component containing three sub-tabs: "Game history", "Chart", and "My history"
2. WHEN the "Game history" tab is active, THE History_Table SHALL display a paginated table with columns: Period (period number), Number (winning number with color-coded background), Big/Small (text label), and Color (colored dots — multiple dots for dual-color numbers 0 and 5)
3. THE "Game history" table SHALL display 10 rows per page with pagination controls including page numbers and previous/next arrows
4. WHEN the "My history" tab is active, THE History_Table SHALL display the Player's bet history with columns: Period, bet type, bet amount, outcome (win/loss), and payout amount
5. WHEN the "Chart" tab is active, THE History_Table SHALL display a placeholder or basic visual trend indicator of recent winning numbers (this tab is optional for initial release)
6. THE History_Table "Game history" data SHALL be fetched from a paginated API endpoint `GET /api/v1/game/history` that returns completed rounds with period number, winning number, winning color, and big/small label
7. THE History_Table "My history" data SHALL be fetched from a paginated API endpoint `GET /api/v1/game/my-history` that returns the player's bets with outcomes

### Requirement 12: Quick Multiplier Row

**User Story:** As a player, I want quick multiplier buttons to set my bet quantity multiplier, so that I can adjust bet sizes rapidly without manual input.

#### Acceptance Criteria

1. THE Bet_Confirmation_Sheet SHALL display the Quick_Multiplier_Row containing buttons: "Random", X1, X5, X10, X20, X50, X100
2. WHEN the Player taps a multiplier button (X1 through X100), THE Bet_Confirmation_Sheet SHALL set the quantity field to the selected multiplier value
3. WHEN the Player taps the "Random" button, THE Bet_Confirmation_Sheet SHALL randomly select one of the available bet options (a color, number, or big/small) and populate the bet type accordingly
4. THE Quick_Multiplier_Row SHALL highlight the currently active multiplier button with distinct styling
5. THE total amount displayed in the Bet_Confirmation_Sheet footer SHALL update immediately when the multiplier changes, calculated as `selected_balance × selected_multiplier`

### Requirement 13: Wallet Card at Top

**User Story:** As a player, I want a prominent wallet balance card at the top of the game view, so that I can always see my current balance and quickly access deposit/withdraw actions.

#### Acceptance Criteria

1. THE Game_View SHALL display the Wallet_Card at the top of the page, above the Game_Mode_Tabs
2. THE Wallet_Card SHALL display the player's current wallet balance with a currency symbol (₹) and a wallet icon
3. THE Wallet_Card SHALL display a "Withdraw" button and a "Deposit" button side by side
4. WHEN the Player taps the "Withdraw" button, THE Game_View SHALL navigate to the wallet withdrawal page (`/wallet`)
5. WHEN the Player taps the "Deposit" button, THE Game_View SHALL navigate to the wallet deposit page (`/wallet`)
6. THE Wallet_Card balance SHALL update in real-time when the Player places a bet (debit) or receives a payout (credit), reflecting the value from the wallet store

### Requirement 14: Game History API Endpoints

**User Story:** As a frontend developer, I want paginated API endpoints for game history and player bet history, so that the History_Table can fetch data efficiently.

#### Acceptance Criteria

1. THE backend SHALL expose a `GET /api/v1/game/history` endpoint that returns paginated completed rounds with fields: period_number, winning_number, winning_color, big_small_label, and completed_at
2. THE `GET /api/v1/game/history` endpoint SHALL accept query parameters `page` (default 1) and `size` (default 10) for pagination
3. THE `GET /api/v1/game/history` endpoint SHALL return results ordered by completed_at descending (most recent first)
4. THE backend SHALL expose a `GET /api/v1/game/my-history` endpoint (authenticated) that returns the player's bets with fields: period_number, bet_type, bet_amount, is_winner, payout_amount, and created_at
5. THE `GET /api/v1/game/my-history` endpoint SHALL accept query parameters `page` (default 1) and `size` (default 10) for pagination
6. WHEN the winning number is 5, 6, 7, 8, or 9, THE `big_small_label` field SHALL be "Big"
7. WHEN the winning number is 0, 1, 2, 3, or 4, THE `big_small_label` field SHALL be "Small"

### Requirement 15: Period Number Backend Generation

**User Story:** As a backend developer, I want the system to generate formatted period numbers for each round, so that rounds have human-readable identifiers.

#### Acceptance Criteria

1. WHEN a new round is created via `Game_Engine.start_round()`, THE Game_Engine SHALL generate a Period_Number in the format `YYYYMMDD` + `mode_prefix` (3 digits) + `sequence_number` (7 digits, zero-padded)
2. THE `mode_prefix` SHALL be derived from the GameMode configuration (e.g., "100" for 30s mode, "101" for 1Min mode, "102" for 3Min mode, "103" for 5Min mode)
3. THE `sequence_number` SHALL auto-increment per game mode per UTC date, starting at 0000001 each new day
4. THE GameRound model SHALL include a `period_number` field (String, unique, indexed) to store the generated period number
5. THE WebSocket round_state and new_round messages SHALL include the `period_number` field
6. IF the sequence number exceeds 9999999 for a given mode and date, THEN THE Game_Engine SHALL log an error and use the next available number without wrapping

### Requirement 16: Game Mode WebSocket Switching

**User Story:** As a player, I want the WebSocket connection to switch seamlessly when I change game modes, so that I receive real-time updates for the correct round.

#### Acceptance Criteria

1. WHEN a Player selects a different game mode tab, THE WS_Client SHALL disconnect from the current round's WebSocket connection
2. WHEN a Player selects a different game mode tab, THE WS_Client SHALL establish a new WebSocket connection to the active round for the selected game mode
3. THE backend SHALL expose a mechanism (via the game modes endpoint or a dedicated endpoint) to retrieve the current active round ID for a given game mode
4. WHEN the new WebSocket connection is established, THE WS_Manager SHALL send an initial round_state message for the new mode's active round
5. IF the WebSocket disconnection or reconnection fails, THEN THE Game_View SHALL display a reconnecting banner and retry the connection
