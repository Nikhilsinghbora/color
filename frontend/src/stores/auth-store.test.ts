import { describe, it, expect, beforeEach } from 'vitest';
import { useAuthStore } from './auth-store';

/**
 * Helper: build a minimal JWT with the given payload.
 * Header and signature are dummy values — we only need the payload for decoding.
 */
function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = btoa(JSON.stringify(payload));
  const sig = 'signature';
  return `${header}.${body}.${sig}`;
}

describe('Auth Store', () => {
  beforeEach(() => {
    // Clear localStorage and reset store to initial state before each test
    localStorage.clear();
    useAuthStore.getState().clearTokens();
  });

  it('starts with unauthenticated state', () => {
    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.player).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isAdmin).toBe(false);
  });

  it('setTokens stores tokens, sets isAuthenticated, and decodes player', () => {
    const access = makeJwt({
      sub: 'user-123',
      email: 'test@example.com',
      username: 'testplayer',
      is_admin: false,
    });
    const refresh = 'refresh-token-abc';

    useAuthStore.getState().setTokens(access, refresh);

    const state = useAuthStore.getState();
    expect(state.accessToken).toBe(access);
    expect(state.refreshToken).toBe(refresh);
    expect(state.isAuthenticated).toBe(true);
    expect(state.player).toEqual({
      id: 'user-123',
      email: 'test@example.com',
      username: 'testplayer',
      isAdmin: false,
    });
    expect(state.isAdmin).toBe(false);
  });

  it('setTokens correctly identifies admin users', () => {
    const access = makeJwt({
      sub: 'admin-1',
      email: 'admin@example.com',
      username: 'adminuser',
      is_admin: true,
    });

    useAuthStore.getState().setTokens(access, 'refresh');

    const state = useAuthStore.getState();
    expect(state.isAdmin).toBe(true);
    expect(state.player?.isAdmin).toBe(true);
  });

  it('clearTokens resets all state', () => {
    const access = makeJwt({
      sub: 'user-1',
      email: 'a@b.com',
      username: 'u',
      is_admin: true,
    });
    useAuthStore.getState().setTokens(access, 'r');

    useAuthStore.getState().clearTokens();

    const state = useAuthStore.getState();
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.player).toBeNull();
    expect(state.isAuthenticated).toBe(false);
    expect(state.isAdmin).toBe(false);
  });

  it('setPlayer updates player and isAdmin', () => {
    useAuthStore.getState().setPlayer({
      id: 'p-1',
      email: 'p@test.com',
      username: 'player1',
      isAdmin: true,
    });

    const state = useAuthStore.getState();
    expect(state.player?.username).toBe('player1');
    expect(state.isAdmin).toBe(true);
  });

  it('decodeAndSetPlayer handles malformed JWT gracefully', () => {
    // Should not throw — just leaves player as null
    useAuthStore.getState().decodeAndSetPlayer('not-a-jwt');
    expect(useAuthStore.getState().player).toBeNull();
  });

  it('decodeAndSetPlayer handles base64url encoding', () => {
    // Manually create a base64url-encoded payload (with - and _ chars)
    const payload = { sub: 'id+special/chars', email: 'e@e.com', username: 'u', is_admin: false };
    const header = btoa(JSON.stringify({ alg: 'HS256' }));
    // Use standard btoa then convert to base64url
    const body = btoa(JSON.stringify(payload))
      .replace(/\+/g, '-')
      .replace(/\//g, '_')
      .replace(/=+$/, '');
    const token = `${header}.${body}.sig`;

    useAuthStore.getState().decodeAndSetPlayer(token);

    const state = useAuthStore.getState();
    expect(state.player?.id).toBe('id+special/chars');
  });

  it('persists tokens to localStorage', () => {
    const access = makeJwt({
      sub: 'user-123',
      email: 'test@example.com',
      username: 'testplayer',
      is_admin: false,
    });
    const refresh = 'refresh-token-abc';

    useAuthStore.getState().setTokens(access, refresh);

    // Check that localStorage contains the persisted data
    const stored = localStorage.getItem('auth-storage');
    expect(stored).toBeTruthy();
    const parsed = JSON.parse(stored!);
    expect(parsed.state.accessToken).toBe(access);
    expect(parsed.state.refreshToken).toBe(refresh);
    expect(parsed.state.isAuthenticated).toBe(true);
  });

  it('restores tokens from localStorage on rehydration', () => {
    const access = makeJwt({
      sub: 'restored-user',
      email: 'restored@example.com',
      username: 'restoredplayer',
      is_admin: false,
    });
    const refresh = 'restored-refresh-token';

    // Manually set localStorage to simulate a persisted state
    const persistedState = {
      state: {
        accessToken: access,
        refreshToken: refresh,
        isAuthenticated: true,
      },
      version: 0,
    };
    localStorage.setItem('auth-storage', JSON.stringify(persistedState));

    // Force store rehydration by calling persist.rehydrate()
    useAuthStore.persist.rehydrate();

    // Give rehydration time to complete (it's async)
    return new Promise<void>((resolve) => {
      setTimeout(() => {
        const state = useAuthStore.getState();
        expect(state.accessToken).toBe(access);
        expect(state.refreshToken).toBe(refresh);
        expect(state.isAuthenticated).toBe(true);
        // Player should be decoded from the token
        expect(state.player?.id).toBe('restored-user');
        expect(state.player?.email).toBe('restored@example.com');
        resolve();
      }, 100);
    });
  });
});
