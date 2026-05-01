'use client';

import { useEffect, useState } from 'react';
import { useGameStore } from '@/stores/game-store';
import { useAuthStore } from '@/stores/auth-store';

export default function DebugPage() {
  const [mounted, setMounted] = useState(false);

  // Game store state
  const connectionStatus = useGameStore((s) => s.connectionStatus);
  const currentRound = useGameStore((s) => s.currentRound);
  const timerRemaining = useGameStore((s) => s.timerRemaining);
  const phase = useGameStore((s) => s.phase);
  const gameModes = useGameStore((s) => s.gameModes);
  const activeGameModeId = useGameStore((s) => s.activeGameModeId);

  // Auth store state
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);
  const accessToken = useAuthStore((s) => s.accessToken);
  const player = useAuthStore((s) => s.player);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    return <div className="min-h-screen bg-gray-900 text-white p-8">Loading...</div>;
  }

  const activeMode = gameModes.find((m) => m.id === activeGameModeId);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-6xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold mb-6">🐛 Debug Dashboard</h1>

        {/* Authentication State */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4 text-blue-400">🔐 Authentication State</h2>
          <div className="space-y-2 font-mono text-sm">
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Is Authenticated:</span>
              <span className={isAuthenticated ? 'text-green-400' : 'text-red-400'}>
                {isAuthenticated ? '✅ Yes' : '❌ No'}
              </span>
            </div>
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Has Access Token:</span>
              <span className={accessToken ? 'text-green-400' : 'text-red-400'}>
                {accessToken ? '✅ Yes' : '❌ No'}
              </span>
            </div>
            {accessToken && (
              <div className="flex gap-4">
                <span className="text-gray-400 w-40">Token Preview:</span>
                <span className="text-yellow-400 break-all">{accessToken.substring(0, 50)}...</span>
              </div>
            )}
            {player && (
              <div className="flex gap-4">
                <span className="text-gray-400 w-40">Player:</span>
                <span className="text-green-400">{player.username} ({player.email})</span>
              </div>
            )}
          </div>
        </div>

        {/* WebSocket Connection State */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4 text-purple-400">🔌 WebSocket State</h2>
          <div className="space-y-2 font-mono text-sm">
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Connection Status:</span>
              <span className={
                connectionStatus === 'connected' ? 'text-green-400' :
                connectionStatus === 'connecting' ? 'text-yellow-400' :
                connectionStatus === 'reconnecting' ? 'text-orange-400' :
                'text-red-400'
              }>
                {connectionStatus === 'connected' && '✅ Connected'}
                {connectionStatus === 'connecting' && '⏳ Connecting...'}
                {connectionStatus === 'reconnecting' && '🔄 Reconnecting...'}
                {connectionStatus === 'disconnected' && '❌ Disconnected'}
              </span>
            </div>
          </div>
        </div>

        {/* Game State */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4 text-green-400">🎮 Game State</h2>
          <div className="space-y-2 font-mono text-sm">
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Game Modes Loaded:</span>
              <span className="text-white">{gameModes.length} modes</span>
            </div>
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Active Mode:</span>
              <span className="text-white">{activeMode?.name || 'None'}</span>
            </div>
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Active Round ID:</span>
              <span className="text-yellow-400 break-all">{activeMode?.active_round_id || 'None'}</span>
            </div>
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Current Round ID:</span>
              <span className="text-yellow-400 break-all">{currentRound?.roundId || 'None'}</span>
            </div>
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Phase:</span>
              <span className="text-white">{phase}</span>
            </div>
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">Timer Remaining:</span>
              <span className="text-white">{timerRemaining}s</span>
            </div>
            {currentRound && (
              <>
                <div className="flex gap-4">
                  <span className="text-gray-400 w-40">Total Players:</span>
                  <span className="text-white">{currentRound.totalPlayers}</span>
                </div>
                <div className="flex gap-4">
                  <span className="text-gray-400 w-40">Total Pool:</span>
                  <span className="text-white">${currentRound.totalPool}</span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Environment Variables */}
        <div className="bg-gray-800 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4 text-cyan-400">⚙️ Environment</h2>
          <div className="space-y-2 font-mono text-sm">
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">NEXT_PUBLIC_API_URL:</span>
              <span className="text-white break-all">
                {process.env.NEXT_PUBLIC_API_URL || '❌ Not set'}
              </span>
            </div>
            <div className="flex gap-4">
              <span className="text-gray-400 w-40">NEXT_PUBLIC_WS_URL:</span>
              <span className="text-white break-all">
                {process.env.NEXT_PUBLIC_WS_URL || '❌ Not set'}
              </span>
            </div>
          </div>
        </div>

        {/* Troubleshooting */}
        <div className="bg-blue-900/30 border border-blue-500 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">🔍 Troubleshooting Guide</h2>
          <div className="space-y-3 text-sm">
            {!isAuthenticated && (
              <div className="text-yellow-300">
                ⚠️ Not authenticated. <a href="/login" className="underline">Click here to login</a>
              </div>
            )}

            {isAuthenticated && connectionStatus === 'disconnected' && (
              <div className="text-red-300">
                ❌ WebSocket disconnected. Possible causes:
                <ul className="list-disc list-inside ml-4 mt-2">
                  <li>Backend not running (check: <code className="bg-gray-700 px-1">curl http://localhost:8000/api/v1/health</code>)</li>
                  <li>Wrong WebSocket URL (check NEXT_PUBLIC_WS_URL above)</li>
                  <li>Token expired (try refreshing page)</li>
                  <li>No active round (check if game modes are seeded)</li>
                </ul>
              </div>
            )}

            {isAuthenticated && connectionStatus === 'connected' && (
              <div className="text-green-300">
                ✅ Everything looks good! WebSocket is connected.
              </div>
            )}

            {gameModes.length === 0 && isAuthenticated && (
              <div className="text-yellow-300">
                ⚠️ No game modes loaded. Run: <code className="bg-gray-700 px-1">python -m scripts.seed_data</code>
              </div>
            )}
          </div>
        </div>

        {/* Actions */}
        <div className="flex gap-4">
          <button
            onClick={() => window.location.reload()}
            className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
          >
            Refresh Page
          </button>
          <a
            href="/game"
            className="bg-green-600 hover:bg-green-700 text-white font-bold py-2 px-4 rounded inline-block"
          >
            Go to Game
          </a>
          <a
            href="/ws-test"
            className="bg-purple-600 hover:bg-purple-700 text-white font-bold py-2 px-4 rounded inline-block"
          >
            WebSocket Test
          </a>
        </div>
      </div>
    </div>
  );
}
