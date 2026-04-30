'use client';

import { NUMBER_COLOR_MAP } from '@/lib/number-color-map';

/** Map a number's color mapping to a CSS class for the button background. */
function getNumberBgClass(num: number): string {
  const mapping = NUMBER_COLOR_MAP[num];
  if (!mapping) return 'bg-gray-500';
  if (mapping.secondary === 'violet') return 'casino-btn-green-violet';
  if (mapping.primary === 'green') return 'casino-btn-green';
  if (mapping.primary === 'red') return 'casino-btn-red';
  return 'bg-gray-500';
}

const NUMBERS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] as const;

export interface NumberGridProps {
  onSelectNumber: (num: number) => void;
  disabled: boolean;
  /** Set of number strings ("0"–"9") that already have a placed bet. */
  placedNumbers?: Set<string>;
}

export default function NumberGrid({
  onSelectNumber,
  disabled,
  placedNumbers = new Set(),
}: NumberGridProps) {
  return (
    <section aria-label="Number betting grid" className="mx-auto w-full px-4">
      <div className="grid grid-cols-5 gap-2">
        {NUMBERS.map((num) => {
          const isPlaced = placedNumbers.has(String(num));

          return (
            <button
              key={num}
              type="button"
              disabled={disabled}
              onClick={() => onSelectNumber(num)}
              aria-label={`Bet on number ${num} at x9.6 odds`}
              className={`
                casino-transition relative flex flex-col items-center justify-center
                rounded-lg px-2 py-3 font-semibold text-white
                ${getNumberBgClass(num)}
              `}
            >
              <span className="text-lg font-bold">{num}</span>
              <span className="text-[10px] opacity-80">x9.6</span>
              {isPlaced && (
                <span
                  className="absolute right-0.5 top-0.5 flex h-4 w-4 items-center justify-center rounded-full bg-white/30 text-[9px]"
                  aria-label={`Bet placed on number ${num}`}
                >
                  ✓
                </span>
              )}
            </button>
          );
        })}
      </div>
    </section>
  );
}
