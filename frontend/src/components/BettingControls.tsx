'use client';

import { useState, useCallback } from 'react';
import type { ColorOption, BetResponse } from '@/types';
import { useGameStore } from '@/stores/game-store';
import { useWalletStore } from '@/stores/wallet-store';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import { calculatePotentialPayout } from '@/lib/utils';

/** Map color names to Tailwind bg classes. */
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

export interface BettingControlsProps {
  colorOptions: ColorOption[];
  minBet: string;
  maxBet: string;
  roundId: string;
  phase: string;
  onBetPlaced?: (color: string, amount: string) => void;
}

export default function BettingControls({
  colorOptions,
  minBet,
  maxBet,
  roundId,
  phase,
  onBetPlaced,
}: BettingControlsProps) {
  const selectedBets = useGameStore((s) => s.selectedBets);
  const setBetSelection = useGameStore((s) => s.setBetSelection);
  const removeBetSelection = useGameStore((s) => s.removeBetSelection);
  const addPlacedBet = useGameStore((s) => s.addPlacedBet);
  const placedBets = useGameStore((s) => s.placedBets);

  const balance = useWalletStore((s) => s.balance);
  const updateBalance = useWalletStore((s) => s.updateBalance);

  const [errors, setErrors] = useState<Record<string, string>>({});
  const [submitting, setSubmitting] = useState<Record<string, boolean>>({});
  const [toast, setToast] = useState<string | null>(null);

  const isBetting = phase === 'betting';

  const clearError = useCallback((color: string) => {
    setErrors((prev) => {
      const { [color]: _, ...rest } = prev;
      return rest;
    });
  }, []);

  const handleChipClick = useCallback(
    (color: string) => {
      if (!isBetting) return;
      if (color in selectedBets) {
        removeBetSelection(color);
        clearError(color);
      } else {
        setBetSelection(color, '');
      }
    },
    [isBetting, selectedBets, setBetSelection, removeBetSelection, clearError],
  );

  const handleAmountChange = useCallback(
    (color: string, value: string) => {
      setBetSelection(color, value);
      clearError(color);
    },
    [setBetSelection, clearError],
  );

  const handlePlaceBet = useCallback(
    async (color: string) => {
      const amount = selectedBets[color] ?? '';
      const odds = colorOptions.find((o) => o.color === color)?.odds ?? '1';

      // Client-side validation
      if (!amount || isNaN(Number(amount)) || Number(amount) <= 0) {
        setErrors((prev) => ({ ...prev, [color]: 'Enter a valid bet amount' }));
        return;
      }
      if (Number(amount) < Number(minBet)) {
        setErrors((prev) => ({
          ...prev,
          [color]: `Minimum bet is $${minBet}`,
        }));
        return;
      }
      if (Number(amount) > Number(maxBet)) {
        setErrors((prev) => ({
          ...prev,
          [color]: `Maximum bet is $${maxBet}`,
        }));
        return;
      }
      if (balance !== null && Number(amount) > Number(balance)) {
        setErrors((prev) => ({
          ...prev,
          [color]: 'Insufficient balance',
        }));
        return;
      }

      setSubmitting((prev) => ({ ...prev, [color]: true }));
      try {
        const { data } = await apiClient.post<BetResponse>('/game/bet', {
          round_id: roundId,
          color,
          amount,
        });

        addPlacedBet({
          id: data.id,
          color: data.color,
          amount: data.amount,
          oddsAtPlacement: data.odds_at_placement,
          potentialPayout: calculatePotentialPayout(data.amount, data.odds_at_placement),
        });

        updateBalance(data.balance_after);
        removeBetSelection(color);
        clearError(color);

        setToast(`Bet placed: $${data.amount} on ${data.color}`);
        setTimeout(() => setToast(null), 3000);

        onBetPlaced?.(data.color, data.amount);
      } catch (err: unknown) {
        const parsed = parseApiError(err);
        if (parsed) {
          const msg = getErrorMessage(parsed.code, parsed.message);
          if (parsed.code === 'BETTING_CLOSED') {
            setErrors((prev) => ({ ...prev, [color]: msg }));
          } else {
            setErrors((prev) => ({ ...prev, [color]: msg }));
          }
        } else {
          setErrors((prev) => ({
            ...prev,
            [color]: 'An unexpected error occurred',
          }));
        }
      } finally {
        setSubmitting((prev) => ({ ...prev, [color]: false }));
      }
    },
    [
      selectedBets,
      colorOptions,
      minBet,
      maxBet,
      balance,
      roundId,
      addPlacedBet,
      updateBalance,
      removeBetSelection,
      clearError,
      onBetPlaced,
    ],
  );

  const placedColorSet = new Set(placedBets.map((b) => b.color));

  return (
    <div data-testid="betting-controls">
      {/* Toast notification */}
      {toast && (
        <div
          role="status"
          aria-live="polite"
          className="mb-4 rounded-md bg-green-100 px-4 py-2 text-center text-sm font-medium text-green-800 dark:bg-green-900 dark:text-green-200"
        >
          {toast}
        </div>
      )}

      {/* Color chips */}
      <section aria-label="Betting color options" className="mx-auto max-w-2xl">
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4">
          {colorOptions.map((opt) => {
            const isSelected = opt.color in selectedBets;
            const isPlaced = placedColorSet.has(opt.color);
            const disabled = !isBetting;

            return (
              <button
                key={opt.color}
                type="button"
                disabled={disabled}
                aria-label={`${opt.color} — odds ${opt.odds}x`}
                aria-pressed={isSelected}
                onClick={() => handleChipClick(opt.color)}
                className={`
                  flex flex-col items-center justify-center rounded-lg p-4 text-white
                  transition-all focus:outline-none focus:ring-2 focus:ring-offset-2
                  ${getBg(opt.color)} ${getRing(opt.color)}
                  ${disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer hover:scale-105 hover:shadow-lg'}
                  ${isSelected ? 'ring-4 ring-offset-2 scale-110 shadow-xl' : ''}
                  ${isPlaced ? 'opacity-80' : ''}
                `}
              >
                <span className="text-lg font-bold capitalize">{opt.color}</span>
                <span className="mt-1 text-sm font-medium opacity-90">{opt.odds}x</span>
                {isPlaced && (
                  <span className="mt-1 text-xs font-semibold">Bet placed</span>
                )}
              </button>
            );
          })}
        </div>
      </section>

      {/* Bet input fields for selected colors */}
      {Object.keys(selectedBets).length > 0 && isBetting && (
        <section
          aria-label="Bet inputs"
          className="mx-auto mt-6 max-w-2xl space-y-4"
        >
          {Object.entries(selectedBets).map(([color, amount]) => {
            const odds = colorOptions.find((o) => o.color === color)?.odds ?? '1';
            const payout =
              amount && !isNaN(Number(amount)) && Number(amount) > 0
                ? calculatePotentialPayout(amount, odds)
                : '0.00';
            const error = errors[color];
            const isSubmitting = submitting[color] ?? false;

            return (
              <div
                key={color}
                className="rounded-lg border border-border bg-card p-4"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-block h-4 w-4 rounded-full ${getBg(color)}`}
                    aria-hidden="true"
                  />
                  <span className="font-semibold capitalize text-card-foreground">
                    {color}
                  </span>
                  <span className="text-sm text-muted-foreground">
                    ({odds}x)
                  </span>
                </div>

                <div className="mt-3 flex items-center gap-3">
                  <div className="flex-1">
                    <label htmlFor={`bet-amount-${color}`} className="sr-only">
                      Bet amount for {color}
                    </label>
                    <input
                      id={`bet-amount-${color}`}
                      type="number"
                      min={minBet}
                      max={maxBet}
                      step="0.01"
                      value={amount}
                      onChange={(e) => handleAmountChange(color, e.target.value)}
                      placeholder={`$${minBet} – $${maxBet}`}
                      disabled={isSubmitting}
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                      aria-describedby={error ? `bet-error-${color}` : undefined}
                      aria-invalid={!!error}
                    />
                  </div>
                  <button
                    type="button"
                    disabled={isSubmitting}
                    onClick={() => handlePlaceBet(color)}
                    className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {isSubmitting ? 'Placing…' : 'Place Bet'}
                  </button>
                </div>

                {/* Min/max hint */}
                <p className="mt-1 text-xs text-muted-foreground">
                  Min: ${minBet} · Max: ${maxBet}
                </p>

                {/* Potential payout */}
                {amount && Number(amount) > 0 && (
                  <p className="mt-1 text-sm text-muted-foreground">
                    Potential payout: <strong>${payout}</strong>
                  </p>
                )}

                {/* Inline error */}
                {error && (
                  <p
                    id={`bet-error-${color}`}
                    role="alert"
                    className="mt-1 text-sm text-red-600 dark:text-red-400"
                  >
                    {error}
                  </p>
                )}
              </div>
            );
          })}
        </section>
      )}

      {/* Bet summary */}
      {placedBets.length > 0 && (
        <section
          aria-label="Bet summary"
          className="mx-auto mt-6 max-w-2xl rounded-lg border border-border bg-card p-4"
        >
          <h2 className="mb-3 text-lg font-semibold text-card-foreground">
            Your Bets
          </h2>
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
    </div>
  );
}
