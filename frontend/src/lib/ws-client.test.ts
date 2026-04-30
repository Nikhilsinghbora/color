import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { calculateBackoff, createWSClient } from './ws-client';

// ---------------------------------------------------------------------------
// Mock WebSocket
// ---------------------------------------------------------------------------

type WSListener = ((event: { data: string }) => void) | (() => void);

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
    // Simulate async open
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sentMessages.push(data);
  }

  close() {
    this.readyState = MockWebSocket.CLOSED;
    setTimeout(() => this.onclose?.(), 0);
  }

  // Test helpers
  simulateMessage(data: unknown) {
    this.onmessage?.({ data: JSON.stringify(data) });
  }

  simulateClose() {
    this.readyState = MockWebSocket.CLOSED;
    this.onclose?.();
  }

  simulateError() {
    this.onerror?.();
  }
}

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.useFakeTimers();
  MockWebSocket.instances = [];
  vi.stubGlobal('WebSocket', MockWebSocket);
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

// ---------------------------------------------------------------------------
// calculateBackoff
// ---------------------------------------------------------------------------

describe('calculateBackoff', () => {
  it('returns 1000ms for attempt 1', () => {
    expect(calculateBackoff(1)).toBe(1000);
  });

  it('returns 2000ms for attempt 2', () => {
    expect(calculateBackoff(2)).toBe(2000);
  });

  it('returns 4000ms for attempt 3', () => {
    expect(calculateBackoff(3)).toBe(4000);
  });

  it('returns 16000ms for attempt 5', () => {
    expect(calculateBackoff(5)).toBe(16000);
  });

  it('caps at 30000ms for large attempt numbers', () => {
    expect(calculateBackoff(6)).toBe(30000);
    expect(calculateBackoff(10)).toBe(30000);
    expect(calculateBackoff(100)).toBe(30000);
  });
});

// ---------------------------------------------------------------------------
// createWSClient
// ---------------------------------------------------------------------------

