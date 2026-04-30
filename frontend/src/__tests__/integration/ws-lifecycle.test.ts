import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { createWSClient } from '@/lib/ws-client';
import { useGameStore } from '@/stores/game-store';
import type { WSIncomingMessage } from '@/types';

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

class MockWebSocket {
  static OPEN = 1;
  static CLOSED = 3;
  static instances: MockWebSocket[] = [];

  url: string;
  readyState = MockWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  sentMessages: string[] = [];

  constructor(url: string) {
    this.url = url;
    MockWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    setTimeout(() => this.onclose?.(), 0);
  }

  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers();
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket);
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
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// Integration: WebSocket Lifecycle
// Requirements: 3.1–3.6, 3.7
// ---------------------------------------------------------------------------

describe('Integration: WebSocket Lifecycle', () => {
  it('connect → receive round_state → timer ticks → phase change → result → new round', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    const received: WSIncomingMessage[] = [];

    client.onMessage((msg) => {
      received.push(msg);
      // Dispatch to game store like useWebSocket hook does
      const gs = useGameStore.getState();
      switch (msg.type) {
        case 'round_state':
          gs.setRoundState({
            roundId: msg.round_id,
            phase: msg.phase,
            timer: msg.timer,
            totalPlayers: msg.total_players,
            totalPool: msg.total_pool,
            gameMode: 'classic',
          });
          break;
        case 'timer_tick':
          gs.updateTimer(msg.remaining);
          break;
        case 'phase_change':
          gs.setPhase(msg.phase);
          break;
        case 'result':
          gs.setResult({
            winningColor: msg.winning_color,
            winningNumber: msg.winning_number,
            playerPayouts: msg.payouts.map((p) => ({
              betId: p.bet_id,
              amount: p.amount,
              isWinner: true,
            })),
          });
          break;
        case 'new_round':
          gs.resetRound(msg.round_id, msg.timer);
          break;
      }
    });

    // Step 1: Connect
    client.connect('round-1', 'token-abc');
    expect(client.getStatus()).toBe('connecting');
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');

    const ws = MockWebSocket.instances[0];

    // Step 2: Receive round_state
    ws.simulateMessage({
      type: 'round_state',
      phase: 'betting',
      timer: 30,
      round_id: 'round-1',
      total_players: 10,
      total_pool: '500.00',
    });

    expect(useGameStore.getState().phase).toBe('betting');
    expect(useGameStore.getState().timerRemaining).toBe(30);
    expect(useGameStore.getState().currentRound?.totalPlayers).toBe(10);

    // Step 3: Timer ticks
    ws.simulateMessage({ type: 'timer_tick', remaining: 25 });
    expect(useGameStore.getState().timerRemaining).toBe(25);

    ws.simulateMessage({ type: 'timer_tick', remaining: 20 });
    expect(useGameStore.getState().timerRemaining).toBe(20);

    // Step 4: Phase change to resolution
    ws.simulateMessage({ type: 'phase_change', phase: 'resolution' });
    expect(useGameStore.getState().phase).toBe('resolution');

    // Step 5: Result
    ws.simulateMessage({
      type: 'result',
      winning_color: 'blue',
      winning_number: 3,
      payouts: [{ bet_id: 'bet-1', amount: '200.00' }],
    });
    expect(useGameStore.getState().result?.winningColor).toBe('blue');

    // Step 6: New round
    ws.simulateMessage({ type: 'new_round', round_id: 'round-2', timer: 30 });
    expect(useGameStore.getState().currentRound?.roundId).toBe('round-2');
    expect(useGameStore.getState().phase).toBe('betting');
    expect(useGameStore.getState().result).toBeNull();
    expect(useGameStore.getState().placedBets).toEqual([]);

    // All messages received
    expect(received).toHaveLength(6);

    // Step 7: Disconnect
    client.disconnect();
    expect(client.getStatus()).toBe('disconnected');
  });

  it('disconnect → reconnect with exponential backoff', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');

    // Unexpected close
    MockWebSocket.instances[0].simulateClose();
    expect(client.getStatus()).toBe('reconnecting');

    // First reconnect at 1s
    await vi.advanceTimersByTimeAsync(1000);
    expect(MockWebSocket.instances).toHaveLength(2);

    // Let it connect
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');

    // Close again — backoff resets on successful connection
    MockWebSocket.instances[1].simulateClose();
    expect(client.getStatus()).toBe('reconnecting');

    // Should reconnect at 1s again (reset after success)
    await vi.advanceTimersByTimeAsync(1000);
    expect(MockWebSocket.instances).toHaveLength(3);
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');
  });

  it('handles multiple rapid disconnects with increasing backoff', async () => {
    // Create a WS that doesn't auto-connect on open
    const originalWS = globalThis.WebSocket;

    class FailingWebSocket extends MockWebSocket {
      constructor(url: string) {
        super(url);
        // Override: simulate immediate failure
        setTimeout(() => {
          this.readyState = MockWebSocket.CLOSED;
          this.onclose?.();
        }, 0);
      }
    }

    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');

    // Now make subsequent connections fail
    vi.stubGlobal('WebSocket', FailingWebSocket);

    // First disconnect
    MockWebSocket.instances[0].simulateClose();
    expect(client.getStatus()).toBe('reconnecting');

    // After 1s, reconnect attempt fails immediately
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(1); // let the failing WS close

    // Should be reconnecting again with 2s backoff
    expect(client.getStatus()).toBe('reconnecting');

    // Restore and let it succeed
    vi.stubGlobal('WebSocket', MockWebSocket);
    await vi.advanceTimersByTimeAsync(2000);
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');
  });

  it('sends messages only when connected', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });

    // Not connected — send is a no-op
    client.send({ type: 'ping' });
    expect(MockWebSocket.instances).toHaveLength(0);

    // Connect
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    // Now send works
    client.send({ type: 'chat', message: 'hello' });
    expect(MockWebSocket.instances[0].sentMessages).toHaveLength(1);
    expect(JSON.parse(MockWebSocket.instances[0].sentMessages[0])).toEqual({
      type: 'chat',
      message: 'hello',
    });
  });

  it('token expiry triggers refresh and reconnect', async () => {
    const onTokenExpired = vi.fn().mockResolvedValue('fresh-token');
    const client = createWSClient({ baseUrl: 'ws://test', onTokenExpired });

    client.connect('round-1', 'old-token');
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');

    // Server sends TOKEN_EXPIRED
    MockWebSocket.instances[0].simulateMessage({
      type: 'error',
      code: 'TOKEN_EXPIRED',
      message: 'Token expired',
    });

    await vi.advanceTimersByTimeAsync(1);
    expect(onTokenExpired).toHaveBeenCalledOnce();

    // New connection with fresh token
    const lastWs = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(lastWs.url).toContain('token=fresh-token');
  });
});
