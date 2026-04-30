'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdminGuard } from '@/hooks/useAdminGuard';
import { apiClient } from '@/lib/api-client';
import type { RNGAuditEntry } from '@/types';

interface PaginatedRNGAudit {
  items: RNGAuditEntry[];
  total: number;
  page: number;
  size: number;
  has_more: boolean;
}

export default function AdminRNGAuditPage() {
  useAdminGuard();

  const [entries, setEntries] = useState<RNGAuditEntry[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEntries = useCallback(async (p: number) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<PaginatedRNGAudit>('/admin/rng-audit', {
        params: { page: p },
      });
      setEntries(data.items);
      setHasMore(data.has_more);
    } catch {
      setError('Failed to load RNG audit entries');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEntries(page);
  }, [page, fetchEntries]);

  return (
    <main className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6">RNG Audit</h1>

      {error && <p role="alert" className="text-red-600 mb-4">{error}</p>}
      {loading && <p role="status">Loading RNG audit entries...</p>}

      {!loading && (
        <>
          <table className="w-full border-collapse" role="table">
            <thead>
              <tr>
                <th className="text-left p-2 border-b">Round ID</th>
                <th className="text-left p-2 border-b">Algorithm</th>
                <th className="text-left p-2 border-b">Raw Value</th>
                <th className="text-left p-2 border-b">Options</th>
                <th className="text-left p-2 border-b">Selected Color</th>
                <th className="text-left p-2 border-b">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr key={entry.id}>
                  <td className="p-2 border-b">{entry.round_id}</td>
                  <td className="p-2 border-b">{entry.algorithm}</td>
                  <td className="p-2 border-b">{entry.raw_value}</td>
                  <td className="p-2 border-b">{entry.num_options}</td>
                  <td className="p-2 border-b">{entry.selected_color}</td>
                  <td className="p-2 border-b">{new Date(entry.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {entries.length === 0 && <p className="text-gray-500 mt-4">No RNG audit entries found</p>}

          <div className="flex gap-2 mt-4">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page <= 1}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Previous
            </button>
            <span className="px-3 py-1">Page {page}</span>
            <button
              onClick={() => setPage((p) => p + 1)}
              disabled={!hasMore}
              className="px-3 py-1 border rounded disabled:opacity-50"
            >
              Next
            </button>
          </div>
        </>
      )}
    </main>
  );
}
