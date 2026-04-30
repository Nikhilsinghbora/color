'use client';

const BIG_SMALL_CONFIG = [
  {
    type: 'big' as const,
    label: 'Big',
    range: '5-9',
    multiplier: 'x2.0',
    className: 'bg-orange-500 hover:bg-orange-600',
  },
  {
    type: 'small' as const,
    label: 'Small',
    range: '0-4',
    multiplier: 'x2.0',
    className: 'bg-blue-500 hover:bg-blue-600',
  },
] as const;

export interface BigSmallButtonsProps {
  onSelectBigSmall: (type: 'big' | 'small') => void;
  disabled: boolean;
  placedBigSmall?: Set<string>;
}

export default function BigSmallButtons({
  onSelectBigSmall,
  disabled,
  placedBigSmall = new Set(),
}: BigSmallButtonsProps) {
  return (
    <section aria-label="Big/Small betting buttons" className="mx-auto w-full px-4">
      <div className="grid grid-cols-2 gap-3">
        {BIG_SMALL_CONFIG.map(({ type, label, range, multiplier, className }) => {
          const isPlaced = placedBigSmall.has(type);

          return (
            <button
              key={type}
              type="button"
              disabled={disabled}
              onClick={() => onSelectBigSmall(type)}
              aria-label={`Bet on ${label} ${range} at ${multiplier} odds`}
              className={`
                casino-transition relative flex flex-col items-center justify-center
                rounded-xl px-3 py-4 font-semibold text-white
                ${className}
              `}
            >
              <span className="text-base font-bold">
                {label} {range}
              </span>
              <span className="mt-0.5 text-xs opacity-90">{multiplier}</span>
              {isPlaced && (
                <span
                  className="absolute right-1.5 top-1.5 flex h-5 w-5 items-center justify-center rounded-full bg-white/30 text-xs"
                  aria-label={`Bet placed on ${label}`}
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
