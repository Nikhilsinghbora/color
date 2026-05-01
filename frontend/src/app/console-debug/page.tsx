'use client';

import { useEffect } from 'react';
import { useGameStore } from '@/stores/game-store';
import { useAuthStore } from '@/stores/auth-store';

export default function ConsoleDebugPage() {
  const timerRemaining = useGameStore((s) => s.timerRemaining);
  const currentRound = useGameStore((s) => s.currentRound);
  const connectionStatus = useGameStore((s) => s.connectionStatus);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  // Log every change to timer
  useEffect(() => {
    console.log('🔔 [Console Debug] Timer changed to:', timerRemaining);
  }, [timerRemaining]);

  // Log every change to round state
  useEffect(() => {
    console.log('🔔 [Console Debug] Round state changed:', {
      roundId: currentRound?.roundId,
      phase: currentRound?.phase,
      timer: currentRound?.timer,
      totalPlayers: currentRound?.totalPlayers,
      totalPool: currentRound?.totalPool,
    });
  }, [currentRound]);

  // Log connection status changes
  useEffect(() => {
    console.log('🔔 [Console Debug] Connection status changed to:', connectionStatus);
  }, [connectionStatus]);

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">🔔 Console Debug - Live Monitoring</h1>

        <div className="bg-blue-900/30 border border-blue-500 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-bold mb-4">📝 Instructions</h2>
          <ol className="list-decimal list-inside space-y-2">
            <li>Keep this page open</li>
            <li>Open DevTools Console (F12)</li>
            <li>Watch for <code className="bg-gray-700 px-2 py-1">🔔 [Console Debug]</code> logs</li>
            <li>These logs show every state change in real-time</li>
            <li>Open another tab with <a href="/game" className="text-blue-400 underline" target="_blank">/game</a></li>
            <li>Watch this page's console - you'll see all updates</li>
          </ol>
        </div>

        <div className="bg-gray-800 rounded-lg p-6 space-y-4">
          <h2 className="text-xl font-bold mb-4">Current State (Updates Live)</h2>

          <div className="space-y-2 font-mono text-sm">
            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Authenticated:</span>
              <span className={isAuthenticated ? 'text-green-400' : 'text-red-400'}>
                {isAuthenticated ? '✅ Yes' : '❌ No'}
              </span>
            </div>

            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Connection Status:</span>
              <span className={
                connectionStatus === 'connected' ? 'text-green-400' :
                connectionStatus === 'connecting' ? 'text-yellow-400' :
                'text-red-400'
              }>
                {connectionStatus}
              </span>
            </div>

            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Timer Remaining:</span>
              <span className={timerRemaining > 0 ? 'text-green-400' : 'text-red-400'}>
                {timerRemaining}s
              </span>
            </div>

            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Round ID:</span>
              <span className="text-yellow-400 break-all">
                {currentRound?.roundId || 'None'}
              </span>
            </div>

            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Round Timer (from state):</span>
              <span className="text-white">
                {currentRound?.timer || 0}s
              </span>
            </div>

            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Phase:</span>
              <span className="text-white">
                {currentRound?.phase || 'None'}
              </span>
            </div>

            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Total Players:</span>
              <span className="text-white">
                {currentRound?.totalPlayers || 0}
              </span>
            </div>

            <div className="flex gap-4">
              <span className="text-gray-400 w-48">Total Pool:</span>
              <span className="text-white">
                ${currentRound?.totalPool || '0.00'}
              </span>
            </div>
          </div>
        </div>

        <div className="mt-6 bg-yellow-900/30 border border-yellow-500 rounded-lg p-6">
          <h2 className="text-xl font-bold mb-4">🔍 What to Look For</h2>
          <div className="space-y-2 text-sm">
            <p><strong>If timer stays at 0:</strong></p>
            <ul className="list-disc list-inside ml-4 space-y-1">
              <li>Check console for "Timer changed to: 0" - means store IS updating but value is 0</li>
              <li>Check console for "Timer changed to: 28, 27, 26..." - means store IS counting down</li>
              <li>If you see "Timer changed to: X" but display shows 0, it's a rendering issue</li>
              <li>If you DON'T see "Timer changed" logs, store is not updating</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
