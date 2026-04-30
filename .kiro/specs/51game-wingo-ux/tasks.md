# Implementation Plan: 51game WinGo UX Overhaul

## Overview

This plan implements a comprehensive UI/UX overhaul across 16 requirements, ordered so backend changes land first (database migrations, service logic, API endpoints), followed by frontend components built incrementally. Each task builds on previous steps, and checkpoints validate progress at key milestones.

## Tasks

- [x] 1. Database schema migrations and model updates
  - [x] 1.1 Add `period_number` column to `GameRound` model and `mode_prefix` column to `GameMode` model
    - Add `period_number: Mapped[Optional[str]] = mapped_column(String(20), unique=True, nullable=True, index=True)` to `GameRound` in `app/models/game.py`
    - Add `mode_prefix: Mapped[str] = mapped_column(String(3), nullable=False, default="100")` to `GameMode` in `app/models/game.py`
    - _Requirements: 5.4, 15.4_

  - [x] 1.2 Create `PeriodSequence` model for sequence tracking
    - Create new model in `app/models/game.py` with fields: `id`, `game_mode_id` (FK to game_modes), `date_str` (String(8)), `last_sequence` (int, default 0)
    - Add `UniqueConstraint("game_mode_id", "date_str")` table arg
    - _Requirements: 15.1, 15.3_

  - [x] 1.3 Generate Alembic migration for schema changes
    - Run `alembic revision --autogenerate -m "add_period_number_and_mode_prefix"` to create migration
    - Verify migration includes: `period_number` column on `game_rounds`, `mode_prefix` column on `game_modes`, `period_sequences` table
    - Apply migration with `alembic upgrade head`
    - _Requirements: 5.4, 15.4_

  - [x] 1.4 Update `GameMode.odds` JSON to include big/small odds in seed data or migration
    - Extend the odds JSON structure to include `"big": "2.0"` and `"small": "2.0"` alongside existing color/number odds
    - Create a data migration or update seed script to add big/small odds to existing game modes
    - _Requirements: 1.1, 1.2_

- [x] 2. Backend service: Big/Small betting and service fee
  - [x] 2.1 Update `Game_Engine.place_bet()` to accept "big" and "small" bet types
    - In `app/services/game_engine.py`, extend the valid bet choices validation to include `{"big", "small"}` alongside existing color names and digit strings
    - Look up odds from `game_mode.odds["big"]` or `game_mode.odds["small"]` for big/small bets
    - Reject any bet choice not in valid colors, valid digits, or `{"big", "small"}` with a `ValueError`
    - _Requirements: 1.1, 1.2, 1.7_

  - [x] 2.2 Update `Payout_Calculator` with service fee and big/small resolution
    - Add `SERVICE_FEE_RATE = Decimal("0.02")` configurable constant in `app/services/payout_calculator.py` (or `app/config.py`)
    - Modify `calculate_payout()` to apply service fee: `payout = (bet_amount × (1 - SERVICE_FEE_RATE)) × odds`, quantized to 2 decimal places
    - Add `BIG_NUMBERS = {5, 6, 7, 8, 9}` and `SMALL_NUMBERS = {0, 1, 2, 3, 4}` constants
    - Add `_is_big_small_bet(color: str) -> bool` helper that returns True for "big" or "small"
    - Add `_is_big_small_winner(bet_type: str, winning_number: int) -> bool` helper
    - Update `calculate_round_payouts()` to handle big/small bets: check `_is_big_small_bet()` before color/number checks, determine winner via `_is_big_small_winner()`, look up odds from `odds["big"]` or `odds["small"]`
    - _Requirements: 1.3, 1.4, 1.5, 1.6, 2.1, 2.2, 2.3, 2.4_

  - [x] 2.3 Write unit tests for big/small betting and service fee
    - Test `place_bet()` accepts "big" and "small" and rejects invalid values
    - Test `calculate_payout()` applies 2% service fee correctly (e.g., ₹100 bet at 2.0x → ₹196.00)
    - Test `_is_big_small_winner()` for all numbers 0–9 against both "big" and "small"
    - Test `calculate_round_payouts()` with mixed bet types (color, number, big, small)
    - _Requirements: 1.1–1.7, 2.1–2.4_

