# Implementation Plan: Casino UI Redesign

## Overview

This plan implements three interconnected changes: (1) casino-style dark-themed UI with new components, (2) number betting backend support with winning_number on GameRound and updated RNG/payout logic, and (3) single-player bug fix via WS_Manager initial state push. Tasks are ordered so backend changes land first, then frontend components are built incrementally, and finally everything is wired together.

## Tasks

- [x] 1. Backend: Number betting data model and RNG changes
  - [x] 1.1 Add `winning_number` column to `GameRound` model and create database migration
    - Add `winning_number: Mapped[Optional[int]]` to `app/models/game.py` `GameRound` class
    - Create Alembic migration: `ALTER TABLE game_rounds ADD COLUMN winning_number INTEGER` with CHECK constraint `(winning_number IS NULL OR (winning_number >= 0 AND winning_number <= 9))`
    - _Requirements: 8.3, 8.5_

  - [x] 1.2 Update `RNG_Engine` to generate winning number 0–9 and derive color from `NUMBER_COLOR_MAP`
    - Add `NUMBER_COLOR_MAP`, `GREEN_WINNING_NUMBERS`, `RED_WINNING_NUMBERS`, `VIOLET_WINNING_NUMBERS` constants to `app/services/rng_engine.py`
    - Add `selected_number: int` field to `RNGResult` dataclass
    - Modify `generate_outcome()` to use `secrets.randbelow(10)` for the winning number, derive `selected_color` from `NUMBER_COLOR_MAP`, and keep `color_options` parameter for backward compatibility
    - Update `RNGAuditLog` entry creation to include the winning number
    - _Requirements: 8.3, 8.5_

  - [x] 1.3 Write property test for RNG uniform distribution
    - **Property 7: RNG winning number uniform distribution**
    - Use Hypothesis to generate 1000+ RNG outcomes and validate chi-squared goodness-of-fit (p > 0.01) for numbers 0–9
    - **Validates: Requirements 8.5**

  - [x] 1.4 Write property test for Number-to-Color mapping consistency (backend)
    - **Property 1: Number-to-Color mapping consistency (backend portion)**
    - For all numbers 0–9, verify `NUMBER_COLOR_MAP[n]` returns one of "green", "red", or "violet"
    - **Validates: Requirements 2.2, 5.2, 8.3, 8.5**

- [x] 2. Backend: Payout calculator and game engine updates
  - [x] 2.1 Update `payout_calculator.calculate_round_payouts()` to handle number bets and dual-color numbers
    - Accept `winning_number: int` parameter in addition to `winning_color`
    - For digit-string bets ("0"–"9"): winner if `int(bet.color) == winning_number`, payout uses `odds["number"]` (x9.6)
    - For color bets: green wins if `winning_number in {0,1,3,5,7,9}`, red wins if `winning_number in {2,4,6,8}`, violet wins if `winning_number in {0,5}`
    - All payouts quantized to 2 decimal places
    - _Requirements: 8.3, 8.4_

  - [x] 2.2 Write property test for number bet payout correctness
    - **Property 3: Number bet payout correctness**
    - For any winning number w (0–9), any bet_number (0–9), and any bet_amount > 0: winner iff bet_number == w, payout = bet_amount * number_odds quantized to 2dp
    - **Validates: Requirements 8.4**

  - [x] 2.3 Write property test for color bet payout correctness with dual-color numbers
    - **Property 4: Color bet payout correctness with dual-color numbers**
    - For any winning number w (0–9) and any color bet (green/red/violet): verify correct winner determination per GREEN/RED/VIOLET_WINNING_NUMBERS sets, payout = bet_amount * color_odds quantized to 2dp
    - **Validates: Requirements 8.3, 8.4**

  - [x] 2.4 Update `game_engine.resolve_round()` to store `winning_number` from RNG result
    - Set `game_round.winning_number = rng_result.selected_number` alongside existing `winning_color`
    - _Requirements: 8.3_

  - [x] 2.5 Update `game_engine.finalize_round()` to pass `winning_number` to payout calculator
    - Pass `game_round.winning_number` to `payout_calculator.calculate_round_payouts()`
    - _Requirements: 8.4_

  - [x] 2.6 Update `game_engine.place_bet()` to accept number bets (digit strings "0"–"9")
    - Validate that `color` is either a valid color name or a single digit "0"–"9"
    - For number bets, use `odds["number"]` for `odds_at_placement`
    - _Requirements: 8.2_

  - [x] 2.7 Write property test for number bet acceptance and validation
    - **Property 5: Number bet acceptance and validation**
    - For any digit string "0"–"9" and any amount: accepted iff min_bet <= amount <= max_bet and sufficient balance
    - **Validates: Requirements 8.2**

