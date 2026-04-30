import { describe, it, expect } from 'vitest';
import fc from 'fast-check';
import { NUMBER_COLOR_MAP } from './number-color-map';

describe('NUMBER_COLOR_MAP', () => {
  it('contains entries for all numbers 0–9', () => {
    for (let i = 0; i <= 9; i++) {
      expect(NUMBER_COLOR_MAP[i]).toBeDefined();
    }
  });

  it('maps 0 to green with violet secondary', () => {
    expect(NUMBER_COLOR_MAP[0]).toEqual({ primary: 'green', secondary: 'violet' });
  });

  it('maps 5 to green with violet secondary', () => {
    expect(NUMBER_COLOR_MAP[5]).toEqual({ primary: 'green', secondary: 'violet' });
  });

  it('maps odd non-dual numbers (1, 3, 7, 9) to green only', () => {
    for (const n of [1, 3, 7, 9]) {
      expect(NUMBER_COLOR_MAP[n]).toEqual({ primary: 'green' });
    }
  });

  it('maps even non-dual numbers (2, 4, 6, 8) to red only', () => {
    for (const n of [2, 4, 6, 8]) {
      expect(NUMBER_COLOR_MAP[n]).toEqual({ primary: 'red' });
    }
  });

  it('every entry has primary as green or red', () => {
    for (let i = 0; i <= 9; i++) {
      expect(['green', 'red']).toContain(NUMBER_COLOR_MAP[i].primary);
    }
  });

  it('only 0 and 5 have a secondary color', () => {
    for (let i = 0; i <= 9; i++) {
      if (i === 0 || i === 5) {
        expect(NUMBER_COLOR_MAP[i].secondary).toBe('violet');
      } else {
        expect(NUMBER_COLOR_MAP[i].secondary).toBeUndefined();
      }
    }
  });
});

// Feature: casino-ui-redesign, Property 1: Number-to-Color mapping consistency (frontend portion)
describe('Property: Number-to-Color mapping consistency (frontend)', () => {
  // **Validates: Requirements 2.2, 5.2, 8.3, 8.5**
  it('for all numbers 0–9, primary is "green" or "red" and optional secondary is "violet"', () => {
    fc.assert(
      fc.property(
        fc.integer({ min: 0, max: 9 }),
        (n) => {
          const entry = NUMBER_COLOR_MAP[n];

          // Entry must exist
          expect(entry).toBeDefined();

          // Primary must be "green" or "red"
          expect(['green', 'red']).toContain(entry.primary);

          // If secondary exists, it must be "violet"
          if (entry.secondary !== undefined) {
            expect(entry.secondary).toBe('violet');
          }
        }
      ),
      { numRuns: 100 }
    );
  });
});
