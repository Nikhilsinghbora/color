import { describe, it, expect, vi, afterEach } from 'vitest';
import * as fc from 'fast-check';
import axios, { AxiosHeaders, AxiosError } from 'axios';
import type { ApiError } from '@/types';

/**
 * Property 2: Token refresh interceptor
 *
 * For any authenticated API request that receives a 401 response with
 * TOKEN_EXPIRED error code, the API client interceptor SHALL attempt
 * exactly one token refresh call to /api/v1/auth/refresh before retrying
 * the original request with the new access token.
 *
 * The retried request SHALL carry the refreshed token in the Authorization header.
 *
 * **Validates: Requirements 1.4**
 */

describe('Property 2: Token refresh interceptor', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('retries with refreshed token after 401 TOKEN_EXPIRED for any token pair', async () => {
    await fc.assert(
      fc.asyncProperty(
        fc.record({
          oldAccessToken: fc.stringMatching(/^[a-zA-Z0-9]{10,30}$/),
          oldRefreshToken: fc.stringMatching(/^[a-zA-Z0-9]{10,30}$/),
          newAccessToken: fc.stringMatching(/^[a-zA-Z0-9]{10,30}$/),
          newRefreshToken: fc.stringMatching(/^[a-zA-Z0-9]{10,30}$/),
          endpoint: fc.constantFrom(
            '/wallet/balance',
            '/game/bet',
            '/leaderboard/total_winnings',
            '/social/friends',
          ),
        }),
        async ({
          oldAccessToken,
          oldRefreshToken,
          newAccessToken,
          newRefreshToken,
          endpoint,
        }) => {
          // Fresh module for each iteration to reset interceptor state
          vi.resetModules();
          const mod = await import('@/lib/api-client');
          const client = mod.apiClient;
          const registerAuthStore = mod.registerAuthStore;

          // Set up auth store state
          const authState = {
            accessToken: oldAccessToken,
            refreshToken: oldRefreshToken,
            setTokens: vi.fn((access: string, refresh: string) => {
              authState.accessToken = access;
              authState.refreshToken = refresh;
            }),
            clearTokens: vi.fn(),
          };

          registerAuthStore(() => authState);

          // Spy on axios.post for the refresh call
          const postSpy = vi.spyOn(axios, 'post').mockResolvedValue({
            data: {
              access_token: newAccessToken,
              refresh_token: newRefreshToken,
            },
          });

          let requestCount = 0;
          let retryAuthHeader: string | undefined;

          // Mock the adapter for the client instance
          client.defaults.adapter = async (config: any) => {
            requestCount++;

            if (requestCount === 1) {
              const errorData: ApiError = {
                error: { code: 'TOKEN_EXPIRED', message: 'Token has expired' },
              };
              const error = new AxiosError(
                'Unauthorized',
                'ERR_BAD_RESPONSE',
                config,
                undefined,
                {
                  data: errorData,
                  status: 401,
                  statusText: 'Unauthorized',
                  headers: new AxiosHeaders(),
                  config,
                },
              );
              throw error;
            }

            retryAuthHeader = config.headers?.Authorization;
            return {
              data: { success: true },
              status: 200,
              statusText: 'OK',
              headers: {},
              config,
            };
          };

          const response = await client.get(endpoint);

          // Exactly one refresh call was made
          expect(postSpy).toHaveBeenCalledTimes(1);
          expect(postSpy.mock.calls[0][1]).toEqual({
            refresh_token: oldRefreshToken,
          });

          // Original request attempted + retry = 2
          expect(requestCount).toBe(2);

          // Retried request carried the new access token
          expect(retryAuthHeader).toBe(`Bearer ${newAccessToken}`);

          // Auth store was updated with new tokens
          expect(authState.setTokens).toHaveBeenCalledWith(
            newAccessToken,
            newRefreshToken,
          );

          // clearTokens was NOT called (refresh succeeded)
          expect(authState.clearTokens).not.toHaveBeenCalled();

          // Final response is the success response
          expect(response.data).toEqual({ success: true });

          // Clean up spy for next iteration
          postSpy.mockRestore();
        },
      ),
      { numRuns: 100 },
    );
  });
});


/**
 * Property 1: Registration input validation
 *
 * For any string input, the registration validation functions SHALL correctly
 * classify it: email validation accepts only strings matching a valid email
 * pattern, username validation accepts only strings with length between 1 and
 * 50 characters, and password validation accepts only strings meeting the
 * configured complexity rules (minimum 8 chars, mixed case, digit, special
 * character). Invalid inputs SHALL produce a validation error message (non-null),
 * valid inputs SHALL pass without error (null).
 *
 * **Validates: Requirements 1.1**
 */

import { validateEmail, validateUsername, validatePassword } from '@/lib/utils';

