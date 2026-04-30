import type { WSIncomingMessage, WSOutgoingMessage } from '@/types';

// ---------------------------------------------------------------------------
// Backoff calculation (exported for testing)
// ---------------------------------------------------------------------------

/**
 * Calculate reconnection delay using exponential backoff.
 * delay = min(2^(attempt-1) * 1000, 30000) ms
 * @param attempt - Reconnection attempt number (starts at 1)
 */
export function calculateBackoff(attempt: number): number {
  const delay = Math.pow(2, attempt - 1) * 1000;
  return Math.min(delay, 30000);
}

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type WSStatus = 'connecting' | 'connected' | 'disconnected' | 'reconnecting';

type MessageHandler = (msg: WSIncomingMessage) => void;

export interface WSClient {
  connect(roundId: string, token: string): void;
  disconnect(): void;
  send(message: WSOutgoingMessage): void;
  onMessage(handler: MessageHandler): () => void;
  getStatus(): WSStatus;
}

export interface WSClientOptions {
  /** Override the base WS URL. Defaults to NEXT_PUBLIC_WS_URL or derived from window.location. */
  baseUrl?: string;
  /** Called when the token has expired during a WS session. Should return a fresh token or null. */
  onTokenExpired?: () => Promise<string | null>;
}

// ---------------------------------------------------------------------------
// Factory
// ---------------------------------------------------------------------------

export function createWSClient(options: WSClientOptions = {}): WSClient {
  let ws: WebSocket | null = null;
  let status: WSStatus = 'disconnected';
  let reconnectAttempt = 0;
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  let intentionalClose = false;

  // Current connection params (needed for reconnection)
  let currentRoundId: string | null = null;
  let currentToken: string | null = null;

  const handlers = new Set<MessageHandler>();

  // ---- helpers ----

  function getBaseUrl(): string {
    if (options.baseUrl) return options.baseUrl;

    if (typeof process !== 'undefined' && process.env?.NEXT_PUBLIC_WS_URL) {
      return process.env.NEXT_PUBLIC_WS_URL;
    }

    if (typeof window !== 'undefined') {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      return `${proto}//${window.location.host}`;
    }

    return 'ws://localhost:3000';
  }

  function buildUrl(roundId: string, token: string): string {
    const base = getBaseUrl().replace(/\/$/, '');
    return `${base}/ws/game/${roundId}?token=${token}`;
  }

  function setStatus(s: WSStatus) {
    status = s;
  }

  function clearReconnectTimer() {
    if (reconnectTimer !== null) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  function scheduleReconnect() {
    if (intentionalClose || !currentRoundId || !currentToken) return;

    reconnectAttempt++;
    setStatus('reconnecting');
    const delay = calculateBackoff(reconnectAttempt);

    reconnectTimer = setTimeout(() => {
      if (intentionalClose) return;
      openConnection(currentRoundId!, currentToken!);
    }, delay);
  }

  async function handleTokenExpiry(): Promise<boolean> {
    if (!options.onTokenExpired) return false;

    try {
      const newToken = await options.onTokenExpired();
      if (newToken && currentRoundId) {
        currentToken = newToken;
        openConnection(currentRoundId, newToken);
        return true;
      }
    } catch {
      // refresh failed — fall through
    }
    return false;
  }

  function dispatchMessage(msg: WSIncomingMessage) {
    handlers.forEach((h) => {
      try {
        h(msg);
      } catch {
        // handler error — don't crash the client
      }
    });
  }

  function openConnection(roundId: string, token: string) {
    // Clean up any existing socket
    if (ws) {
      try { ws.close(); } catch { /* ignore */ }
      ws = null;
    }

    setStatus('connecting');
    const url = buildUrl(roundId, token);

    try {
      ws = new WebSocket(url);
    } catch {
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      setStatus('connected');
      reconnectAttempt = 0; // reset on successful connection
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as WSIncomingMessage;

        // Handle auth token expiry error from server
        if (data.type === 'error' && data.code === 'TOKEN_EXPIRED') {
          ws?.close();
          handleTokenExpiry().then((reconnected) => {
            if (!reconnected) {
              setStatus('disconnected');
            }
          });
          return;
        }

        dispatchMessage(data);
      } catch {
        // Invalid JSON — ignore per design doc
      }
    };

    ws.onclose = () => {
      ws = null;
      if (!intentionalClose) {
        scheduleReconnect();
      } else {
        setStatus('disconnected');
      }
    };

    ws.onerror = () => {
      // onerror is always followed by onclose, so reconnect logic is in onclose
    };
  }

  // ---- public API ----

  return {
    connect(roundId: string, token: string) {
      intentionalClose = false;
      clearReconnectTimer();
      reconnectAttempt = 0;
      currentRoundId = roundId;
      currentToken = token;
      openConnection(roundId, token);
    },

    disconnect() {
      intentionalClose = true;
      clearReconnectTimer();
      reconnectAttempt = 0;
      currentRoundId = null;
      currentToken = null;
      if (ws) {
        try { ws.close(); } catch { /* ignore */ }
        ws = null;
      }
      setStatus('disconnected');
    },

    send(message: WSOutgoingMessage) {
      if (ws && ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify(message));
      }
    },

    onMessage(handler: MessageHandler): () => void {
      handlers.add(handler);
      return () => {
        handlers.delete(handler);
      };
    },

    getStatus(): WSStatus {
      return status;
    },
  };
}
