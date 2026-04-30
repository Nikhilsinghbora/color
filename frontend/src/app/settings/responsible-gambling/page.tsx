'use client';

import { useEffect, useState, FormEvent } from 'react';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import type { DepositLimit, LimitPeriod, SelfExclusionRequest } from '@/types';

type ToastType = 'success' | 'error';

interface Toast {
  id: number;
  type: ToastType;
  message: string;
}

let toastId = 0;

const LIMIT_PERIODS: { value: LimitPeriod; label: string }[] = [
  { value: 'daily', label: 'Daily' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'monthly', label: 'Monthly' },
];

const EXCLUSION_DURATIONS: { value: SelfExclusionRequest['duration']; label: string }[] = [
  { value: '24h', label: '24 Hours' },
  { value: '7d', label: '7 Days' },
  { value: '30d', label: '30 Days' },
  { value: 'permanent', label: 'Permanent' },
];

export default function ResponsibleGamblingPage() {
  useAuthGuard();

  const [limits, setLimits] = useState<DepositLimit[]>([]);
  const [isLoadingLimits, setIsLoadingLimits] = useState(true);
  const [limitAmounts, setLimitAmounts] = useState<Record<LimitPeriod, string>>({
    daily: '',
    weekly: '',
    monthly: '',
  });
  const [limitErrors, setLimitErrors] = useState<Record<LimitPeriod, string>>({
    daily: '',
    weekly: '',
    monthly: '',
  });
  const [savingLimit, setSavingLimit] = useState<LimitPeriod | null>(null);

  // Session limit
  const [sessionMinutes, setSessionMinutes] = useState('');
  const [sessionError, setSessionError] = useState('');
  const [isSavingSession, setIsSavingSession] = useState(false);

  // Self-exclusion
  const [exclusionDuration, setExclusionDuration] = useState<SelfExclusionRequest['duration']>('24h');
  const [showExclusionDialog, setShowExclusionDialog] = useState(false);
  const [isExcluding, setIsExcluding] = useState(false);

  // Loss warning modal
  const [showLossWarning, setShowLossWarning] = useState(false);

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
    async function fetchLimits() {
      setIsLoadingLimits(true);
      try {
        const { data } = await apiClient.get<DepositLimit[]>(
          '/responsible-gambling/deposit-limit',
        );
        setLimits(data);
        // Pre-fill current limit amounts
        const amounts: Record<LimitPeriod, string> = { daily: '', weekly: '', monthly: '' };
        for (const limit of data) {
          amounts[limit.period] = limit.amount;
        }
        setLimitAmounts(amounts);
      } catch {
        // Silently handle — limits will show as empty
      } finally {
        setIsLoadingLimits(false);
      }
    }
    fetchLimits();
  }, []);

  async function handleSetLimit(period: LimitPeriod, e: FormEvent) {
    e.preventDefault();
    setLimitErrors((prev) => ({ ...prev, [period]: '' }));

    const amt = limitAmounts[period].trim();
    if (!amt || isNaN(Number(amt)) || Number(amt) <= 0) {
      setLimitErrors((prev) => ({ ...prev, [period]: 'Please enter a valid amount' }));
      return;
    }

    setSavingLimit(period);
    try {
      const { data } = await apiClient.post<DepositLimit>(
        '/responsible-gambling/deposit-limit',
        { period, amount: amt },
      );
      setLimits((prev) => {
        const updated = prev.filter((l) => l.period !== period);
        return [...updated, data];
      });
      addToast('success', `${period.charAt(0).toUpperCase() + period.slice(1)} deposit limit set to $${amt}`);
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        setLimitErrors((prev) => ({ ...prev, [period]: getErrorMessage(apiErr.code, apiErr.message) }));
      } else {
        setLimitErrors((prev) => ({ ...prev, [period]: 'Failed to set limit. Please try again.' }));
      }
    } finally {
      setSavingLimit(null);
    }
  }

  async function handleSetSessionLimit(e: FormEvent) {
    e.preventDefault();
    setSessionError('');

    const mins = sessionMinutes.trim();
    if (!mins || isNaN(Number(mins)) || Number(mins) <= 0) {
      setSessionError('Please enter a valid number of minutes');
      return;
    }

    setIsSavingSession(true);
    try {
      await apiClient.post('/responsible-gambling/session-limit', {
        duration_minutes: Number(mins),
      });
      addToast('success', `Session limit set to ${mins} minutes`);
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        setSessionError(getErrorMessage(apiErr.code, apiErr.message));
      } else {
        setSessionError('Failed to set session limit. Please try again.');
      }
    } finally {
      setIsSavingSession(false);
    }
  }

  async function handleSelfExclude() {
    setIsExcluding(true);
    try {
      await apiClient.post('/responsible-gambling/self-exclude', {
        duration: exclusionDuration,
      });
      addToast('success', `Self-exclusion activated for ${EXCLUSION_DURATIONS.find((d) => d.value === exclusionDuration)?.label}`);
      setShowExclusionDialog(false);
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        addToast('error', getErrorMessage(apiErr.code, apiErr.message));
      } else {
        addToast('error', 'Failed to activate self-exclusion. Please try again.');
      }
    } finally {
      setIsExcluding(false);
    }
  }

  function handleAcknowledgeLossWarning() {
    setShowLossWarning(false);
  }

  function getCurrentLimit(period: LimitPeriod): DepositLimit | undefined {
    return limits.find((l) => l.period === period);
  }

  return (
    <main className="min-h-screen bg-background px-4 py-6">
      {/* Toast notifications */}
      <div aria-live="polite" className="fixed right-4 top-4 z-50 flex flex-col gap-2">
        {toasts.map((toast) => (
          <div
            key={toast.id}
            role="status"
            className={`rounded-md px-4 py-3 text-sm font-medium shadow-lg ${
              toast.type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
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

      {/* Loss warning modal */}
      {showLossWarning && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Loss warning"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        >
          <div className="mx-4 max-w-md rounded-lg bg-card p-6 shadow-xl">
            <h2 className="text-lg font-bold text-card-foreground mb-4">Loss Warning</h2>
            <p className="text-sm text-muted-foreground mb-6">
              You have reached your loss threshold. Please take a moment to review your gambling activity.
              You must acknowledge this warning before placing any further bets.
            </p>
            <button
              type="button"
              onClick={handleAcknowledgeLossWarning}
              className="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90"
            >
              I Acknowledge
            </button>
          </div>
        </div>
      )}

      {/* Self-exclusion confirmation dialog */}
      {showExclusionDialog && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Self-exclusion confirmation"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50"
        >
          <div className="mx-4 max-w-md rounded-lg bg-card p-6 shadow-xl">
            <h2 className="text-lg font-bold text-card-foreground mb-4">Confirm Self-Exclusion</h2>
            <p className="text-sm text-muted-foreground mb-2">
              You are about to self-exclude for{' '}
              <strong>{EXCLUSION_DURATIONS.find((d) => d.value === exclusionDuration)?.label}</strong>.
            </p>
            <p className="text-sm text-muted-foreground mb-6">
              During this period, you will not be able to place any bets or access game features.
              {exclusionDuration === 'permanent' && ' This action cannot be reversed.'}
            </p>
            <div className="flex gap-3">
              <button
                type="button"
                onClick={() => setShowExclusionDialog(false)}
                className="flex-1 rounded-md border border-border px-4 py-2 font-medium text-foreground hover:bg-muted"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleSelfExclude}
                disabled={isExcluding}
                className="flex-1 rounded-md bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isExcluding ? 'Processing…' : 'Confirm Exclusion'}
              </button>
            </div>
          </div>
        </div>
      )}

      <section aria-label="Responsible gambling settings" className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-bold text-foreground text-center mb-6">Responsible Gambling</h1>

        {/* Deposit limits */}
        <section aria-label="Deposit limits" className="mb-8">
          <h2 className="text-lg font-semibold text-foreground mb-4">Deposit Limits</h2>
          {isLoadingLimits ? (
            <div className="flex justify-center py-4" aria-label="Loading limits">
              <div className="h-6 w-6 animate-spin rounded-full border-4 border-primary border-t-transparent" role="status">
                <span className="sr-only">Loading…</span>
              </div>
            </div>
          ) : (
            <div className="space-y-4">
              {LIMIT_PERIODS.map(({ value: period, label }) => {
                const current = getCurrentLimit(period);
                return (
                  <form
                    key={period}
                    onSubmit={(e) => handleSetLimit(period, e)}
                    className="rounded-lg border border-border bg-card p-4"
                  >
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-sm font-semibold text-card-foreground">{label} Limit</h3>
                      {current && (
                        <span className="text-xs text-muted-foreground">
                          Used: ${current.current_usage} / ${current.amount}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <label htmlFor={`limit-${period}`} className="sr-only">
                        {label} deposit limit amount
                      </label>
                      <input
                        id={`limit-${period}`}
                        type="number"
                        min="0.01"
                        step="0.01"
                        value={limitAmounts[period]}
                        onChange={(e) =>
                          setLimitAmounts((prev) => ({ ...prev, [period]: e.target.value }))
                        }
                        placeholder="0.00"
                        className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-foreground text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                        aria-describedby={limitErrors[period] ? `limit-error-${period}` : undefined}
                      />
                      <button
                        type="submit"
                        disabled={savingLimit === period}
                        className="rounded-md bg-primary px-4 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
                      >
                        {savingLimit === period ? 'Saving…' : 'Set'}
                      </button>
                    </div>
                    {limitErrors[period] && (
                      <p id={`limit-error-${period}`} role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
                        {limitErrors[period]}
                      </p>
                    )}
                  </form>
                );
              })}
            </div>
          )}
        </section>

        {/* Session limit */}
        <section aria-label="Session time limit" className="mb-8 rounded-lg border border-border bg-card p-6">
          <h2 className="text-lg font-semibold text-card-foreground mb-4">Session Time Limit</h2>
          <form onSubmit={handleSetSessionLimit}>
            <label htmlFor="session-minutes" className="block text-sm font-medium text-muted-foreground">
              Duration (minutes)
            </label>
            <input
              id="session-minutes"
              type="number"
              min="1"
              step="1"
              value={sessionMinutes}
              onChange={(e) => setSessionMinutes(e.target.value)}
              placeholder="e.g. 60"
              className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              aria-describedby={sessionError ? 'session-error' : undefined}
            />
            {sessionError && (
              <p id="session-error" role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
                {sessionError}
              </p>
            )}
            <button
              type="submit"
              disabled={isSavingSession}
              className="mt-4 w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isSavingSession ? 'Saving…' : 'Set Session Limit'}
            </button>
          </form>
        </section>

        {/* Self-exclusion */}
        <section aria-label="Self-exclusion" className="rounded-lg border border-red-200 bg-card p-6 dark:border-red-900">
          <h2 className="text-lg font-semibold text-card-foreground mb-2">Self-Exclusion</h2>
          <p className="text-sm text-muted-foreground mb-4">
            If you feel you need a break from gambling, you can temporarily or permanently exclude yourself from the platform.
          </p>
          <div className="mb-4">
            <label htmlFor="exclusion-duration" className="block text-sm font-medium text-muted-foreground mb-1">
              Exclusion Duration
            </label>
            <select
              id="exclusion-duration"
              value={exclusionDuration}
              onChange={(e) => setExclusionDuration(e.target.value as SelfExclusionRequest['duration'])}
              className="w-full rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
            >
              {EXCLUSION_DURATIONS.map((d) => (
                <option key={d.value} value={d.value}>{d.label}</option>
              ))}
            </select>
          </div>
          <button
            type="button"
            onClick={() => setShowExclusionDialog(true)}
            className="w-full rounded-md bg-red-600 px-4 py-2 font-medium text-white hover:bg-red-700"
          >
            Request Self-Exclusion
          </button>
        </section>
      </section>
    </main>
  );
}
