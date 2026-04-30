'use client';

import { useState, useEffect, useCallback } from 'react';
import Link from 'next/link';
import { useAdminGuard } from '@/hooks/useAdminGuard';
import { apiClient } from '@/lib/api-client';
import type { AdminDashboardMetrics } from '@/types';

const PERIODS = ['daily', 'weekly', 'monthly', 'all_time'] as const;

const ADMIN_NAV = [
  { href: '/admin', label: 'Dashboard' },
  { href: '/admin/profit', label: 'Profit & Margins' },
  { href: '/admin/config', label: 'Game Config' },
  { href: '/admin/players', label: 'Players' },
  { href: '/admin/audit', label: 'Audit Logs' },
  { href: '/admin/rng-audit', label: 'RNG Audit' },
] as const;

export default function AdminDashboardPage() {
  useAdminGuard();

  const [metrics, setMetrics] = useState<AdminDashboardMetrics | null>(null);
  const [period, setPeriod] = useState<string>('daily');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchMetrics = useCallback(async (p: string) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<AdminDashboardMetrics>('/admin/dashboard', {
        params: { period: p },
      });
      setMetrics(data);
    } catch {
      setError('Failed to load dashboard metrics');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchMetrics(period);
  }, [period, fetchMetrics]);

  return (
    <main className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-4">Admin Dashboard</h1>

      {/* Admin navigation */}
      <nav className="flex flex-wrap gap-2 mb-6" aria-label="Admin navigation">
        {ADMIN_NAV.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`px-3 py-1.5 rounded text-sm border ${
              item.href === '/admin'
                ? 'bg-blue-600 text-white border-blue-600'
                : 'hover:bg-gray-100 border-gray-300'
            }`}
          >
            {item.label}
          </Link>
        ))}
      </nav>

      <div className="mb-6">
        <label htmlFor="period-select" className="sr-only">Select period</label>
        <select
          id="period-select"
          aria-label="Select dashboard period"
          value={period}
          onChange={(e) => setPeriod(e.target.value)}
          className="border rounded px-3 py-2 bg-[var(--bg-primary,#fff)] text-[var(--text-primary,#000)]"
        >
          {PERIODS.map((p) => (
            <option key={p} value={p}>
              {p.replace('_', ' ').replace(/\b\w/g, (c) => c.toUpperCase())}
            </option>
          ))}
        </select>
      </div>

      {loading && <p role="status">Loading metrics...</p>}
      {error && <p role="alert" className="text-red-600">{error}</p>}

      {metrics && !loading && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4" role="region" aria-label="Dashboard metrics">
          <div className="border rounded p-4">
            <p className="text-sm text-gray-500">Active Players</p>
            <p className="text-2xl font-bold">{metrics.active_players}</p>
          </div>
          <div className="border rounded p-4">
            <p className="text-sm text-gray-500">Total Bets</p>
            <p className="text-2xl font-bold">${metrics.total_bets}</p>
          </div>
          <div className="border rounded p-4">
            <p className="text-sm text-gray-500">Total Payouts</p>
            <p className="text-2xl font-bold">${metrics.total_payouts}</p>
          </div>
          <div className="border rounded p-4">
            <p className="text-sm text-gray-500">Revenue</p>
            <p className="text-2xl font-bold">${metrics.revenue}</p>
          </div>
        </div>
      )}
    </main>
  );
}
