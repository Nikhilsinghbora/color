'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import apiClient from '@/lib/api-client';
import type { GameMode } from '@/types';

/** Visual theme per mode_type. */
const MODE_THEMES: Record<
  string,
  { border: string; bg: string; badge: string; icon: string }
> = {
  classic: {
    border: 'border-indigo-400 dark:border-indigo-500',
    bg: 'bg-indigo-50 dark:bg-indigo-950',
    badge: 'bg-indigo-100 text-indigo-700 dark:bg-indigo-900 dark:text-indigo-300',
    icon: '🎯',
  },
  timed_challenge: {
    border: 'border-amber-400 dark:border-amber-500',
    bg: 'bg-amber-50 dark:bg-amber-950',
    badge: 'bg-amber-100 text-amber-700 dark:bg-amber-900 dark:text-amber-300',
    icon: '⏱️',
  },
  tournament: {
    border: 'border-emerald-400 dark:border-emerald-500',
    bg: 'bg-emerald-50 dark:bg-emerald-950',
    badge: 'bg-emerald-100 text-emerald-700 dark:bg-emerald-900 dark:text-emerald-300',
    icon: '🏆',
  },
};

const DEFAULT_THEME = {
  border: 'border-gray-300 dark:border-gray-600',
  bg: 'bg-gray-50 dark:bg-gray-900',
  badge: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300',
  icon: '🎮',
};

function getTheme(modeType: string) {
  return MODE_THEMES[modeType] ?? DEFAULT_THEME;
}

/** Human-readable label for mode_type. */
function modeTypeLabel(modeType: string): string {
  switch (modeType) {
    case 'classic':
      return 'Classic';
    case 'timed_challenge':
      return 'Timed Challenge';
    case 'tournament':
      return 'Tournament';
    default:
      return modeType;
  }
}

/** Color swatch bg class. */
const COLOR_BG: Record<string, string> = {
  red: 'bg-red-500',
  blue: 'bg-blue-500',
  green: 'bg-green-500',
  yellow: 'bg-yellow-400',
  purple: 'bg-purple-500',
  orange: 'bg-orange-500',
  pink: 'bg-pink-500',
  cyan: 'bg-cyan-500',
};

function colorBg(color: string) {
  return COLOR_BG[color.toLowerCase()] ?? 'bg-gray-500';
}

export default function GameModesPage() {
  useAuthGuard();

  const router = useRouter();
  const [modes, setModes] = useState<GameMode[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function fetchModes() {
      try {
        setIsLoading(true);
        setError(null);
        const { data } = await apiClient.get<GameMode[]>('/game/modes');
        if (!cancelled) {
          setModes(data);
        }
      } catch {
        if (!cancelled) {
          setError('Failed to load game modes. Please try again.');
        }
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    }

    fetchModes();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleSelectMode(mode: GameMode) {
    router.push(`/game?mode=${mode.id}`);
  }

  return (
    <main className="min-h-screen bg-background px-4 py-6">
      <section className="mx-auto max-w-4xl">
        <h1 className="mb-6 text-2xl font-bold text-foreground">Game Modes</h1>

        {/* Loading skeleton */}
        {isLoading && (
          <div
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
            aria-label="Loading game modes"
            role="status"
          >
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="animate-pulse rounded-lg border border-gray-200 p-6 dark:border-gray-700"
              >
                <div className="mb-3 h-6 w-2/3 rounded bg-gray-200 dark:bg-gray-700" />
                <div className="mb-2 h-4 w-1/2 rounded bg-gray-200 dark:bg-gray-700" />
                <div className="mb-2 h-4 w-full rounded bg-gray-200 dark:bg-gray-700" />
                <div className="h-4 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
              </div>
            ))}
            <span className="sr-only">Loading game modes…</span>
          </div>
        )}

        {/* Error state */}
        {error && !isLoading && (
          <div role="alert" className="rounded-md bg-red-50 p-4 text-red-700 dark:bg-red-950 dark:text-red-300">
            <p>{error}</p>
            <button
              type="button"
              onClick={() => window.location.reload()}
              className="mt-2 text-sm font-medium underline hover:no-underline"
            >
              Retry
            </button>
          </div>
        )}

        {/* Modes grid */}
        {!isLoading && !error && (
          <div
            className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3"
            role="list"
            aria-label="Available game modes"
          >
            {modes.map((mode) => {
              const theme = getTheme(mode.mode_type);

              return (
                <article
                  key={mode.id}
                  role="listitem"
                  className={`
                    relative flex flex-col rounded-lg border-2 p-5 transition-shadow
                    ${theme.border} ${theme.bg}
                    ${mode.is_active ? 'cursor-pointer hover:shadow-lg focus-within:ring-2 focus-within:ring-primary' : 'opacity-60'}
                  `}
                >
                  {/* Header */}
                  <div className="mb-3 flex items-start justify-between">
                    <div className="flex items-center gap-2">
                      <span className="text-2xl" aria-hidden="true">{theme.icon}</span>
                      <h2 className="text-lg font-semibold text-foreground">{mode.name}</h2>
                    </div>
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        mode.is_active
                          ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
                          : 'bg-gray-100 text-gray-500 dark:bg-gray-800 dark:text-gray-400'
                      }`}
                    >
                      {mode.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </div>

                  {/* Mode type badge */}
                  <span
                    className={`mb-3 inline-block w-fit rounded px-2 py-0.5 text-xs font-medium ${theme.badge}`}
                    data-testid={`mode-type-${mode.id}`}
                  >
                    {modeTypeLabel(mode.mode_type)}
                  </span>

                  {/* Color options with odds */}
                  <div className="mb-3">
                    <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                      Colors &amp; Odds
                    </h3>
                    <div className="flex flex-wrap gap-2">
                      {mode.color_options.map((color) => (
                        <span
                          key={color}
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs text-white"
                        >
                          <span
                            className={`inline-block h-3 w-3 rounded-full ${colorBg(color)}`}
                            aria-hidden="true"
                          />
                          <span className="capitalize text-foreground">{color}</span>
                          <span className="text-muted-foreground">
                            {mode.odds[color] ?? '—'}x
                          </span>
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Rules / details */}
                  <dl className="mb-4 grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
                    <dt className="text-muted-foreground">Min Bet</dt>
                    <dd className="font-medium text-foreground">${mode.min_bet}</dd>
                    <dt className="text-muted-foreground">Max Bet</dt>
                    <dd className="font-medium text-foreground">${mode.max_bet}</dd>
                    <dt className="text-muted-foreground">Round Duration</dt>
                    <dd className="font-medium text-foreground">{mode.round_duration_seconds}s</dd>
                  </dl>

                  {/* Select button */}
                  <button
                    type="button"
                    disabled={!mode.is_active}
                    onClick={() => handleSelectMode(mode)}
                    aria-label={`Select ${mode.name} game mode`}
                    className={`
                      mt-auto w-full rounded-md px-4 py-2 text-sm font-medium transition-colors
                      focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2
                      ${
                        mode.is_active
                          ? 'bg-primary text-primary-foreground hover:bg-primary/90'
                          : 'cursor-not-allowed bg-gray-200 text-gray-400 dark:bg-gray-700 dark:text-gray-500'
                      }
                    `}
                  >
                    {mode.is_active ? 'Play Now' : 'Unavailable'}
                  </button>
                </article>
              );
            })}
          </div>
        )}
      </section>
    </main>
  );
}
