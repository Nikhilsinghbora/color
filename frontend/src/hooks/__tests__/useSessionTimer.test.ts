import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useSessionTimer } from '../useSessionTimer';
import { useUIStore } from '@/stores/ui-store';

describe('useSessionTimer', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    // Reset UI store
    useUIStore.setState({
      sessionStartTime: null,
      sessionLimitMinutes: null,
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('returns zero elapsed and false limitReached when no session', () => {
    const { result } = renderHook(() => useSessionTimer());
    expect(result.current.elapsed).toBe(0);
    expect(result.current.limitReached).toBe(false);
  });

  it('tracks elapsed minutes from session start', () => {
    const now = Date.now();
    useUIStore.setState({
      sessionStartTime: now - 5 * 60000, // 5 minutes ago
      sessionLimitMinutes: 60,
    });

    const { result } = renderHook(() => useSessionTimer());
    expect(result.current.elapsed).toBe(5);
    expect(result.current.limitReached).toBe(false);
  });

  it('sets limitReached when elapsed >= limit', () => {
    const now = Date.now();
    useUIStore.setState({
      sessionStartTime: now - 30 * 60000, // 30 minutes ago
      sessionLimitMinutes: 30,
    });

    const { result } = renderHook(() => useSessionTimer());
    expect(result.current.limitReached).toBe(true);
  });

  it('does not set limitReached when no limit configured', () => {
    const now = Date.now();
    useUIStore.setState({
      sessionStartTime: now - 120 * 60000, // 2 hours ago
      sessionLimitMinutes: null,
    });

    const { result } = renderHook(() => useSessionTimer());
    expect(result.current.elapsed).toBe(120);
    expect(result.current.limitReached).toBe(false);
  });

  it('updates elapsed as time passes', () => {
    const now = Date.now();
    useUIStore.setState({
      sessionStartTime: now,
      sessionLimitMinutes: 10,
    });

    const { result } = renderHook(() => useSessionTimer());
    expect(result.current.elapsed).toBe(0);

    // Advance 2 minutes
    act(() => {
      vi.advanceTimersByTime(2 * 60000);
    });
    expect(result.current.elapsed).toBe(2);
  });
});
