'use client';

import { useState, useEffect } from 'react';
import { useUIStore } from '@/stores/ui-store';

export function useSessionTimer() {
  const sessionStartTime = useUIStore((s) => s.sessionStartTime);
  const sessionLimitMinutes = useUIStore((s) => s.sessionLimitMinutes);

  const [elapsed, setElapsed] = useState(0);
  const [limitReached, setLimitReached] = useState(false);

  useEffect(() => {
    if (sessionStartTime === null) {
      setElapsed(0);
      setLimitReached(false);
      return;
    }

    const tick = () => {
      const elapsedMs = Date.now() - sessionStartTime;
      const elapsedMinutes = Math.floor(elapsedMs / 60000);
      setElapsed(elapsedMinutes);

      if (sessionLimitMinutes !== null && elapsedMinutes >= sessionLimitMinutes) {
        setLimitReached(true);
      } else {
        setLimitReached(false);
      }
    };

    // Run immediately
    tick();

    const interval = setInterval(tick, 1000);

    return () => {
      clearInterval(interval);
    };
  }, [sessionStartTime, sessionLimitMinutes]);

  return { elapsed, limitReached };
}
