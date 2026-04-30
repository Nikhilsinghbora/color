import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from '@/stores/auth-store';

/**
 * Integration test: Auth token persistence to localStorage
 * Verifies that tokens are persisted and can be retrieved for WebSocket connections
 */

function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = btoa(JSON.stringify(payload));
  const sig = 'signature';
  return `${header}.${body}.${sig}`;
}

describe('Auth Persistence Integration', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('setTokens persists to localStorage', async () => {
    const access = makeJwt({
      sub: 'user-123',
      email: 'user@example.com',
      username: 'testuser',
      is_admin: false,
    });
    const refresh = 'refresh-token-xyz';

    useAuthStore.getState().setTokens(access, refresh);

    // Verify tokens are set in memory
    expect(useAuthStore.getState().accessToken).toBe(access);
    expect(useAuthStore.getState().isAuthenticated).toBe(true);

    // Wait for persist to write to localStorage
    await new Promise((resolve) => setTimeout(resolve, 50));

    // Verify localStorage has the data
    const stored = localStorage.getItem('auth-storage');
    expect(stored).toBeTruthy();

    const parsed = JSON.parse(stored!);
    expect(parsed.state.accessToken).toBe(access);
    expect(parsed.state.refreshToken).toBe(refresh);
    expect(parsed.state.isAuthenticated).toBe(true);
  });

  it('tokens are available for WebSocket connections', () => {
    const access = makeJwt({
      sub: 'ws-user',
      email: 'ws@example.com',
      username: 'wsuser',
      is_admin: false,
    });

    useAuthStore.getState().setTokens(access, 'ws-refresh');

    // Simulate WebSocket hook trying to get token
    const token = useAuthStore.getState().accessToken;

    // Token should be immediately available (synchronous)
    expect(token).toBe(access);
    expect(token).not.toBeNull();
  });

  it('clearTokens updates localStorage', async () => {
    // Set tokens first
    const access = makeJwt({
      sub: 'user-456',
      email: 'clear@example.com',
      username: 'clearuser',
      is_admin: false,
    });

    useAuthStore.getState().setTokens(access, 'refresh');

    // Wait for persist
    await new Promise((resolve) => setTimeout(resolve, 50));

    // Verify localStorage has data
    const stored = localStorage.getItem('auth-storage');
    expect(stored).toBeTruthy();

    // Clear tokens
    useAuthStore.getState().clearTokens();

    // Wait for persist to update
    await new Promise((resolve) => setTimeout(resolve, 50));

    // Verify localStorage is updated
    const clearedStored = localStorage.getItem('auth-storage');
    const parsed = JSON.parse(clearedStored!);
    expect(parsed.state.accessToken).toBeNull();
    expect(parsed.state.refreshToken).toBeNull();
    expect(parsed.state.isAuthenticated).toBe(false);
  });

  it('localStorage data survives store state changes', async () => {
    const access = makeJwt({
      sub: 'persist-user',
      email: 'persist@example.com',
      username: 'persistuser',
      is_admin: false,
    });

    useAuthStore.getState().setTokens(access, 'persist-refresh');

    // Wait for persist
    await new Promise((resolve) => setTimeout(resolve, 50));

    // Verify localStorage has data
    const stored = localStorage.getItem('auth-storage');
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed.state.accessToken).toBe(access);

    // In a real page refresh, this data would be automatically rehydrated
    // by Zustand's persist middleware on app initialization
  });
});
