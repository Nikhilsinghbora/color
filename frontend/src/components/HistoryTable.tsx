'use client';

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api-client';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GameHistoryEntry {
  period_number: string;
  winning_number: number;
  winning_color: string;
  big_small_label: 'Big' | 'Small';
  completed_at: string;
}

export interface MyHistoryEntry {
  period_number: string;
  bet_type: string;
  bet_amount: string;
  is_winner: boolean;
  payout_amount: string;
  created_at: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  size: number;
  has_more: boolean;
}

export interface HistoryTableProps {
  gameModeId: string;
}

type SubTab = 'game' | 'chart' | 'my';

// ---------------------------------------------------------------------------
// Color helpers
// ---------------------------------------------------------------------------

/** Number-to-color mapping per the game rules. */
const NUMBER_COLORS: Record<number, string[]> = {
  0: ['red', 'violet'],
  1: ['green'],
  2: ['red'],
  3: ['green'],
  4: ['red'],
  5: ['green', 'violet'],
  6: ['red'],
  7: ['green'],
  8: ['red'],
  9: ['green'],
};

function getNumberBg(winningColor: string): string {
  switch (winningColor.toLowerCase()) {
    case 'green':
      return 'bg-casino-green text-white';
    case 'red':
      return 'bg-casino-red text-white';
    case 'violet':
      return 'bg-casino-violet text-white';
    default:
      return 'bg-gray-500 text-white';
  }
}

function getColorDotClass(color: string): string {
  switch (color.toLowerCase()) {
    case 'green':
      return 'bg-casino-green';
    case 'red':
      return 'bg-casino-red';
    case 'violet':
      return 'bg-casino-violet';
    default:
      return 'bg-gray-500';
  }
}

// ---------------------------------------------------------------------------
// Pagination component
// ---------------------------------------------------------------------------

function Pagination({
  page,
  totalPages,
  onPageChange,
}: {
  page: number;
  totalPages: number;
  onPageChange: (p: number) => void;
}) {
  if (totalPages <= 1) return null;

  // Show up to 5 page numbers centered around current page
  const pages: number[] = [];
  const start = Math.max(1, page - 2);
  const end = Math.min(totalPages, start + 4);
  for (let i = start; i <= end; i++) {
    pages.push(i);
  }

  return (
    <nav aria-label="Pagination" className="flex items-center justify-center gap-1 pt-3">
      <button
        type="button"
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        aria-label="Previous page"
        className="rounded px-2 py-1 text-xs text-casino-text-muted hover:text-casino-text-primary disabled:opacity-40 disabled:cursor-not-allowed"
      >
        ‹
      </button>
      {pages.map((p) => (
        <button
          key={p}
          type="button"
          onClick={() => onPageChange(p)}
          aria-current={p === page ? 'page' : undefined}
          className={`rounded px-2 py-1 text-xs font-semibold ${
            p === page
              ? 'bg-casino-green text-white'
              : 'text-casino-text-muted hover:text-casino-text-primary'
          }`}
        >
          {p}
        </button>
      ))}
      <button
        type="button"
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        aria-label="Next page"
        className="rounded px-2 py-1 text-xs text-casino-text-muted hover:text-casino-text-primary disabled:opacity-40 disabled:cursor-not-allowed"
      >
        ›
      </button>
    </nav>
  );
}

// ---------------------------------------------------------------------------
// Sub-tab: Game History
// ---------------------------------------------------------------------------

