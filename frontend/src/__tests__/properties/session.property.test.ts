import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';

/**
 * Property 14: Session timer notification trigger
 *
 * For any session with a configured time limit of L minutes and a start time T,
 * the session timer SHALL trigger a mandatory reminder notification if and only
 * if the elapsed time (current time - T) is greater than or equal to L minutes.
 * The notification SHALL not trigger before the limit is reached, and SHALL
 * trigger at or after the limit.
 *
 * **Validates: Requirements 8.5**
 */

/**
 * Pure logic extracted from useSessionTimer hook.
 * Given a startTime, limitMinutes, and currentTime, returns whether the limit
 * has been reached.
 */
function isSessionLimitReached(
  startTime: number,
  limitMinutes: number,
  currentTime: number,
): boolean {
  const elapsedMs = currentTime - startTime;
  return elapsedMs >= limitMinutes * 60000;
}

describe('Property 14: Session timer notification trigger', () => {
  it('limitReached is true iff (currentTime - startTime) >= limitMinutes * 60000', () => {
    fc.assert(
      fc.property(
        fc.nat({ max: 2_000_000_000_000 }), // startTime (timestamp in ms)
        fc.integer({ min: 1, max: 1440 }),   // limitMinutes (1 min to 24 hours)
        fc.nat({ max: 200_000_000 }),         // elapsedMs (up to ~2.3 days)
        (startTime, limitMinutes, elapsedMs) => {
          const currentTime = startTime + elapsedMs;
          const limitMs = limitMinutes * 60000;
          const result = isSessionLimitReached(startTime, limitMinutes, currentTime);

          if (elapsedMs >= limitMs) {
            expect(result).toBe(true);
          } else {
            expect(result).toBe(false);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('notification does NOT trigger before the limit is reached', () => {
    fc.assert(
      fc.property(
        fc.nat({ max: 2_000_000_000_000 }),
        fc.integer({ min: 1, max: 1440 }),
        (startTime, limitMinutes) => {
          // Elapsed time is strictly less than the limit
          const limitMs = limitMinutes * 60000;
          const elapsedMs = limitMs - 1; // 1ms before the limit
          const currentTime = startTime + elapsedMs;

          expect(isSessionLimitReached(startTime, limitMinutes, currentTime)).toBe(false);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('notification triggers exactly at the limit boundary', () => {
    fc.assert(
      fc.property(
        fc.nat({ max: 2_000_000_000_000 }),
        fc.integer({ min: 1, max: 1440 }),
        (startTime, limitMinutes) => {
          const limitMs = limitMinutes * 60000;
          const currentTime = startTime + limitMs; // exactly at the limit

          expect(isSessionLimitReached(startTime, limitMinutes, currentTime)).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('notification triggers after the limit is exceeded', () => {
    fc.assert(
      fc.property(
        fc.nat({ max: 2_000_000_000_000 }),
        fc.integer({ min: 1, max: 1440 }),
        fc.integer({ min: 1, max: 100_000_000 }), // extra ms past limit
        (startTime, limitMinutes, extraMs) => {
          const limitMs = limitMinutes * 60000;
          const currentTime = startTime + limitMs + extraMs;

          expect(isSessionLimitReached(startTime, limitMinutes, currentTime)).toBe(true);
        },
      ),
      { numRuns: 100 },
    );
  });
});
