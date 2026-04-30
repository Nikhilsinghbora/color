# Requirements Document

## Introduction

This document defines the requirements for two changes to the Color Prediction Game platform: (1) a complete UI redesign of the frontend game view to match a casino-style color prediction game aesthetic with number-based betting, circular countdown timer, and dark gradient theme, and (2) a bug fix ensuring the game functions correctly when only a single player is connected. The redesign transforms the current generic Tailwind layout with simple color chips into a polished casino-style interface featuring a result display area, color betting buttons (Green, Violet, Red) with multipliers, a 0–9 number betting grid with color-coded numbers, a bottom bar with balance/win/bet controls, and history/my-bets tabs. The single-player bug fix addresses issues in the round lifecycle and WebSocket state propagation that prevent the game from functioning when only one player is present.

## Glossary

- **Game_View**: The primary frontend page component (`frontend/src/app/game/page.tsx`) that renders the active game round, betting controls, timer, and results
- **Result_Display**: A large UI area at the top of the Game_View showing the last winning number with its corresponding color background (green, red, or violet)
- **Countdown_Timer**: A circular visual timer component displaying seconds remaining in the current betting phase
- **Color_Bet_Button**: One of three large betting buttons (Green, Violet, Red) that a Player can tap to place a color-based bet with displayed multiplier
- **Number_Grid**: A 0–9 grid of numbered betting buttons where each number is color-coded (green, red, or green+violet) and carries a fixed multiplier
- **Bottom_Bar**: A persistent bar at the bottom of the Game_View displaying the Player's balance, last win amount, and bet amount controls (increment, set amount, undo, clear)
- **History_Tab**: A tab at the bottom of the Game_View showing the history of recent round results
- **My_Bets_Tab**: A tab at the bottom of the Game_View showing the Player's bets for the current and recent rounds
- **Game_Store**: The Zustand store (`frontend/src/stores/game-store.ts`) managing client-side game state including round info, phase, timer, bets, and results
- **WS_Client**: The WebSocket client hook (`frontend/src/hooks/useWebSocket.ts`) that connects to the backend and dispatches incoming messages to the Game_Store
- **WS_Manager**: The backend WebSocket connection manager (`app/services/ws_manager.py`) that tracks per-round, per-player connections and handles Redis pub/sub fan-out
- **Game_Engine**: The backend service (`app/services/game_engine.py`) that orchestrates round lifecycle (start, resolve, finalize) and bet placement
- **Advance_Task**: The Celery periodic task (`app/tasks/game_tasks.py:advance_game_round`) that drives round state transitions based on timer expiry
- **Round_Phase**: One of three sequential phases: betting, resolution, result
- **Number_Color_Map**: The mapping of numbers 0–9 to colors: 0 and 5 are green+violet, 1/3/7/9 are green, 2/4/6/8 are red

## Requirements

### Requirement 1: Casino-Style Dark Theme and Layout

**User Story:** As a player, I want the game view to have a polished casino-style dark gradient theme, so that the experience feels immersive and professional.

#### Acceptance Criteria

1. THE Game_View SHALL render with a dark blue-to-dark-purple vertical gradient background as the primary page background
2. THE Game_View SHALL use a single-column mobile-first layout with the following vertical section order: Result_Display, Countdown_Timer, Color_Bet_Buttons, Number_Grid, Bottom_Bar, and tab area (History_Tab / My_Bets_Tab)
3. THE Game_View SHALL apply rounded corners, subtle shadows, and semi-transparent card backgrounds to all content sections to create visual depth
4. THE Game_View SHALL use white and light-colored text throughout for readability against the dark background, maintaining a minimum contrast ratio of 4.5:1 for normal text
5. THE Game_View SHALL render all interactive elements (buttons, tabs, inputs) with smooth transition animations for hover, active, and disabled states

### Requirement 2: Result Display Area

**User Story:** As a player, I want to see the last winning result prominently displayed, so that I can quickly understand the outcome of the previous round.

#### Acceptance Criteria

1. WHEN a round enters the result phase, THE Result_Display SHALL show the winning number (0–9) in large bold text centered within a circular or rounded container
2. THE Result_Display SHALL set the container background color to match the winning number's color according to the Number_Color_Map (green for 1/3/5/7/9, red for 2/4/6/8, green+violet gradient for 0/5)
3. WHILE the current round is in the betting phase and no previous result exists, THE Result_Display SHALL show a placeholder state indicating "Waiting for result"
4. WHEN a new round begins after a result, THE Result_Display SHALL continue showing the previous round's winning number and color until the new round's result is available

