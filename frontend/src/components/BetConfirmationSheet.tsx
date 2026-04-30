'use client';

import { useState, useCallback, useMemo, useEffect } from 'react';

const BALANCE_PRESETS = [1, 10, 100, 1000] as const;

const MULTIPLIER_OPTIONS = [
  { label: 'Random', value: 'random' as const },
  { label: 'X1', value: 1 },
  { label: 'X5', value: 5 },
  { label: 'X10', value: 10 },
  { label: 'X20', value: 20 },
  { label: 'X50', value: 50 },
  { label: 'X100', value: 100 },
] as const;

/** Map bet type codes to human-readable labels for the header. */
function formatBetTypeLabel(betType: string): string {
  switch (betType) {
    case 'green':
      return 'Select Green';
    case 'red':
      return 'Select Red';
    case 'violet':
      return 'Select Violet';
    case 'big':
      return 'Select Big';
    case 'small':
      return 'Select Small';
    default:
      // Digit strings "0"–"9"
      if (/^\d$/.test(betType)) return `Select ${betType}`;
      return `Select ${betType}`;
  }
}

export interface BetConfirmationSheetProps {
  isOpen: boolean;
  betType: string; // "green", "red", "violet", "0"-"9", "big", "small"
  gameModeName: string;
  balance: string;
  onConfirm: (amount: number, quantity: number) => void;
  onCancel: () => void;
}

