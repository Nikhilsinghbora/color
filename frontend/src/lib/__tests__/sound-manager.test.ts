import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { SoundManager } from '../sound-manager';

// ── Web Audio API mocks ─────────────────────────────────────────────

function createMockOscillator() {
  return {
    type: 'sine' as OscillatorType,
    frequency: { setValueAtTime: vi.fn() },
    connect: vi.fn(),
    start: vi.fn(),
    stop: vi.fn(),
  };
}

function createMockGain() {
  return {
    gain: {
      value: 1,
      setValueAtTime: vi.fn(),
      exponentialRampToValueAtTime: vi.fn(),
    },
    connect: vi.fn(),
  };
}

// Track created nodes so tests can inspect them
let createdOscillators: ReturnType<typeof createMockOscillator>[] = [];
let createdGains: ReturnType<typeof createMockGain>[] = [];
let ctxConstructorCalls = 0;

class MockAudioContext {
  currentTime = 0;
  destination = {};

  constructor() {
    ctxConstructorCalls++;
  }

  createOscillator() {
    const osc = createMockOscillator();
    createdOscillators.push(osc);
    return osc;
  }

  createGain() {
    const g = createMockGain();
    createdGains.push(g);
    return g;
  }
}

// ── helpers ─────────────────────────────────────────────────────────

let storageBacking: Record<string, string> = {};

function setupLocalStorageMock() {
  storageBacking = {};
  vi.stubGlobal('localStorage', {
    getItem: vi.fn((key: string) => storageBacking[key] ?? null),
    setItem: vi.fn((key: string, value: string) => {
      storageBacking[key] = value;
    }),
    removeItem: vi.fn((key: string) => {
      delete storageBacking[key];
    }),
  });
}

// ── tests ───────────────────────────────────────────────────────────