- [ ] 3. Backend: Single-player bug fix and WebSocket state initialization
  - [-] 3.1 Update `WS_Manager.connect()` to send initial `round_state` message on connection
    - After `await websocket.accept()`, fetch current round state via `game_engine.get_round_state()` using a database session
    - Calculate `total_players` from `get_round_connection_count(round_id)`
    - Calculate remaining timer seconds from `betting_ends_at - now`
    - Send `round_state` message with phase, timer, total_players, total_pool to the newly connected WebSocket
    - Handle errors gracefully: if fetch fails, log and continue (player gets state on next broadcast)
    - _Requirements: 9.2, 9.3, 10.1, 10.3_

  - [~] 3.2 Write property test for WebSocket connection count accuracy
    - **Property 6: WebSocket connection count accuracy**
    - For any sequence of connect/disconnect operations, `get_round_connection_count(round_id)` returns the number of currently active unique players
    - **Validates: Requirements 10.3**

  - [~] 3.3 Update Celery task `_publish_round_state()` to include `winning_number` in result phase payload
    - Add `winning_number` to the published payload when phase is RESULT
    - Ensure round resolution has no minimum player count or bet count requirement (verify existing behavior)
    - _Requirements: 9.1, 9.6, 10.5_

- [~] 4. Checkpoint — Backend tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 5. Frontend: Shared utilities and type updates
  - [~] 5.1 Create `frontend/src/lib/number-color-map.ts` with `NUMBER_COLOR_MAP` constant
    - Define `NUMBER_COLOR_MAP: Record<number, { primary: string; secondary?: string }>` mapping 0–9 to colors
    - Numbers 0 and 5 have `{ primary: 'green', secondary: 'violet' }`, 1/3/7/9 are green, 2/4/6/8 are red
    - _Requirements: 2.2, 5.2_

  - [~] 5.2 Write property test for Number-to-Color mapping consistency (frontend)
    - **Property 1: Number-to-Color mapping consistency (frontend portion)**
    - For all numbers 0–9, verify `NUMBER_COLOR_MAP[n].primary` is one of "green", "red" and optional `secondary` is "violet"
    - **Validates: Requirements 2.2, 5.2, 8.3, 8.5**

  - [~] 5.3 Update `frontend/src/types/index.ts` with number betting types
    - Add `winning_number: number` to the `result` variant of `WSIncomingMessage`
    - Add `winningNumber: number` to `RoundResult` interface
    - _Requirements: 8.3_

  - [~] 5.4 Update `frontend/src/stores/game-store.ts` with new state fields and logic
    - Add `lastResult: { winningNumber: number; winningColor: string } | null` field
    - Add `betAmount: string` field for BottomBar bet amount control
    - Add `roundHistory: Array<{ roundId: string; winningNumber: number; winningColor: string }>` for History tab
    - Update `setResult` to also set `lastResult` and append to `roundHistory`
    - Update `resetRound` to preserve `lastResult` from previous round
    - Ensure `setRoundState` works correctly with `totalPlayers: 1`
    - _Requirements: 2.4, 6.1, 7.2, 9.3, 10.2_

  - [~] 5.5 Update `frontend/src/hooks/useWebSocket.ts` to handle `winning_number` in result messages
    - Pass `winningNumber: msg.winning_number` when calling `gameStore.setResult()`
    - _Requirements: 8.3_

