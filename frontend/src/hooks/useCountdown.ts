'use client';

import { useState, useEffect, useRef } from 'react';

export function useCountdown(initialSeconds: number) {
  const [remaining, setRemaining] = useState(initialSeconds);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const lastInitialRef = useRef(initialSeconds);

  // Sync when initialSeconds changes (e.g. from WS timer tick reset)
  useEffect(() => {
    // Only reset if the value actually changed to prevent unnecessary resets
    if (initialSeconds !== lastInitialRef.current) {
      lastInitialRef.current = initialSeconds;
      setRemaining(initialSeconds);
    }
  }, [initialSeconds]);

  useEffect(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    if (remaining <= 0) return;

    intervalRef.current = setInterval(() => {
      setRemaining((prev) => {
        if (prev <= 1) {
          if (intervalRef.current) {
            clearInterval(intervalRef.current);
            intervalRef.current = null;
          }
          return 0;
        }
        return prev - 1;
      });
    }, 1000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [remaining]);

  return {
    remaining,
    isExpired: remaining <= 0,
  };
}
