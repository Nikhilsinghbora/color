'use client';

import type { GameMode } from '@/types';

export interface GameModeTabsProps {
  modes: GameMode[];
  activeMode: string;
  onModeChange: (modeId: string) => void;
}

export default function GameModeTabs({
  modes,
  activeMode,
  onModeChange,
}: GameModeTabsProps) {
  return (
    <nav aria-label="Game mode tabs" className="mx-4 mt-3">
      <div
        className="flex gap-1 rounded-xl bg-casino-card p-1 border border-casino-card-border"
        role="tablist"
        aria-label="Game modes"
      >
        {modes.map((mode) => {
          const isActive = mode.id === activeMode;

          return (
            <button
              key={mode.id}
              type="button"
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${mode.id}`}
              id={`tab-${mode.id}`}
              onClick={() => {
                if (!isActive) {
                  onModeChange(mode.id);
                }
              }}
              className={`
                casino-transition flex-1 rounded-lg px-2 py-2 text-center text-xs font-semibold
                ${
                  isActive
                    ? 'bg-casino-green text-white shadow-md'
                    : 'bg-transparent text-casino-text-muted hover:text-casino-text-secondary'
                }
              `}
            >
              {mode.name}
            </button>
          );
        })}
      </div>
    </nav>
  );
}