### Requirement 3: Circular Countdown Timer

**User Story:** As a player, I want to see a circular countdown timer during the betting phase, so that I know exactly how much time I have left to place bets.

#### Acceptance Criteria

1. WHILE the current round is in the betting phase, THE Countdown_Timer SHALL display a circular progress ring that depletes as time passes, with the remaining seconds shown as a number in the center
2. THE Countdown_Timer SHALL synchronize its value with WebSocket timer_tick messages from the backend, resetting the local countdown on each received tick
3. WHEN the countdown reaches zero, THE Countdown_Timer SHALL display a "Time's up" or equivalent visual state and the progress ring SHALL be fully depleted
4. WHILE the current round is in the resolution phase, THE Countdown_Timer SHALL be hidden or replaced with a "Resolving..." animation
5. THE Countdown_Timer SHALL use a stroke-dasharray SVG circle or equivalent CSS technique to render the circular progress ring with smooth animation between seconds

### Requirement 4: Color Betting Buttons

**User Story:** As a player, I want three large color betting buttons (Green, Violet, Red) with visible multipliers, so that I can quickly place color-based bets.

#### Acceptance Criteria

1. THE Game_View SHALL display three Color_Bet_Buttons arranged horizontally: Green (labeled "Green" with multiplier text), Violet (labeled "Violet" with multiplier text), and Red (labeled "Red" with multiplier text)
2. WHEN a Player taps a Color_Bet_Button during the betting phase, THE Game_View SHALL open a bet amount input overlay or expand an inline bet entry area for that color
3. THE Green Color_Bet_Button SHALL display a multiplier of x2.0 (or the configured odds from the game mode), the Violet Color_Bet_Button SHALL display a multiplier of x4.8 (or configured odds), and the Red Color_Bet_Button SHALL display a multiplier of x2.0 (or configured odds)
4. WHILE the current round is not in the betting phase, THE Color_Bet_Buttons SHALL be visually disabled with reduced opacity and SHALL NOT respond to tap or click events
5. WHEN a Player has placed a bet on a color, THE corresponding Color_Bet_Button SHALL display a visual indicator (badge or checkmark) showing the bet has been placed

### Requirement 5: Number Betting Grid (0–9)

**User Story:** As a player, I want a grid of numbered buttons (0–9) with color coding and multipliers, so that I can place more specific bets on individual numbers.

#### Acceptance Criteria

1. THE Number_Grid SHALL display buttons for numbers 0 through 9 arranged in a grid layout (two rows of five, or a similar compact arrangement)
2. THE Number_Grid SHALL color each number button according to the Number_Color_Map: numbers 0 and 5 SHALL have a green background with a violet accent or overlay, numbers 1, 3, 7, and 9 SHALL have a green background, and numbers 2, 4, 6, and 8 SHALL have a red background
3. THE Number_Grid SHALL display a multiplier of x9.6 (or the configured number-bet odds) on each number button
4. WHEN a Player taps a number button during the betting phase, THE Game_View SHALL open a bet amount input overlay or expand an inline bet entry area for that number
5. WHILE the current round is not in the betting phase, THE Number_Grid buttons SHALL be visually disabled with reduced opacity and SHALL NOT respond to tap or click events
6. WHEN a Player has placed a bet on a number, THE corresponding number button SHALL display a visual indicator showing the bet has been placed

### Requirement 6: Bottom Bar with Balance, Win, and Bet Controls

**User Story:** As a player, I want a persistent bottom bar showing my balance, last win, and bet amount controls, so that I can manage my bets without navigating away.

#### Acceptance Criteria

1. THE Bottom_Bar SHALL be fixed at the bottom of the Game_View viewport and SHALL display three sections: current wallet balance (labeled "Balance"), last win amount (labeled "Win"), and bet amount controls
2. THE Bottom_Bar balance display SHALL update in real-time when the Player places a bet (debit) or receives a payout (credit), reflecting the value from the wallet store
3. THE Bottom_Bar win display SHALL show the total payout amount from the most recent completed round, or "0.00" if the Player did not win
4. THE Bottom_Bar bet amount controls SHALL include: a numeric display of the current bet amount, increment/decrement buttons (or preset amount buttons like x2, /2), an undo button to remove the last bet selection, and a clear button to remove all pending bet selections
5. WHEN the Player adjusts the bet amount using the Bottom_Bar controls, THE Game_View SHALL apply the selected bet amount to the next color or number bet placed
6. THE Bottom_Bar SHALL remain visible and accessible during all round phases (betting, resolution, result)

