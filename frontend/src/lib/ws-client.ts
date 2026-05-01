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

    // In Next.js, NEXT_PUBLIC_ env vars are available at build time and runtime
    const envWsUrl = process.env.NEXT_PUBLIC_WS_URL;
    if (envWsUrl) {
      console.log('[ws-client] Using NEXT_PUBLIC_WS_URL:', envWsUrl);
      return envWsUrl;
    }

    if (typeof window !== 'undefined') {
      const proto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const fallback = `${proto}//${window.location.host}`;
      console.log('[ws-client] No NEXT_PUBLIC_WS_URL, using fallback:', fallback);
      return fallback;
    }

    console.log('[ws-client] Using default: ws://localhost:3000');
    return 'ws://localhost:3000';
  }

  function buildUrl(roundId: string, token: string): string {
    const base = getBaseUrl().replace(/\/$/, '');
    const url = `${base}/ws/game/${roundId}?token=${token}`;
    console.log('[ws-client] Built WebSocket URL:', url.replace(/token=.*/, 'token=***'));
    return url;
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
      console.log('[ws-client] Closing existing WebSocket connection');
      try { ws.close(); } catch { /* ignore */ }
      ws = null;
    }

    setStatus('connecting');
    const url = buildUrl(roundId, token);

    try {
      console.log('[ws-client] Creating WebSocket instance...');
      ws = new WebSocket(url);
    } catch (error) {
      console.error('[ws-client] Failed to create WebSocket:', error);
      scheduleReconnect();
      return;
    }

    ws.onopen = () => {
      console.log('[ws-client] ✅ WebSocket connection OPENED');
      setStatus('connected');
      reconnectAttempt = 0; // reset on successful connection
    };

    ws.onmessage = (event: MessageEvent) => {
      try {
        const data = JSON.parse(event.data) as WSIncomingMessage;
        console.log('[ws-client] 📩 Received message:', data.type);

        // Handle auth token expiry error from server
        if (data.type === 'error' && data.code === 'TOKEN_EXPIRED') {
          console.warn('[ws-client] Token expired, attempting refresh');
          ws?.close();
          handleTokenExpiry().then((reconnected) => {
            if (!reconnected) {
              setStatus('disconnected');
            }
          });
          return;
        }

        dispatchMessage(data);
      } catch (error) {
        console.warn('[ws-client] Failed to parse message:', error);
        // Invalid JSON — ignore per design doc
      }
    };

    ws.onclose = (event) => {
      console.log('[ws-client] 🔌 WebSocket connection CLOSED:', {
        code: event.code,
        reason: event.reason || 'no reason',
        wasClean: event.wasClean,
      });

      // Common close codes:
      // 1000 = Normal closure
      // 1001 = Going away
      // 1006 = Abnormal closure (no close frame received)
      // 4001 = Authentication failed (custom code from our backend)
      if (event.code === 4001) {
        console.error('[ws-client] ❌ Authentication failed - token invalid or expired');
      } else if (event.code === 1006) {
        console.warn('[ws-client] ⚠️ Connection closed abnormally - backend may have rejected connection');
      }

      ws = null;
      if (!intentionalClose) {
        scheduleReconnect();
      } else {
        setStatus('disconnected');
      }
    };

    ws.onerror = (error) => {
      console.error('[ws-client] ❌ WebSocket ERROR:', error);
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
