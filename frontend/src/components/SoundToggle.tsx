'use client';

import { useState, useCallback, useEffect } from 'react';
import { soundManager } from '@/lib/sound-manager';

/**
 * Speaker icon button (🔊/🔇) that toggles mute/unmute via SoundManager.
 *
 * Requirements: 8.5, 8.6
 */
export default function SoundToggle() {
  // Start with false to avoid hydration mismatch, then sync with soundManager on mount
  const [muted, setMuted] = useState(false);
  const [mounted, setMounted] = useState(false);

  // Sync with soundManager after component mounts (client-side only)
  useEffect(() => {
    setMuted(soundManager.getIsMuted());
    setMounted(true);
  }, []);

  const handleToggle = useCallback(() => {
    // Ensure AudioContext is initialized on user interaction
    soundManager.initialize();

    const next = !muted;
    soundManager.setMuted(next);
    setMuted(next);
  }, [muted]);

  // Don't render until mounted to avoid hydration mismatch
  if (!mounted) {
    return (
      <button
        type="button"
        aria-label="Sound toggle"
        data-testid="sound-toggle"
        className="flex h-8 w-8 items-center justify-center rounded-full text-lg hover:bg-white/10 casino-transition"
        disabled
      >
        🔊
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={handleToggle}
      aria-label={muted ? 'Unmute sounds' : 'Mute sounds'}
      data-testid="sound-toggle"
      className="flex h-8 w-8 items-center justify-center rounded-full text-lg hover:bg-white/10 casino-transition"
    >
      {muted ? '🔇' : '🔊'}
    </button>
  );
}
