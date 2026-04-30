'use client';

import { useEffect } from 'react';
import { useUIStore } from '@/stores/ui-store';
import { NavBar } from '@/components/NavBar';
import { OfflineBanner } from '@/components/OfflineBanner';
import { ToastProvider } from '@/components/Toast';

export function ClientShell({ children }: { children: React.ReactNode }) {
  const theme = useUIStore((s) => s.theme);

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
  }, [theme]);

  return (
    <ToastProvider>
      <NavBar />
      <OfflineBanner />
      <div className="flex-1">{children}</div>
    </ToastProvider>
  );
}
