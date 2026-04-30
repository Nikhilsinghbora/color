import { describe, it, expect, beforeEach } from 'vitest';
import { useGameStore } from './game-store';
import type { RoundState, PlacedBet, RoundResult } from '@/types';

function resetStore() {
  useGameStore.setState({
    currentRound: null,
    phase: 'betting',
    timerRemaining: 0,
    colorOptions: [],
    selectedBets: {},
    placedBets: [],
    result: null,
    connectionStatus: 'disconnected',
  });
}

const sampleRoundState: RoundState = {
  roundId: 'round-1',
  phase: 'betting',
  timer: 30,
  totalPlayers: 5,
  totalPool: '500.00',
  gameMode: 'classic',
};

const sampleBet: PlacedBet = {
  id: 'bet-1',
  color: 'red',
  amount: '10.00',
  oddsAtPlacement: '2.5',
  potentialPayout: '25.00',
};

const sampleResult: RoundResult = {
  winningColor: 'red',
  playerPayouts: [
    { betId: 'bet-1', amount: '25.00', isWinner: true },
  ],
};

describe('Game Store', () => {
  beforeEach(() => {
    resetStore();
  });

  it('starts with default state', () => {
    const state = useGameStore.getState();
    expect(state.currentRound).toBeNull();
    expect(state.phase).toBe('betting');
    expect(state.timerRemaining).toBe(0);
    expect(state.colorOptions).toEqual([]);
    expect(state.selectedBets).toEqual({});
    expect(state.placedBets).toEqual([]);
    expect(state.result).toBeNull();
    expect(state.connectionStatus).toBe('disconnected');
  });

  describe('setRoundState', () => {
    it('sets currentRound, phase, and timerRemaining from round state', () => {
      useGameStore.getState().setRoundState(sampleRoundState);

      const state = useGameStore.getState();
      expect(state.currentRound).toEqual(sampleRoundState);
      expect(state.phase).toBe('betting');
      expect(state.timerRemaining).toBe(30);
    });

    it('updates phase when round state has different phase', () => {
      const resolutionRound: RoundState = { ...sampleRoundState, phase: 'resolution', timer: 0 };
      useGameStore.getState().setRoundState(resolutionRound);

      expect(useGameStore.getState().phase).toBe('resolution');
    });
  });

  describe('setPhase', () => {
    it('updates the phase', () => {
      useGameStore.getState().setPhase('resolution');
      expect(useGameStore.getState().phase).toBe('resolution');

      useGameStore.getState().setPhase('result');
      expect(useGameStore.getState().phase).toBe('result');
    });
  });

  describe('updateTimer', () => {
    it('updates timerRemaining', () => {
      useGameStore.getState().updateTimer(15);
      expect(useGameStore.getState().timerRemaining).toBe(15);
    });

    it('can set timer to zero', () => {
      useGameStore.getState().updateTimer(0);
      expect(useGameStore.getState().timerRemaining).toBe(0);
    });
  });

  describe('setBetSelection / removeBetSelection', () => {
    it('adds a bet selection', () => {
      useGameStore.getState().setBetSelection('red', '10.00');
      expect(useGameStore.getState().selectedBets).toEqual({ red: '10.00' });
    });

    it('overwrites an existing selection for the same color', () => {
      useGameStore.getState().setBetSelection('red', '10.00');
      useGameStore.getState().setBetSelection('red', '20.00');
      expect(useGameStore.getState().selectedBets).toEqual({ red: '20.00' });
    });

    it('supports multiple color selections', () => {
      useGameStore.getState().setBetSelection('red', '10.00');
      useGameStore.getState().setBetSelection('blue', '5.00');
      expect(useGameStore.getState().selectedBets).toEqual({
        red: '10.00',
        blue: '5.00',
      });
    });

    it('removes a bet selection', () => {
      useGameStore.getState().setBetSelection('red', '10.00');
      useGameStore.getState().setBetSelection('blue', '5.00');
      useGameStore.getState().removeBetSelection('red');
      expect(useGameStore.getState().selectedBets).toEqual({ blue: '5.00' });
    });

    it('removing a non-existent selection is a no-op', () => {
      useGameStore.getState().setBetSelection('red', '10.00');
      useGameStore.getState().removeBetSelection('green');
      expect(useGameStore.getState().selectedBets).toEqual({ red: '10.00' });
    });
  });

  describe('addPlacedBet', () => {
    it('appends a bet to placedBets', () => {
      useGameStore.getState().addPlacedBet(sampleBet);
      expect(useGameStore.getState().placedBets).toEqual([sampleBet]);
    });

    it('appends multiple bets in order', () => {
      const bet2: PlacedBet = { ...sampleBet, id: 'bet-2', color: 'blue' };
      useGameStore.getState().addPlacedBet(sampleBet);
      useGameStore.getState().addPlacedBet(bet2);
      expect(useGameStore.getState().placedBets).toHaveLength(2);
      expect(useGameStore.getState().placedBets[0].id).toBe('bet-1');
      expect(useGameStore.getState().placedBets[1].id).toBe('bet-2');
    });
  });

  describe('setResult', () => {
    it('sets the round result', () => {
      useGameStore.getState().setResult(sampleResult);
      expect(useGameStore.getState().result).toEqual(sampleResult);
    });
  });

  describe('resetRound', () => {
    it('clears all bets, selections, result and resets phase/timer', () => {
      // Set up some state first
      useGameStore.getState().setRoundState(sampleRoundState);
      useGameStore.getState().setBetSelection('red', '10.00');
      useGameStore.getState().addPlacedBet(sampleBet);
      useGameStore.getState().setResult(sampleResult);
      useGameStore.getState().setPhase('result');

      // Reset
      useGameStore.getState().resetRound('round-2', 25);

      const state = useGameStore.getState();
      expect(state.currentRound?.roundId).toBe('round-2');
      expect(state.phase).toBe('betting');
      expect(state.timerRemaining).toBe(25);
      expect(state.selectedBets).toEqual({});
      expect(state.placedBets).toEqual([]);
      expect(state.result).toBeNull();
    });

    it('preserves connectionStatus and colorOptions on reset', () => {
      useGameStore.setState({ connectionStatus: 'connected', colorOptions: [{ color: 'red', odds: '2.0' }] });
      useGameStore.getState().resetRound('round-3', 30);

      const state = useGameStore.getState();
      expect(state.connectionStatus).toBe('connected');
      expect(state.colorOptions).toEqual([{ color: 'red', odds: '2.0' }]);
    });
  });

  describe('setConnectionStatus', () => {
    it('updates connection status', () => {
      useGameStore.getState().setConnectionStatus('connecting');
      expect(useGameStore.getState().connectionStatus).toBe('connecting');

      useGameStore.getState().setConnectionStatus('connected');
      expect(useGameStore.getState().connectionStatus).toBe('connected');

      useGameStore.getState().setConnectionStatus('reconnecting');
      expect(useGameStore.getState().connectionStatus).toBe('reconnecting');

      useGameStore.getState().setConnectionStatus('disconnected');
      expect(useGameStore.getState().connectionStatus).toBe('disconnected');
    });
  });
});
