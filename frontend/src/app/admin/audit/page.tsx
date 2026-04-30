'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdminGuard } from '@/hooks/useAdminGuard';
import { apiClient } from '@/lib/api-client';
import type { AuditLogEntry } from '@/types';

interface PaginatedAuditLogs {
  items: AuditLogEntry[];
  total: number;
  page: number;
  size: number;
  has_more: boolean;
}

export default function AdminAuditPage() {
  useAdminGuard();

  const [logs, setLogs] = useState<AuditLogEntry[]>([]);
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [eventType, setEventType] = useState('');
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchLogs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string | number> = { page };
      if (eventType) params.type = eventType;
      if (dateFrom) params.from = dateFrom;
      if (dateTo) params.to = dateTo;

      const { data } = await apiClient.get<PaginatedAuditLogs>('/admin/audit-logs', { params });
      setLogs(data.items);
      setHasMore(data.has_more);
    } catch {
      setError('Failed to load audit logs');
    } finally {
      setLoading(false);
    }
  }, [page, eventType, dateFrom, dateTo]);

  useEffect(() => {
    fetchLogs();
  }, [fetchLogs]);

  return (
    <main className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6">Audit Logs</h1>

      <div className="flex flex-wrap gap-4 mb-6">
        <div>
          <label htmlFor="event-type-filter" className="block text-sm font-medium mb-1">Event Type</label>
          <input
            id="event-type-filter"
            type="text"
            aria-label="Filter by event type"
            placeholder="e.g. login, bet_placed"
            value={eventType}
            onChange={(e) => { setEventType(e.target.value); setPage(1); }}
            className="border rounded px-2 py-1"
          />
        </div>
        <div>
          <label htmlFor="date-from-filter" className="block text-sm font-medium mb-1">From</label>
          <input
            id="date-from-filter"
            type="date"
            aria-label="Filter from date"
            value={dateFrom}
            onChange={(e) => { setDateFrom(e.target.value); setPage(1); }}
            className="border rounded px-2 py-1"
          />
        </div>
        <div>
          <label htmlFor="date-to-filter" className="block text-sm font-medium mb-1">To</label>
          <input
            id="date-to-filter"
            type="date"
            aria-label="Filter to date"
            value={dateTo}
            onChange={(e) => { setDateTo(e.target.value); setPage(1); }}
            className="border rounded px-2 py-1"
          />
        </div>
      </div>

      {error && <p role="alert" className="text-red-600 mb-4">{error}</p>}
      {loading && <p role="status">Loading audit logs...</p>}

      {!loading && (
        <>
          <table className="w-full border-collapse" role="table">
            <thead>
              <tr>
                <th className="text-left p-2 border-b">Event Type</th>
                <th className="text-left p-2 border-b">Actor</th>
                <th className="text-left p-2 border-b">Target</th>
                <th className="text-left p-2 border-b">IP Address</th>
                <th className="text-left p-2 border-b">Timestamp</th>
              </tr>
            </thead>
            <tbody>
              {logs.map((log) => (
                <tr key={log.id}>
                  <td className="p-2 border-b">{log.event_type}</td>
                  <td className="p-2 border-b">{log.actor_id}</td>
                  <td className="p-2 border-b">{log.target_id ?? '—'}</td>
                  <td className="p-2 border-b">{log.ip_address ?? '—'}</td>
                  <td className="p-2 border-b">{new Date(log.created_at).toLocaleString()}</td>
                </tr>
              ))}
            </tbody>
          </table>

          {logs.length === 0 && <p className="text-gray-500 mt-4">No audit logs found</p>}

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
