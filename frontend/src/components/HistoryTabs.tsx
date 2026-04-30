'use client';

import { useState } from 'react';
import { useGameStore } from '@/stores/game-store';

type Tab = 'history' | 'mybets';

/** Map a winning color to a Tailwind bg class for the small result circle. */
function getCircleBg(color: string): string {
  switch (color.toLowerCase()) {
    case 'green':
      return 'bg-casino-green';
    case 'red':
      return 'bg-casino-red';
    case 'violet':
      return 'bg-casino-violet';
    default:
      return 'bg-gray-500';
  }
}

export default function HistoryTabs() {
  const [activeTab, setActiveTab] = useState<Tab>('history');
  const [collapsed, setCollapsed] = useState(false);

  const roundHistory = useGameStore((s) => s.roundHistory);
  const placedBets = useGameStore((s) => s.placedBets);
  const result = useGameStore((s) => s.result);

  return (
    <section aria-label="History and bets" className="mx-auto w-full px-4">
      {/* Tab bar + collapse toggle */}
      <div className="flex items-center justify-between">
        <div className="flex gap-1" role="tablist">
          <button
            role="tab"
            aria-selected={activeTab === 'history'}
            onClick={() => setActiveTab('history')}
            className={`rounded-t-lg px-4 py-2 text-xs font-semibold transition-colors ${
              activeTab === 'history'
                ? 'bg-casino-card text-casino-text-primary'
                : 'text-casino-text-muted hover:text-casino-text-secondary'
            }`}
          >
            History
          </button>
          <button
            role="tab"
            aria-selected={activeTab === 'mybets'}
            onClick={() => setActiveTab('mybets')}
            className={`rounded-t-lg px-4 py-2 text-xs font-semibold transition-colors ${
              activeTab === 'mybets'
                ? 'bg-casino-card text-casino-text-primary'
                : 'text-casino-text-muted hover:text-casino-text-secondary'
            }`}
          >
            My Bets
          </button>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed((c) => !c)}
          aria-label={collapsed ? 'Expand history panel' : 'Collapse history panel'}
          className="px-2 py-1 text-xs text-casino-text-muted hover:text-casino-text-secondary"
        >
          {collapsed ? '▲' : '▼'}
        </button>
      </div>

      {/* Tab content */}
      {!collapsed && (
        <div className="casino-card rounded-tl-none p-3">
          {activeTab === 'history' && (
            <div
              role="tabpanel"
              aria-label="Round history"
              className="flex gap-1.5 overflow-x-auto py-1"
            >
              {roundHistory.length === 0 ? (
                <p className="text-xs text-casino-text-muted">No history yet</p>
              ) : (
                [...roundHistory].reverse().map((entry, idx) => (
                  <div
                    key={`${entry.roundId}-${idx}`}
                    className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full text-xs font-bold text-white ${getCircleBg(entry.winningColor)}`}
                    title={`Round ${entry.roundId}: ${entry.winningNumber} (${entry.winningColor})`}
                  >
                    {entry.winningNumber}
                  </div>
                ))
              )}
            </div>
          )}

          {activeTab === 'mybets' && (
            <div role="tabpanel" aria-label="My bets">
              {placedBets.length === 0 ? (
                <p className="text-xs text-casino-text-muted">No bets placed</p>
              ) : (
                <ul className="space-y-1.5">
                  {placedBets.map((bet) => {
                    const isNumber = /^\d$/.test(bet.color);
                    const typeLabel = isNumber ? `Number ${bet.color}` : bet.color;
                    const payout = result?.playerPayouts.find(
                      (p) => p.betId === bet.id,
                    );
                    let outcomeLabel = 'Pending';
                    let outcomeClass = 'text-casino-text-muted';
                    if (payout) {
                      if (payout.isWinner) {
                        outcomeLabel = `Won $${payout.amount}`;
                        outcomeClass = 'text-casino-green';
                      } else {
                        outcomeLabel = 'Lost';
                        outcomeClass = 'text-casino-red';
                      }
                    }

                    return (
                      <li
                        key={bet.id}
                        className="flex items-center justify-between text-xs text-casino-text-secondary"
                      >
                        <span className="capitalize">{typeLabel}</span>
                        <span>
                          ${bet.amount} @ {bet.oddsAtPlacement}x
                        </span>
                        <span className={`font-semibold ${outcomeClass}`}>
                          {outcomeLabel}
                        </span>
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
