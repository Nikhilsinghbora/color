import { describe, it, expect, beforeEach, vi } from 'vitest';
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

describe('Integration: Deposit Flow', () => {
  beforeEach(() => {
    useWalletStore.setState({
      balance: '100.00',
      transactions: [],
      transactionPage: 1,
      hasMoreTransactions: false,
      isLoading: false,
    });
    vi.clearAllMocks();
  });

  it('deposit → balance updates from API response', async () => {
    mockedPost.mockResolvedValueOnce({
      data: { balance: '200.00' },
    });

    await useWalletStore.getState().deposit('100.00', 'tok_stripe_test');

    expect(mockedPost).toHaveBeenCalledWith('/wallet/deposit', {
      amount: '100.00',
      stripe_token: 'tok_stripe_test',
    });

    const state = useWalletStore.getState();
    expect(state.balance).toBe('200.00');
    expect(state.isLoading).toBe(false);
  });

  it('deposit failure does not change balance', async () => {
    mockedPost.mockRejectedValueOnce(new Error('Payment declined'));

    await expect(
      useWalletStore.getState().deposit('100.00', 'tok_bad'),
    ).rejects.toThrow('Payment declined');

    const state = useWalletStore.getState();
    expect(state.balance).toBe('100.00');
    expect(state.isLoading).toBe(false);
  });

  it('multiple deposits accumulate correctly', async () => {
    mockedPost.mockResolvedValueOnce({ data: { balance: '200.00' } });
    await useWalletStore.getState().deposit('100.00', 'tok_1');
    expect(useWalletStore.getState().balance).toBe('200.00');

    mockedPost.mockResolvedValueOnce({ data: { balance: '350.00' } });
    await useWalletStore.getState().deposit('150.00', 'tok_2');
    expect(useWalletStore.getState().balance).toBe('350.00');
  });
});