- [x] 3. Backend service: Period number generation
  - [x] 3.1 Create period number generator service
    - Create `app/services/period_number.py` with:
      - `format_period_number(date_str: str, mode_prefix: str, sequence: int) -> str` — formats `YYYYMMDD + mode_prefix(3) + sequence(7, zero-padded)`
      - `parse_period_number(period_number: str) -> tuple[str, str, int]` — parses back into components
      - `async def generate_period_number(session: AsyncSession, game_mode_id: UUID, mode_prefix: str) -> str` — atomically increments `PeriodSequence` for the current UTC date and mode, returns formatted period number
    - Handle sequence overflow (> 9999999) by logging error and using next available number
    - _Requirements: 15.1, 15.2, 15.3, 15.6_

  - [x] 3.2 Integrate period number into `Game_Engine.start_round()`
    - In `app/services/game_engine.py`, after creating the `GameRound`, call `generate_period_number()` with the game mode's `mode_prefix`
    - Assign the generated period number to `game_round.period_number`
    - _Requirements: 5.3, 15.1_

  - [x] 3.3 Add `period_number` to `RoundState` dataclass and `get_round_state()`
    - Add `period_number: Optional[str]` field to the `RoundState` dataclass in `app/services/game_engine.py`
    - Populate it from `game_round.period_number` in `get_round_state()`
    - _Requirements: 5.4, 15.5_

  - [x] 3.4 Write unit tests for period number generation
    - Test `format_period_number()` produces correct format (e.g., "20250429100051058")
    - Test `parse_period_number()` round-trips correctly
    - Test sequence auto-increments per mode per date
    - Test sequence resets for a new date
    - _Requirements: 15.1–15.6_

- [x] 4. Backend: Game history API endpoints and active round lookup
  - [x] 4.1 Create `GET /api/v1/game/history` endpoint
    - Add endpoint in `app/api/game.py` that queries completed `GameRound` records
    - Accept `page` (default 1), `size` (default 10), and optional `mode_id` query parameters
    - Return paginated results with fields: `period_number`, `winning_number`, `winning_color`, `big_small_label` (derived: "Big" if winning_number >= 5, else "Small"), `completed_at`
    - Order by `completed_at` descending
    - Create response schema in `app/schemas/game.py`
    - _Requirements: 14.1, 14.2, 14.3, 14.6, 14.7_

  - [x] 4.2 Create `GET /api/v1/game/my-history` endpoint
    - Add authenticated endpoint in `app/api/game.py` that queries the player's `Bet` records joined with `GameRound` for period numbers
    - Accept `page` (default 1) and `size` (default 10) query parameters
    - Return paginated results with fields: `period_number`, `bet_type` (the `color` field value), `bet_amount`, `is_winner`, `payout_amount`, `created_at`
    - Order by `created_at` descending
    - Create response schema in `app/schemas/game.py`
    - _Requirements: 14.4, 14.5_

  - [x] 4.3 Add active round lookup per game mode
    - Create `get_active_round_for_mode(session, game_mode_id)` function in `app/services/game_engine.py` that returns the current BETTING or RESOLUTION round for a mode
    - Extend the `GET /api/v1/game/modes` response to include `active_round_id` field
    - Update `GameModeResponse` schema to include `active_round_id` and `mode_prefix`
    - _Requirements: 16.3, 16.4_

  - [x] 4.4 Write unit tests for history endpoints and active round lookup
    - Test `/history` returns paginated results ordered by completed_at desc
    - Test `/history` big_small_label is correct for various winning numbers
    - Test `/my-history` returns only the authenticated player's bets
    - Test `get_active_round_for_mode()` returns the correct round
    - _Requirements: 14.1–14.7, 16.3_

- [x] 5. Backend: WebSocket updates for period number and mode switching
  - [x] 5.1 Update WebSocket messages to include `period_number`
    - In the Celery task (`app/tasks/game_tasks.py`) or wherever `round_state` and `new_round` messages are published, include the `period_number` field from the `GameRound`
    - Update the `result` message to include `period_number` for the Win/Loss dialog
    - _Requirements: 5.4, 15.5_

  - [x] 5.2 Ensure WebSocket sends initial `round_state` on new connections
    - Verify that when a client connects to a round's WebSocket, the `WS_Manager` sends an initial `round_state` message including `period_number`
    - This supports game mode switching — the frontend gets full state on reconnect
    - _Requirements: 16.4_

  - [x] 5.3 Write unit tests for WebSocket message payloads
    - Test that `round_state` messages include `period_number`
    - Test that `new_round` messages include `period_number`
    - _Requirements: 5.4, 15.5_

