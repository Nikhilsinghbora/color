import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { calculateBackoff } from '@/lib/ws-client';

/**
 * Property 8: WebSocket reconnection backoff calculation
 *
 * For any reconnection attempt number N (where N ≥ 1), the computed reconnection
 * delay SHALL equal min(2^(N-1) * 1000, 30000) milliseconds. The delay SHALL never
 * exceed 30,000 milliseconds and SHALL never be less than 1,000 milliseconds.
 *
 * **Validates: Requirements 3.7**
 */
describe('Property 8: WebSocket reconnection backoff calculation', () => {
  it('should compute delay as min(2^(N-1) * 1000, 30000) for any attempt N >= 1', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 1000 }), (attempt) => {
        const result = calculateBackoff(attempt);
        const expected = Math.min(Math.pow(2, attempt - 1) * 1000, 30000);
        expect(result).toBe(expected);
      }),
      { numRuns: 100 }
    );
  });

  it('should never return a delay less than 1000ms', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 1000 }), (attempt) => {
        const result = calculateBackoff(attempt);
        expect(result).toBeGreaterThanOrEqual(1000);
      }),
      { numRuns: 100 }
    );
  });

  it('should never return a delay greater than 30000ms', () => {
    fc.assert(
      fc.property(fc.integer({ min: 1, max: 1000 }), (attempt) => {
        const result = calculateBackoff(attempt);
        expect(result).toBeLessThanOrEqual(30000);
      }),
      { numRuns: 100 }
    );
  });
});

import { useGameStore } from '@/stores/game-store';
import type { RoundPhase } from '@/types';

/**
 * Property 5: Betting controls follow game phase
 *
 * For any game round state, betting controls SHALL be enabled if and only if
 * the current phase is `betting`. When the phase is `resolution` or `result`,
 * all betting controls SHALL be disabled.
 *
 * **Validates: Requirements 3.2, 3.4**
 */
describe('Property 5: Betting controls follow game phase', () => {
  const phaseArb = fc.constantFrom<RoundPhase>('betting', 'resolution', 'result');

  beforeEach(() => {
    useGameStore.setState({
      phase: 'betting',
      selectedBets: {},
      placedBets: [],
      result: null,
      timerRemaining: 0,
      currentRound: null,
      connectionStatus: 'disconnected',
      colorOptions: [],
    });
  });

  it('should enable betting controls only during betting phase', () => {
    fc.assert(
      fc.property(phaseArb, (phase) => {
        useGameStore.getState().setPhase(phase);
        const state = useGameStore.getState();
        const bettingEnabled = state.phase === 'betting';

        if (phase === 'betting') {
          expect(bettingEnabled).toBe(true);
        } else {
          expect(bettingEnabled).toBe(false);
        }
      }),
      { numRuns: 100 }
    );
  });

  it('should disable betting controls during resolution phase', () => {
    fc.assert(
      fc.property(fc.constant('resolution' as RoundPhase), (phase) => {
        useGameStore.getState().setPhase(phase);
        const state = useGameStore.getState();
        expect(state.phase).toBe('resolution');
        expect(state.phase === 'betting').toBe(false);
      }),
      { numRuns: 100 }
    );
  });

  it('should disable betting controls during result phase', () => {
    fc.assert(
      fc.property(fc.constant('result' as RoundPhase), (phase) => {
        useGameStore.getState().setPhase(phase);
        const state = useGameStore.getState();
        expect(state.phase).toBe('result');
        expect(state.phase === 'betting').toBe(false);
      }),
      { numRuns: 100 }
    );
  });
});

/**
 * Property 6: Game store reflects WebSocket state updates
 *
 * For any WebSocket message of type `timer_tick` with a `remaining` value, or of
 * type `round_state` with `total_players` and `total_pool` values, the Game Store
 * SHALL update its corresponding fields to exactly match the received values.
 *
 * **Validates: Requirements 3.3, 3.8**
 */
