import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useAdminGuard } from '../useAdminGuard';
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

describe('useAdminGuard', () => {
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
    renderHook(() => useAdminGuard());
    expect(mockReplace).toHaveBeenCalledWith('/login');
  });

  it('redirects to /game when authenticated but not admin', () => {
    useAuthStore.setState({
      accessToken: 'test-token',
      isAuthenticated: true,
      isAdmin: false,
    });

    renderHook(() => useAdminGuard());
    expect(mockReplace).toHaveBeenCalledWith('/game');
  });

  it('does not redirect when authenticated and admin', () => {
    useAuthStore.setState({
      accessToken: 'test-token',
      isAuthenticated: true,
      isAdmin: true,
    });

    renderHook(() => useAdminGuard());
    expect(mockReplace).not.toHaveBeenCalled();
  });
});