describe('createWSClient', () => {
  it('starts with disconnected status', () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    expect(client.getStatus()).toBe('disconnected');
  });

  it('connects and transitions to connecting then connected', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'token-abc');

    expect(client.getStatus()).toBe('connecting');

    // Let the mock WebSocket fire onopen
    await vi.advanceTimersByTimeAsync(1);

    expect(client.getStatus()).toBe('connected');
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(MockWebSocket.instances[0].url).toBe('ws://test/ws/game/round-1?token=token-abc');
  });

  it('dispatches parsed messages to handlers', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    const handler = vi.fn();
    client.onMessage(handler);
    client.connect('round-1', 'tok');

    await vi.advanceTimersByTimeAsync(1);

    const msg = { type: 'timer_tick', remaining: 15 };
    MockWebSocket.instances[0].simulateMessage(msg);

    expect(handler).toHaveBeenCalledWith(msg);
  });

  it('unsubscribe removes handler', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    const handler = vi.fn();
    const unsub = client.onMessage(handler);
    client.connect('round-1', 'tok');

    await vi.advanceTimersByTimeAsync(1);

    unsub();
    MockWebSocket.instances[0].simulateMessage({ type: 'timer_tick', remaining: 10 });

    expect(handler).not.toHaveBeenCalled();
  });

  it('sends messages as JSON when connected', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    client.send({ type: 'ping' });

    expect(MockWebSocket.instances[0].sentMessages).toEqual([
      JSON.stringify({ type: 'ping' }),
    ]);
  });

  it('does not send when not connected', () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    // Not connected — send should be a no-op
    client.send({ type: 'ping' });
    expect(MockWebSocket.instances).toHaveLength(0);
  });

  it('disconnect sets status to disconnected and cleans up', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    client.disconnect();

    expect(client.getStatus()).toBe('disconnected');
  });

  it('reconnects with exponential backoff on unexpected close', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    expect(client.getStatus()).toBe('connected');

    // Simulate unexpected close
    MockWebSocket.instances[0].simulateClose();

    expect(client.getStatus()).toBe('reconnecting');

    // Advance by 1000ms (first backoff)
    await vi.advanceTimersByTimeAsync(1000);

    // A new WebSocket should have been created
    expect(MockWebSocket.instances).toHaveLength(2);
    expect(client.getStatus()).toBe('connecting');

    // Let it connect
    await vi.advanceTimersByTimeAsync(1);
    expect(client.getStatus()).toBe('connected');
  });

  it('does not reconnect after intentional disconnect', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    client.disconnect();

    // Advance time — no reconnection should happen
    await vi.advanceTimersByTimeAsync(60000);

    // Only the original instance
    expect(MockWebSocket.instances).toHaveLength(1);
    expect(client.getStatus()).toBe('disconnected');
  });

  it('resets reconnect attempt counter on successful connection', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    // Close unexpectedly
    MockWebSocket.instances[0].simulateClose();
    // First reconnect at 1s
    await vi.advanceTimersByTimeAsync(1000);
    await vi.advanceTimersByTimeAsync(1); // let it connect

    expect(client.getStatus()).toBe('connected');

    // Close again — should use 1s backoff again (reset)
    MockWebSocket.instances[1].simulateClose();
    expect(client.getStatus()).toBe('reconnecting');

    await vi.advanceTimersByTimeAsync(1000);
    expect(MockWebSocket.instances).toHaveLength(3);
  });

  it('handles TOKEN_EXPIRED error by refreshing and reconnecting', async () => {
    const onTokenExpired = vi.fn().mockResolvedValue('new-token');
    const client = createWSClient({ baseUrl: 'ws://test', onTokenExpired });
    client.connect('round-1', 'old-token');
    await vi.advanceTimersByTimeAsync(1);

    // Server sends token expired error
    MockWebSocket.instances[0].simulateMessage({
      type: 'error',
      code: 'TOKEN_EXPIRED',
      message: 'Token expired',
    });

    // Wait for the async token refresh
    await vi.advanceTimersByTimeAsync(1);

    expect(onTokenExpired).toHaveBeenCalledOnce();

    // Should have created a new connection with the new token
    const lastInstance = MockWebSocket.instances[MockWebSocket.instances.length - 1];
    expect(lastInstance.url).toContain('token=new-token');
  });

  it('ignores invalid JSON messages', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    const handler = vi.fn();
    client.onMessage(handler);
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    // Send invalid JSON directly
    MockWebSocket.instances[0].onmessage?.({ data: 'not-json{{{' });

    expect(handler).not.toHaveBeenCalled();
  });

  it('handles all WSIncomingMessage types', async () => {
    const client = createWSClient({ baseUrl: 'ws://test' });
    const handler = vi.fn();
    client.onMessage(handler);
    client.connect('round-1', 'tok');
    await vi.advanceTimersByTimeAsync(1);

    const ws = MockWebSocket.instances[0];

    const messages = [
      { type: 'round_state', phase: 'betting', timer: 30, round_id: 'r1', total_players: 5, total_pool: '100.00' },
      { type: 'timer_tick', remaining: 25 },
      { type: 'phase_change', phase: 'resolution' },
      { type: 'result', winning_color: 'red', payouts: [] },
      { type: 'new_round', round_id: 'r2', timer: 30 },
      { type: 'chat_message', sender: 'alice', message: 'hi', timestamp: '2024-01-01T00:00:00Z' },
      { type: 'bet_update', total_players: 6, total_pool: '200.00' },
      { type: 'error', code: 'SOME_ERROR', message: 'oops' },
    ];

    for (const msg of messages) {
      ws.simulateMessage(msg);
    }

    expect(handler).toHaveBeenCalledTimes(messages.length);
    messages.forEach((msg, i) => {
      expect(handler).toHaveBeenNthCalledWith(i + 1, msg);
    });
  });
});
