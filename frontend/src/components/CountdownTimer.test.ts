// Feature: casino-ui-redesign, Property 2: Countdown timer progress ring calculation
//
// For any totalSeconds > 0 and 0 <= remainingSeconds <= totalSeconds:
//   dashoffset = circumference * (1 - remainingSeconds / totalSeconds)
// At 0 remaining → full circumference (fully depleted).
// At totalSeconds remaining → 0 (full ring).
//
// Validates: Requirements 3.1, 3.3

import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { calculateDashoffset } from './CountdownTimer';

const RADIUS = 44;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

describe('Property 2: Countdown timer progress ring calculation', () => {
  it('dashoffset equals circumference * (1 - remaining / total) for any valid inputs', () => {
    fc.assert(
      fc.property(
        // totalSeconds: positive integer 1..3600
        fc.integer({ min: 1, max: 3600 }),
        // remainingSeconds: 0..totalSeconds (generated relative to total)
        fc.integer({ min: 0, max: 3600 }),
        (totalSeconds, rawRemaining) => {
          const remainingSeconds = Math.min(rawRemaining, totalSeconds);
          const result = calculateDashoffset(totalSeconds, remainingSeconds, CIRCUMFERENCE);
          const expected = CIRCUMFERENCE * (1 - remainingSeconds / totalSeconds);
          expect(result).toBeCloseTo(expected, 10);
        },
      ),
      { numRuns: 200 },
    );
  });

  it('dashoffset is full circumference when remainingSeconds is 0 (fully depleted)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 3600 }),
        (totalSeconds) => {
          const result = calculateDashoffset(totalSeconds, 0, CIRCUMFERENCE);
          expect(result).toBeCloseTo(CIRCUMFERENCE, 10);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('dashoffset is 0 when remainingSeconds equals totalSeconds (full ring)', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 3600 }),
        (totalSeconds) => {
          const result = calculateDashoffset(totalSeconds, totalSeconds, CIRCUMFERENCE);
          expect(result).toBeCloseTo(0, 10);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('dashoffset is between 0 and circumference for any valid remaining', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 1, max: 3600 }),
        fc.integer({ min: 0, max: 3600 }),
        (totalSeconds, rawRemaining) => {
          const remainingSeconds = Math.min(rawRemaining, totalSeconds);
          const result = calculateDashoffset(totalSeconds, remainingSeconds, CIRCUMFERENCE);
          expect(result).toBeGreaterThanOrEqual(-0.0001);
          expect(result).toBeLessThanOrEqual(CIRCUMFERENCE + 0.0001);
        },
      ),
      { numRuns: 200 },
    );
  });

  it('dashoffset decreases monotonically as remainingSeconds increases', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 2, max: 3600 }),
        fc.integer({ min: 0, max: 3599 }),
        (totalSeconds, rawR1) => {
          const r1 = Math.min(rawR1, totalSeconds - 1);
          const r2 = r1 + 1; // r2 > r1, both <= totalSeconds
          const d1 = calculateDashoffset(totalSeconds, r1, CIRCUMFERENCE);
          const d2 = calculateDashoffset(totalSeconds, r2, CIRCUMFERENCE);
          // More remaining → less depleted → smaller dashoffset
          expect(d2).toBeLessThanOrEqual(d1 + 0.0001);
        },
      ),
      { numRuns: 200 },
    );
  });
});
