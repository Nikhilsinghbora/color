'use client';

import { useEffect, useState, FormEvent } from 'react';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { useWalletStore } from '@/stores/wallet-store';
import { parseApiError, getErrorMessage } from '@/lib/api-client';

type ToastType = 'success' | 'error';

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

let toastId = 0;

export default function WalletPage() {
  useAuthGuard();

  const balance = useWalletStore((s) => s.balance);
  const transactions = useWalletStore((s) => s.transactions);
  const hasMoreTransactions = useWalletStore((s) => s.hasMoreTransactions);
  const transactionPage = useWalletStore((s) => s.transactionPage);
  const isLoading = useWalletStore((s) => s.isLoading);
  const fetchBalance = useWalletStore((s) => s.fetchBalance);
  const fetchTransactions = useWalletStore((s) => s.fetchTransactions);
  const deposit = useWalletStore((s) => s.deposit);
  const withdraw = useWalletStore((s) => s.withdraw);

  const [depositAmount, setDepositAmount] = useState('');
  const [depositError, setDepositError] = useState('');
  const [isDepositing, setIsDepositing] = useState(false);

  const [withdrawAmount, setWithdrawAmount] = useState('');
  const [withdrawError, setWithdrawError] = useState('');
  const [isWithdrawing, setIsWithdrawing] = useState(false);

  const [toasts, setToasts] = useState<Toast[]>([]);

  function addToast(type: ToastType, message: string) {
    const id = ++toastId;
    setToasts((prev) => [...prev, { id, type, message }]);
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 4000);
  }

  function removeToast(id: number) {
    setToasts((prev) => prev.filter((t) => t.id !== id));
  }

  useEffect(() => {
    fetchBalance();
    fetchTransactions(1);
  }, [fetchBalance, fetchTransactions]);

  async function handleDeposit(e: FormEvent) {
    e.preventDefault();
    setDepositError('');

    const amt = depositAmount.trim();
    if (!amt || isNaN(Number(amt)) || Number(amt) <= 0) {
      setDepositError('Please enter a valid deposit amount');
      return;
    }

    setIsDepositing(true);
    try {
      // Mock Stripe token — in production this would come from Stripe Elements
      await deposit(amt, 'mock_stripe_token');
      addToast('success', `Successfully deposited $${amt}`);
      setDepositAmount('');
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        setDepositError(getErrorMessage(apiErr.code, apiErr.message));
      } else {
        setDepositError('Deposit failed. Please try again.');
      }
    } finally {
      setIsDepositing(false);
    }
  }

  async function handleWithdraw(e: FormEvent) {
    e.preventDefault();
    setWithdrawError('');

    const amt = withdrawAmount.trim();
    if (!amt || isNaN(Number(amt)) || Number(amt) <= 0) {
      setWithdrawError('Please enter a valid withdrawal amount');
      return;
    }

    setIsWithdrawing(true);
    try {
      await withdraw(amt);
      addToast('success', `Successfully withdrew $${amt}`);
      setWithdrawAmount('');
      // Refresh balance and transactions after withdrawal
      await fetchBalance();
      await fetchTransactions(1);
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        const msg = getErrorMessage(apiErr.code, apiErr.message);
        if (apiErr.code === 'INSUFFICIENT_BALANCE') {
          setWithdrawError(`${msg}. Current balance: $${balance ?? '0.00'}`);
        } else {
          setWithdrawError(msg);
        }
      } else {
        setWithdrawError('Withdrawal failed. Please try again.');
      }
    } finally {
      setIsWithdrawing(false);
    }
  }

  function handleLoadMore() {
    fetchTransactions(transactionPage + 1);
  }

  function formatTimestamp(iso: string): string {
    try {
      return new Date(iso).toLocaleString();
    } catch {
      return iso;
    }
  }

  const typeBadgeClass: Record<string, string> = {
    deposit: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-200',
    withdrawal: 'bg-red-100 text-red-800 dark:bg-red-900 dark:text-red-200',
    bet_debit: 'bg-orange-100 text-orange-800 dark:bg-orange-900 dark:text-orange-200',
    payout_credit: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-200',
  };

  const typeLabel: Record<string, string> = {
    deposit: 'Deposit',
    withdrawal: 'Withdrawal',
    bet_debit: 'Bet',
    payout_credit: 'Payout',
  };

  return (
    <main className="min-h-screen bg-background px-4 py-6">
      {/* Toast notifications */}
      <div
        aria-live="polite"
        className="fixed right-4 top-4 z-50 flex flex-col gap-2"
      >
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`rounded-md px-4 py-3 text-sm font-medium shadow-lg transition-all ${
              toast.type === 'success'
                ? 'bg-green-500 text-white'
                : 'bg-red-500 text-white'
            }`}
          >
            <div className="flex items-center justify-between gap-3">
              <span>{toast.message}</span>
              <button
                type="button"
                onClick={() => removeToast(toast.id)}
                aria-label="Dismiss notification"
                className="text-white/80 hover:text-white"
              >
                ✕
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Balance display */}
      <section aria-label="Wallet balance" className="mx-auto mb-8 max-w-2xl text-center">
        <h1 className="text-2xl font-bold text-foreground">Wallet</h1>
        <div className="mt-4 rounded-lg border border-border bg-card p-6">
          <p className="text-sm text-muted-foreground">Current Balance</p>
          <p data-testid="wallet-balance" className="mt-1 text-4xl font-bold text-foreground">
            ${balance ?? '—'}
          </p>
        </div>
      </section>

      <div className="mx-auto max-w-2xl grid gap-6 md:grid-cols-2">
        {/* Deposit section */}
        <section aria-label="Deposit funds" className="rounded-lg border border-border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold text-card-foreground">Deposit</h2>
          <form onSubmit={handleDeposit}>
            <label htmlFor="deposit-amount" className="block text-sm font-medium text-muted-foreground">
              Amount ($)
            </label>
            <input
              id="deposit-amount"
              type="number"
              min="0.01"
              step="0.01"
              value={depositAmount}
              onChange={(e) => setDepositAmount(e.target.value)}
              placeholder="0.00"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              aria-describedby={depositError ? 'deposit-error' : undefined}
            />
            {depositError && (
              <p id="deposit-error" role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
                {depositError}
              </p>
            )}
            <button
              type="submit"
              disabled={isDepositing}
              className="mt-4 w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isDepositing ? 'Processing…' : 'Deposit'}
            </button>
          </form>
        </section>

        {/* Withdrawal section */}
        <section aria-label="Withdraw funds" className="rounded-lg border border-border bg-card p-6">
          <h2 className="mb-4 text-lg font-semibold text-card-foreground">Withdraw</h2>
          <form onSubmit={handleWithdraw}>
            <label htmlFor="withdraw-amount" className="block text-sm font-medium text-muted-foreground">
              Amount ($)
            </label>
            <input
              id="withdraw-amount"
              type="number"
              min="0.01"
              step="0.01"
              value={withdrawAmount}
              onChange={(e) => setWithdrawAmount(e.target.value)}
              placeholder="0.00"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              aria-describedby={withdrawError ? 'withdraw-error' : undefined}
            />
            {withdrawError && (
              <p id="withdraw-error" role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
                {withdrawError}
              </p>
            )}
            <button
              type="submit"
              disabled={isWithdrawing}
              className="mt-4 w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isWithdrawing ? 'Processing…' : 'Withdraw'}
            </button>
          </form>
        </section>
      </div>

      {/* Transaction history */}
      <section aria-label="Transaction history" className="mx-auto mt-8 max-w-2xl">
        <h2 className="mb-4 text-lg font-semibold text-foreground">Transaction History</h2>
        {transactions.length === 0 && !isLoading ? (
          <p className="text-sm text-muted-foreground">No transactions yet.</p>
        ) : (
          <ul className="space-y-3" role="list">
            {transactions.map((tx) => (
              <li
                key={tx.id}
                className="flex items-center justify-between rounded-lg border border-border bg-card px-4 py-3"
              >
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-block rounded-full px-2 py-0.5 text-xs font-semibold ${
                      typeBadgeClass[tx.type] ?? 'bg-gray-100 text-gray-800'
                    }`}
                  >
                    {typeLabel[tx.type] ?? tx.type}
                  </span>
                  <span className="text-sm font-medium text-card-foreground">${tx.amount}</span>
                </div>
                <time className="text-xs text-muted-foreground" dateTime={tx.created_at}>
                  {formatTimestamp(tx.created_at)}
                </time>
              </li>
            ))}
          </ul>
        )}

        {hasMoreTransactions && (
          <div className="mt-4 text-center">
            <button
              type="button"
              onClick={handleLoadMore}
              disabled={isLoading}
              className="rounded-md border border-border px-4 py-2 text-sm font-medium text-foreground hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? 'Loading…' : 'Load more'}
            </button>
          </div>
        )}
      </section>
    </main>
  );
}