describe('SoundManager', () => {
  beforeEach(() => {
    setupLocalStorageMock();
    createdOscillators = [];
    createdGains = [];
    ctxConstructorCalls = 0;
    vi.stubGlobal('AudioContext', MockAudioContext);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── initialization ──────────────────────────────────────────────

  describe('initialize()', () => {
    it('creates an AudioContext on first call', () => {
      const sm = new SoundManager();
      expect(sm.isInitialized()).toBe(false);

      sm.initialize();

      expect(sm.isInitialized()).toBe(true);
      expect(ctxConstructorCalls).toBe(1);
    });

    it('is idempotent — second call is a no-op', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.initialize();

      expect(ctxConstructorCalls).toBe(1);
    });

    it('handles missing AudioContext gracefully', () => {
      vi.stubGlobal('AudioContext', class {
        constructor() { throw new Error('not supported'); }
      });

      const sm = new SoundManager();
      sm.initialize();

      expect(sm.isInitialized()).toBe(false);
    });
  });

  // ── autoplay compliance ─────────────────────────────────────────

  describe('autoplay compliance (requirement 8.7)', () => {
    it('playTick is a no-op before initialize()', () => {
      const sm = new SoundManager();
      sm.playTick(); // should not throw

      expect(createdOscillators).toHaveLength(0);
    });

    it('playLastSecond is a no-op before initialize()', () => {
      const sm = new SoundManager();
      sm.playLastSecond();

      expect(createdOscillators).toHaveLength(0);
    });

    it('playBetConfirm is a no-op before initialize()', () => {
      const sm = new SoundManager();
      sm.playBetConfirm();

      expect(createdOscillators).toHaveLength(0);
    });

    it('playWinCelebration is a no-op before initialize()', () => {
      const sm = new SoundManager();
      sm.playWinCelebration();

      expect(createdOscillators).toHaveLength(0);
    });
  });

  // ── sound playback ──────────────────────────────────────────────

  describe('sound playback after initialization', () => {
    it('playTick creates an oscillator and gain node', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playTick();

      expect(createdOscillators).toHaveLength(1);
      expect(createdGains).toHaveLength(1);
    });

    it('playLastSecond creates an oscillator and gain node', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playLastSecond();

      expect(createdOscillators).toHaveLength(1);
      expect(createdGains).toHaveLength(1);
    });

    it('playBetConfirm creates two oscillators (ascending tones)', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playBetConfirm();

      expect(createdOscillators).toHaveLength(2);
      expect(createdGains).toHaveLength(2);
    });

    it('playWinCelebration creates three oscillators (arpeggio)', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playWinCelebration();

      expect(createdOscillators).toHaveLength(3);
      expect(createdGains).toHaveLength(3);
    });

    it('oscillator is connected to gain, gain to destination', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playTick();

      const osc = createdOscillators[0];
      const gain = createdGains[0];

      expect(osc.connect).toHaveBeenCalledWith(gain);
      expect(gain.connect).toHaveBeenCalled();
    });

    it('oscillator start and stop are called', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playTick();

      const osc = createdOscillators[0];
      expect(osc.start).toHaveBeenCalled();
      expect(osc.stop).toHaveBeenCalled();
    });

    it('playTick uses square wave type', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playTick();

      const osc = createdOscillators[0];
      expect(osc.type).toBe('square');
    });

    it('playLastSecond uses sine wave type', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.playLastSecond();

      const osc = createdOscillators[0];
      expect(osc.type).toBe('sine');
    });
  });

  // ── mute control ────────────────────────────────────────────────

  describe('mute control (requirements 8.5, 8.6)', () => {
    it('defaults to unmuted when localStorage has no value', () => {
      const sm = new SoundManager();
      expect(sm.getIsMuted()).toBe(false);
    });

    it('reads muted=true from localStorage on construction', () => {
      storageBacking['sound_muted'] = 'true';
      const sm = new SoundManager();
      expect(sm.getIsMuted()).toBe(true);
    });

    it('reads muted=false from localStorage on construction', () => {
      storageBacking['sound_muted'] = 'false';
      const sm = new SoundManager();
      expect(sm.getIsMuted()).toBe(false);
    });

    it('setMuted(true) persists to localStorage', () => {
      const sm = new SoundManager();
      sm.setMuted(true);

      expect(sm.getIsMuted()).toBe(true);
      expect(localStorage.setItem).toHaveBeenCalledWith('sound_muted', 'true');
    });

    it('setMuted(false) persists to localStorage', () => {
      const sm = new SoundManager();
      sm.setMuted(false);

      expect(sm.getIsMuted()).toBe(false);
      expect(localStorage.setItem).toHaveBeenCalledWith('sound_muted', 'false');
    });

    it('play methods are no-ops when muted', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.setMuted(true);

      sm.playTick();
      sm.playLastSecond();
      sm.playBetConfirm();
      sm.playWinCelebration();

      expect(createdOscillators).toHaveLength(0);
    });

    it('play methods work again after unmuting', () => {
      const sm = new SoundManager();
      sm.initialize();
      sm.setMuted(true);
      sm.setMuted(false);

      sm.playTick();

      expect(createdOscillators).toHaveLength(1);
    });
  });

  // ── localStorage error handling ─────────────────────────────────

  describe('localStorage error handling', () => {
    it('defaults to unmuted when localStorage throws on read', () => {
      vi.stubGlobal('localStorage', {
        getItem: vi.fn(() => { throw new Error('blocked'); }),
        setItem: vi.fn(),
      });

      const sm = new SoundManager();
      expect(sm.getIsMuted()).toBe(false);
    });

    it('does not throw when localStorage throws on write', () => {
      vi.stubGlobal('localStorage', {
        getItem: vi.fn(() => null),
        setItem: vi.fn(() => { throw new Error('blocked'); }),
      });

      const sm = new SoundManager();
      expect(() => sm.setMuted(true)).not.toThrow();
    });
  });
});
