import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render } from '@testing-library/react';
import { axe } from 'vitest-axe';
import 'vitest-axe/extend-expect';

// ---------------------------------------------------------------------------
// Requirements: 10.1–10.5
// Smoke test: axe-core accessibility audit on game view, wallet, leaderboard
// ---------------------------------------------------------------------------

// --- Shared mocks ---

const replaceMock = vi.fn();
const pushMock = vi.fn();

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  useSearchParams: () => ({ get: () => null }),
  usePathname: () => '/game',
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

vi.mock('@/lib/api-client', () => ({
  apiClient: {
    get: vi.fn().mockResolvedValue({ data: { entries: [], player_rank: null } }),
    post: vi.fn(),
  },
  registerAuthStore: vi.fn(),
  parseApiError: vi.fn(),
  getErrorMessage: vi.fn((code: string) => code),
}));

// --- Game store mock ---
const mockGameState = {
  phase: 'betting' as const,
  timerRemaining: 30,
  currentRound: {
    roundId: 'round-1',
    phase: 'betting' as const,
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
  connectionStatus: 'connected',
  selectedBets: {},
};

vi.mock('@/stores/game-store', () => ({
  useGameStore: (selector: (s: typeof mockGameState) => unknown) => selector(mockGameState),
}));

// --- Wallet store mock ---
const mockWalletState = {
  balance: '100.00',
  transactions: [
    { id: 't1', type: 'deposit', amount: '50.00', balance_after: '50.00', description: null, created_at: '2024-01-01T00:00:00Z' },
  ],
  transactionPage: 1,
  hasMoreTransactions: false,
  isLoading: false,
  fetchBalance: vi.fn(),
  fetchTransactions: vi.fn(),
  deposit: vi.fn(),
  withdraw: vi.fn(),
  updateBalance: vi.fn(),
};

vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector: (s: typeof mockWalletState) => unknown) => selector(mockWalletState),
}));

// --- Auth store mock ---
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

// --- Imports (after mocks) ---
import GameViewPage from '@/app/game/page';
import WalletPage from '@/app/wallet/page';
import LeaderboardPage from '@/app/leaderboard/page';

describe('Smoke: Accessibility (axe-core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('Game View page has no critical accessibility violations', async () => {
    const { container } = render(<GameViewPage />);
    const results = await axe(container);
    // Filter to only critical and serious violations
    const critical = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    expect(critical).toEqual([]);
  });

  it('Wallet page has no critical accessibility violations', async () => {
    const { container } = render(<WalletPage />);
    const results = await axe(container);
    const critical = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    expect(critical).toEqual([]);
  });

  it('Leaderboard page has no critical accessibility violations', async () => {
    const { container } = render(<LeaderboardPage />);
    const results = await axe(container);
    const critical = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    expect(critical).toEqual([]);
  });
});
