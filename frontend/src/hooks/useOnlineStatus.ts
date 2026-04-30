'use client';

import { useState, useEffect } from 'react';
import { useUIStore } from '@/stores/ui-store';

export function useOnlineStatus(): boolean {
  // Always start with `true` so server and client initial render match (no banner).
  // The real navigator.onLine value is picked up in the effect on the client.
  const [isOnline, setIsOnline] = useState(true);

  useEffect(() => {
    // Sync actual browser state on mount
    const currentlyOnline = navigator.onLine;
    setIsOnline(currentlyOnline);
    useUIStore.getState().setOffline(!currentlyOnline);

    const handleOnline = () => {
      setIsOnline(true);
      useUIStore.getState().setOffline(false);
    };

    const handleOffline = () => {
      setIsOnline(false);
      useUIStore.getState().setOffline(true);
    };

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  return isOnline;
}
