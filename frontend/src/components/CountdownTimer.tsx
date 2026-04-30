'use client';

/**
 * Calculate the SVG stroke-dashoffset for the countdown progress ring.
 *
 * Exported so it can be tested independently (Property 2).
 *
 * @param totalSeconds  Total duration of the countdown (must be > 0)
 * @param remainingSeconds  Seconds remaining (0 <= remaining <= total)
 * @param circumference  Circle circumference (2 * π * radius)
 * @returns dashoffset value — 0 when full, circumference when depleted
 */
export function calculateDashoffset(
  totalSeconds: number,
  remainingSeconds: number,
  circumference: number,
): number {
  if (totalSeconds <= 0) return circumference;
  const clamped = Math.max(0, Math.min(remainingSeconds, totalSeconds));
  return circumference * (1 - clamped / totalSeconds);
}

const RADIUS = 44;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

export interface CountdownTimerProps {
  totalSeconds: number;
  remainingSeconds: number;
  /** When true, hides the timer and shows a resolving animation. */
  isResolving?: boolean;
}

export default function CountdownTimer({
  totalSeconds,
  remainingSeconds,
  isResolving = false,
}: CountdownTimerProps) {
  if (isResolving) {
    return (
      <div
        className="mx-auto flex flex-col items-center justify-center py-4"
        aria-label="Resolving round"
        role="status"
      >
        <svg
          className="h-6 w-6 animate-spin text-casino-text-secondary"
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
        <span className="mt-2 text-sm font-medium text-casino-text-secondary">
          Resolving…
        </span>
      </div>
    );
  }

  const dashoffset = calculateDashoffset(totalSeconds, remainingSeconds, CIRCUMFERENCE);

  return (
    <div
      className="mx-auto flex items-center justify-center py-4 relative"
      role="timer"
      aria-live="polite"
      aria-label={`${remainingSeconds} seconds remaining`}
      style={{ width: '100px', height: '100px' }}
    >
      <svg
        width="100"
        height="100"
        viewBox="0 0 100 100"
        className="-rotate-90 absolute inset-0"
        aria-hidden="true"
      >
        {/* Track circle */}
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="var(--casino-timer-track)"
          strokeWidth="6"
        />
        {/* Progress circle */}
        <circle
          cx="50"
          cy="50"
          r={RADIUS}
          fill="none"
          stroke="var(--casino-timer-fill)"
          strokeWidth="6"
          strokeLinecap="round"
          strokeDasharray={CIRCUMFERENCE}
          strokeDashoffset={dashoffset}
          style={{ transition: 'stroke-dashoffset 0.4s ease' }}
        />
      </svg>
      {/* Centered seconds text — absolutely positioned in the center */}
      <span className="absolute inset-0 flex items-center justify-center text-2xl font-bold text-casino-text-primary">
        {remainingSeconds}
      </span>
    </div>
  );
}