- [ ] 6. Frontend: Casino dark theme and globals
  - [~] 6.1 Update `frontend/src/app/globals.css` with casino dark gradient theme variables
    - Add casino-specific CSS custom properties for dark blue-to-purple gradient background
    - Add color variables for green (#00C853), violet (#7C4DFF), red (#FF1744) betting buttons
    - Add transition animation utilities for hover/active/disabled states
    - Ensure minimum 4.5:1 contrast ratio for text on dark backgrounds
    - _Requirements: 1.1, 1.3, 1.4, 1.5_

- [ ] 7. Frontend: New UI components
  - [~] 7.1 Create `ResultDisplay` component
    - Create `frontend/src/components/ResultDisplay.tsx`
    - Read `result`, `phase`, `lastResult` from game store
    - Show winning number in large bold text within circular container with color background per `NUMBER_COLOR_MAP`
    - Show "Waiting for result" placeholder during betting phase with no prior result
    - Continue showing previous result until new result arrives
    - _Requirements: 2.1, 2.2, 2.3, 2.4_

  - [~] 7.2 Create `CountdownTimer` component with SVG circular progress ring
    - Create `frontend/src/components/CountdownTimer.tsx`
    - Accept `totalSeconds` and `remainingSeconds` props
    - Render SVG circle with `stroke-dasharray`/`stroke-dashoffset`: `dashoffset = circumference * (1 - remainingSeconds / totalSeconds)`
    - Show numeric seconds in center
    - Hidden during resolution phase, replaced with "Resolving..." animation
    - Fully depleted ring when countdown reaches zero
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5_

  - [~] 7.3 Write property test for countdown timer progress ring calculation
    - **Property 2: Countdown timer progress ring calculation**
    - For any totalSeconds > 0 and 0 <= remainingSeconds <= totalSeconds: dashoffset = circumference * (1 - remainingSeconds / totalSeconds). At 0 remaining → full circumference. At totalSeconds remaining → 0.
    - **Validates: Requirements 3.1, 3.3**

  - [~] 7.4 Create `ColorBetButtons` component
    - Create `frontend/src/components/ColorBetButtons.tsx`
    - Three horizontal buttons: Green (x2.0), Violet (x4.8), Red (x2.0)
    - Each shows multiplier text and checkmark badge when bet placed
    - Disabled with reduced opacity during non-betting phases
    - On tap during betting phase, trigger bet amount input for that color
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [~] 7.5 Create `NumberGrid` component
    - Create `frontend/src/components/NumberGrid.tsx`
    - 2×5 grid of number buttons (0–9) color-coded per `NUMBER_COLOR_MAP`
    - Numbers 0 and 5 show green+violet gradient/accent
    - Each button shows x9.6 multiplier and badge when bet placed
    - Disabled during non-betting phases
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5, 5.6_

  - [~] 7.6 Create `BottomBar` component
    - Create `frontend/src/components/BottomBar.tsx`
    - Fixed bottom bar with three sections: Balance (from wallet store), Win (last round payout or "0.00"), bet amount controls
    - Bet controls: numeric display, x2/÷2 buttons, undo last bet, clear all pending bets
    - Visible during all round phases
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6_

  - [~] 7.7 Create `HistoryTabs` component
    - Create `frontend/src/components/HistoryTabs.tsx`
    - Tab bar with "History" and "My Bets" tabs
    - History: horizontal scrollable row of colored circles for recent results from `roundHistory`
    - My Bets: list of player's bets with type, amount, odds, outcome
    - Collapsible panel to maximize game area
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

- [ ] 8. Frontend: Compose game page with new layout
  - [~] 8.1 Rewrite `frontend/src/app/game/page.tsx` with casino layout
    - Replace current layout with dark gradient background
    - Compose components in vertical order: ResultDisplay → CountdownTimer → ColorBetButtons → NumberGrid → BottomBar → HistoryTabs
    - Single-column mobile-first layout with rounded corners, shadows, semi-transparent card backgrounds
    - Smooth transition animations on interactive elements
    - Wire color/number bet button callbacks to bet placement API via existing `BettingControls` logic or inline handlers
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 10.2, 10.4_

- [~] 9. Checkpoint — Frontend builds and renders correctly
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 10. Integration: Wire frontend to backend number betting
  - [~] 10.1 Update bet placement flow to support number bets
    - When a number button is tapped, send POST to `/api/v1/game/bet` with `color` set to the digit string ("0"–"9")
    - Reuse existing bet placement API client and error handling from `BettingControls`
    - _Requirements: 8.1, 8.2_

  - [~] 10.2 Update `useWebSocket` handler to process `winning_number` from result messages and populate `lastResult`/`roundHistory`
    - Extract `winning_number` from result WS message and pass to `setResult`
    - Ensure game store `lastResult` is set for `ResultDisplay` component
    - _Requirements: 8.3, 9.3_

- [~] 11. Final checkpoint — All tests pass end-to-end
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Backend changes (tasks 1–3) are independent of frontend and can be verified first
- The existing `Bet.color` column is reused for number bets (digit strings) — no schema change needed for bets
