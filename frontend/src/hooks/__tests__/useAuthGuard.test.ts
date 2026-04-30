import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAuthGuard } from '../useAuthGuard';
import { useAuthStore } from '@/stores/auth-store';

const mockReplace = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({
    replace: mockReplace,
    push: vi.fn(),
    back: vi.fn(),
    forward: vi.fn(),
    refresh: vi.fn(),
    prefetch: vi.fn(),
  }),
}));

describe('useAuthGuard', () => {
  beforeEach(() => {
    mockReplace.mockClear();
    useAuthStore.setState({
      accessToken: null,
      refreshToken: null,
      player: null,
      isAuthenticated: false,
      isAdmin: false,
    });
  });

  it('redirects to /login when not authenticated', () => {
    renderHook(() => useAuthGuard());
    expect(mockReplace).toHaveBeenCalledWith('/login');
  });

  it('does not redirect when authenticated', () => {
    useAuthStore.setState({
      accessToken: 'test-token',
      isAuthenticated: true,
    });

    renderHook(() => useAuthGuard());
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
