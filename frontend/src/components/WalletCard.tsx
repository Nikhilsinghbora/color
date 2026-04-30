'use client';

import { useRouter } from 'next/navigation';
import { useWalletStore } from '@/stores/wallet-store';

export default function WalletCard() {
  const router = useRouter();
  const balance = useWalletStore((s) => s.balance);

  return (
    <section aria-label="Wallet card" className="mx-4 mt-4">
      <div className="casino-card flex items-center justify-between px-4 py-3">
        {/* Wallet icon + balance */}
        <div className="flex items-center gap-3">
          <span className="text-2xl" aria-hidden="true">
            💰
          </span>
          <div className="flex flex-col">
            <span className="text-[10px] uppercase tracking-wider text-casino-text-muted">
              Balance
            </span>
            <span
              className="text-lg font-bold text-casino-text-primary"
              data-testid="wallet-balance"
            >
              ₹{balance ?? '0.00'}
            </span>
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => router.push('/wallet')}
            className="casino-transition rounded-lg bg-casino-card px-3 py-1.5 text-xs font-semibold text-casino-text-secondary border border-casino-card-border"
            aria-label="Withdraw funds"
          >
            Withdraw
          </button>
          <button
            type="button"
            onClick={() => router.push('/wallet')}
            className="casino-transition rounded-lg bg-casino-green px-3 py-1.5 text-xs font-semibold text-white"
            aria-label="Deposit funds"
          >
            Deposit
          </button>
        </div>
      </div>
    </section>
  );
}
