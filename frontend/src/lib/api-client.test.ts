import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import {
  apiClient,
  parseApiError,
  getErrorMessage,
  registerAuthStore,
  ERROR_MESSAGES,
} from './api-client';
import type { AxiosError } from 'axios';

// ---------------------------------------------------------------------------
// parseApiError
// ---------------------------------------------------------------------------

describe('parseApiError', () => {
  it('extracts error code and message from a well-formed API error', () => {
    const axiosError = new axios.AxiosError(
      'Request failed',
      '400',
      undefined,
      undefined,
      {
        data: {
          error: {
            code: 'INSUFFICIENT_BALANCE',
            message: 'Balance too low',
            details: { balance: '10.00' },
          },
        },
        status: 400,
        statusText: 'Bad Request',
        headers: {},
        config: {} as never,
      },
    );

    const result = parseApiError(axiosError);
    expect(result).toEqual({
      code: 'INSUFFICIENT_BALANCE',
      message: 'Balance too low',
      details: { balance: '10.00' },
    });
  });

  it('returns null for non-Axios errors', () => {
    expect(parseApiError(new Error('random'))).toBeNull();
    expect(parseApiError('string')).toBeNull();
    expect(parseApiError(null)).toBeNull();
  });

  it('returns null when response data has no error field', () => {
    const axiosError = new axios.AxiosError(
      'fail',
      '500',
      undefined,
      undefined,
      {
        data: { something: 'else' },
        status: 500,
        statusText: 'Internal Server Error',
        headers: {},
        config: {} as never,
      },
    );
    expect(parseApiError(axiosError)).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// getErrorMessage
// ---------------------------------------------------------------------------

describe('getErrorMessage', () => {
  it('returns mapped message for known error codes', () => {
    expect(getErrorMessage('INSUFFICIENT_BALANCE')).toBe('Insufficient balance');
    expect(getErrorMessage('BET_BELOW_MIN')).toBe('Bet amount is below the minimum');
    expect(getErrorMessage('BET_ABOVE_MAX')).toBe('Bet amount exceeds the maximum');
    expect(getErrorMessage('BETTING_CLOSED')).toBe('Betting is closed for this round');
    expect(getErrorMessage('RATE_LIMIT_EXCEEDED')).toBe(
      'Too many requests. Please try again later.',
    );
    expect(getErrorMessage('INVALID_CREDENTIALS')).toBe('Invalid email or password');
    expect(getErrorMessage('TOKEN_EXPIRED')).toBe(
      'Session expired. Please log in again.',
    );
    expect(getErrorMessage('ACCOUNT_LOCKED')).toBe('Account is locked');
    expect(getErrorMessage('ACCOUNT_SUSPENDED')).toBe('Account has been suspended');
    expect(getErrorMessage('SELF_EXCLUDED')).toBe('Account is self-excluded');
    expect(getErrorMessage('DEPOSIT_LIMIT_EXCEEDED')).toBe('Deposit limit exceeded');
    expect(getErrorMessage('INTERNAL_ERROR')).toBe(
      'Something went wrong. Please try again.',
    );
  });

  it('falls back to serverMessage for unknown codes', () => {
    expect(getErrorMessage('UNKNOWN_CODE', 'Server says oops')).toBe(
      'Server says oops',
    );
  });

  it('falls back to generic message when nothing matches', () => {
    expect(getErrorMessage('UNKNOWN_CODE')).toBe('An unexpected error occurred');
  });
});

// ---------------------------------------------------------------------------
// ERROR_MESSAGES export
// ---------------------------------------------------------------------------

describe('ERROR_MESSAGES', () => {
  it('contains all required error codes', () => {
    const requiredCodes = [
      'INSUFFICIENT_BALANCE',
      'BET_BELOW_MIN',
      'BET_ABOVE_MAX',
      'BETTING_CLOSED',
      'RATE_LIMIT_EXCEEDED',
      'INVALID_CREDENTIALS',
      'TOKEN_EXPIRED',
      'ACCOUNT_LOCKED',
      'ACCOUNT_SUSPENDED',
      'SELF_EXCLUDED',
      'DEPOSIT_LIMIT_EXCEEDED',
      'INTERNAL_ERROR',
    ];
    for (const code of requiredCodes) {
      expect(ERROR_MESSAGES).toHaveProperty(code);
      expect(typeof ERROR_MESSAGES[code]).toBe('string');
    }
  });
});

// ---------------------------------------------------------------------------
// Request interceptor — Bearer token attachment
// ---------------------------------------------------------------------------

describe('request interceptor', () => {
  beforeEach(() => {
    registerAuthStore(() => ({
      accessToken: 'test-access-token',
      refreshToken: 'test-refresh-token',
      setTokens: vi.fn(),
      clearTokens: vi.fn(),
    }));
  });

  it('attaches Authorization header when token is present', async () => {
    // We intercept the adapter to inspect the config
    const adapter = vi.fn().mockResolvedValue({ data: {}, status: 200, headers: {} });
    const result = await apiClient.get('/test', { adapter });
    const sentConfig = adapter.mock.calls[0][0];
    expect(sentConfig.headers.get('Authorization')).toBe('Bearer test-access-token');
  });

  it('does not attach header when token is null', async () => {
    registerAuthStore(() => ({
      accessToken: null,
      refreshToken: null,
      setTokens: vi.fn(),
      clearTokens: vi.fn(),
    }));
    const adapter = vi.fn().mockResolvedValue({ data: {}, status: 200, headers: {} });
    await apiClient.get('/test', { adapter });
    const sentConfig = adapter.mock.calls[0][0];
    expect(sentConfig.headers.get('Authorization')).toBeUndefined();
  });
});

// ---------------------------------------------------------------------------
// Response interceptor — 401 TOKEN_EXPIRED refresh flow
// ---------------------------------------------------------------------------

describe('response interceptor — token refresh', () => {
  const mockSetTokens = vi.fn();
  const mockClearTokens = vi.fn();

  beforeEach(() => {
    vi.restoreAllMocks();
    mockSetTokens.mockClear();
    mockClearTokens.mockClear();
    registerAuthStore(() => ({
      accessToken: 'old-access',
      refreshToken: 'old-refresh',
      setTokens: mockSetTokens,
      clearTokens: mockClearTokens,
    }));
  });

  it('refreshes token and retries on 401 TOKEN_EXPIRED', async () => {
    let callCount = 0;
    const adapter = vi.fn().mockImplementation((config) => {
      // Refresh call (plain axios, not apiClient) won't hit this adapter
      callCount++;
      if (callCount === 1) {
        // First call: simulate 401 TOKEN_EXPIRED
        return Promise.reject(
          new axios.AxiosError('Unauthorized', '401', config, {}, {
            data: { error: { code: 'TOKEN_EXPIRED', message: 'expired' } },
            status: 401,
            statusText: 'Unauthorized',
            headers: {},
            config,
          }),
        );
      }
      // Retry call: succeed
      return Promise.resolve({
        data: { success: true },
        status: 200,
        statusText: 'OK',
        headers: {},
        config,
      });
    });

    // Mock the refresh endpoint (plain axios.post)
    const postSpy = vi.spyOn(axios, 'post').mockResolvedValueOnce({
      data: { access_token: 'new-access', refresh_token: 'new-refresh' },
    });

    const response = await apiClient.get('/protected', { adapter });
    expect(response.data).toEqual({ success: true });
    expect(postSpy).toHaveBeenCalledTimes(1);
    expect(mockSetTokens).toHaveBeenCalledWith('new-access', 'new-refresh');
  });

  it('clears auth and redirects on refresh failure', async () => {
    const adapter = vi.fn().mockImplementation((config) => {
      return Promise.reject(
        new axios.AxiosError('Unauthorized', '401', config, {}, {
          data: { error: { code: 'TOKEN_EXPIRED', message: 'expired' } },
          status: 401,
          statusText: 'Unauthorized',
          headers: {},
          config,
        }),
      );
    });

    vi.spyOn(axios, 'post').mockRejectedValueOnce(new Error('Refresh failed'));

    // Mock window.location
    const originalLocation = window.location;
    Object.defineProperty(window, 'location', {
      writable: true,
      value: { href: '' },
    });

    await expect(apiClient.get('/protected', { adapter })).rejects.toThrow(
      'Refresh failed',
    );
    expect(mockClearTokens).toHaveBeenCalled();
    expect(window.location.href).toBe('/login');

    // Restore
    Object.defineProperty(window, 'location', {
      writable: true,
      value: originalLocation,
    });
  });

  it('does not intercept non-TOKEN_EXPIRED 401 errors', async () => {
    const adapter = vi.fn().mockImplementation((config) => {
      return Promise.reject(
        new axios.AxiosError('Unauthorized', '401', config, {}, {
          data: { error: { code: 'INVALID_CREDENTIALS', message: 'bad creds' } },
          status: 401,
          statusText: 'Unauthorized',
          headers: {},
          config,
        }),
      );
    });

    const postSpy = vi.spyOn(axios, 'post');

    await expect(apiClient.get('/login', { adapter })).rejects.toThrow();
    // Should NOT attempt refresh
    expect(postSpy).not.toHaveBeenCalled();
  });
});
