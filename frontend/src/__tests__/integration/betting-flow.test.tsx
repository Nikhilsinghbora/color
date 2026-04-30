import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useGameStore } from '@/stores/game-store';
import { useWalletStore } from '@/stores/wallet-store';

// Mock the api-client module
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  registerAuthStore: vi.fn(),
}));

import { apiClient } from '@/lib/api-client';

const mockedPost = vi.mocked(apiClient.post);

describe('Integration: Betting Flow', () => {
  beforeEach(() => {
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
    useWalletStore.setState({
      balance: '500.00',
      transactions: [],
      transactionPage: 1,
      hasMoreTransactions: false,
      isLoading: false,
    });
    vi.clearAllMocks();
  });

  it('place bet → update game store → update wallet balance → receive result', async () => {
    // Step 1: Set round state (simulating WS round_state message)
    useGameStore.getState().setRoundState({
      roundId: 'round-1',
      phase: 'betting',
      timer: 30,
      totalPlayers: 5,
      totalPool: '200.00',
      gameMode: 'classic',
    });

    expect(useGameStore.getState().phase).toBe('betting');
    expect(useGameStore.getState().timerRemaining).toBe(30);

    // Step 2: Select a bet
    useGameStore.getState().setBetSelection('red', '50.00');
    expect(useGameStore.getState().selectedBets).toEqual({ red: '50.00' });

    // Step 3: Place bet via API
    mockedPost.mockResolvedValueOnce({
      data: {
        id: 'bet-1',
        color: 'red',
        amount: '50.00',
        odds_at_placement: '2.00',
        balance_after: '450.00',
      },
    });

    const { data } = await apiClient.post('/game/bet', {
      round_id: 'round-1',
      color: 'red',
      amount: '50.00',
    });

    // Step 4: Update game store with placed bet
    useGameStore.getState().addPlacedBet({
      id: data.id,
      color: data.color,
      amount: data.amount,
      oddsAtPlacement: data.odds_at_placement,
      potentialPayout: '100.00',
    });

    // Step 5: Update wallet balance
    useWalletStore.getState().updateBalance(data.balance_after);

    expect(useGameStore.getState().placedBets).toHaveLength(1);
    expect(useGameStore.getState().placedBets[0].id).toBe('bet-1');
    expect(useWalletStore.getState().balance).toBe('450.00');

    // Step 6: Phase changes to resolution
    useGameStore.getState().setPhase('resolution');
    expect(useGameStore.getState().phase).toBe('resolution');

    // Step 7: Receive result
    useGameStore.getState().setResult({
      winningColor: 'red',
      winningNumber: 2,
      playerPayouts: [{ betId: 'bet-1', amount: '100.00', isWinner: true }],
    });

    const result = useGameStore.getState().result;
    expect(result?.winningColor).toBe('red');
    expect(result?.playerPayouts[0].isWinner).toBe(true);

    // Step 8: Update wallet with payout
    useWalletStore.getState().updateBalance('550.00');
    expect(useWalletStore.getState().balance).toBe('550.00');

    // Step 9: New round resets state
    useGameStore.getState().resetRound('round-2', 30);

    const gameState = useGameStore.getState();
    expect(gameState.currentRound?.roundId).toBe('round-2');
    expect(gameState.phase).toBe('betting');
    expect(gameState.placedBets).toEqual([]);
    expect(gameState.selectedBets).toEqual({});
    expect(gameState.result).toBeNull();
  });
});
