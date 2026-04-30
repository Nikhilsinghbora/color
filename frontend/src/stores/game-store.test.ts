import { describe, it, expect, beforeEach } from 'vitest';
import { useGameStore } from './game-store';
import type { RoundState, PlacedBet, RoundResult, GameMode } from '@/types';

function resetStore() {
  useGameStore.setState({
    currentRound: null,
    phase: 'betting',
    timerRemaining: 0,
    colorOptions: [],
    selectedBets: {},
    placedBets: [],
    result: null,
    lastResult: null,
    betAmount: '10',
    roundHistory: [],
    connectionStatus: 'disconnected',
    activeGameModeId: null,
    gameModes: [],
    periodNumber: null,
    showBetSheet: false,
    betSheetType: null,
    showWinLossDialog: false,
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
  winningNumber: 2,
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
    expect(state.lastResult).toBeNull();
    expect(state.betAmount).toBe('10');
    expect(state.roundHistory).toEqual([]);
    expect(state.connectionStatus).toBe('disconnected');
    expect(state.activeGameModeId).toBeNull();
    expect(state.gameModes).toEqual([]);
    expect(state.periodNumber).toBeNull();
    expect(state.showBetSheet).toBe(false);
    expect(state.betSheetType).toBeNull();
    expect(state.showWinLossDialog).toBe(false);
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

    it('works correctly with totalPlayers: 1 (single player)', () => {
      const singlePlayerRound: RoundState = {
        roundId: 'round-solo',
        phase: 'betting',
        timer: 30,
        totalPlayers: 1,
        totalPool: '0',
        gameMode: 'classic',
      };
      useGameStore.getState().setRoundState(singlePlayerRound);

      const state = useGameStore.getState();
      expect(state.currentRound).toEqual(singlePlayerRound);
      expect(state.currentRound?.totalPlayers).toBe(1);
      expect(state.phase).toBe('betting');
      expect(state.timerRemaining).toBe(30);
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

    it('sets lastResult from the round result', () => {
      useGameStore.getState().setResult(sampleResult);
      expect(useGameStore.getState().lastResult).toEqual({
        winningNumber: 2,
        winningColor: 'red',
      });
    });

    it('appends to roundHistory when currentRound exists', () => {
      useGameStore.getState().setRoundState(sampleRoundState);
      useGameStore.getState().setResult(sampleResult);

      const history = useGameStore.getState().roundHistory;
      expect(history).toHaveLength(1);
      expect(history[0]).toEqual({
        roundId: 'round-1',
        winningNumber: 2,
        winningColor: 'red',
      });
    });

    it('does not append to roundHistory when currentRound is null', () => {
      useGameStore.getState().setResult(sampleResult);
      expect(useGameStore.getState().roundHistory).toEqual([]);
    });

    it('accumulates roundHistory across multiple rounds', () => {
      useGameStore.getState().setRoundState(sampleRoundState);
      useGameStore.getState().setResult(sampleResult);

      useGameStore.getState().resetRound('round-2', 30);
      const greenResult: RoundResult = {
        winningColor: 'green',
        winningNumber: 7,
        playerPayouts: [],
      };
      useGameStore.getState().setResult(greenResult);

      const history = useGameStore.getState().roundHistory;
      expect(history).toHaveLength(2);
      expect(history[0].roundId).toBe('round-1');
      expect(history[1].roundId).toBe('round-2');
      expect(history[1].winningColor).toBe('green');
      expect(history[1].winningNumber).toBe(7);
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

    it('preserves lastResult from previous round', () => {
      useGameStore.getState().setRoundState(sampleRoundState);
      useGameStore.getState().setResult(sampleResult);

      // lastResult should be set
      expect(useGameStore.getState().lastResult).toEqual({
        winningNumber: 2,
        winningColor: 'red',
      });

      // Reset round — lastResult should survive
      useGameStore.getState().resetRound('round-2', 30);

      const state = useGameStore.getState();
      expect(state.result).toBeNull(); // current result is cleared
      expect(state.lastResult).toEqual({
        winningNumber: 2,
        winningColor: 'red',
      });
    });

    it('preserves roundHistory on reset', () => {
      useGameStore.getState().setRoundState(sampleRoundState);
      useGameStore.getState().setResult(sampleResult);
      useGameStore.getState().resetRound('round-2', 30);

      expect(useGameStore.getState().roundHistory).toHaveLength(1);
      expect(useGameStore.getState().roundHistory[0].roundId).toBe('round-1');
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

  describe('setBetAmount', () => {
    it('updates the bet amount', () => {
      useGameStore.getState().setBetAmount('50');
      expect(useGameStore.getState().betAmount).toBe('50');
    });

    it('preserves betAmount across resetRound', () => {
      useGameStore.getState().setBetAmount('100');
      useGameStore.getState().resetRound('round-2', 30);
      expect(useGameStore.getState().betAmount).toBe('100');
    });
  });

  describe('setActiveGameMode', () => {
    it('sets the active game mode id', () => {
      useGameStore.getState().setActiveGameMode('mode-1');
      expect(useGameStore.getState().activeGameModeId).toBe('mode-1');
    });

    it('overwrites the previous active game mode', () => {
      useGameStore.getState().setActiveGameMode('mode-1');
      useGameStore.getState().setActiveGameMode('mode-2');
      expect(useGameStore.getState().activeGameModeId).toBe('mode-2');
    });
  });

  describe('setGameModes', () => {
    const sampleModes: GameMode[] = [
      {
        id: 'mode-30s',
        name: 'Win Go 30s',
        mode_type: 'classic',
        color_options: ['red', 'green', 'violet'],
        odds: { red: '2.0', green: '2.0', violet: '4.8', number: '9.6', big: '2.0', small: '2.0' },
        min_bet: '1',
        max_bet: '1000',
        round_duration_seconds: 30,
        is_active: true,
        mode_prefix: '100',
        active_round_id: 'round-abc',
      },
      {
        id: 'mode-1min',
        name: 'Win Go 1Min',
        mode_type: 'classic',
        color_options: ['red', 'green', 'violet'],
        odds: { red: '2.0', green: '2.0', violet: '4.8', number: '9.6', big: '2.0', small: '2.0' },
        min_bet: '1',
        max_bet: '1000',
        round_duration_seconds: 60,
        is_active: true,
        mode_prefix: '101',
      },
    ];

    it('sets the game modes array', () => {
      useGameStore.getState().setGameModes(sampleModes);
      expect(useGameStore.getState().gameModes).toEqual(sampleModes);
      expect(useGameStore.getState().gameModes).toHaveLength(2);
    });

    it('replaces existing game modes', () => {
      useGameStore.getState().setGameModes(sampleModes);
      useGameStore.getState().setGameModes([sampleModes[0]]);
      expect(useGameStore.getState().gameModes).toHaveLength(1);
    });
  });

  describe('setPeriodNumber', () => {
    it('sets the period number', () => {
      useGameStore.getState().setPeriodNumber('202504291000000001');
      expect(useGameStore.getState().periodNumber).toBe('202504291000000001');
    });

    it('overwrites the previous period number', () => {
      useGameStore.getState().setPeriodNumber('202504291000000001');
      useGameStore.getState().setPeriodNumber('202504291000000002');
      expect(useGameStore.getState().periodNumber).toBe('202504291000000002');
    });
  });

  describe('resetRound clears periodNumber', () => {
    it('clears periodNumber on reset', () => {
      useGameStore.getState().setPeriodNumber('202504291000000001');
      expect(useGameStore.getState().periodNumber).toBe('202504291000000001');

      useGameStore.getState().resetRound('round-new', 30);
      expect(useGameStore.getState().periodNumber).toBeNull();
    });

    it('preserves activeGameModeId and gameModes on reset', () => {
      useGameStore.getState().setActiveGameMode('mode-1');
      useGameStore.getState().setGameModes([{
        id: 'mode-1',
        name: 'Win Go 30s',
        mode_type: 'classic',
        color_options: ['red', 'green', 'violet'],
        odds: { red: '2.0', green: '2.0' },
        min_bet: '1',
        max_bet: '1000',
        round_duration_seconds: 30,
        is_active: true,
        mode_prefix: '100',
      }]);

      useGameStore.getState().resetRound('round-new', 30);

      expect(useGameStore.getState().activeGameModeId).toBe('mode-1');
      expect(useGameStore.getState().gameModes).toHaveLength(1);
    });
  });

  describe('openBetSheet / closeBetSheet', () => {
    it('openBetSheet sets showBetSheet to true and betSheetType', () => {
      useGameStore.getState().openBetSheet('green');

      const state = useGameStore.getState();
      expect(state.showBetSheet).toBe(true);
      expect(state.betSheetType).toBe('green');
    });

    it('openBetSheet works with number bet types', () => {
      useGameStore.getState().openBetSheet('5');

      const state = useGameStore.getState();
      expect(state.showBetSheet).toBe(true);
      expect(state.betSheetType).toBe('5');
    });

    it('openBetSheet works with big/small bet types', () => {
      useGameStore.getState().openBetSheet('big');
      expect(useGameStore.getState().betSheetType).toBe('big');

      useGameStore.getState().openBetSheet('small');
      expect(useGameStore.getState().betSheetType).toBe('small');
    });

    it('openBetSheet overwrites previous bet type', () => {
      useGameStore.getState().openBetSheet('red');
      useGameStore.getState().openBetSheet('big');

      const state = useGameStore.getState();
      expect(state.showBetSheet).toBe(true);
      expect(state.betSheetType).toBe('big');
    });

    it('closeBetSheet resets showBetSheet and betSheetType', () => {
      useGameStore.getState().openBetSheet('green');
      expect(useGameStore.getState().showBetSheet).toBe(true);

      useGameStore.getState().closeBetSheet();

      const state = useGameStore.getState();
      expect(state.showBetSheet).toBe(false);
      expect(state.betSheetType).toBeNull();
    });

    it('closeBetSheet is safe to call when sheet is already closed', () => {
      useGameStore.getState().closeBetSheet();

      const state = useGameStore.getState();
      expect(state.showBetSheet).toBe(false);
      expect(state.betSheetType).toBeNull();
    });

    it('resetRound does not affect bet sheet state', () => {
      useGameStore.getState().openBetSheet('red');
      useGameStore.getState().resetRound('round-new', 30);

      // Bet sheet state is independent of round state
      const state = useGameStore.getState();
      expect(state.showBetSheet).toBe(true);
      expect(state.betSheetType).toBe('red');
    });
  });

  describe('openWinLossDialog / closeWinLossDialog', () => {
    it('openWinLossDialog sets showWinLossDialog to true', () => {
      useGameStore.getState().openWinLossDialog();
      expect(useGameStore.getState().showWinLossDialog).toBe(true);
    });

    it('closeWinLossDialog sets showWinLossDialog to false', () => {
      useGameStore.getState().openWinLossDialog();
      expect(useGameStore.getState().showWinLossDialog).toBe(true);

      useGameStore.getState().closeWinLossDialog();
      expect(useGameStore.getState().showWinLossDialog).toBe(false);
    });

    it('closeWinLossDialog is safe to call when dialog is already closed', () => {
      useGameStore.getState().closeWinLossDialog();
      expect(useGameStore.getState().showWinLossDialog).toBe(false);
    });

    it('resetRound does not affect win/loss dialog state', () => {
      useGameStore.getState().openWinLossDialog();
      useGameStore.getState().resetRound('round-new', 30);

      expect(useGameStore.getState().showWinLossDialog).toBe(true);
    });
  });
});
