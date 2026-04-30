'use client';

import { useCallback } from 'react';
import { useGameStore } from '@/stores/game-store';
import { useWalletStore } from '@/stores/wallet-store';

export interface BottomBarProps {
  /** Callback to undo the most recently placed bet selection. */
  onUndoLastBet?: () => void;
  /** Callback to clear all pending bet selections. */
  onClearBets?: () => void;
}

export default function BottomBar({ onUndoLastBet, onClearBets }: BottomBarProps) {
  const balance = useWalletStore((s) => s.balance);
  const result = useGameStore((s) => s.result);
  const betAmount = useGameStore((s) => s.betAmount);
  const setBetAmount = useGameStore((s) => s.setBetAmount);

  // Calculate total win from last round payouts
  const lastWin =
    result?.playerPayouts
      .filter((p) => p.isWinner)
      .reduce((sum, p) => sum + Number(p.amount), 0)
      .toFixed(2) ?? '0.00';

  const handleMultiply = useCallback(() => {
    const current = Number(betAmount) || 0;
    if (current > 0) setBetAmount(String(current * 2));
  }, [betAmount, setBetAmount]);

  const handleDivide = useCallback(() => {
    const current = Number(betAmount) || 0;
    if (current >= 2) {
      setBetAmount(String(Math.max(1, Math.floor(current / 2))));
    }
  }, [betAmount, setBetAmount]);

  return (
    <section
      aria-label="Bottom bar"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-casino-card-border bg-[var(--casino-gradient-from)] px-4 py-3"
    >
      <div className="mx-auto flex max-w-lg items-center justify-between gap-2">
        {/* Balance */}
        <div className="flex flex-col items-center">
          <span className="text-[10px] uppercase tracking-wider text-casino-text-muted">
            Balance
          </span>
          <span className="text-sm font-bold text-casino-text-primary">
            ${balance ?? '0.00'}
          </span>
        </div>

        {/* Win */}
        <div className="flex flex-col items-center">
          <span className="text-[10px] uppercase tracking-wider text-casino-text-muted">
            Win
          </span>
          <span
            className={`text-sm font-bold ${
              Number(lastWin) > 0 ? 'text-casino-green' : 'text-casino-text-primary'
            }`}
          >
            ${lastWin}
          </span>
        </div>

        {/* Bet amount controls */}
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            onClick={handleDivide}
            aria-label="Halve bet amount"
            className="casino-transition rounded-md bg-casino-card px-2 py-1 text-xs font-bold text-casino-text-primary"
          >
            ÷2
          </button>

          <span
            className="min-w-[3rem] rounded-md bg-casino-card px-2 py-1 text-center text-sm font-bold text-casino-text-primary"
            aria-label={`Current bet amount ${betAmount}`}
          >
            {betAmount}
          </span>

          <button
            type="button"
            onClick={handleMultiply}
            aria-label="Double bet amount"
            className="casino-transition rounded-md bg-casino-card px-2 py-1 text-xs font-bold text-casino-text-primary"
          >
            x2
          </button>

          {onUndoLastBet && (
            <button
              type="button"
              onClick={onUndoLastBet}
              aria-label="Undo last bet"
              className="casino-transition rounded-md bg-casino-card px-2 py-1 text-xs text-casino-text-secondary"
            >
              ↩
            </button>
          )}

          {onClearBets && (
            <button
              type="button"
              onClick={onClearBets}
              aria-label="Clear all bets"
              className="casino-transition rounded-md bg-casino-card px-2 py-1 text-xs text-casino-red"
            >
              ✕
            </button>
          )}
        </div>
      </div>
    </section>
  );
}
