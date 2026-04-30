'use client';

import { useEffect, useState, useCallback } from 'react';

/** Color indicator mapping for the winning number display. */
function getColorClass(color: string): string {
  switch (color.toLowerCase()) {
    case 'green':
      return 'bg-casino-green';
    case 'red':
      return 'bg-casino-red';
    case 'violet':
      return 'bg-casino-violet';
    default:
      return 'bg-casino-green';
  }
}

export interface WinLossDialogProps {
  isOpen: boolean;
  isWin: boolean;
  winningNumber: number;
  winningColor: string;
  isBig: boolean;
  totalBonus: string;
  periodNumber: string;
  onClose: () => void;
}

const AUTO_CLOSE_SECONDS = 3;

export default function WinLossDialog({
  isOpen,
  isWin,
  winningNumber,
  winningColor,
  isBig,
  totalBonus,
  periodNumber,
  onClose,
}: WinLossDialogProps) {
  const [countdown, setCountdown] = useState(AUTO_CLOSE_SECONDS);

  // Reset countdown when dialog opens
  useEffect(() => {
    if (!isOpen) return;
    setCountdown(AUTO_CLOSE_SECONDS);
  }, [isOpen]);

  // Auto-close countdown timer
  useEffect(() => {
    if (!isOpen) return;

    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          clearInterval(interval);
          onClose();
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isOpen, onClose]);

  const handleClose = useCallback(() => {
    onClose();
  }, [onClose]);

  if (!isOpen) return null;

  const bigSmallLabel = isBig ? 'Big' : 'Small';

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/60"
        onClick={handleClose}
        aria-hidden="true"
        data-testid="winloss-backdrop"
      />

      {/* Centered modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label={isWin ? 'Win result' : 'Loss result'}
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        data-testid="winloss-dialog"
      >
        <div
          className={`relative w-full max-w-sm rounded-2xl border px-6 pb-6 pt-5 shadow-2xl ${
            isWin
              ? 'border-yellow-500/30 bg-gradient-to-b from-[#1a2e1a] to-[#1a2332]'
              : 'border-casino-card-border bg-[#1a2332]'
          }`}
        >
          {/* Close button (X) */}
          <button
            type="button"
            onClick={handleClose}
            aria-label="Close dialog"
            className="absolute right-3 top-3 flex h-8 w-8 items-center justify-center rounded-full text-casino-text-muted hover:bg-white/10 hover:text-casino-text-primary casino-transition"
            data-testid="winloss-close-btn"
          >
            ✕
          </button>

          {/* Header */}
          <h2
            className={`mb-4 text-center text-xl font-bold ${
              isWin ? 'text-yellow-400' : 'text-casino-text-muted'
            }`}
            data-testid="winloss-header"
          >
            {isWin ? '🎉 Congratulations' : 'Sorry'}
          </h2>

          {/* Lottery result */}
          <div className="mb-4 flex flex-col items-center gap-2">
            <p className="text-xs text-casino-text-muted">Lottery Result</p>
            <div className="flex items-center gap-3">
              {/* Winning number with color indicator */}
              <span
                className={`flex h-10 w-10 items-center justify-center rounded-full text-lg font-bold text-white ${getColorClass(winningColor)}`}
                data-testid="winloss-winning-number"
              >
                {winningNumber}
              </span>
              {/* Big/Small label */}
              <span
                className="rounded-lg bg-casino-card px-3 py-1 text-sm font-semibold text-casino-text-secondary border border-casino-card-border"
                data-testid="winloss-big-small"
              >
                {bigSmallLabel}
              </span>
            </div>
          </div>

          {/* Total bonus */}
          <div className="mb-3 text-center">
            <p className="text-xs text-casino-text-muted">Total Bonus</p>
            <p
              className={`text-2xl font-bold ${isWin ? 'text-casino-green' : 'text-casino-text-primary'}`}
              data-testid="winloss-bonus"
            >
              ₹{totalBonus}
            </p>
          </div>

          {/* Period number */}
          <div className="mb-4 text-center">
            <p className="text-xs text-casino-text-muted">Period</p>
            <p
              className="text-sm font-medium text-casino-text-secondary"
              data-testid="winloss-period"
            >
              {periodNumber}
            </p>
          </div>

          {/* Auto-close countdown */}
          <div className="text-center">
            <span
              className="text-xs text-casino-text-muted"
              data-testid="winloss-countdown"
            >
              Closing in {countdown}s
            </span>
          </div>
        </div>
      </div>
    </>
  );
}
