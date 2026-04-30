'use client';

const COLOR_CONFIG = [
  { color: 'green', label: 'Green', multiplier: 'x2.0', className: 'casino-btn-green' },
  { color: 'violet', label: 'Violet', multiplier: 'x4.8', className: 'casino-btn-violet' },
  { color: 'red', label: 'Red', multiplier: 'x2.0', className: 'casino-btn-red' },
] as const;

export interface ColorBetButtonsProps {
  onSelectColor: (color: string) => void;
  disabled: boolean;
  /** Set of colors that already have a placed bet. */
  placedColors?: Set<string>;
}

export default function ColorBetButtons({
  onSelectColor,
  disabled,
  placedColors = new Set(),
}: ColorBetButtonsProps) {
  return (
    <section aria-label="Color betting buttons" className="mx-auto w-full px-4">
      <div className="grid grid-cols-3 gap-3">
        {COLOR_CONFIG.map(({ color, label, multiplier, className }) => {
          const isPlaced = placedColors.has(color);

          return (
            <button
              key={color}
              type="button"
              disabled={disabled}
              onClick={() => onSelectColor(color)}
              aria-label={`Bet on ${label} at ${multiplier} odds`}
              className={`
                casino-transition relative flex flex-col items-center justify-center
                rounded-xl px-3 py-4 font-semibold text-white
                ${className}
              `}
            >
              <span className="text-base font-bold">{label}</span>
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
