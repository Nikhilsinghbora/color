'use client';

import { useGameStore } from '@/stores/game-store';
import { NUMBER_COLOR_MAP } from '@/lib/number-color-map';

/** Map color names to CSS class names for the result circle background. */
function getResultBgClass(winningNumber: number): string {
  const mapping = NUMBER_COLOR_MAP[winningNumber];
  if (!mapping) return 'bg-gray-500';
  if (mapping.secondary === 'violet') return 'casino-btn-green-violet';
  if (mapping.primary === 'green') return 'casino-btn-green';
  if (mapping.primary === 'red') return 'casino-btn-red';
  return 'bg-gray-500';
}

export default function ResultDisplay() {
  const result = useGameStore((s) => s.result);
  const phase = useGameStore((s) => s.phase);
  const lastResult = useGameStore((s) => s.lastResult);

  // Determine what to display: current result, or previous result carried over
  const displayResult = result ?? lastResult;
  const showPlaceholder = !displayResult;

  return (
    <section
      aria-label="Round result display"
      className="casino-card mx-auto flex flex-col items-center justify-center px-4 py-6"
    >
      {showPlaceholder ? (
        <div className="flex h-24 w-24 items-center justify-center rounded-full border-2 border-dashed border-casino-card-border">
          <span className="text-center text-sm text-casino-text-muted">
            Waiting for result
          </span>
        </div>
      ) : (
        <>
          <div
            className={`flex h-24 w-24 items-center justify-center rounded-full shadow-lg ${getResultBgClass(displayResult.winningNumber)}`}
            role="img"
            aria-label={`Winning number ${displayResult.winningNumber}, color ${displayResult.winningColor}`}
          >
            <span className="text-4xl font-bold text-white">
              {displayResult.winningNumber}
            </span>
          </div>
          <p className="mt-3 text-sm capitalize text-casino-text-secondary">
            {displayResult.winningColor}
          </p>
          {phase === 'betting' && result === null && lastResult !== null && (
            <p className="mt-1 text-xs text-casino-text-muted">Previous round</p>
          )}
        </>
      )}
    </section>
  );
}
