'use client';

import { useEffect, useState, useRef, useCallback } from 'react';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import { useAuthStore } from '@/stores/auth-store';
import type {
  LeaderboardMetric,
  LeaderboardPeriod,
  LeaderboardEntry,
  LeaderboardResponse,
} from '@/types';

const METRICS: { value: LeaderboardMetric; label: string }[] = [
  { value: 'total_winnings', label: 'Total Winnings' },
  { value: 'win_rate', label: 'Win Rate' },
  { value: 'win_streak', label: 'Win Streak' },
];

const PERIODS: { value: LeaderboardPeriod; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
  { value: 'all_time', label: 'All Time' },
];

export default function LeaderboardPage() {
  useAuthGuard();

  const playerId = useAuthStore((s) => s.player?.id ?? null);

  const [metric, setMetric] = useState<LeaderboardMetric>('total_winnings');
  const [period, setPeriod] = useState<LeaderboardPeriod>('all_time');
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [playerRank, setPlayerRank] = useState<LeaderboardEntry | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  const playerRowRef = useRef<HTMLTableRowElement>(null);

  const fetchLeaderboard = useCallback(async () => {
    setIsLoading(true);
    setError('');
    try {
      const { data } = await apiClient.get<LeaderboardResponse>(
        `/leaderboard/${metric}`,
        { params: { period } },
      );
      setEntries(data.entries);
      setPlayerRank(data.player_rank);
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        setError(getErrorMessage(apiErr.code, apiErr.message));
      } else {
        setError('Failed to load leaderboard. Please try again.');
      }
    } finally {
      setIsLoading(false);
    }
  }, [metric, period]);

  useEffect(() => {
    fetchLeaderboard();
  }, [fetchLeaderboard]);

  useEffect(() => {
    if (playerRowRef.current && typeof playerRowRef.current.scrollIntoView === 'function') {
      playerRowRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [entries, playerId]);

  function formatMetricValue(value: string, m: LeaderboardMetric): string {
    if (m === 'win_rate') return `${value}%`;
    if (m === 'win_streak') return value;
    return `$${value}`;
  }

  return (
    <main className="min-h-screen bg-background px-4 py-6">
      <section aria-label="Leaderboard" className="mx-auto max-w-3xl">
        <h1 className="text-2xl font-bold text-foreground text-center mb-6">Leaderboard</h1>

        {/* Filter controls */}
        <div className="mb-6 flex flex-wrap items-center justify-center gap-4" role="group" aria-label="Leaderboard filters">
          <div>
            <label htmlFor="metric-select" className="block text-sm font-medium text-muted-foreground mb-1">
              Metric
            </label>
            <select
              id="metric-select"
              value={metric}
              onChange={(e) => setMetric(e.target.value as LeaderboardMetric)}
              className="rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Select leaderboard metric"
            >
              {METRICS.map((m) => (
                <option key={m.value} value={m.value}>{m.label}</option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="period-select" className="block text-sm font-medium text-muted-foreground mb-1">
              Period
            </label>
            <select
              id="period-select"
              value={period}
              onChange={(e) => setPeriod(e.target.value as LeaderboardPeriod)}
              className="rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              aria-label="Select leaderboard period"
            >
              {PERIODS.map((p) => (
                <option key={p.value} value={p.value}>{p.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Error */}
        {error && (
          <div role="alert" className="mb-4 rounded-md bg-red-100 px-4 py-2 text-center text-sm text-red-800 dark:bg-red-900 dark:text-red-200">
            {error}
          </div>
        )}

        {/* Loading */}
        {isLoading && (
          <div className="flex justify-center py-8" aria-label="Loading leaderboard">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" role="status">
              <span className="sr-only">Loading…</span>
            </div>
          </div>
        )}

        {/* Leaderboard table */}
        {!isLoading && entries.length > 0 && (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-left" aria-label="Leaderboard rankings">
              <thead className="bg-muted">
                <tr>
                  <th scope="col" className="px-4 py-3 text-sm font-semibold text-muted-foreground">Rank</th>
                  <th scope="col" className="px-4 py-3 text-sm font-semibold text-muted-foreground">Player</th>
                  <th scope="col" className="px-4 py-3 text-sm font-semibold text-muted-foreground text-right">
                    {METRICS.find((m) => m.value === metric)?.label ?? 'Value'}
                  </th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => {
                  const isCurrentPlayer = playerId !== null && entry.player_id === playerId;
                  return (
                    <tr
                      key={`${entry.rank}-${entry.player_id}`}
                      ref={isCurrentPlayer ? playerRowRef : undefined}
                      className={`border-t border-border ${
                        isCurrentPlayer
                          ? 'bg-primary/10 font-semibold'
                          : 'hover:bg-muted/50'
                      }`}
                      aria-current={isCurrentPlayer ? 'true' : undefined}
                    >
                      <td className="px-4 py-3 text-sm text-foreground" data-testid="entry-rank">{entry.rank}</td>
                      <td className="px-4 py-3 text-sm text-foreground" data-testid="entry-username">{entry.username}</td>
                      <td className="px-4 py-3 text-sm text-foreground text-right" data-testid="entry-metric">
                        {formatMetricValue(entry.metric_value, metric)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Empty state */}
        {!isLoading && entries.length === 0 && !error && (
          <p className="text-center text-sm text-muted-foreground py-8">No leaderboard data available.</p>
        )}

        {/* Player rank summary */}
        {playerRank && (
          <div className="mt-4 rounded-lg border border-border bg-card p-4 text-center">
            <p className="text-sm text-muted-foreground">Your Rank</p>
            <p className="text-lg font-bold text-foreground">
              #{playerRank.rank} — {formatMetricValue(playerRank.metric_value, metric)}
            </p>
          </div>
        )}
      </section>
    </main>
  );
}
