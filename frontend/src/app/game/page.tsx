'use client';

import { useSearchParams } from 'next/navigation';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useCountdown } from '@/hooks/useCountdown';
import { useGameStore } from '@/stores/game-store';

const DEFAULT_ROUND_ID = 'current';

/** Map color names to Tailwind-friendly bg classes. */
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

const COLOR_RING: Record<string, string> = {
  red: 'ring-red-400',
  blue: 'ring-blue-400',
  green: 'ring-green-400',
  yellow: 'ring-yellow-300',
  purple: 'ring-purple-400',
  orange: 'ring-orange-400',
  pink: 'ring-pink-400',
  cyan: 'ring-cyan-400',
};

function getBg(color: string) {
  return COLOR_BG[color.toLowerCase()] ?? 'bg-gray-500';
}

function getRing(color: string) {
  return COLOR_RING[color.toLowerCase()] ?? 'ring-gray-400';
}

export default function GameViewPage() {
  useAuthGuard();

  const searchParams = useSearchParams();
  const roundId = searchParams.get('roundId') ?? DEFAULT_ROUND_ID;

  const { status: wsStatus } = useWebSocket(roundId);

  const phase = useGameStore((s) => s.phase);
  const timerRemaining = useGameStore((s) => s.timerRemaining);
  const currentRound = useGameStore((s) => s.currentRound);
  const colorOptions = useGameStore((s) => s.colorOptions);
  const placedBets = useGameStore((s) => s.placedBets);
  const result = useGameStore((s) => s.result);
  const connectionStatus = useGameStore((s) => s.connectionStatus);

  const { remaining, isExpired } = useCountdown(timerRemaining);

  const isBetting = phase === 'betting';
  const isResolution = phase === 'resolution';
  const isResult = phase === 'result';

  const showReconnecting =
    connectionStatus === 'reconnecting' || connectionStatus === 'disconnected';

  return (
    <main className="min-h-screen bg-background px-4 py-6">
      {/* Connection status banner */}
      {showReconnecting && (
        <div
          role="alert"
          aria-live="assertive"
          className="mb-4 rounded-md bg-yellow-100 px-4 py-2 text-center text-sm font-medium text-yellow-800 dark:bg-yellow-900 dark:text-yellow-200"
        >
          {connectionStatus === 'reconnecting'
            ? 'Reconnecting to game server…'
            : 'Disconnected from game server. Attempting to reconnect…'}
        </div>
      )}

      {/* Round info */}
      <section aria-label="Round information" className="mx-auto mb-6 max-w-2xl text-center">
        <h1 className="text-2xl font-bold text-foreground">
          Round {currentRound?.roundId ?? '—'}
        </h1>
        <div className="mt-2 flex items-center justify-center gap-6 text-sm text-muted-foreground">
          <span data-testid="total-players">
            Players: <strong>{currentRound?.totalPlayers ?? 0}</strong>
          </span>
          <span data-testid="total-pool">
            Pool: <strong>${currentRound?.totalPool ?? '0'}</strong>
          </span>
        </div>
      </section>

      {/* Countdown timer */}
      {isBetting && (
        <section aria-label="Countdown timer" className="mx-auto mb-8 max-w-2xl text-center">
          <div
            role="timer"
            aria-live="polite"
            className="inline-flex h-20 w-20 items-center justify-center rounded-full border-4 border-primary text-3xl font-bold text-primary"
          >
            {remaining}
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {isExpired ? "Time's up!" : 'seconds remaining'}
          </p>
        </section>
      )}

      {/* Resolution phase */}
      {isResolution && (
        <section
          aria-label="Resolving round"
          className="mx-auto mb-8 max-w-2xl text-center"
        >
          <div className="flex items-center justify-center gap-2" aria-live="polite">
            <svg
              className="h-6 w-6 animate-spin text-primary"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle
                className="opacity-25"
                cx="12"
                cy="12"
                r="10"
                stroke="currentColor"
                strokeWidth="4"
              />
              <path
                className="opacity-75"
                fill="currentColor"
                d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
              />
            </svg>
            <span className="text-xl font-semibold text-foreground">Resolving…</span>
          </div>
        </section>
      )}

      {/* Result phase */}
      {isResult && result && (
        <section
          aria-label="Round result"
          className="mx-auto mb-8 max-w-2xl text-center"
        >
          <p className="text-lg font-semibold text-foreground">
            Winning color:{' '}
            <span
              className={`inline-block rounded px-3 py-1 text-white ${getBg(result.winningColor)}`}
            >
              {result.winningColor}
            </span>
          </p>
          {result.playerPayouts.length > 0 && (
            <ul className="mt-3 space-y-1 text-sm" aria-label="Your payouts">
              {result.playerPayouts.map((p) => (
                <li
                  key={p.betId}
                  className={p.isWinner ? 'font-semibold text-green-600' : 'text-red-500'}
                >
                  {p.isWinner ? `Won $${p.amount}` : `Lost $${p.amount}`}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {/* Color chips */}
      <section aria-label="Color options" className="mx-auto max-w-2xl">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
          {colorOptions.map((opt) => {
            const isWinner = isResult && result?.winningColor === opt.color;
            const disabled = !isBetting;

            return (
              <button
                key={opt.color}
                type="button"
                disabled={disabled}
                aria-label={`${opt.color} — odds ${opt.odds}x`}
                aria-pressed={false}
                className={`
                  flex flex-col items-center justify-center rounded-lg p-4 text-white
                  transition-all focus:outline-none focus:ring-2 focus:ring-offset-2
                  ${getBg(opt.color)} ${getRing(opt.color)}
                  ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:scale-105 hover:shadow-lg'}
                  ${isWinner ? 'ring-4 ring-offset-2 scale-110 shadow-xl' : ''}
                `}
              >
                <span className="text-lg font-bold capitalize">{opt.color}</span>
                <span className="mt-1 text-sm font-medium opacity-90">{opt.odds}x</span>
              </button>
            );
          })}
        </div>
      </section>

      {/* Placed bets summary */}
      {placedBets.length > 0 && (
        <section
          aria-label="Your bets"
          className="mx-auto mt-8 max-w-2xl rounded-lg border border-border bg-card p-4"
        >
          <h2 className="mb-3 text-lg font-semibold text-card-foreground">Your Bets</h2>
          <ul className="space-y-2">
            {placedBets.map((bet) => (
              <li
                key={bet.id}
                className="flex items-center justify-between text-sm text-card-foreground"
              >
                <span className="flex items-center gap-2">
                  <span
                    className={`inline-block h-3 w-3 rounded-full ${getBg(bet.color)}`}
                    aria-hidden="true"
                  />
                  <span className="capitalize">{bet.color}</span>
                </span>
                <span>
                  ${bet.amount} → <strong>${bet.potentialPayout}</strong>
                </span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
