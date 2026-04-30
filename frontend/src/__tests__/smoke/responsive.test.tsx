import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render } from '@testing-library/react';

// ---------------------------------------------------------------------------
// Requirements: 10.1–10.5
// Smoke test: key pages render at 320px, 768px, 1920px without overflow
// ---------------------------------------------------------------------------

const replaceMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock, push: vi.fn() }),
  useSearchParams: () => ({ get: () => null }),
  usePathname: () => '/',
  useParams: () => ({}),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { entries: [], player_rank: null } }),
    post: vi.fn().mockResolvedValue({ data: {} }),
  },
  registerAuthStore: vi.fn(),
  parseApiError: vi.fn(),
  getErrorMessage: vi.fn((code: string) => code),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: vi.fn(),
}));

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: vi.fn().mockReturnValue({ status: 'connected', sendMessage: vi.fn() }),
}));

vi.mock('@/hooks/useCountdown', () => ({
  useCountdown: vi.fn().mockReturnValue({ remaining: 25, isExpired: false }),
}));

vi.mock('@/stores/game-store', () => ({
  useGameStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      phase: 'betting',
      timerRemaining: 30,
      currentRound: {
        roundId: 'round-1',
        phase: 'betting',
        timer: 30,
        totalPlayers: 5,
        totalPool: '500.00',
        gameMode: 'classic',
      },
      colorOptions: [
        { color: 'red', odds: '2.0' },
        { color: 'blue', odds: '3.0' },
      ],
      placedBets: [],
      result: null,
      lastResult: null,
      betAmount: '10',
      roundHistory: [],
      connectionStatus: 'connected',
      selectedBets: {},
      addPlacedBet: vi.fn(),
      setBetAmount: vi.fn(),
    }),
}));

vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      balance: '100.00',
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

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      isAuthenticated: true,
      isAdmin: false,
      accessToken: 'tok',
      refreshToken: 'ref',
      player: { id: 'p1', email: 'a@b.com', username: 'player1', isAdmin: false },
    }),
}));

import GameViewPage from '@/app/game/page';
import WalletPage from '@/app/wallet/page';
import LeaderboardPage from '@/app/leaderboard/page';
import LoginPage from '@/app/login/page';

const VIEWPORTS = [
  { name: 'mobile (320px)', width: 320 },
  { name: 'tablet (768px)', width: 768 },
  { name: 'desktop (1920px)', width: 1920 },
];

/**
 * Simulate viewport width by setting innerWidth on the window object.
 * Note: jsdom doesn't truly render CSS, so we verify the component
 * renders without throwing at each viewport width. True overflow
 * detection requires a real browser, but this ensures no JS-level
 * breakage at different widths.
 */
function setViewportWidth(width: number) {
  Object.defineProperty(window, 'innerWidth', {
    writable: true,
    configurable: true,
    value: width,
  });
  window.dispatchEvent(new Event('resize'));
}

describe('Smoke: Responsive rendering', () => {
  const originalInnerWidth = window.innerWidth;

  afterEach(() => {
    Object.defineProperty(window, 'innerWidth', {
      writable: true,
      configurable: true,
      value: originalInnerWidth,
    });
  });

  beforeEach(() => {
    vi.clearAllMocks();
  });

  for (const viewport of VIEWPORTS) {
    describe(`at ${viewport.name}`, () => {
      beforeEach(() => {
        setViewportWidth(viewport.width);
      });

      it('Login page renders without crash', () => {
        const { container } = render(<LoginPage />);
        expect(container.querySelector('main')).toBeTruthy();
      });

      it('Game View page renders without crash', () => {
        const { container } = render(<GameViewPage />);
        expect(container.querySelector('main')).toBeTruthy();
      });

      it('Wallet page renders without crash', () => {
        const { container } = render(<WalletPage />);
        expect(container.querySelector('main')).toBeTruthy();
      });

      it('Leaderboard page renders without crash', () => {
        const { container } = render(<LeaderboardPage />);
        expect(container.querySelector('main')).toBeTruthy();
      });
    });
  }
});
