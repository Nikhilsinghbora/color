'use client';

export interface RulesModalProps {
  isOpen: boolean;
  onClose: () => void;
}

export default function RulesModal({ isOpen, onClose }: RulesModalProps) {
  if (!isOpen) return null;

  return (
    <>
      {/* Backdrop overlay */}
      <div
        className="fixed inset-0 z-40 bg-black/60"
        onClick={onClose}
        aria-hidden="true"
        data-testid="rules-backdrop"
      />

      {/* Centered modal */}
      <div
        role="dialog"
        aria-modal="true"
        aria-label="How to Play"
        className="fixed inset-0 z-50 flex items-center justify-center p-4"
        data-testid="rules-dialog"
      >
        <div className="relative w-full max-w-sm rounded-2xl border border-casino-card-border bg-[#1a2332] px-6 pb-6 pt-5 shadow-2xl">
          {/* Header */}
          <h2
            className="mb-4 text-center text-xl font-bold text-casino-text-primary"
            data-testid="rules-header"
          >
            How to Play
          </h2>

          {/* Rules content */}
          <div className="space-y-4 text-sm text-casino-text-secondary">
            {/* Color bets */}
            <section data-testid="rules-color-section">
              <h3 className="mb-1 font-semibold text-casino-text-primary">
                Color Bets
              </h3>
              <ul className="list-inside list-disc space-y-1">
                <li>
                  <span className="inline-block h-2.5 w-2.5 rounded-full bg-casino-green mr-1 align-middle" />
                  Green pays <strong>2x</strong>
                </li>
                <li>
                  <span className="inline-block h-2.5 w-2.5 rounded-full bg-casino-red mr-1 align-middle" />
                  Red pays <strong>2x</strong>
                </li>
                <li>
                  <span className="inline-block h-2.5 w-2.5 rounded-full bg-casino-violet mr-1 align-middle" />
                  Violet pays <strong>4.8x</strong>
                </li>
              </ul>
            </section>

            {/* Number bets */}
            <section data-testid="rules-number-section">
              <h3 className="mb-1 font-semibold text-casino-text-primary">
                Number Bets
              </h3>
              <p>
                Pick a number (0–9). If it matches the winning number, you win{' '}
                <strong>9.6x</strong> your bet.
              </p>
            </section>

            {/* Big/Small bets */}
            <section data-testid="rules-bigsmall-section">
              <h3 className="mb-1 font-semibold text-casino-text-primary">
                Big / Small Bets
              </h3>
              <ul className="list-inside list-disc space-y-1">
                <li>
                  Big (5–9) pays <strong>2x</strong>
                </li>
                <li>
                  Small (0–4) pays <strong>2x</strong>
                </li>
              </ul>
            </section>

            {/* Service fee */}
            <section data-testid="rules-fee-section">
              <h3 className="mb-1 font-semibold text-casino-text-primary">
                Service Fee
              </h3>
              <p>
                A <strong>2%</strong> service fee is deducted from all winning
                payouts.
              </p>
            </section>
          </div>

          {/* Close button at bottom */}
          <button
            type="button"
            onClick={onClose}
            className="mt-5 w-full rounded-lg bg-casino-green py-2.5 text-sm font-semibold text-white hover:opacity-90 casino-transition"
            data-testid="rules-close-btn"
          >
            Close
          </button>
        </div>
      </div>
    </>
  );
}