- [x] 6. Backend checkpoint
  - Ensure all backend tests pass. Run `pytest` to verify migrations, big/small betting, service fee, period numbers, history endpoints, and WebSocket updates. Ask the user if questions arise.

- [x] 7. Frontend: Wallet card and announcement bar
  - [x] 7.1 Create `WalletCard` component
    - Create `frontend/src/components/WalletCard.tsx`
    - Display wallet icon, balance with ₹ symbol from `useWalletStore`
    - Add "Withdraw" and "Deposit" buttons that navigate to `/wallet`
    - Balance updates in real-time when bets are placed or payouts received
    - _Requirements: 13.1, 13.2, 13.3, 13.4, 13.5, 13.6_

  - [x] 7.2 Create `AnnouncementBar` component
    - Create `frontend/src/components/AnnouncementBar.tsx`
    - Display speaker/megaphone icon on left, scrolling marquee text (CSS `@keyframes`), "Detail" button on right
    - Text content configurable via a frontend constant or fetched from API
    - "Detail" button navigates to announcements page or opens a modal
    - _Requirements: 9.1, 9.2, 9.3, 9.4, 9.5_

  - [x] 7.3 Write unit tests for WalletCard and AnnouncementBar
    - Test WalletCard renders balance and buttons
    - Test AnnouncementBar renders marquee text and detail button
    - _Requirements: 13.1–13.6, 9.1–9.5_

- [x] 8. Frontend: Game mode tabs and WebSocket switching
  - [x] 8.1 Create `GameModeTabs` component
    - Create `frontend/src/components/GameModeTabs.tsx`
    - Accept `modes`, `activeMode`, `onModeChange` props
    - Render horizontal tab bar with labels "Win Go 30s", "Win Go 1Min", "Win Go 3Min", "Win Go 5Min"
    - Highlight active tab with distinct background/text styling
    - _Requirements: 4.1, 4.2, 4.6_

  - [x] 8.2 Update game store with game mode state
    - In `frontend/src/stores/game-store.ts`, add fields: `activeGameModeId`, `gameModes`, `periodNumber`
    - Add actions: `setActiveGameMode()`, `setGameModes()`, `setPeriodNumber()`
    - Update `resetRound()` to also clear `periodNumber`
    - _Requirements: 4.4, 4.5_

  - [x] 8.3 Update `useWebSocket` hook for mode switching and period number
    - Modify `useWebSocket` to accept `gameModeId` parameter alongside `roundId`
    - Handle `period_number` in `round_state` and `new_round` messages — call `setPeriodNumber()`
    - When mode changes, disconnect current WebSocket and connect to new mode's active round
    - _Requirements: 4.3, 4.4, 16.1, 16.2, 16.4, 16.5_

  - [x] 8.4 Fetch game modes on page load and wire mode switching in game page
    - In `frontend/src/app/game/page.tsx`, fetch `GET /api/v1/game/modes` on mount and store in game store
    - Wire `GameModeTabs` `onModeChange` to update `activeGameModeId`, which triggers WebSocket reconnect
    - Display reconnecting banner when WebSocket is disconnected during mode switch
    - _Requirements: 4.3, 4.5, 16.5_

  - [x] 8.5 Write unit tests for GameModeTabs and mode switching
    - Test tab rendering and active state highlighting
    - Test mode change callback fires correctly
    - _Requirements: 4.1–4.6_

