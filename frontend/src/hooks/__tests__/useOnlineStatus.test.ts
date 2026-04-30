import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useOnlineStatus } from '../useOnlineStatus';
import { useUIStore } from '@/stores/ui-store';

describe('useOnlineStatus', () => {
  const originalOnLine = navigator.onLine;

  beforeEach(() => {
    useUIStore.setState({ isOffline: false });
    Object.defineProperty(navigator, 'onLine', {
      value: true,
      writable: true,
      configurable: true,
    });
  });

  afterEach(() => {
    Object.defineProperty(navigator, 'onLine', {
      value: originalOnLine,
      writable: true,
      configurable: true,
    });
  });

  it('returns true when online', () => {
    const { result } = renderHook(() => useOnlineStatus());
    expect(result.current).toBe(true);
  });

  it('updates to false on offline event', () => {
    const { result } = renderHook(() => useOnlineStatus());

    act(() => {
      window.dispatchEvent(new Event('offline'));
    });

    expect(result.current).toBe(false);
    expect(useUIStore.getState().isOffline).toBe(true);
  });

  it('updates to true on online event', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });

    const { result } = renderHook(() => useOnlineStatus());

    act(() => {
      window.dispatchEvent(new Event('online'));
    });

    expect(result.current).toBe(true);
    expect(useUIStore.getState().isOffline).toBe(false);
  });

  it('syncs UI store on mount', () => {
    Object.defineProperty(navigator, 'onLine', { value: false, configurable: true });

    renderHook(() => useOnlineStatus());
    expect(useUIStore.getState().isOffline).toBe(true);
  });
});