### Requirement 7: History and My Bets Tabs

**User Story:** As a player, I want to view recent round results and my own betting history, so that I can track patterns and review my performance.

#### Acceptance Criteria

1. THE Game_View SHALL display a tab bar below the Bottom_Bar (or as a sliding panel) with two tabs: "History" and "My Bets"
2. WHEN the Player selects the History_Tab, THE Game_View SHALL display a scrollable list of recent round results showing the round number, winning number, and winning color for each round
3. WHEN the Player selects the My_Bets_Tab, THE Game_View SHALL display a scrollable list of the Player's bets for the current round and recent past rounds, showing bet type (color or number), bet amount, odds, and outcome (win/loss/pending)
4. THE History_Tab SHALL display results as small colored circles or badges (green, red, violet) in a horizontal scrollable row for compact viewing
5. THE tab content area SHALL be collapsible so the Player can maximize the main game area when not reviewing history

### Requirement 8: Number Betting Backend Support

**User Story:** As a player, I want to place bets on specific numbers (0–9) in addition to colors, so that I can make higher-risk, higher-reward predictions.

#### Acceptance Criteria

1. WHEN a Player places a bet on a number (0–9), THE Game_View SHALL send a POST request to `/api/v1/game/bet` with the bet type indicating a number bet and the selected number value
2. THE Game_Engine SHALL accept number bets where the color field contains the number value (e.g., "0", "1", ... "9") and SHALL validate the bet amount against the configured Betting_Limits
3. WHEN a round is resolved, THE Game_Engine SHALL determine a winning number (0–9) in addition to the winning color, and THE winning number SHALL map to a color according to the Number_Color_Map
4. WHEN a round enters the result phase, THE Game_Engine SHALL mark number bets as winners if the bet's number matches the winning number, using the number-specific odds (e.g., x9.6) for payout calculation
5. THE RNG_Engine SHALL generate a winning number from 0–9 with uniform probability, and THE winning color SHALL be derived from the Number_Color_Map based on the winning number

### Requirement 9: Single-Player Game Functionality

**User Story:** As a player, I want the game to work correctly when I am the only player in a round, so that I can play and practice without needing other participants.

#### Acceptance Criteria

1. WHEN only one Player is connected to a round via WebSocket, THE Advance_Task SHALL resolve the round when the betting timer expires, identical to the behavior with multiple players
2. WHEN only one Player is connected, THE WS_Manager SHALL broadcast round_state, timer_tick, phase_change, result, and new_round messages to that single Player's WebSocket connection
3. WHEN a single Player connects to a round, THE Game_Store SHALL initialize the round state (phase, timer, totalPlayers, totalPool) from the first round_state WebSocket message without requiring a bet_update message from another player
4. WHEN only one Player is connected and places a bet, THE Game_View SHALL update the totalPlayers count to 1 and the totalPool to reflect the Player's bet amount based on the round_state or bet_update message
5. IF the WebSocket connection for the single Player drops and reconnects, THEN THE WS_Client SHALL re-establish the connection and THE Game_Store SHALL restore the current round state from the next round_state message
6. THE Advance_Task SHALL resolve rounds based solely on the betting_ends_at timer expiry, with no minimum player count or minimum bet count requirement

### Requirement 10: WebSocket State Initialization for Single Player

**User Story:** As a player joining a round alone, I want the game UI to properly initialize and display the current round state, so that I can start playing immediately.

#### Acceptance Criteria

1. WHEN a Player's WebSocket connection is accepted, THE WS_Manager SHALL send an initial round_state message containing the current phase, remaining timer seconds, total players (1 for single player), and total pool amount
2. WHEN the Game_Store receives a round_state message with totalPlayers equal to 1, THE Game_View SHALL render the full game interface including the Countdown_Timer, Color_Bet_Buttons, Number_Grid, and Bottom_Bar without waiting for additional players
3. WHEN the WS_Manager broadcasts a round_state message, THE WS_Manager SHALL calculate the total_players count from the number of active WebSocket connections for that round using the get_round_connection_count method
4. IF no bet_update message is received during a round (zero bets placed), THEN THE Game_View SHALL continue to display the countdown timer and allow the round to resolve with no winners
5. WHEN a round resolves with zero bets, THE Advance_Task SHALL finalize the round with zero total payouts and immediately start a new round for the same game mode
