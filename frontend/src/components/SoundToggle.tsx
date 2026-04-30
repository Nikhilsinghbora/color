'use client';

import { useState, useCallback } from 'react';
import { soundManager } from '@/lib/sound-manager';

/**
 * Speaker icon button (🔊/🔇) that toggles mute/unmute via SoundManager.
 *
 * Requirements: 8.5, 8.6
 */
export default function SoundToggle() {
  const [muted, setMuted] = useState(() => soundManager.getIsMuted());

  const handleToggle = useCallback(() => {
    // Ensure AudioContext is initialized on user interaction
    soundManager.initialize();

    const next = !muted;
    soundManager.setMuted(next);
    setMuted(next);
  }, [muted]);

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