- [x] 9. Frontend: Big/Small buttons and bet confirmation bottom sheet
  - [x] 9.1 Create `BigSmallButtons` component
    - Create `frontend/src/components/BigSmallButtons.tsx`
    - Render two horizontal buttons: "Big 5-9 x2.0" and "Small 0-4 x2.0"
    - Disabled with reduced opacity during non-betting phases
    - Show checkmark badge when bet placed on big/small
    - Tapping opens the bet confirmation sheet (calls `openBetSheet("big")` or `openBetSheet("small")`)
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 9.2 Create `BetConfirmationSheet` component
    - Create `frontend/src/components/BetConfirmationSheet.tsx`
    - Bottom sheet overlay with:
      - Header showing game mode name + bet type (e.g., "Win Go 1Min — Select Green")
      - Balance preset buttons: ₹1, ₹10, ₹100, ₹1000 (single select)
      - Quantity controls: minus button, numeric input (1–100), plus button
      - Quick multiplier row: Random, X1, X5, X10, X20, X50, X100 (single select, sets quantity)
      - "I agree with the pre-sale rules" checkbox
      - Footer: Cancel button + Confirm button showing "Total amount ₹X.XX" (= preset × quantity)
    - Confirm disabled until checkbox checked
    - Validate total ≤ balance before submitting; show inline error if exceeded
    - Cancel closes without placing bet
    - _Requirements: 6.1–6.10, 12.1–12.5_

  - [x] 9.3 Add bet sheet state to game store and wire into game page
    - Add `showBetSheet`, `betSheetType` fields and `openBetSheet()`, `closeBetSheet()` actions to game store
    - Update game page: all betting buttons (color, number, big, small) call `openBetSheet(type)` instead of placing bet directly
    - On confirm, call the existing `placeBet()` logic with the configured amount × quantity
    - _Requirements: 6.1, 6.7, 6.8_

  - [x] 9.4 Write unit tests for BigSmallButtons and BetConfirmationSheet
    - Test BigSmallButtons renders labels, disabled state, and badge indicators
    - Test BetConfirmationSheet preset selection, quantity controls, multiplier row, total calculation, and validation
    - _Requirements: 3.1–3.7, 6.1–6.10, 12.1–12.5_

- [x] 10. Frontend: Win/Loss dialog and sound effects
  - [x] 10.1 Create `WinLossDialog` component
    - Create `frontend/src/components/WinLossDialog.tsx`
    - Centered modal overlay with:
      - "Congratulations" header (gold/green theme) for wins, "Sorry" header (muted/gray) for losses
      - Lottery result: winning number with color indicator + "Big"/"Small" label
      - Total bonus amount with ₹ symbol
      - Period number of the resolved round
      - 3-second auto-close countdown timer
      - Close button (X) for early dismissal
    - _Requirements: 7.1–7.8_

  - [x] 10.2 Add win/loss dialog state to game store and trigger on result
    - Add `showWinLossDialog` field and `openWinLossDialog()`, `closeWinLossDialog()` actions to game store
    - In `useWebSocket` hook, when `result` message arrives and player had placed bets, call `openWinLossDialog()`
    - _Requirements: 7.1_

  - [x] 10.3 Create `SoundManager` service
    - Create `frontend/src/lib/sound-manager.ts`
    - Implement `SoundManager` class with Web Audio API:
      - `initialize()` — called on first user interaction to create AudioContext
      - `playTick()`, `playLastSecond()`, `playBetConfirm()`, `playWinCelebration()` — synthesized sounds or loaded audio files
      - `setMuted(muted)` / `getIsMuted()` — toggle with localStorage persistence (`sound_muted` key)
    - All play methods are no-ops until `initialize()` is called (browser autoplay compliance)
    - _Requirements: 8.1–8.7_

  - [x] 10.4 Create `SoundToggle` component and integrate sounds into game flow
    - Create `frontend/src/components/SoundToggle.tsx` — speaker icon button (🔊/🔇) toggling mute
    - In game page, call `SoundManager.initialize()` on first user interaction
    - Play tick sounds during last 5 seconds of countdown (integrate with `useCountdown` or timer effect)
    - Play distinct last-second sound at 1 second remaining
    - Play bet confirmation sound on successful bet placement
    - Play win celebration sound when WinLossDialog shows a win
    - _Requirements: 8.1–8.7_

  - [x] 10.5 Write unit tests for WinLossDialog and SoundManager
    - Test WinLossDialog renders win/loss states correctly, auto-close countdown, and close button
    - Test SoundManager mute persistence and autoplay gate
    - _Requirements: 7.1–7.8, 8.1–8.7_