export default function BetConfirmationSheet({
  isOpen,
  betType,
  gameModeName,
  balance,
  onConfirm,
  onCancel,
}: BetConfirmationSheetProps) {
  const [selectedPreset, setSelectedPreset] = useState<number>(1);
  const [quantity, setQuantity] = useState<number>(1);
  const [activeMultiplier, setActiveMultiplier] = useState<number | 'random'>(1);
  const [agreedToRules, setAgreedToRules] = useState(false);
  const [balanceError, setBalanceError] = useState<string | null>(null);

  // Reset state when the sheet opens with a new bet type
  useEffect(() => {
    if (isOpen) {
      setSelectedPreset(1);
      setQuantity(1);
      setActiveMultiplier(1);
      setAgreedToRules(false);
      setBalanceError(null);
    }
  }, [isOpen, betType]);

  const totalAmount = useMemo(() => selectedPreset * quantity, [selectedPreset, quantity]);

  const balanceNum = useMemo(() => {
    const parsed = parseFloat(balance);
    return isNaN(parsed) ? 0 : parsed;
  }, [balance]);

  const clampQuantity = useCallback((val: number): number => {
    return Math.max(1, Math.min(100, Math.round(val)));
  }, []);

  const handleQuantityChange = useCallback(
    (newVal: number) => {
      const clamped = clampQuantity(newVal);
      setQuantity(clamped);
      setBalanceError(null);
    },
    [clampQuantity],
  );

  const handleMultiplierSelect = useCallback(
    (option: (typeof MULTIPLIER_OPTIONS)[number]) => {
      if (option.value === 'random') {
        // Random sets a random quantity between 1 and 100
        const randomQty = Math.floor(Math.random() * 100) + 1;
        setActiveMultiplier('random');
        setQuantity(randomQty);
      } else {
        setActiveMultiplier(option.value);
        setQuantity(option.value);
      }
      setBalanceError(null);
    },
    [],
  );

  const handlePresetSelect = useCallback((preset: number) => {
    setSelectedPreset(preset);
    setBalanceError(null);
  }, []);

  const handleConfirm = useCallback(() => {
    if (!agreedToRules) return;

    const total = selectedPreset * quantity;
    if (total > balanceNum) {
      setBalanceError('Insufficient balance. Total exceeds your wallet balance.');
      return;
    }

    onConfirm(selectedPreset, quantity);
  }, [agreedToRules, selectedPreset, quantity, balanceNum, onConfirm]);

  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/50"
        onClick={onCancel}
        aria-hidden="true"
        data-testid="bet-sheet-backdrop"
      />

      {/* Bottom sheet */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Bet confirmation"
        className="fixed inset-x-0 bottom-0 z-50 rounded-t-2xl border-t border-casino-card-border bg-[#1a2332] px-4 pb-6 pt-4"
        data-testid="bet-confirmation-sheet"
      >
        {/* ── Header ── */}
        <div className="mb-4 text-center">
          <h2 className="text-base font-bold text-casino-text-primary" data-testid="bet-sheet-header">
            {gameModeName} — {formatBetTypeLabel(betType)}
          </h2>
        </div>

        {/* ── Balance Preset Buttons ── */}
        <div className="mb-4">
          <p className="mb-2 text-xs text-casino-text-muted">Balance</p>
          <div className="grid grid-cols-4 gap-2" role="radiogroup" aria-label="Balance preset">
            {BALANCE_PRESETS.map((preset) => (
              <button
                key={preset}
                type="button"
                role="radio"
                aria-checked={selectedPreset === preset}
                onClick={() => handlePresetSelect(preset)}
                className={`casino-transition rounded-lg px-2 py-2 text-sm font-semibold ${
                  selectedPreset === preset
                    ? 'bg-casino-green text-white'
                    : 'bg-casino-card text-casino-text-secondary border border-casino-card-border'
                }`}
                data-testid={`preset-${preset}`}
              >
                ₹{preset}
              </button>
            ))}
          </div>
        </div>

        {/* ── Quantity Controls ── */}
        <div className="mb-4">
          <p className="mb-2 text-xs text-casino-text-muted">Quantity</p>
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => handleQuantityChange(quantity - 1)}
              disabled={quantity <= 1}
              aria-label="Decrease quantity"
              className="flex h-10 w-10 items-center justify-center rounded-lg bg-casino-card text-lg font-bold text-casino-text-primary border border-casino-card-border disabled:opacity-40"
            >
              −
            </button>
            <input
              type="number"
              min={1}
              max={100}
              value={quantity}
              onChange={(e) => handleQuantityChange(Number(e.target.value))}
              aria-label="Bet quantity"
              className="h-10 w-20 rounded-lg bg-casino-card text-center text-sm font-semibold text-casino-text-primary border border-casino-card-border outline-none focus:border-casino-green [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none [&::-webkit-outer-spin-button]:appearance-none"
              data-testid="quantity-input"
            />
            <button
              type="button"
              onClick={() => handleQuantityChange(quantity + 1)}
              disabled={quantity >= 100}
              aria-label="Increase quantity"
              className="flex h-10 w-10 items-center justify-center rounded-lg bg-casino-card text-lg font-bold text-casino-text-primary border border-casino-card-border disabled:opacity-40"
            >
              +
            </button>
          </div>
        </div>

        {/* ── Quick Multiplier Row ── */}
        <div className="mb-4">
          <p className="mb-2 text-xs text-casino-text-muted">Multiplier</p>
          <div className="flex flex-wrap gap-2" role="radiogroup" aria-label="Quick multiplier">
            {MULTIPLIER_OPTIONS.map((option) => {
              const isActive =
                option.value === activeMultiplier;
              return (
                <button
                  key={option.label}
                  type="button"
                  role="radio"
                  aria-checked={isActive}
                  onClick={() => handleMultiplierSelect(option)}
                  className={`casino-transition rounded-lg px-3 py-1.5 text-xs font-semibold ${
                    isActive
                      ? 'bg-casino-green text-white'
                      : 'bg-casino-card text-casino-text-secondary border border-casino-card-border'
                  }`}
                  data-testid={`multiplier-${option.label}`}
                >
                  {option.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* ── Agree to Rules Checkbox ── */}
        <div className="mb-4 flex items-center gap-2">
          <input
            type="checkbox"
            id="agree-rules"
            checked={agreedToRules}
            onChange={(e) => setAgreedToRules(e.target.checked)}
            className="h-4 w-4 rounded border-casino-card-border accent-casino-green"
            data-testid="agree-checkbox"
          />
          <label htmlFor="agree-rules" className="text-xs text-casino-text-secondary">
            I agree with the pre-sale rules
          </label>
        </div>

        {/* ── Balance Error ── */}
        {balanceError && (
          <div
            role="alert"
            aria-live="assertive"
            className="mb-3 rounded-lg bg-casino-red/20 px-3 py-2 text-center text-xs font-medium text-casino-red"
            data-testid="balance-error"
          >
            {balanceError}
          </div>
        )}

        {/* ── Footer: Cancel + Confirm ── */}
        <div className="flex gap-3">
          <button
            type="button"
            onClick={onCancel}
            className="casino-transition flex-1 rounded-xl bg-casino-card py-3 text-sm font-semibold text-casino-text-secondary border border-casino-card-border"
            data-testid="cancel-button"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleConfirm}
            disabled={!agreedToRules}
            className="casino-transition flex-1 rounded-xl bg-casino-green py-3 text-sm font-semibold text-white disabled:opacity-40"
            data-testid="confirm-button"
          >
            Total amount ₹{totalAmount.toFixed(2)}
          </button>
        </div>
      </div>
    </>
  );
}
