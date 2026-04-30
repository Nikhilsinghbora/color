/**
 * SoundManager — synthesized game sounds via Web Audio API.
 *
 * All play* methods are silent no-ops until initialize() is called after a
 * user interaction (click / tap / keypress), satisfying browser autoplay
 * policies.
 *
 * Mute preference is persisted in localStorage under the key "sound_muted".
 *
 * Requirements: 8.1–8.7
 */

const STORAGE_KEY = 'sound_muted';

export class SoundManager {
  private audioContext: AudioContext | null = null;
  private muted: boolean;
  private initialized = false;

  constructor() {
    this.muted = this.loadMutedPreference();
  }

  // ── lifecycle ──────────────────────────────────────────────────────

  /** Call on first user interaction to unlock the AudioContext. */
  initialize(): void {
    if (this.initialized) return;

    try {
      this.audioContext = new AudioContext();
      this.initialized = true;
    } catch {
      // Web Audio API not available — all sounds stay silent.
    }
  }

  /** Whether initialize() has been called successfully. */
  isInitialized(): boolean {
    return this.initialized;
  }

  // ── mute control ──────────────────────────────────────────────────

  setMuted(muted: boolean): void {
    this.muted = muted;
    this.persistMutedPreference(muted);
  }

  getIsMuted(): boolean {
    return this.muted;
  }

  // ── sound effects ─────────────────────────────────────────────────

  /** Regular countdown tick (requirements 8.1). */
  playTick(): void {
    if (!this.canPlay()) return;
    this.playTone({ frequency: 800, duration: 0.08, type: 'square', volume: 0.3 });
  }

  /** Distinct last-second warning (requirement 8.2). */
  playLastSecond(): void {
    if (!this.canPlay()) return;
    this.playTone({ frequency: 1200, duration: 0.2, type: 'sine', volume: 0.5 });
  }

  /** Bet confirmed (requirement 8.3). */
  playBetConfirm(): void {
    if (!this.canPlay()) return;
    // Two quick ascending tones for a "cha-ching" feel.
    this.playTone({ frequency: 600, duration: 0.08, type: 'sine', volume: 0.35, delay: 0 });
    this.playTone({ frequency: 900, duration: 0.12, type: 'sine', volume: 0.35, delay: 0.1 });
  }

  /** Win celebration (requirement 8.4). */
  playWinCelebration(): void {
    if (!this.canPlay()) return;
    // Ascending arpeggio — three notes.
    this.playTone({ frequency: 523, duration: 0.15, type: 'sine', volume: 0.4, delay: 0 });
    this.playTone({ frequency: 659, duration: 0.15, type: 'sine', volume: 0.4, delay: 0.15 });
    this.playTone({ frequency: 784, duration: 0.25, type: 'sine', volume: 0.4, delay: 0.3 });
  }

  // ── internals ─────────────────────────────────────────────────────

  private canPlay(): boolean {
    return this.initialized && !this.muted && this.audioContext !== null;
  }

  private playTone(opts: {
    frequency: number;
    duration: number;
    type: OscillatorType;
    volume: number;
    delay?: number;
  }): void {
    const ctx = this.audioContext;
    if (!ctx) return;

    const { frequency, duration, type, volume, delay = 0 } = opts;

    const oscillator = ctx.createOscillator();
    const gain = ctx.createGain();

    oscillator.type = type;
    oscillator.frequency.setValueAtTime(frequency, ctx.currentTime);

    gain.gain.setValueAtTime(volume, ctx.currentTime + delay);
    // Quick fade-out to avoid click artifacts.
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + delay + duration);

    oscillator.connect(gain);
    gain.connect(ctx.destination);

    oscillator.start(ctx.currentTime + delay);
    oscillator.stop(ctx.currentTime + delay + duration);
  }

  private loadMutedPreference(): boolean {
    try {
      return localStorage.getItem(STORAGE_KEY) === 'true';
    } catch {
      return false;
    }
  }

  private persistMutedPreference(muted: boolean): void {
    try {
      localStorage.setItem(STORAGE_KEY, String(muted));
    } catch {
      // localStorage unavailable — preference won't persist.
    }
  }
}

/** Singleton instance for app-wide use. */
export const soundManager = new SoundManager();
