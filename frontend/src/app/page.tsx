'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';

export default function Home() {
  const router = useRouter();
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace('/game');
    } else {
      router.replace('/login');
    }
  }, [isAuthenticated, router]);

  return (
    <main className="flex flex-1 items-center justify-center">
      <div className="animate-pulse text-muted-foreground">Loading...</div>
    </main>
  );
}
