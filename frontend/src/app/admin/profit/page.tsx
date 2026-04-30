'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdminGuard } from '@/hooks/useAdminGuard';
import { apiClient } from '@/lib/api-client';
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ReferenceLine,
  ResponsiveContainer,
  BarChart,
  Bar,
} from 'recharts';

interface ProfitSettings {
  id: string;
  house_profit_percentage: string;
  winners_pool_percentage: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

interface ProfitGraphPoint {
  date: string;
  total_bets: number;
  total_payouts: number;
  house_profit: number;
  profit_margin_pct: number;
  rounds_played: number;
}

interface ProfitGraphData {
  points: ProfitGraphPoint[];
  period: string;
  target_margin_pct: number;
  summary_total_bets: number;
  summary_total_payouts: number;
  summary_total_profit: number;
  summary_avg_margin_pct: number;
}

export default function AdminProfitPage() {
  useAdminGuard();

  // ── Settings state ──
  const [settings, setSettings] = useState<ProfitSettings | null>(null);
  const [housePercent, setHousePercent] = useState('20');
  const [winnersPercent, setWinnersPercent] = useState('80');
  const [settingsLoading, setSettingsLoading] = useState(true);
  const [settingsSaving, setSettingsSaving] = useState(false);
  const [settingsError, setSettingsError] = useState<string | null>(null);
  const [settingsSuccess, setSettingsSuccess] = useState<string | null>(null);

  // ── Graph state ──
  const [graphData, setGraphData] = useState<ProfitGraphData | null>(null);
  const [graphPeriod, setGraphPeriod] = useState<'daily' | 'weekly' | 'monthly'>('daily');
  const [graphDays, setGraphDays] = useState(30);
  const [graphLoading, setGraphLoading] = useState(true);
  const [graphError, setGraphError] = useState<string | null>(null);

  // ── Fetch settings ──
  useEffect(() => {
    (async () => {
      setSettingsLoading(true);
      try {
        const { data } = await apiClient.get<ProfitSettings>('/admin/profit-settings');
        setSettings(data);
        setHousePercent(data.house_profit_percentage);
        setWinnersPercent(data.winners_pool_percentage);
      } catch {
        // No settings yet — use defaults
        setHousePercent('20');
        setWinnersPercent('80');
      } finally {
        setSettingsLoading(false);
      }
    })();
  }, []);

  // ── Fetch graph data ──
  const fetchGraph = useCallback(async () => {
    setGraphLoading(true);
    setGraphError(null);
    try {
      const { data } = await apiClient.get<ProfitGraphData>('/admin/profit-graph', {
        params: { period: graphPeriod, days: graphDays },
      });
      // Convert string decimals to numbers for recharts
      const points = data.points.map((p) => ({
        ...p,
        total_bets: Number(p.total_bets),
        total_payouts: Number(p.total_payouts),
        house_profit: Number(p.house_profit),
        profit_margin_pct: Number(p.profit_margin_pct),
      }));
      setGraphData({
        ...data,
        points,
        target_margin_pct: Number(data.target_margin_pct),
        summary_total_bets: Number(data.summary_total_bets),
        summary_total_payouts: Number(data.summary_total_payouts),
        summary_total_profit: Number(data.summary_total_profit),
        summary_avg_margin_pct: Number(data.summary_avg_margin_pct),
      });
    } catch {
      setGraphError('Failed to load profit graph data');
    } finally {
      setGraphLoading(false);
    }
  }, [graphPeriod, graphDays]);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  // ── Auto-calculate complement ──
  const handleHouseChange = (val: string) => {
    setHousePercent(val);
    const num = parseFloat(val);
    if (!isNaN(num) && num >= 0 && num <= 100) {
      setWinnersPercent((100 - num).toFixed(2));
    }
  };

  const handleWinnersChange = (val: string) => {
    setWinnersPercent(val);
    const num = parseFloat(val);
    if (!isNaN(num) && num >= 0 && num <= 100) {
      setHousePercent((100 - num).toFixed(2));
    }
  };

  // ── Save settings ──
  const handleSaveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    setSettingsSaving(true);
    setSettingsError(null);
    setSettingsSuccess(null);
    try {
      const { data } = await apiClient.post<ProfitSettings>('/admin/profit-settings', {
        house_profit_percentage: housePercent,
        winners_pool_percentage: winnersPercent,
      });
      setSettings(data);
      setSettingsSuccess('Profit margin updated. Takes effect from the next round.');
      fetchGraph(); // refresh graph
    } catch {
      setSettingsError('Failed to save profit settings. Ensure percentages sum to 100.');
    } finally {
      setSettingsSaving(false);
    }
  };

