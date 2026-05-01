'use client';

import { useState } from 'react';

export default function ConnectivityTestPage() {
  const [results, setResults] = useState<string[]>([]);
  const [testing, setTesting] = useState(false);

  const addResult = (message: string) => {
    setResults((prev) => [...prev, `[${new Date().toLocaleTimeString()}] ${message}`]);
  };

  const runTests = async () => {
    setResults([]);
    setTesting(true);

    try {
      // Test 1: Direct fetch to backend
      addResult('🧪 Test 1: Direct fetch to http://localhost:8000/api/v1/health');
      try {
        const response = await fetch('http://localhost:8000/api/v1/health');
        const data = await response.json();
        addResult(`✅ Success! Response: ${JSON.stringify(data)}`);
      } catch (error) {
        addResult(`❌ Failed: ${error instanceof Error ? error.message : String(error)}`);
      }

      // Test 2: Check environment variables
      addResult('\n🧪 Test 2: Environment variables');
      addResult(`NEXT_PUBLIC_API_URL: ${process.env.NEXT_PUBLIC_API_URL || '❌ Not set'}`);
      addResult(`NEXT_PUBLIC_WS_URL: ${process.env.NEXT_PUBLIC_WS_URL || '❌ Not set'}`);

      // Test 3: Fetch with API client URL
      const apiUrl = process.env.NEXT_PUBLIC_API_URL;
      if (apiUrl) {
        addResult(`\n🧪 Test 3: Fetch using NEXT_PUBLIC_API_URL (${apiUrl})`);
        try {
          const response = await fetch(`${apiUrl.replace('/api/v1', '')}/api/v1/health`);
          const data = await response.json();
          addResult(`✅ Success! Response: ${JSON.stringify(data)}`);
        } catch (error) {
          addResult(`❌ Failed: ${error instanceof Error ? error.message : String(error)}`);
        }
      }

      // Test 4: Check CORS
      addResult('\n🧪 Test 4: CORS Check');
      try {
        const response = await fetch('http://localhost:8000/api/v1/health', {
          method: 'OPTIONS',
        });
        addResult(`✅ OPTIONS request succeeded (status: ${response.status})`);
        const corsHeaders = {
          'Access-Control-Allow-Origin': response.headers.get('Access-Control-Allow-Origin'),
          'Access-Control-Allow-Methods': response.headers.get('Access-Control-Allow-Methods'),
          'Access-Control-Allow-Headers': response.headers.get('Access-Control-Allow-Headers'),
        };
        addResult(`CORS headers: ${JSON.stringify(corsHeaders, null, 2)}`);
      } catch (error) {
        addResult(`❌ OPTIONS request failed: ${error instanceof Error ? error.message : String(error)}`);
      }

      // Test 5: Game modes endpoint (with auth)
      addResult('\n🧪 Test 5: Game modes endpoint');
      const token = localStorage.getItem('auth-storage');
      if (token) {
        try {
          const authData = JSON.parse(token);
          const accessToken = authData?.state?.accessToken;

          if (accessToken) {
            addResult('Found access token in localStorage');
            const response = await fetch('http://localhost:8000/api/v1/game/modes', {
              headers: {
                'Authorization': `Bearer ${accessToken}`,
              },
            });

            if (response.ok) {
              const data = await response.json();
              addResult(`✅ Success! Got ${data.length} game modes`);
            } else {
              addResult(`❌ Failed with status: ${response.status}`);
              const text = await response.text();
              addResult(`Response: ${text.substring(0, 200)}`);
            }
          } else {
            addResult('❌ No access token in localStorage');
          }
        } catch (error) {
          addResult(`❌ Failed: ${error instanceof Error ? error.message : String(error)}`);
        }
      } else {
        addResult('❌ No auth-storage in localStorage');
      }

    } catch (error) {
      addResult(`❌ Unexpected error: ${error instanceof Error ? error.message : String(error)}`);
    } finally {
      setTesting(false);
    }
  };

  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">🔌 Connectivity Test</h1>

        <div className="bg-blue-900/30 border border-blue-500 rounded-lg p-6 mb-6">
          <h2 className="text-xl font-bold mb-4">What This Tests</h2>
          <ul className="list-disc list-inside space-y-2">
            <li>Direct connection to backend health endpoint</li>
            <li>Environment variables configuration</li>
            <li>CORS headers from backend</li>
            <li>Authenticated API request (game modes)</li>
          </ul>
        </div>

        <button
          onClick={runTests}
          disabled={testing}
          className="bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 text-white font-bold py-3 px-6 rounded mb-6"
        >
          {testing ? '⏳ Testing...' : '🚀 Run Connectivity Tests'}
        </button>

        {results.length > 0 && (
          <div className="bg-gray-800 rounded-lg p-6">
            <h2 className="text-xl font-bold mb-4">Test Results</h2>
            <div className="font-mono text-sm space-y-1 whitespace-pre-wrap">
              {results.map((result, i) => (
                <div
                  key={i}
                  className={
                    result.includes('✅') ? 'text-green-400' :
                    result.includes('❌') ? 'text-red-400' :
                    result.includes('🧪') ? 'text-cyan-400 font-bold' :
                    'text-gray-300'
                  }
                >
                  {result}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