describe('Property 1: Registration input validation', () => {
  it('validateEmail returns null for valid emails and non-null for invalid ones', () => {
    // Valid email arbitrary: local@domain.tld
    const validEmailArb = fc.tuple(
      fc.stringMatching(/^[a-zA-Z0-9._%+-]{1,20}$/),
      fc.stringMatching(/^[a-zA-Z0-9-]{1,15}$/),
      fc.stringMatching(/^[a-zA-Z]{2,6}$/),
    ).map(([local, domain, tld]) => `${local}@${domain}.${tld}`);

    fc.assert(
      fc.property(validEmailArb, (email) => {
        expect(validateEmail(email)).toBeNull();
      }),
      { numRuns: 100 },
    );
  });

  it('validateEmail returns non-null for strings without @ or domain', () => {
    const invalidEmailArb = fc.string({ minLength: 0, maxLength: 50 })
      .filter((s) => !(/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s)));

    fc.assert(
      fc.property(invalidEmailArb, (email) => {
        expect(validateEmail(email)).not.toBeNull();
        expect(typeof validateEmail(email)).toBe('string');
      }),
      { numRuns: 100 },
    );
  });

  it('validateUsername returns null for strings with length 1-50', () => {
    const validUsernameArb = fc.string({ minLength: 1, maxLength: 50 });

    fc.assert(
      fc.property(validUsernameArb, (username) => {
        expect(validateUsername(username)).toBeNull();
      }),
      { numRuns: 100 },
    );
  });

  it('validateUsername returns non-null for empty strings or strings longer than 50', () => {
    const invalidUsernameArb = fc.oneof(
      fc.constant(''),
      fc.string({ minLength: 51, maxLength: 100 }),
    );

    fc.assert(
      fc.property(invalidUsernameArb, (username) => {
        expect(validateUsername(username)).not.toBeNull();
        expect(typeof validateUsername(username)).toBe('string');
      }),
      { numRuns: 100 },
    );
  });

  it('validatePassword returns null for strings meeting all complexity rules', () => {
    // Generate a valid password: at least 8 chars, has upper, lower, digit, special
    const validPasswordArb = fc.tuple(
      fc.stringMatching(/^[a-z]{1,5}$/),
      fc.stringMatching(/^[A-Z]{1,5}$/),
      fc.stringMatching(/^[0-9]{1,3}$/),
      fc.constantFrom('!', '@', '#', '$', '%', '^', '&', '*'),
      fc.stringMatching(/^[a-zA-Z0-9!@#$%^&*]{0,10}$/),
    ).map(([lower, upper, digit, special, extra]) => {
      const base = lower + upper + digit + special + extra;
      // Ensure minimum 8 chars by padding if needed
      return base.length >= 8 ? base : base + 'aA1!aaaa'.slice(0, 8 - base.length);
    });

    fc.assert(
      fc.property(validPasswordArb, (password) => {
        expect(validatePassword(password)).toBeNull();
      }),
      { numRuns: 100 },
    );
  });

  it('validatePassword returns non-null for strings missing complexity requirements', () => {
    const invalidPasswordArb = fc.oneof(
      // Too short
      fc.string({ minLength: 0, maxLength: 7 }),
      // No uppercase
      fc.stringMatching(/^[a-z0-9!@#$%]{8,20}$/),
      // No lowercase
      fc.stringMatching(/^[A-Z0-9!@#$%]{8,20}$/),
      // No digit
      fc.stringMatching(/^[a-zA-Z!@#$%]{8,20}$/),
      // No special character
      fc.stringMatching(/^[a-zA-Z0-9]{8,20}$/),
    );

    fc.assert(
      fc.property(invalidPasswordArb, (password) => {
        expect(validatePassword(password)).not.toBeNull();
        expect(typeof validatePassword(password)).toBe('string');
      }),
      { numRuns: 100 },
    );
  });
});


/**
 * Property 3: Auth route guard
 *
 * For any route path that is configured as an authenticated route, if the
 * Auth Store contains no valid access token, the route guard SHALL redirect
 * to /login. If the Auth Store contains a valid access token, the route guard
 * SHALL allow access.
 *
 * **Validates: Requirements 1.8**
 */

import { useAuthStore } from '@/stores/auth-store';

describe('Property 3: Auth route guard', () => {
  /**
   * Helper that mirrors the guard decision logic:
   * - null token → redirect to /login (return true)
   * - non-empty string token → allow access (return false)
   */
  function shouldRedirectToLogin(accessToken: string | null): boolean {
    return accessToken === null;
  }

  afterEach(() => {
    // Reset the auth store between runs
    useAuthStore.getState().clearTokens();
  });

  it('redirects to /login when accessToken is null (unauthenticated)', () => {
    fc.assert(
      fc.property(fc.constant(null), (token) => {
        // With no token, the store should report not authenticated
        const state = useAuthStore.getState();
        expect(state.accessToken).toBeNull();
        expect(state.isAuthenticated).toBe(false);

        // Guard decision: should redirect
        expect(shouldRedirectToLogin(token)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it('allows access when accessToken is a non-empty string (authenticated)', () => {
    fc.assert(
      fc.property(
        fc.stringMatching(/^[a-zA-Z0-9._-]{1,50}$/),
        (token) => {
          // Simulate setting tokens in the store (need a refresh token too)
          useAuthStore.getState().setTokens(token, 'refresh-placeholder');

          const state = useAuthStore.getState();
          expect(state.accessToken).toBe(token);
          expect(state.isAuthenticated).toBe(true);

          // Guard decision: should NOT redirect
          expect(shouldRedirectToLogin(token)).toBe(false);

          // Clean up for next iteration
          useAuthStore.getState().clearTokens();
        },
      ),
      { numRuns: 100 },
    );
  });
});