  return (
    <main className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6">Profit & Margin Management</h1>

      {/* ── Profit Settings Card ── */}
      <section className="border rounded-lg p-6 mb-8" aria-label="Profit margin settings">
        <h2 className="text-lg font-semibold mb-4">Profit / Distribution Split</h2>
        <p className="text-sm text-gray-500 mb-4">
          Set the house profit percentage. The remainder is the winner distribution pool.
          The game engine will pick outcomes that maintain this margin.
        </p>

        {settingsLoading ? (
          <p role="status">Loading settings...</p>
        ) : (
          <form onSubmit={handleSaveSettings} className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div>
                <label htmlFor="house-pct" className="block text-sm font-medium mb-1">
                  House Profit %
                </label>
                <input
                  id="house-pct"
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={housePercent}
                  onChange={(e) => handleHouseChange(e.target.value)}
                  className="border rounded px-3 py-2 w-full bg-[var(--bg-primary,#fff)] text-[var(--text-primary,#000)]"
                />
              </div>
              <div>
                <label htmlFor="winners-pct" className="block text-sm font-medium mb-1">
                  Winner Distribution %
                </label>
                <input
                  id="winners-pct"
                  type="number"
                  step="0.01"
                  min="0"
                  max="100"
                  value={winnersPercent}
                  onChange={(e) => handleWinnersChange(e.target.value)}
                  className="border rounded px-3 py-2 w-full bg-[var(--bg-primary,#fff)] text-[var(--text-primary,#000)]"
                />
              </div>
            </div>

            {/* Visual bar */}
            <div className="w-full h-8 rounded-full overflow-hidden flex" aria-hidden="true">
              <div
                className="bg-red-500 flex items-center justify-center text-xs text-white font-medium transition-all"
                style={{ width: `${Math.min(100, Math.max(0, parseFloat(housePercent) || 0))}%` }}
              >
                {housePercent}%
              </div>
              <div
                className="bg-green-500 flex items-center justify-center text-xs text-white font-medium transition-all"
                style={{ width: `${Math.min(100, Math.max(0, parseFloat(winnersPercent) || 0))}%` }}
              >
                {winnersPercent}%
              </div>
            </div>

            {settingsError && <p role="alert" className="text-red-600 text-sm">{settingsError}</p>}
            {settingsSuccess && <p role="status" className="text-green-600 text-sm">{settingsSuccess}</p>}

            <button
              type="submit"
              disabled={settingsSaving}
              className="bg-blue-600 text-white px-6 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
            >
              {settingsSaving ? 'Saving...' : 'Save Margin Settings'}
            </button>

            {settings && (
              <p className="text-xs text-gray-400 mt-2">
                Last updated: {new Date(settings.updated_at).toLocaleString()}
              </p>
            )}
          </form>
        )}
      </section>

      {/* ── Summary Cards ── */}
      {graphData && (
        <section className="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8" aria-label="Profit summary">
          <div className="border rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase">Total Bets</p>
            <p className="text-xl font-bold">${graphData.summary_total_bets.toLocaleString()}</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase">Total Payouts</p>
            <p className="text-xl font-bold">${graphData.summary_total_payouts.toLocaleString()}</p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase">Total Profit</p>
            <p className={`text-xl font-bold ${graphData.summary_total_profit >= 0 ? 'text-green-600' : 'text-red-600'}`}>
              ${graphData.summary_total_profit.toLocaleString()}
            </p>
          </div>
          <div className="border rounded-lg p-4">
            <p className="text-xs text-gray-500 uppercase">Avg Margin</p>
            <p className={`text-xl font-bold ${graphData.summary_avg_margin_pct >= graphData.target_margin_pct ? 'text-green-600' : 'text-yellow-600'}`}>
              {graphData.summary_avg_margin_pct}%
            </p>
            <p className="text-xs text-gray-400">Target: {graphData.target_margin_pct}%</p>
          </div>
        </section>
      )}

      {/* ── Graph Controls ── */}
      <section className="border rounded-lg p-6 mb-8" aria-label="Profit margin graph">
        <div className="flex flex-wrap items-center gap-4 mb-6">
          <h2 className="text-lg font-semibold">Profit & Margin Graph</h2>
          <div className="flex gap-2 ml-auto">
            {(['daily', 'weekly', 'monthly'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setGraphPeriod(p)}
                className={`px-3 py-1 rounded text-sm ${
                  graphPeriod === p
                    ? 'bg-blue-600 text-white'
                    : 'border hover:bg-gray-100'
                }`}
              >
                {p.charAt(0).toUpperCase() + p.slice(1)}
              </button>
            ))}
          </div>
          <select
            aria-label="Time range"
            value={graphDays}
            onChange={(e) => setGraphDays(Number(e.target.value))}
            className="border rounded px-2 py-1 text-sm bg-[var(--bg-primary,#fff)] text-[var(--text-primary,#000)]"
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={180}>Last 180 days</option>
            <option value={365}>Last year</option>
          </select>
        </div>

