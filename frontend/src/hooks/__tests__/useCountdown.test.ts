import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useCountdown } from '../useCountdown';

describe('useCountdown', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('initializes with the given seconds', () => {
    const { result } = renderHook(() => useCountdown(30));
    expect(result.current.remaining).toBe(30);
    expect(result.current.isExpired).toBe(false);
  });

  it('decrements every second', () => {
    const { result } = renderHook(() => useCountdown(5));

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.remaining).toBe(4);

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(result.current.remaining).toBe(3);
  });

  it('expires when reaching zero', () => {
    const { result } = renderHook(() => useCountdown(2));

    act(() => {
      vi.advanceTimersByTime(2000);
    });
    expect(result.current.remaining).toBe(0);
    expect(result.current.isExpired).toBe(true);
  });

  it('does not go below zero', () => {
    const { result } = renderHook(() => useCountdown(1));

    act(() => {
      vi.advanceTimersByTime(5000);
    });
    expect(result.current.remaining).toBe(0);
  });

  it('resets when initialSeconds changes', () => {
    const { result, rerender } = renderHook(
      ({ seconds }) => useCountdown(seconds),
      { initialProps: { seconds: 10 } },
    );

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(result.current.remaining).toBe(7);

    rerender({ seconds: 20 });
    expect(result.current.remaining).toBe(20);
  });

  it('handles zero initial seconds', () => {
    const { result } = renderHook(() => useCountdown(0));
    expect(result.current.remaining).toBe(0);
    expect(result.current.isExpired).toBe(true);
  });
});
