import { describe, it, expect, beforeEach, vi } from 'vitest';
import { useAuthStore } from '@/stores/auth-store';

// Mock the api-client module
vi.mock('@/lib/api-client', () => {
  const mockApiClient = {
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  };
  return {
    apiClient: mockApiClient,
    registerAuthStore: vi.fn(),
    parseApiError: vi.fn(),
    getErrorMessage: vi.fn((code: string) => code),
  };
});

import { apiClient } from '@/lib/api-client';

const mockedPost = vi.mocked(apiClient.post);

/** Build a minimal JWT with the given payload. */
function makeJwt(payload: Record<string, unknown>): string {
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }));
  const body = btoa(JSON.stringify(payload));
  return `${header}.${body}.signature`;
}

describe('Integration: Auth Flow', () => {
  beforeEach(() => {
    useAuthStore.getState().clearTokens();
    vi.clearAllMocks();
  });

  it('login → stores tokens → sets player → logout clears state', async () => {
    const accessToken = makeJwt({
      sub: 'user-1',
      email: 'player@test.com',
      username: 'player1',
      is_admin: false,
    });
    const refreshToken = 'refresh-tok-abc';

    // Simulate login API response
    mockedPost.mockResolvedValueOnce({
      data: { access_token: accessToken, refresh_token: refreshToken },
    });

    // Step 1: Login
    const { data } = await apiClient.post('/auth/login', {
      email: 'player@test.com',
      password: 'Password1!',
    });

    useAuthStore.getState().setTokens(data.access_token, data.refresh_token);

    // Verify authenticated state
    let state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(true);
    expect(state.accessToken).toBe(accessToken);
    expect(state.refreshToken).toBe(refreshToken);
    expect(state.player?.username).toBe('player1');
    expect(state.player?.email).toBe('player@test.com');

    // Step 2: Simulate token refresh
    const newAccessToken = makeJwt({
      sub: 'user-1',
      email: 'player@test.com',
      username: 'player1',
      is_admin: false,
    });
    const newRefreshToken = 'refresh-tok-new';

    mockedPost.mockResolvedValueOnce({
      data: { access_token: newAccessToken, refresh_token: newRefreshToken },
    });

    const refreshResp = await apiClient.post('/auth/refresh', {
      refresh_token: refreshToken,
    });

    useAuthStore
      .getState()
      .setTokens(refreshResp.data.access_token, refreshResp.data.refresh_token);

    state = useAuthStore.getState();
    expect(state.accessToken).toBe(newAccessToken);
    expect(state.refreshToken).toBe(newRefreshToken);
    expect(state.isAuthenticated).toBe(true);

    // Step 3: Logout
    useAuthStore.getState().clearTokens();

    state = useAuthStore.getState();
    expect(state.isAuthenticated).toBe(false);
    expect(state.accessToken).toBeNull();
    expect(state.refreshToken).toBeNull();
    expect(state.player).toBeNull();
  });

  it('login with admin user sets isAdmin flag', async () => {
    const accessToken = makeJwt({
      sub: 'admin-1',
      email: 'admin@test.com',
      username: 'admin',
      is_admin: true,
    });

    mockedPost.mockResolvedValueOnce({
      data: { access_token: accessToken, refresh_token: 'ref' },
    });

    const { data } = await apiClient.post('/auth/login', {
      email: 'admin@test.com',
      password: 'Admin1!',
    });

    useAuthStore.getState().setTokens(data.access_token, data.refresh_token);

    const state = useAuthStore.getState();
    expect(state.isAdmin).toBe(true);
    expect(state.player?.isAdmin).toBe(true);
  });
});