describe('Property 6: Game store reflects WebSocket state updates', () => {
  beforeEach(() => {
    useGameStore.setState({
      phase: 'betting',
      selectedBets: {},
      placedBets: [],
      result: null,
      timerRemaining: 0,
      currentRound: null,
      connectionStatus: 'disconnected',
      colorOptions: [],
    });
  });

  it('should update timerRemaining to match any timer_tick remaining value', () => {
    fc.assert(
      fc.property(fc.integer({ min: 0, max: 3600 }), (remaining) => {
        useGameStore.getState().updateTimer(remaining);
        const state = useGameStore.getState();
        expect(state.timerRemaining).toBe(remaining);
      }),
      { numRuns: 100 }
    );
  });

  it('should update round state fields to match any round_state message values', () => {
    const roundStateArb = fc.record({
      roundId: fc.string({ minLength: 1, maxLength: 50 }),
      phase: fc.constantFrom<RoundPhase>('betting', 'resolution', 'result'),
      timer: fc.integer({ min: 0, max: 3600 }),
      totalPlayers: fc.integer({ min: 0, max: 10000 }),
      totalPool: fc.stringMatching(/^\d{1,10}\.\d{2}$/),
      gameMode: fc.string({ minLength: 1, maxLength: 30 }),
    });

    fc.assert(
      fc.property(roundStateArb, (roundState) => {
        useGameStore.getState().setRoundState(roundState);
        const state = useGameStore.getState();

        expect(state.currentRound).not.toBeNull();
        expect(state.currentRound!.totalPlayers).toBe(roundState.totalPlayers);
        expect(state.currentRound!.totalPool).toBe(roundState.totalPool);
        expect(state.timerRemaining).toBe(roundState.timer);
        expect(state.phase).toBe(roundState.phase);
      }),
      { numRuns: 100 }
    );
  });
});

/**
 * Property 7: Game state full reset on new round
 *
 * For any game state (including placed bets, selected bets, result data, and timer),
 * when a `new_round` message is received, the Game Store SHALL clear all placed bets,
 * clear all selections, clear the previous result, set the phase to `betting`, set the
 * timer to the received value, and set the round ID to the new value. No state from
 * the previous round SHALL persist.
 *
 * **Validates: Requirements 3.6**
 */
describe('Property 7: Game state full reset on new round', () => {
  it('should fully reset game state on new round regardless of prior state', () => {
    const priorStateArb = fc.record({
      selectedBets: fc.dictionary(
        fc.stringMatching(/^[a-z]{3,10}$/),
        fc.stringMatching(/^\d{1,5}\.\d{2}$/),
        { minKeys: 0, maxKeys: 5 }
      ),
      placedBets: fc.array(
        fc.record({
          id: fc.uuid(),
          color: fc.stringMatching(/^[a-z]{3,10}$/),
          amount: fc.stringMatching(/^\d{1,5}\.\d{2}$/),
          oddsAtPlacement: fc.stringMatching(/^\d{1,3}\.\d{2}$/),
          potentialPayout: fc.stringMatching(/^\d{1,6}\.\d{2}$/),
        }),
        { minLength: 0, maxLength: 5 }
      ),
      result: fc.option(
        fc.record({
          winningColor: fc.stringMatching(/^[a-z]{3,10}$/),
          winningNumber: fc.integer({ min: 0, max: 9 }),
          playerPayouts: fc.array(
            fc.record({
              betId: fc.uuid(),
              amount: fc.stringMatching(/^\d{1,5}\.\d{2}$/),
              isWinner: fc.boolean(),
            }),
            { minLength: 0, maxLength: 3 }
          ),
        }),
        { nil: null }
      ),
      timerRemaining: fc.integer({ min: 0, max: 3600 }),
      phase: fc.constantFrom<RoundPhase>('betting', 'resolution', 'result'),
    });

    const newRoundArb = fc.record({
      roundId: fc.uuid(),
      timer: fc.integer({ min: 1, max: 300 }),
    });

    fc.assert(
      fc.property(priorStateArb, newRoundArb, (priorState, newRound) => {
        // Set up prior state
        useGameStore.setState({
          selectedBets: priorState.selectedBets,
          placedBets: priorState.placedBets,
          result: priorState.result,
          timerRemaining: priorState.timerRemaining,
          phase: priorState.phase,
        });

        // Trigger new round reset
        useGameStore.getState().resetRound(newRound.roundId, newRound.timer);

        const state = useGameStore.getState();

        // All prior state should be cleared
        expect(state.placedBets).toEqual([]);
        expect(state.selectedBets).toEqual({});
        expect(state.result).toBeNull();

        // New round values should be set
        expect(state.phase).toBe('betting');
        expect(state.timerRemaining).toBe(newRound.timer);
        expect(state.currentRound).not.toBeNull();
        expect(state.currentRound!.roundId).toBe(newRound.roundId);
      }),
      { numRuns: 100 }
    );
  });
});
