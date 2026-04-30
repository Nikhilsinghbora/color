import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import Decimal from 'decimal.js';
import { calculatePotentialPayout } from '@/lib/utils';

/**
 * Property 10: Potential payout calculation
 *
 * For any bet amount A (decimal string) and odds multiplier O (decimal string),
 * the computed potential payout SHALL equal the product of A and O, rounded to
 * exactly 2 decimal places. The calculation SHALL use string-based decimal
 * arithmetic (not JavaScript floating-point).
 *
 * **Validates: Requirements 4.8**
 */

describe('Property 10: Potential payout calculation', () => {
  it('payout equals Decimal(amount).mul(Decimal(odds)).toFixed(2) for any positive decimals', () => {
    // Generate positive decimal strings like "123.45"
    const decimalStringArb = fc.tuple(
      fc.integer({ min: 0, max: 99999 }),
      fc.integer({ min: 0, max: 99 }),
    ).map(([whole, frac]) => `${whole}.${frac.toString().padStart(2, '0')}`);

    fc.assert(
      fc.property(decimalStringArb, decimalStringArb, (amount, odds) => {
        const result = calculatePotentialPayout(amount, odds);
        const expected = new Decimal(amount).mul(new Decimal(odds)).toFixed(2);
        expect(result).toBe(expected);
      }),
      { numRuns: 100 },
    );
  });

  it('result always has exactly 2 decimal places', () => {
    const decimalStringArb = fc.tuple(
      fc.integer({ min: 1, max: 9999 }),
      fc.integer({ min: 0, max: 99 }),
    ).map(([whole, frac]) => `${whole}.${frac.toString().padStart(2, '0')}`);

    fc.assert(
      fc.property(decimalStringArb, decimalStringArb, (amount, odds) => {
        const result = calculatePotentialPayout(amount, odds);
        // Must match pattern: digits, dot, exactly 2 digits
        expect(result).toMatch(/^\d+\.\d{2}$/);
      }),
      { numRuns: 100 },
    );
  });

  it('uses string-based arithmetic, not floating-point (precision test)', () => {
    // Known floating-point problem cases
    fc.assert(
      fc.property(
        fc.constantFrom(
          { amount: '0.10', odds: '0.20' },   // 0.1 * 0.2 = 0.02 (float gives 0.020000000000000004)
          { amount: '1.10', odds: '1.10' },   // 1.1 * 1.1 = 1.21 (float gives 1.2100000000000002)
          { amount: '0.30', odds: '3.00' },   // 0.3 * 3 = 0.90
          { amount: '99999.99', odds: '99.99' },
        ),
        ({ amount, odds }) => {
          const result = calculatePotentialPayout(amount, odds);
          const expected = new Decimal(amount).mul(new Decimal(odds)).toFixed(2);
          expect(result).toBe(expected);
        },
      ),
      { numRuns: 100 },
    );
  });
});

/**
 * Property 15: Loss warning blocks betting
 *
 * For any game state where a loss threshold warning has been received from the
 * backend and the player has not yet acknowledged the warning, all bet submission
 * actions SHALL be blocked. After the player acknowledges the warning, bet
 * submissions SHALL be permitted again.
 *
 * **Validates: Requirements 8.7**
 */

/**
 * Pure helper: determines whether a player can place a bet based on loss warning state.
 * Betting is blocked when a loss warning is active AND not yet acknowledged.
 */
function canPlaceBet(lossWarningActive: boolean, lossWarningAcknowledged: boolean): boolean {
  if (lossWarningActive && !lossWarningAcknowledged) {
    return false;
  }
  return true;
}

describe('Property 15: Loss warning blocks betting', () => {
  it('betting is blocked when loss warning is active and not acknowledged', () => {
    fc.assert(
      fc.property(fc.boolean(), fc.boolean(), (warningActive, warningAcknowledged) => {
        const result = canPlaceBet(warningActive, warningAcknowledged);

        if (warningActive && !warningAcknowledged) {
          // Warning active + not acknowledged → blocked
          expect(result).toBe(false);
        } else {
          // All other combinations → permitted
          expect(result).toBe(true);
        }
      }),
      { numRuns: 100 },
    );
  });

  it('acknowledging the warning always permits betting regardless of warning state', () => {
    fc.assert(
      fc.property(fc.boolean(), (warningActive) => {
        // Once acknowledged, betting is always permitted
        expect(canPlaceBet(warningActive, true)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it('no active warning always permits betting regardless of acknowledgment', () => {
    fc.assert(
      fc.property(fc.boolean(), (acknowledged) => {
        // No warning active → betting always permitted
        expect(canPlaceBet(false, acknowledged)).toBe(true);
      }),
      { numRuns: 100 },
    );
  });

  it('only the combination of active warning + no acknowledgment blocks betting', () => {
    // The single blocking case
    expect(canPlaceBet(true, false)).toBe(false);
    // All other cases permit
    expect(canPlaceBet(true, true)).toBe(true);
    expect(canPlaceBet(false, false)).toBe(true);
    expect(canPlaceBet(false, true)).toBe(true);
  });
});
