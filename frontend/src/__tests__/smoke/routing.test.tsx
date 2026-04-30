import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Requirements: 10.1–10.5
// Smoke test: all routes render without crash, auth guards redirect correctly
// ---------------------------------------------------------------------------

const replaceMock = vi.fn();
const pushMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  useSearchParams: () => ({ get: () => null }),
  usePathname: () => '/',
  useParams: () => ({ id: 'player-1', token: 'reset-tok' }),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
  registerAuthStore: vi.fn(),
  parseApiError: vi.fn(),
  getErrorMessage: vi.fn((code: string) => code),
}));

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({ status: 'connected', sendMessage: vi.fn() }),
}));

vi.mock('@/hooks/useCountdown', () => ({
  useCountdown: vi.fn().mockReturnValue({ remaining: 25, isExpired: false }),
}));

// --- Auth store: start unauthenticated ---
let mockAuthState: Record<string, unknown> = {
  isAuthenticated: false,
  isAdmin: false,
  accessToken: null,
  refreshToken: null,
  player: null,
  setTokens: vi.fn(),
  clearTokens: vi.fn(),
};

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: (s: Record<string, unknown>) => unknown) => selector(mockAuthState),
}));

vi.mock('@/stores/game-store', () => ({
  useGameStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      phase: 'betting',
      timerRemaining: 30,
      currentRound: null,
      colorOptions: [],
      placedBets: [],
      result: null,
      connectionStatus: 'disconnected',
      selectedBets: {},
    }),
}));

vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      balance: '0.00',
      transactions: [],
      transactionPage: 1,
      hasMoreTransactions: false,
      isLoading: false,
      fetchBalance: vi.fn(),
      fetchTransactions: vi.fn(),
      deposit: vi.fn(),
      withdraw: vi.fn(),
      updateBalance: vi.fn(),
    }),
}));

vi.mock('@/stores/ui-store', () => ({
  useUIStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      theme: 'light',
      isChatOpen: false,
      unreadChatCount: 0,
      isOffline: false,
      sessionStartTime: null,
      sessionLimitMinutes: null,
    }),
}));

// --- Page imports ---
import LoginPage from '@/app/login/page';
import RegisterPage from '@/app/register/page';
import ForgotPasswordPage from '@/app/forgot-password/page';
import GameViewPage from '@/app/game/page';
import WalletPage from '@/app/wallet/page';
import LeaderboardPage from '@/app/leaderboard/page';

describe('Smoke: Routing — pages render without crash', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    replaceMock.mockClear();
    mockAuthState = {
      isAuthenticated: false,
      isAdmin: false,
      accessToken: null,
      refreshToken: null,
      player: null,
      setTokens: vi.fn(),
      clearTokens: vi.fn(),
    };
  });

  it('Login page renders without crash', () => {
    const { container } = render(<LoginPage />);
    expect(container.querySelector('main')).toBeTruthy();
    expect(screen.getByRole('heading', { name: /sign in/i })).toBeInTheDocument();
  });

  it('Register page renders without crash', () => {
    const { container } = render(<RegisterPage />);
    expect(container.querySelector('main')).toBeTruthy();
  });

  it('Forgot Password page renders without crash', () => {
    const { container } = render(<ForgotPasswordPage />);
    expect(container.querySelector('main')).toBeTruthy();
  });

  it('Game View page renders without crash (unauthenticated redirects)', () => {
    const { container } = render(<GameViewPage />);
    // Should still render without throwing
    expect(container).toBeTruthy();
  });

  it('Wallet page renders without crash', () => {
    const { container } = render(<WalletPage />);
    expect(container).toBeTruthy();
  });

  it('Leaderboard page renders without crash', () => {
    const { container } = render(<LeaderboardPage />);
    expect(container).toBeTruthy();
  });
});

describe('Smoke: Auth guards redirect correctly', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    replaceMock.mockClear();
  });

  it('unauthenticated user on Game View triggers redirect to /login', () => {
    mockAuthState = {
      isAuthenticated: false,
      isAdmin: false,
      accessToken: null,
      refreshToken: null,
      player: null,
      setTokens: vi.fn(),
      clearTokens: vi.fn(),
    };

    render(<GameViewPage />);
    // useAuthGuard calls router.replace('/login') when not authenticated
    expect(replaceMock).toHaveBeenCalledWith('/login');
  });

  it('authenticated user on Game View does not redirect', () => {
    mockAuthState = {
      isAuthenticated: true,
      isAdmin: false,
      accessToken: 'tok',
      refreshToken: 'ref',
      player: { id: 'p1', email: 'a@b.com', username: 'player1', isAdmin: false },
      setTokens: vi.fn(),
      clearTokens: vi.fn(),
    };

    render(<GameViewPage />);
    expect(replaceMock).not.toHaveBeenCalled();
  });
});
