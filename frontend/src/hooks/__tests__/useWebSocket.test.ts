import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useWebSocket } from '../useWebSocket';
import { useAuthStore } from '@/stores/auth-store';
import { useGameStore } from '@/stores/game-store';
import { useUIStore } from '@/stores/ui-store';

// Mock the ws-client module
const mockConnect = vi.fn();
const mockDisconnect = vi.fn();
const mockSend = vi.fn();
const mockGetStatus = vi.fn().mockReturnValue('disconnected');
let messageHandler: ((msg: unknown) => void) | null = null;

vi.mock('@/lib/ws-client', () => ({
  createWSClient: () => ({
    connect: mockConnect,
    disconnect: mockDisconnect,
    send: mockSend,
    getStatus: mockGetStatus,
    onMessage: (handler: (msg: unknown) => void) => {
      messageHandler = handler;
      return () => {
        messageHandler = null;
      };
    },
  }),
}));

describe('useWebSocket', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    mockConnect.mockClear();
    mockDisconnect.mockClear();
    mockSend.mockClear();
    messageHandler = null;

    useAuthStore.setState({
      accessToken: 'test-token',
      isAuthenticated: true,
    });

    useGameStore.setState({
      currentRound: null,
      phase: 'betting',
      timerRemaining: 0,
      connectionStatus: 'disconnected',
      placedBets: [],
      selectedBets: {},
      result: null,
    });

    useUIStore.setState({
      isChatOpen: false,
      unreadChatCount: 0,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('connects with roundId and token', () => {
    renderHook(() => useWebSocket('round-1'));
    expect(mockConnect).toHaveBeenCalledWith('round-1', 'test-token');
  });

  it('does not connect without a token', () => {
    useAuthStore.setState({ accessToken: null });
    renderHook(() => useWebSocket('round-1'));
    expect(mockConnect).not.toHaveBeenCalled();
  });

  it('does not connect without a roundId', () => {
    renderHook(() => useWebSocket(''));
    expect(mockConnect).not.toHaveBeenCalled();
  });

  it('disconnects on unmount', () => {
    const { unmount } = renderHook(() => useWebSocket('round-1'));
    unmount();
    expect(mockDisconnect).toHaveBeenCalled();
  });

  it('dispatches round_state to game store', () => {
    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({
        type: 'round_state',
        phase: 'betting',
        timer: 30,
        round_id: 'round-1',
        total_players: 5,
        total_pool: '500.00',
      });
    });

    const state = useGameStore.getState();
    expect(state.currentRound?.roundId).toBe('round-1');
    expect(state.currentRound?.totalPlayers).toBe(5);
    expect(state.timerRemaining).toBe(30);
  });

  it('dispatches timer_tick to game store', () => {
    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({ type: 'timer_tick', remaining: 15 });
    });

    expect(useGameStore.getState().timerRemaining).toBe(15);
  });

  it('dispatches phase_change to game store', () => {
    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({ type: 'phase_change', phase: 'resolution' });
    });

    expect(useGameStore.getState().phase).toBe('resolution');
  });

  it('dispatches result to game store', () => {
    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({
        type: 'result',
        winning_color: 'red',
        payouts: [{ player_id: 'p1', bet_id: 'b1', amount: '100.00' }],
      });
    });

    const result = useGameStore.getState().result;
    expect(result?.winningColor).toBe('red');
    expect(result?.playerPayouts).toHaveLength(1);
  });

  it('dispatches new_round to game store', () => {
    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({ type: 'new_round', round_id: 'round-2', timer: 30 });
    });

    const state = useGameStore.getState();
    expect(state.currentRound?.roundId).toBe('round-2');
    expect(state.phase).toBe('betting');
    expect(state.timerRemaining).toBe(30);
  });

  it('dispatches bet_update to game store', () => {
    // Set up an existing round first
    useGameStore.setState({
      currentRound: {
        roundId: 'round-1',
        phase: 'betting',
        timer: 20,
        totalPlayers: 3,
        totalPool: '300.00',
        gameMode: 'classic',
      },
    });

    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({
        type: 'bet_update',
        total_players: 7,
        total_pool: '700.00',
      });
    });

    const round = useGameStore.getState().currentRound;
    expect(round?.totalPlayers).toBe(7);
    expect(round?.totalPool).toBe('700.00');
  });

  it('increments unread chat when chat is closed', () => {
    useUIStore.setState({ isChatOpen: false, unreadChatCount: 0 });

    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({
        type: 'chat_message',
        sender: 'user1',
        message: 'hello',
        timestamp: '2024-01-01T00:00:00Z',
      });
    });

    expect(useUIStore.getState().unreadChatCount).toBe(1);
  });

  it('does not increment unread chat when chat is open', () => {
    useUIStore.setState({ isChatOpen: true, unreadChatCount: 0 });

    renderHook(() => useWebSocket('round-1'));

    act(() => {
      messageHandler?.({
        type: 'chat_message',
        sender: 'user1',
        message: 'hello',
        timestamp: '2024-01-01T00:00:00Z',
      });
    });

    expect(useUIStore.getState().unreadChatCount).toBe(0);
  });

  it('sendMessage delegates to ws client', () => {
    const { result } = renderHook(() => useWebSocket('round-1'));

    act(() => {
      result.current.sendMessage({ type: 'ping' });
    });

    expect(mockSend).toHaveBeenCalledWith({ type: 'ping' });
  });
});
