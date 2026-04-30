'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import type { PlayerPublicProfile } from '@/types';

export default function PlayerProfilePage() {
  useAuthGuard();

  const params = useParams();
  const playerId = params.id as string;

  const [profile, setProfile] = useState<PlayerPublicProfile | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    async function fetchProfile() {
      setIsLoading(true);
      setError('');
      try {
        const { data } = await apiClient.get<PlayerPublicProfile>(
          `/social/profile/${playerId}`,
        );
        setProfile(data);
      } catch (err: unknown) {
        const apiErr = parseApiError(err);
        if (apiErr) {
          setError(getErrorMessage(apiErr.code, apiErr.message));
        } else {
          setError('Failed to load profile. Please try again.');
        }
      } finally {
        setIsLoading(false);
      }
    }

    if (playerId) {
      fetchProfile();
    }
  }, [playerId]);

  return (
    <main className="min-h-screen bg-background px-4 py-6">
      <section aria-label="Player profile" className="mx-auto max-w-lg">
        <h1 className="text-2xl font-bold text-foreground text-center mb-6">Player Profile</h1>

        {isLoading && (
          <div className="flex justify-center py-8" aria-label="Loading profile">
            <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" role="status">
              <span className="sr-only">Loading…</span>
            </div>
          </div>
        )}

        {error && (
          <div role="alert" className="mb-4 rounded-md bg-red-100 px-4 py-2 text-center text-sm text-red-800 dark:bg-red-900 dark:text-red-200">
            {error}
          </div>
        )}

        {!isLoading && profile && (
          <div className="rounded-lg border border-border bg-card p-6">
            <h2 className="text-xl font-bold text-card-foreground text-center mb-6">
              {profile.username}
            </h2>

            <dl className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div className="rounded-lg bg-muted p-4 text-center">
                <dt className="text-sm text-muted-foreground">Total Games</dt>
                <dd className="mt-1 text-2xl font-bold text-foreground" data-testid="total-games">
                  {profile.total_games}
                </dd>
              </div>

              <div className="rounded-lg bg-muted p-4 text-center">
                <dt className="text-sm text-muted-foreground">Win Rate</dt>
                <dd className="mt-1 text-2xl font-bold text-foreground" data-testid="win-rate">
                  {profile.win_rate}%
                </dd>
              </div>

              <div className="rounded-lg bg-muted p-4 text-center">
                <dt className="text-sm text-muted-foreground">Leaderboard Rank</dt>
                <dd className="mt-1 text-2xl font-bold text-foreground" data-testid="leaderboard-rank">
                  {profile.leaderboard_rank !== null ? `#${profile.leaderboard_rank}` : 'Unranked'}
                </dd>
              </div>
            </dl>
          </div>
        )}
      </section>
    </main>
  );
}
