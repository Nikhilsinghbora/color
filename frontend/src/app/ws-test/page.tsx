'use client';

import { useState, useEffect } from 'react';
import { useAuthStore } from '@/stores/auth-store';

export default function WebSocketTestPage() {
  const [logs, setLogs] = useState<string[]>([]);
  const [wsStatus, setWsStatus] = useState<string>('Not connected');
  const accessToken = useAuthStore((s) => s.accessToken);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  const addLog = (message: string) => {
    const timestamp = new Date().toISOString().split('T')[1].split('.')[0];
    setLogs((prev) => [`[${timestamp}] ${message}`, ...prev].slice(0, 50));
    console.log(`[WS Test] ${message}`);
  };

  useEffect(() => {
    addLog(`Auth state: isAuthenticated=${isAuthenticated}, hasToken=${!!accessToken}`);
  }, [isAuthenticated, accessToken]);

  const testConnection = async () => {
    try {
      addLog('Starting WebSocket connection test...');

      // Step 1: Check if we have a token
      if (!accessToken) {
        addLog('ERROR: No access token available. Please login first.');
        return;
      }
      addLog(`Token available: ${accessToken.substring(0, 20)}...`);

      // Step 2: Fetch game modes to get a round ID
      addLog('Fetching game modes...');
      const modesResponse = await fetch('http://localhost:8000/api/v1/game/modes');
      const modes = await modesResponse.json();
      addLog(`Got ${modes.length} game modes`);

      if (modes.length === 0) {
        addLog('ERROR: No game modes available');
        return;
      }

      const firstMode = modes[0];
      const roundId = firstMode.active_round_id;
      addLog(`First mode: ${firstMode.name}, roundId: ${roundId}`);

      if (!roundId) {
        addLog('ERROR: No active round ID');
        return;
      }

      // Step 3: Create WebSocket connection
      const wsUrl = `ws://localhost:8000/ws/game/${roundId}?token=${accessToken}`;
      addLog(`Connecting to: ${wsUrl.replace(/token=.*/, 'token=***')}`);
      setWsStatus('Connecting...');

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        addLog('✅ WebSocket CONNECTED');
        setWsStatus('Connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          addLog(`📩 Received: ${JSON.stringify(data).substring(0, 100)}...`);
        } catch {
          addLog(`📩 Received: ${event.data.substring(0, 100)}...`);
        }
      };

      ws.onerror = (error) => {
        addLog(`❌ WebSocket ERROR: ${error}`);
        setWsStatus('Error');
      };

      ws.onclose = (event) => {
        addLog(`🔌 WebSocket CLOSED: code=${event.code}, reason=${event.reason || 'none'}`);
        setWsStatus('Disconnected');
      };

      // Clean up after 30 seconds
      setTimeout(() => {
        if (ws.readyState === WebSocket.OPEN) {
          addLog('Test complete, closing connection');
          ws.close();
        }
      }, 30000);
    } catch (error) {
      addLog(`❌ Exception: ${error instanceof Error ? error.message : String(error)}`);
      setWsStatus('Failed');
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-4">WebSocket Connection Test</h1>

        <div className="mb-6 p-4 bg-gray-800 rounded-lg">
          <div className="mb-2">
            <strong>Auth Status:</strong> {isAuthenticated ? '✅ Authenticated' : '❌ Not authenticated'}
          </div>
          <div className="mb-2">
            <strong>Token:</strong> {accessToken ? `${accessToken.substring(0, 30)}...` : 'None'}
          </div>
          <div>
            <strong>WebSocket Status:</strong> {wsStatus}
          </div>
        </div>

        <button
          onClick={testConnection}
          className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded mb-6"
        >
          Test WebSocket Connection
        </button>

        <div className="bg-gray-800 rounded-lg p-4">
          <h2 className="text-xl font-bold mb-4">Logs</h2>
          <div className="font-mono text-sm space-y-1 max-h-96 overflow-y-auto">
            {logs.length === 0 ? (
              <div className="text-gray-400">No logs yet. Click the button to test.</div>
            ) : (
              logs.map((log, i) => (
                <div key={i} className="text-green-400">
                  {log}
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
