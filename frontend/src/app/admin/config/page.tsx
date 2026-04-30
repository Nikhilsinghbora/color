'use client';

import { useState, useEffect } from 'react';
import { useAdminGuard } from '@/hooks/useAdminGuard';
import { apiClient } from '@/lib/api-client';
import type { GameMode, GameConfigUpdate } from '@/types';

export default function AdminConfigPage() {
  useAdminGuard();

  const [modes, setModes] = useState<GameMode[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [editState, setEditState] = useState<Record<string, Partial<GameConfigUpdate>>>({});

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const { data } = await apiClient.get<GameMode[]>('/admin/game-config');
        setModes(data);
        const initial: Record<string, Partial<GameConfigUpdate>> = {};
        data.forEach((m: GameMode) => {
          initial[m.id] = {
            game_mode_id: m.id,
            min_bet: m.min_bet,
            max_bet: m.max_bet,
            round_duration_seconds: m.round_duration_seconds,
          };
        });
        setEditState(initial);
      } catch {
        setError('Failed to load game configuration');
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const handleFieldChange = (modeId: string, field: string, value: string | number) => {
    setEditState((prev) => ({
      ...prev,
      [modeId]: { ...prev[modeId], [field]: value },
    }));
  };

  const handleSubmit = async (modeId: string) => {
    setSaving(modeId);
    setSuccessMsg(null);
    setError(null);
    try {
      await apiClient.post('/admin/game-config', {
        game_mode_id: modeId,
        ...editState[modeId],
      });
      setSuccessMsg(`Configuration updated for mode. Changes take effect next round.`);
    } catch {
      setError('Failed to save configuration');
    } finally {
      setSaving(null);
    }
  };

  return (
    <main className="max-w-4xl mx-auto p-4">
      <h1 className="text-2xl font-bold mb-6">Game Configuration</h1>

      {loading && <p role="status">Loading configuration...</p>}
      {error && <p role="alert" className="text-red-600">{error}</p>}
      {successMsg && <p role="status" className="text-green-600 mb-4">{successMsg}</p>}

      {!loading && modes.map((mode) => (
        <form
          key={mode.id}
          aria-label={`Configuration for ${mode.name}`}
          className="border rounded p-4 mb-4"
          onSubmit={(e) => { e.preventDefault(); handleSubmit(mode.id); }}
        >
          <h2 className="text-lg font-semibold mb-3">{mode.name}</h2>
          <p className="text-sm text-gray-500 mb-3">Type: {mode.mode_type}</p>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-4">
            <div>
              <label htmlFor={`min-bet-${mode.id}`} className="block text-sm font-medium mb-1">Min Bet</label>
              <input
                id={`min-bet-${mode.id}`}
                type="text"
                value={editState[mode.id]?.min_bet ?? ''}
                onChange={(e) => handleFieldChange(mode.id, 'min_bet', e.target.value)}
                className="border rounded px-2 py-1 w-full"
              />
            </div>
            <div>
              <label htmlFor={`max-bet-${mode.id}`} className="block text-sm font-medium mb-1">Max Bet</label>
              <input
                id={`max-bet-${mode.id}`}
                type="text"
                value={editState[mode.id]?.max_bet ?? ''}
                onChange={(e) => handleFieldChange(mode.id, 'max_bet', e.target.value)}
                className="border rounded px-2 py-1 w-full"
              />
            </div>
            <div>
              <label htmlFor={`duration-${mode.id}`} className="block text-sm font-medium mb-1">Round Duration (s)</label>
              <input
                id={`duration-${mode.id}`}
                type="number"
                value={editState[mode.id]?.round_duration_seconds ?? ''}
                onChange={(e) => handleFieldChange(mode.id, 'round_duration_seconds', Number(e.target.value))}
                className="border rounded px-2 py-1 w-full"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={saving === mode.id}
            className="bg-blue-600 text-white px-4 py-2 rounded hover:bg-blue-700 disabled:opacity-50"
          >
            {saving === mode.id ? 'Saving...' : 'Save Configuration'}
          </button>
        </form>
      ))}
    </main>
  );
}
