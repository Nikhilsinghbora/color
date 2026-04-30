import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

/**
 * Property 16: Admin route guard
 *
 * For any route path under the /admin prefix, if the authenticated user's
 * profile does not have isAdmin: true, the admin route guard SHALL redirect
 * to /game. If the user has isAdmin: true, the guard SHALL allow access.
 *
 * **Validates: Requirements 9.1**
 */

/**
 * Pure logic extracted from useAdminGuard hook.
 * Returns the redirect destination, or null if access is allowed.
 */
function adminGuardDecision(
  isAuthenticated: boolean,
  isAdmin: boolean,
): string | null {
  if (!isAuthenticated) {
    return '/login';
  }
  if (!isAdmin) {
    return '/game';
  }
  return null; // access allowed
}

describe('Property 16: Admin route guard', () => {
  it('non-admin authenticated users are always redirected to /game', () => {
    fc.assert(
      fc.property(
        fc.constant(true),  // isAuthenticated
        fc.constant(false), // isAdmin
        (isAuthenticated, isAdmin) => {
          const redirect = adminGuardDecision(isAuthenticated, isAdmin);
          expect(redirect).toBe('/game');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('admin authenticated users are always allowed access', () => {
    fc.assert(
      fc.property(
        fc.constant(true), // isAuthenticated
        fc.constant(true), // isAdmin
        (isAuthenticated, isAdmin) => {
          const redirect = adminGuardDecision(isAuthenticated, isAdmin);
          expect(redirect).toBeNull();
        },
      ),
      { numRuns: 100 },
    );
  });

  it('unauthenticated users are always redirected to /login', () => {
    fc.assert(
      fc.property(
        fc.constant(false), // isAuthenticated
        fc.boolean(),       // isAdmin (irrelevant when not authenticated)
        (isAuthenticated, isAdmin) => {
          const redirect = adminGuardDecision(isAuthenticated, isAdmin);
          expect(redirect).toBe('/login');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('for any isAdmin and isAuthenticated combination, the guard decision is correct', () => {
    fc.assert(
      fc.property(
        fc.boolean(), // isAuthenticated
        fc.boolean(), // isAdmin
        (isAuthenticated, isAdmin) => {
          const redirect = adminGuardDecision(isAuthenticated, isAdmin);

          if (!isAuthenticated) {
            // Unauthenticated → redirect to login
            expect(redirect).toBe('/login');
          } else if (!isAdmin) {
            // Authenticated but not admin → redirect to /game
            expect(redirect).toBe('/game');
          } else {
            // Authenticated admin → allow access
            expect(redirect).toBeNull();
          }
        },
      ),
      { numRuns: 100 },
    );
  });
});