function GameHistoryTab({ gameModeId }: { gameModeId: string }) {
  const [data, setData] = useState<GameHistoryEntry[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const fetchData = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<PaginatedResponse<GameHistoryEntry>>(
        '/game/history',
        { params: { page: p, size: pageSize, mode_id: gameModeId } },
      );
      setData(res.data.items);
      setTotal(res.data.total);
      setPage(res.data.page);
    } catch {
      setError('Failed to load game history');
    } finally {
      setLoading(false);
    }
  }, [gameModeId]);

  useEffect(() => {
    fetchData(1);
  }, [fetchData]);

  const handlePageChange = (p: number) => {
    if (p >= 1 && p <= totalPages) {
      fetchData(p);
    }
  };

  if (loading && data.length === 0) {
    return <p className="py-4 text-center text-xs text-casino-text-muted">Loading...</p>;
  }

  if (error) {
    return <p className="py-4 text-center text-xs text-casino-red">{error}</p>;
  }

  if (data.length === 0) {
    return <p className="py-4 text-center text-xs text-casino-text-muted">No history yet</p>;
  }

  return (
    <div>
      <table className="w-full text-xs" role="table">
        <thead>
          <tr className="text-casino-text-muted">
            <th className="py-1.5 text-left font-medium">Period</th>
            <th className="py-1.5 text-center font-medium">Number</th>
            <th className="py-1.5 text-center font-medium">Big/Small</th>
            <th className="py-1.5 text-center font-medium">Color</th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry) => {
            const colors = NUMBER_COLORS[entry.winning_number] ?? [entry.winning_color];
            return (
              <tr
                key={entry.period_number}
                className="border-t border-casino-card-border"
              >
                <td className="py-2 text-left text-casino-text-secondary">
                  {entry.period_number}
                </td>
                <td className="py-2 text-center">
                  <span
                    className={`inline-flex h-6 w-6 items-center justify-center rounded-full text-[10px] font-bold ${getNumberBg(entry.winning_color)}`}
                  >
                    {entry.winning_number}
                  </span>
                </td>
                <td className="py-2 text-center text-casino-text-secondary">
                  {entry.big_small_label}
                </td>
                <td className="py-2 text-center">
                  <span className="inline-flex items-center gap-1">
                    {colors.map((c) => (
                      <span
                        key={c}
                        className={`inline-block h-3 w-3 rounded-full ${getColorDotClass(c)}`}
                        title={c}
                        aria-label={c}
                      />
                    ))}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} onPageChange={handlePageChange} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-tab: My History
// ---------------------------------------------------------------------------

function MyHistoryTab() {
  const [data, setData] = useState<MyHistoryEntry[]>([]);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const pageSize = 10;
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const fetchData = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const res = await apiClient.get<PaginatedResponse<MyHistoryEntry>>(
        '/game/my-history',
        { params: { page: p, size: pageSize } },
      );
      setData(res.data.items);
      setTotal(res.data.total);
      setPage(res.data.page);
    } catch {
      setError('Failed to load your history');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData(1);
  }, [fetchData]);

  const handlePageChange = (p: number) => {
    if (p >= 1 && p <= totalPages) {
      fetchData(p);
    }
  };

  if (loading && data.length === 0) {
    return <p className="py-4 text-center text-xs text-casino-text-muted">Loading...</p>;
  }

  if (error) {
    return <p className="py-4 text-center text-xs text-casino-red">{error}</p>;
  }

  if (data.length === 0) {
    return <p className="py-4 text-center text-xs text-casino-text-muted">No bets yet</p>;
  }

  return (
    <div>
      <table className="w-full text-xs" role="table">
        <thead>
          <tr className="text-casino-text-muted">
            <th className="py-1.5 text-left font-medium">Period</th>
            <th className="py-1.5 text-center font-medium">Type</th>
            <th className="py-1.5 text-center font-medium">Amount</th>
            <th className="py-1.5 text-center font-medium">Result</th>
            <th className="py-1.5 text-right font-medium">Payout</th>
          </tr>
        </thead>
        <tbody>
          {data.map((entry, idx) => (
            <tr
              key={`${entry.period_number}-${idx}`}
              className="border-t border-casino-card-border"
            >
              <td className="py-2 text-left text-casino-text-secondary">
                {entry.period_number}
              </td>
              <td className="py-2 text-center capitalize text-casino-text-secondary">
                {entry.bet_type}
              </td>
              <td className="py-2 text-center text-casino-text-secondary">
                ₹{entry.bet_amount}
              </td>
              <td className="py-2 text-center">
                <span
                  className={`font-semibold ${
                    entry.is_winner ? 'text-casino-green' : 'text-casino-red'
                  }`}
                >
                  {entry.is_winner ? 'Win' : 'Loss'}
                </span>
              </td>
              <td className="py-2 text-right text-casino-text-secondary">
                ₹{entry.payout_amount}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <Pagination page={page} totalPages={totalPages} onPageChange={handlePageChange} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-tab: Chart (placeholder)
// ---------------------------------------------------------------------------

function ChartTab() {
  return (
    <div className="flex flex-col items-center justify-center py-8">
      <span className="text-2xl" aria-hidden="true">📊</span>
      <p className="mt-2 text-xs text-casino-text-muted">
        Chart view coming soon
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main HistoryTable component
// ---------------------------------------------------------------------------

export default function HistoryTable({ gameModeId }: HistoryTableProps) {
  const [activeTab, setActiveTab] = useState<SubTab>('game');

  return (
    <section aria-label="History table" className="mx-auto w-full px-4">
      {/* Sub-tab bar */}
      <div className="flex gap-1" role="tablist">
        <button
          role="tab"
          aria-selected={activeTab === 'game'}
          onClick={() => setActiveTab('game')}
          className={`rounded-t-lg px-4 py-2 text-xs font-semibold transition-colors ${
            activeTab === 'game'
              ? 'bg-casino-card text-casino-text-primary'
              : 'text-casino-text-muted hover:text-casino-text-secondary'
          }`}
        >
          Game history
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'chart'}
          onClick={() => setActiveTab('chart')}
          className={`rounded-t-lg px-4 py-2 text-xs font-semibold transition-colors ${
            activeTab === 'chart'
              ? 'bg-casino-card text-casino-text-primary'
              : 'text-casino-text-muted hover:text-casino-text-secondary'
          }`}
        >
          Chart
        </button>
        <button
          role="tab"
          aria-selected={activeTab === 'my'}
          onClick={() => setActiveTab('my')}
          className={`rounded-t-lg px-4 py-2 text-xs font-semibold transition-colors ${
            activeTab === 'my'
              ? 'bg-casino-card text-casino-text-primary'
              : 'text-casino-text-muted hover:text-casino-text-secondary'
          }`}
        >
          My history
        </button>
      </div>

      {/* Tab content */}
      <div className="casino-card rounded-tl-none p-3">
        {activeTab === 'game' && (
          <div role="tabpanel" aria-label="Game history">
            <GameHistoryTab gameModeId={gameModeId} />
          </div>
        )}
        {activeTab === 'chart' && (
          <div role="tabpanel" aria-label="Chart">
            <ChartTab />
          </div>
        )}
        {activeTab === 'my' && (
          <div role="tabpanel" aria-label="My history">
            <MyHistoryTab />
          </div>
        )}
      </div>
    </section>
  );
}