- [x] 11. Frontend: Rules modal, enhanced history table, and period number display
  - [x] 11.1 Create `RulesModal` component
    - Create `frontend/src/components/RulesModal.tsx`
    - Centered modal explaining: color payouts (Green 2x, Red 2x, Violet 4.8x), number payouts (9.6x), Big/Small payouts (2x), 2% service fee
    - Close button at bottom
    - _Requirements: 10.1–10.7_

  - [x] 11.2 Create `HistoryTable` component replacing `HistoryTabs`
    - Create `frontend/src/components/HistoryTable.tsx`
    - Three sub-tabs: "Game history", "Chart", "My history"
    - "Game history" tab: paginated table with columns Period, Number (color-coded background), Big/Small, Color (dots — multiple for dual-color numbers 0 and 5). 10 rows/page with pagination controls (page numbers, prev/next arrows). Fetches from `GET /api/v1/game/history?page=X&size=10&mode_id=Y`
    - "My history" tab: paginated table with columns Period, bet type, amount, outcome (win/loss), payout. Fetches from `GET /api/v1/game/my-history?page=X&size=10`
    - "Chart" tab: placeholder or basic trend indicator (optional for initial release)
    - _Requirements: 11.1–11.7_

  - [x] 11.3 Update timer area with period number display and "How to Play" button
    - In the game page timer area, replace the UUID-based round identifier with the `periodNumber` from game store
    - Add a "How to Play" button (question mark icon) near the period number that opens the `RulesModal`
    - _Requirements: 5.1, 5.2, 5.5, 10.1, 10.2_

  - [x] 11.4 Write unit tests for RulesModal and HistoryTable
    - Test RulesModal renders all payout rules and service fee explanation
    - Test HistoryTable renders paginated data, tab switching, and color-coded number cells
    - _Requirements: 10.1–10.7, 11.1–11.7_

- [x] 12. Frontend: Assemble updated game page layout
  - [x] 12.1 Restructure `frontend/src/app/game/page.tsx` with new layout order
    - Update the game page to render components in the new order:
      1. WalletCard
      2. AnnouncementBar
      3. GameModeTabs
      4. Timer area (PeriodNumber + CountdownTimer + HowToPlay button + SoundToggle)
      5. ResultDisplay
      6. ColorBetButtons (now opens BetConfirmationSheet on tap)
      7. NumberGrid (now opens BetConfirmationSheet on tap)
      8. BigSmallButtons
      9. HistoryTable (replaces HistoryTabs)
      10. BetConfirmationSheet (overlay)
      11. WinLossDialog (overlay)
    - Remove the old `BottomBar` component from the game page (replaced by WalletCard and BetConfirmationSheet)
    - Remove the old `HistoryTabs` import (replaced by HistoryTable)
    - _Requirements: 3.1, 4.1, 5.1, 6.1, 7.1, 9.1, 11.1, 13.1_

  - [x] 12.2 Update frontend TypeScript types for new WebSocket messages and API responses
    - In `frontend/src/types/` (or `frontend/src/types.ts`), add/update:
      - `RoundState` to include `periodNumber?: string`
      - `GameMode` to include `mode_prefix: string` and `active_round_id?: string`
      - `GameHistoryEntry`, `MyHistoryEntry`, `PaginatedResponse<T>` types
      - `WSIncomingMessage` variants to include `period_number` in `round_state`, `new_round`, and `result`
    - _Requirements: 5.4, 14.1, 14.4, 15.5_

- [x] 13. Frontend checkpoint
  - Ensure all frontend tests pass. Run `npx vitest --run` from the `frontend/` directory to verify all new and existing components. Ask the user if questions arise.

- [x] 14. Final integration checkpoint
  - Ensure all backend and frontend tests pass end-to-end. Verify that:
    - Big/Small bets can be placed and resolved correctly with service fee applied
    - Period numbers are generated and displayed in the timer area and history table
    - Game mode switching disconnects/reconnects WebSocket and loads correct round state
    - Bet confirmation sheet opens for all bet types and submits correctly
    - Win/Loss dialog appears after results when player had bets
    - Sound effects play at correct moments and respect mute preference
    - History table loads paginated data from API endpoints
  - Ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Backend tasks (1–6) should be completed before frontend tasks (7–12)
- Checkpoints at tasks 6, 13, and 14 ensure incremental validation
- The "Chart" sub-tab in HistoryTable (Requirement 11.5) is optional for initial release per the requirements
