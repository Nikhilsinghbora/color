'use client';

import { useUIStore } from '@/stores/ui-store';
import { useAuthGuard } from '@/hooks/useAuthGuard';

export default function SettingsPage() {
  useAuthGuard();
  const theme = useUIStore((s) => s.theme);
  const setTheme = useUIStore((s) => s.setTheme);

  return (
    <main className="mx-auto max-w-2xl px-4 py-8">
      <h1 className="text-2xl font-bold text-foreground mb-6">Settings</h1>

      <section aria-labelledby="theme-heading" className="rounded-lg border border-border bg-card p-6">
        <h2 id="theme-heading" className="text-lg font-semibold text-card-foreground mb-4">
          Appearance
        </h2>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-card-foreground">Theme</p>
            <p className="text-xs text-muted-foreground">Switch between light and dark mode</p>
          </div>

          <button
            onClick={() => setTheme(theme === 'light' ? 'dark' : 'light')}
            className="relative inline-flex h-8 w-14 items-center rounded-full transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            style={{ backgroundColor: theme === 'dark' ? 'var(--primary)' : 'var(--muted)' }}
            role="switch"
            aria-checked={theme === 'dark'}
            aria-label="Dark mode"
          >
            <span
              className={`inline-block h-6 w-6 rounded-full bg-white shadow transition-transform ${
                theme === 'dark' ? 'translate-x-7' : 'translate-x-1'
              }`}
            />
          </button>
        </div>
      </section>
    </main>
  );
}
