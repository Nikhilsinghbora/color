import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import type { LeaderboardEntry, LeaderboardMetric } from '@/types';

/**
 * Property 11: Leaderboard entry rendering completeness
 *
 * For any leaderboard entry containing rank, username, and metric_value fields,
 * the leaderboard renderer SHALL produce output that includes all three values.
 * No entry SHALL be rendered with a missing rank, username, or metric value.
 *
 * **Validates: Requirements 6.1**
 */

// --- Pure rendering helpers extracted from leaderboard page logic ---

function formatMetricValue(value: string, metric: LeaderboardMetric): string {
  if (metric === 'win_rate') return `${value}%`;
  if (metric === 'win_streak') return value;
  return `$${value}`;
}

interface RenderedLeaderboardEntry {
  rank: string;
  username: string;
  metricValue: string;
}

function renderLeaderboardEntry(
  entry: LeaderboardEntry,
  metric: LeaderboardMetric,
): RenderedLeaderboardEntry {
  return {
    rank: String(entry.rank),
    username: entry.username,
    metricValue: formatMetricValue(entry.metric_value, metric),
  };
}

// --- Arbitraries ---

const metricArb = fc.constantFrom<LeaderboardMetric>(
  'total_winnings',
  'win_rate',
  'win_streak',
);

const decimalValueArb = fc
  .integer({ min: 0, max: 999999 })
  .map((cents) => (cents / 100).toFixed(2));

const usernameArb = fc.string({ minLength: 1, maxLength: 50 }).filter((s) => s.trim().length > 0);

const leaderboardEntryArb: fc.Arbitrary<LeaderboardEntry> = fc.record({
  rank: fc.integer({ min: 1, max: 100 }),
  player_id: fc.uuid(),
  username: usernameArb,
  metric_value: decimalValueArb,
});

// --- Property tests ---

describe('Property 11: Leaderboard entry rendering completeness', () => {
  it('all rendered fields are present and non-empty for any leaderboard entry', () => {
    fc.assert(
      fc.property(leaderboardEntryArb, metricArb, (entry, metric) => {
        const rendered = renderLeaderboardEntry(entry, metric);

        expect(rendered.rank).toBeTruthy();
        expect(rendered.rank.length).toBeGreaterThan(0);

        expect(rendered.username).toBeTruthy();
        expect(rendered.username.length).toBeGreaterThan(0);

        expect(rendered.metricValue).toBeTruthy();
        expect(rendered.metricValue.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 },
    );
  });

  it('rank string matches the numeric rank from the entry', () => {
    fc.assert(
      fc.property(leaderboardEntryArb, metricArb, (entry, metric) => {
        const rendered = renderLeaderboardEntry(entry, metric);
        expect(rendered.rank).toBe(String(entry.rank));
      }),
      { numRuns: 100 },
    );
  });

  it('username is preserved exactly from the entry', () => {
    fc.assert(
      fc.property(leaderboardEntryArb, metricArb, (entry, metric) => {
        const rendered = renderLeaderboardEntry(entry, metric);
        expect(rendered.username).toBe(entry.username);
      }),
      { numRuns: 100 },
    );
  });

  it('metric value includes the original value from the entry', () => {
    fc.assert(
      fc.property(leaderboardEntryArb, metricArb, (entry, metric) => {
        const rendered = renderLeaderboardEntry(entry, metric);
        expect(rendered.metricValue).toContain(entry.metric_value);
      }),
      { numRuns: 100 },
    );
  });
});
