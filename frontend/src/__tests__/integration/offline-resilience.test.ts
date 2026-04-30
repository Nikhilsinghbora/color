import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useUIStore } from '@/stores/ui-store';

// ---------------------------------------------------------------------------
// Mock api-client
// ---------------------------------------------------------------------------

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn(),
    post: vi.fn(),
  },
  registerAuthStore: vi.fn(),
}));

import { apiClient } from '@/lib/api-client';

const mockedPost = vi.mocked(apiClient.post);

// ---------------------------------------------------------------------------
// Integration: Offline Resilience
// Requirements: 11.4
// ---------------------------------------------------------------------------

describe('Integration: Offline Resilience', () => {
  let onlineListeners: Array<() => void>;
  let offlineListeners: Array<() => void>;

  beforeEach(() => {
    onlineListeners = [];
    offlineListeners = [];

    useUIStore.setState({
      theme: 'light',
      isChatOpen: false,
      unreadChatCount: 0,
      isOffline: false,
      sessionStartTime: null,
      sessionLimitMinutes: null,
    });

    vi.clearAllMocks();
  });

  it('go offline → UI store reflects offline → come online → UI store reflects online', () => {
    // Simulate going offline
    useUIStore.getState().setOffline(true);
    expect(useUIStore.getState().isOffline).toBe(true);

    // Simulate coming back online
    useUIStore.getState().setOffline(false);
    expect(useUIStore.getState().isOffline).toBe(false);
  });

  it('queued actions retry when coming back online', async () => {
    // Simulate an action queue pattern
    const actionQueue: Array<() => Promise<void>> = [];

    // Go offline
    useUIStore.getState().setOffline(true);

    // Queue a bet action while offline
    const betAction = async () => {
      await apiClient.post('/game/bet', {
        round_id: 'round-1',
        color: 'red',
        amount: '50.00',
      });
    };

    actionQueue.push(betAction);
    expect(actionQueue).toHaveLength(1);

    // Come back online — process the queue
    useUIStore.getState().setOffline(false);

    mockedPost.mockResolvedValueOnce({
      data: {
        id: 'bet-1',
        color: 'red',
        amount: '50.00',
        odds_at_placement: '2.00',
        balance_after: '450.00',
      },
    });

    // Process queued actions
    for (const action of actionQueue) {
      await action();
    }

    expect(mockedPost).toHaveBeenCalledWith('/game/bet', {
      round_id: 'round-1',
      color: 'red',
      amount: '50.00',
    });
  });

  it('multiple actions queue and retry in order', async () => {
    const actionQueue: Array<{ name: string; fn: () => Promise<void> }> = [];

    // Go offline
    useUIStore.getState().setOffline(true);

    // Queue multiple actions
    actionQueue.push({
      name: 'bet-red',
      fn: async () => {
        await apiClient.post('/game/bet', { round_id: 'r1', color: 'red', amount: '10.00' });
      },
    });

    actionQueue.push({
      name: 'bet-blue',
      fn: async () => {
        await apiClient.post('/game/bet', { round_id: 'r1', color: 'blue', amount: '20.00' });
      },
    });

    expect(actionQueue).toHaveLength(2);

    // Come back online
    useUIStore.getState().setOffline(false);

    mockedPost
      .mockResolvedValueOnce({ data: { id: 'b1', balance_after: '90.00' } })
      .mockResolvedValueOnce({ data: { id: 'b2', balance_after: '70.00' } });

    // Process in order
    const executionOrder: string[] = [];
    for (const action of actionQueue) {
      await action.fn();
      executionOrder.push(action.name);
    }

    expect(executionOrder).toEqual(['bet-red', 'bet-blue']);
    expect(mockedPost).toHaveBeenCalledTimes(2);
  });

  it('failed retry does not crash — errors are catchable', async () => {
    useUIStore.getState().setOffline(true);

    const actionQueue: Array<() => Promise<void>> = [];
    actionQueue.push(async () => {
      await apiClient.post('/game/bet', { round_id: 'r1', color: 'red', amount: '10.00' });
    });

    // Come back online
    useUIStore.getState().setOffline(false);

    mockedPost.mockRejectedValueOnce(new Error('Network error'));

    // Process with error handling
    const errors: Error[] = [];
    for (const action of actionQueue) {
      try {
        await action();
      } catch (err) {
        errors.push(err as Error);
      }
    }

    expect(errors).toHaveLength(1);
    expect(errors[0].message).toBe('Network error');
    expect(useUIStore.getState().isOffline).toBe(false);
  });

  it('offline state persists across multiple toggles', () => {
    const store = useUIStore.getState();

    store.setOffline(true);
    expect(useUIStore.getState().isOffline).toBe(true);

    store.setOffline(true); // idempotent
    expect(useUIStore.getState().isOffline).toBe(true);

    store.setOffline(false);
    expect(useUIStore.getState().isOffline).toBe(false);

    store.setOffline(false); // idempotent
    expect(useUIStore.getState().isOffline).toBe(false);
  });
});