        {graphLoading && <p role="status">Loading graph...</p>}
        {graphError && <p role="alert" className="text-red-600">{graphError}</p>}

        {graphData && !graphLoading && graphData.points.length > 0 && (
          <div className="space-y-8">
            {/* Margin % line chart */}
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">Profit Margin %</h3>
              <ResponsiveContainer width="100%" height={300}>
                <LineChart data={graphData.points}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis unit="%" tick={{ fontSize: 12 }} />
                  <Tooltip
                    formatter={(value: number) => [`${value}%`, 'Margin']}
                    labelFormatter={(label) => `Date: ${label}`}
                  />
                  <Legend />
                  <ReferenceLine
                    y={graphData.target_margin_pct}
                    stroke="#ef4444"
                    strokeDasharray="5 5"
                    label={{ value: `Target ${graphData.target_margin_pct}%`, position: 'right', fontSize: 12 }}
                  />
                  <Line
                    type="monotone"
                    dataKey="profit_margin_pct"
                    name="Actual Margin %"
                    stroke="#3b82f6"
                    strokeWidth={2}
                    dot={{ r: 3 }}
                    activeDot={{ r: 5 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* Bets vs Payouts bar chart */}
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">Bets vs Payouts</h3>
              <ResponsiveContainer width="100%" height={300}>
                <BarChart data={graphData.points}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip
                    formatter={(value: number, name: string) => [
                      `$${value.toLocaleString()}`,
                      name,
                    ]}
                  />
                  <Legend />
                  <Bar dataKey="total_bets" name="Total Bets" fill="#6366f1" />
                  <Bar dataKey="total_payouts" name="Total Payouts" fill="#f59e0b" />
                  <Bar dataKey="house_profit" name="House Profit" fill="#22c55e" />
                </BarChart>
              </ResponsiveContainer>
            </div>

            {/* Rounds played */}
            <div>
              <h3 className="text-sm font-medium text-gray-500 mb-2">Rounds Played</h3>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={graphData.points}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Bar dataKey="rounds_played" name="Rounds" fill="#8b5cf6" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        )}

        {graphData && !graphLoading && graphData.points.length === 0 && (
          <p className="text-gray-500 text-center py-12">
            No completed rounds in this time range. Play some rounds to see data here.
          </p>
        )}
      </section>
    </main>
  );
}
