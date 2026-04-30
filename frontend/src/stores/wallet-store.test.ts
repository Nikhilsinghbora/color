import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useWalletStore } from './wallet-store';

// Mock the api-client module
vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

import { apiClient } from '@/lib/api-client';

const mockedGet = vi.mocked(apiClient.get);
const mockedPost = vi.mocked(apiClient.post);

describe('Wallet Store', () => {
  beforeEach(() => {
    // Reset store state
    useWalletStore.setState({
      balance: null,
      transactions: [],
      transactionPage: 1,
      hasMoreTransactions: false,
      isLoading: false,
    });
    vi.clearAllMocks();
  });

  describe('initial state', () => {
    it('starts with null balance and empty transactions', () => {
      const state = useWalletStore.getState();
      expect(state.balance).toBeNull();
      expect(state.transactions).toEqual([]);
      expect(state.transactionPage).toBe(1);
      expect(state.hasMoreTransactions).toBe(false);
      expect(state.isLoading).toBe(false);
    });
  });

  describe('fetchBalance', () => {
    it('fetches balance from API and updates state', async () => {
      mockedGet.mockResolvedValueOnce({ data: { balance: '250.00' } });

      await useWalletStore.getState().fetchBalance();

      expect(mockedGet).toHaveBeenCalledWith('/wallet/balance');
      expect(useWalletStore.getState().balance).toBe('250.00');
      expect(useWalletStore.getState().isLoading).toBe(false);
    });

    it('sets isLoading to false even on error', async () => {
      mockedGet.mockRejectedValueOnce(new Error('Network error'));

      await expect(useWalletStore.getState().fetchBalance()).rejects.toThrow('Network error');
      expect(useWalletStore.getState().isLoading).toBe(false);
    });
  });

  describe('updateBalance', () => {
    it('directly sets the balance', () => {
      useWalletStore.getState().updateBalance('100.50');
      expect(useWalletStore.getState().balance).toBe('100.50');
    });
  });

  describe('fetchTransactions', () => {
    const mockTransactions = {
      items: [
        {
          id: 'tx-1',
          type: 'deposit' as const,
          amount: '50.00',
          balance_after: '150.00',
          description: null,
          created_at: '2024-01-01T00:00:00Z',
        },
      ],
      total: 1,
      page: 1,
      size: 20,
      has_more: false,
    };

    it('fetches first page of transactions', async () => {
      mockedGet.mockResolvedValueOnce({ data: mockTransactions });

      await useWalletStore.getState().fetchTransactions(1);

      expect(mockedGet).toHaveBeenCalledWith('/wallet/transactions?page=1&size=20');
      const state = useWalletStore.getState();
      expect(state.transactions).toHaveLength(1);
      expect(state.transactions[0].id).toBe('tx-1');
      expect(state.transactionPage).toBe(1);
      expect(state.hasMoreTransactions).toBe(false);
      expect(state.isLoading).toBe(false);
    });

    it('appends transactions for subsequent pages', async () => {
      // Set up existing page 1 data
      useWalletStore.setState({
        transactions: [
          {
            id: 'tx-1',
            type: 'deposit',
            amount: '50.00',
            balance_after: '150.00',
            description: null,
            created_at: '2024-01-01T00:00:00Z',
          },
        ],
        transactionPage: 1,
      });

      const page2Data = {
        items: [
          {
            id: 'tx-2',
            type: 'withdrawal' as const,
            amount: '20.00',
            balance_after: '130.00',
            description: 'Withdrawal',
            created_at: '2024-01-02T00:00:00Z',
          },
        ],
        total: 2,
        page: 2,
        size: 20,
        has_more: false,
      };

      mockedGet.mockResolvedValueOnce({ data: page2Data });

      await useWalletStore.getState().fetchTransactions(2);

      const state = useWalletStore.getState();
      expect(state.transactions).toHaveLength(2);
      expect(state.transactions[0].id).toBe('tx-1');
      expect(state.transactions[1].id).toBe('tx-2');
      expect(state.transactionPage).toBe(2);
    });

    it('replaces transactions when fetching page 1 again', async () => {
      useWalletStore.setState({
        transactions: [
          {
            id: 'tx-old',
            type: 'deposit',
            amount: '10.00',
            balance_after: '10.00',
            description: null,
            created_at: '2024-01-01T00:00:00Z',
          },
        ],
      });

      mockedGet.mockResolvedValueOnce({ data: mockTransactions });

      await useWalletStore.getState().fetchTransactions(1);

      const state = useWalletStore.getState();
      expect(state.transactions).toHaveLength(1);
      expect(state.transactions[0].id).toBe('tx-1');
    });

    it('uses current transactionPage when no page argument given', async () => {
      useWalletStore.setState({ transactionPage: 3 });
      mockedGet.mockResolvedValueOnce({
        data: { items: [], total: 0, page: 3, size: 20, has_more: false },
      });

      await useWalletStore.getState().fetchTransactions();

      expect(mockedGet).toHaveBeenCalledWith('/wallet/transactions?page=3&size=20');
    });

    it('sets isLoading to false even on error', async () => {
      mockedGet.mockRejectedValueOnce(new Error('fail'));

      await expect(useWalletStore.getState().fetchTransactions(1)).rejects.toThrow('fail');
      expect(useWalletStore.getState().isLoading).toBe(false);
    });
  });

  describe('deposit', () => {
    it('sends deposit request and updates balance from response', async () => {
      mockedPost.mockResolvedValueOnce({ data: { balance: '300.00' } });

      await useWalletStore.getState().deposit('100.00', 'tok_stripe_123');

      expect(mockedPost).toHaveBeenCalledWith('/wallet/deposit', {
        amount: '100.00',
        stripe_token: 'tok_stripe_123',
      });
      expect(useWalletStore.getState().balance).toBe('300.00');
      expect(useWalletStore.getState().isLoading).toBe(false);
    });

    it('sets isLoading to false even on error', async () => {
      mockedPost.mockRejectedValueOnce(new Error('Payment failed'));

      await expect(
        useWalletStore.getState().deposit('50.00', 'tok_bad'),
      ).rejects.toThrow('Payment failed');
      expect(useWalletStore.getState().isLoading).toBe(false);
    });
  });

  describe('withdraw', () => {
    it('sends withdrawal request', async () => {
      mockedPost.mockResolvedValueOnce({ data: { transaction_id: 'tx-w1' } });

      await useWalletStore.getState().withdraw('25.00');

      expect(mockedPost).toHaveBeenCalledWith('/wallet/withdraw', { amount: '25.00' });
      expect(useWalletStore.getState().isLoading).toBe(false);
    });

    it('sets isLoading to false even on error', async () => {
      mockedPost.mockRejectedValueOnce(new Error('Insufficient balance'));

      await expect(useWalletStore.getState().withdraw('999.00')).rejects.toThrow(
        'Insufficient balance',
      );
      expect(useWalletStore.getState().isLoading).toBe(false);
    });
  });
});
