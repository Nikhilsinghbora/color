'use client';

export default function EnvCheckPage() {
  return (
    <div className="min-h-screen bg-gray-900 text-white p-8">
      <div className="max-w-4xl mx-auto">
        <h1 className="text-3xl font-bold mb-6">Environment Variables Check</h1>

        <div className="bg-gray-800 rounded-lg p-6 space-y-4">
          <div>
            <h2 className="text-xl font-semibold mb-2">Next.js Public Environment Variables</h2>
            <p className="text-sm text-gray-400 mb-4">
              These should be available in the browser (prefixed with NEXT_PUBLIC_)
            </p>
          </div>

          <div className="space-y-2">
            <div className="flex items-start gap-4">
              <span className="font-mono text-yellow-400 min-w-[200px]">NEXT_PUBLIC_API_URL:</span>
              <span className="font-mono text-green-400 break-all">
                {process.env.NEXT_PUBLIC_API_URL || '❌ Not set'}
              </span>
            </div>

            <div className="flex items-start gap-4">
              <span className="font-mono text-yellow-400 min-w-[200px]">NEXT_PUBLIC_WS_URL:</span>
              <span className="font-mono text-green-400 break-all">
                {process.env.NEXT_PUBLIC_WS_URL || '❌ Not set'}
              </span>
            </div>
          </div>

          <div className="mt-6 p-4 bg-blue-900/30 border border-blue-500 rounded">
            <h3 className="font-semibold mb-2">🔍 Troubleshooting</h3>
            <ul className="text-sm space-y-1 list-disc list-inside">
              <li>If variables show "❌ Not set", check <code className="bg-gray-700 px-1">.env.local</code></li>
              <li>After changing .env.local, <strong>restart the dev server</strong></li>
              <li>Run: <code className="bg-gray-700 px-1">npm run dev</code> (kill and restart, not just refresh)</li>
              <li>Variables must start with <code className="bg-gray-700 px-1">NEXT_PUBLIC_</code> to be available in browser</li>
            </ul>
          </div>

          <div className="mt-6 p-4 bg-gray-700 rounded">
            <h3 className="font-semibold mb-2">Expected Values</h3>
            <div className="text-sm space-y-1 font-mono">
              <div>NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1</div>
              <div>NEXT_PUBLIC_WS_URL=ws://localhost:8000</div>
            </div>
          </div>

          <div className="mt-6">
            <button
              onClick={() => window.location.reload()}
              className="bg-blue-600 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded"
            >
              Refresh Page
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
