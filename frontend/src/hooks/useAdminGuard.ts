'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuthStore } from '@/stores/auth-store';

export function useAdminGuard(): void {
  const router = useRouter();
  const isAdmin = useAuthStore((s) => s.isAdmin);
  const isAuthenticated = useAuthStore((s) => s.isAuthenticated);

  useEffect(() => {
    if (!isAuthenticated) {
      router.replace('/login');
      return;
    }
    if (!isAdmin) {
      router.replace('/game');
    }
  }, [isAdmin, isAuthenticated, router]);
}
