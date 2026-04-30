'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAdminGuard } from '@/hooks/useAdminGuard';
import { apiClient } from '@/lib/api-client';
import type { AdminPlayerEntry } from '@/types';

interface PaginatedPlayers {
  items: AdminPlayerEntry[];
  total: number;
  page: number;
  size: number;
  has_more: boolean;
}

export default function AdminPlayersPage() {
  useAdminGuard();

  const [players, setPlayers] = useState<AdminPlayerEntry[]>([]);
  const [search, setSearch] = useState('');
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionMsg, setActionMsg] = useState<string | null>(null);

  const fetchPlayers = useCallback(async (s: string, p: number) => {
    setLoading(true);
    setError(null);
    try {
      const { data } = await apiClient.get<PaginatedPlayers>('/admin/players', {
        params: { search: s || undefined, page: p },
      });
      setPlayers(data.items);
      setHasMore(data.has_more);
    } catch {
      setError('Failed to load players');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPlayers(search, page);
  }, [search, page, fetchPlayers]);

  const handleAction = async (playerId: string, action: 'suspend' | 'ban') => {
    setActionMsg(null);
    try {
      await apiClient.post(`/admin/players/${playerId}/${action}`);
      setActionMsg(`Player ${action}ed successfully`);
      fetchPlayers(search, page);
    } catch {
      setError(`Failed to ${action} player`);
    }
  };

  return (
    <main className="max-w-6xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6">Player Management</h1>

      <div className="mb-4">
        <label htmlFor="player-search" className="sr-only">Search players</label>
        <input
          id="player-search"
          type="search"
          aria-label="Search players"
          placeholder="Search by username or email..."
          value={search}
          onChange={(e) => { setSearch(e.target.value); setPage(1); }}
          className="border rounded px-3 py-2 w-full max-w-md bg-[var(--bg-primary,#fff)] text-[var(--text-primary,#000)]"
        />
      </div>

      {actionMsg && <p role="status" className="text-green-600 mb-4">{actionMsg}</p>}
      {error && <p role="alert" className="text-red-600 mb-4">{error}</p>}
      {loading && <p role="status">Loading players...</p>}

      {!loading && (
        <>
          <table className="w-full border-collapse" role="table">
            <thead>
              <tr>
                <th className="text-left p-2 border-b">Username</th>
                <th className="text-left p-2 border-b">Email</th>
                <th className="text-left p-2 border-b">Status</th>
                <th className="text-left p-2 border-b">Joined</th>
                <th className="text-left p-2 border-b">Actions</th>
              </tr>
            </thead>
            <tbody>
              {players.map((player) => (
                <tr key={player.id}>
                  <td className="p-2 border-b">{player.username}</td>
                  <td className="p-2 border-b">{player.email}</td>
                  <td className="p-2 border-b">{player.is_active ? 'Active' : 'Inactive'}</td>
                  <td className="p-2 border-b">{new Date(player.created_at).toLocaleDateString()}</td>
                  <td className="p-2 border-b">
                    <button
                      onClick={() => handleAction(player.id, 'suspend')}
                      className="text-yellow-600 hover:underline mr-2"
                      aria-label={`Suspend ${player.username}`}
                    >
                      Suspend
                    </button>
                    <button
                      onClick={() => handleAction(player.id, 'ban')}
                      className="text-red-600 hover:underline"
                      aria-label={`Ban ${player.username}`}
                    >
                      Ban
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>

          {players.length === 0 && <p className="text-gray-500 mt-4">No players found</p>}

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
