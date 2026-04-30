import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

// --- Hoisted mocks ---
const { useWebSocketMock, useAuthGuardMock, searchParamsMock } = vi.hoisted(() => ({
  useWebSocketMock: vi.fn().mockReturnValue({ status: 'connected', sendMessage: vi.fn() }),
  useAuthGuardMock: vi.fn(),
  searchParamsMock: { get: vi.fn().mockReturnValue(null) },
}));

vi.mock('next/navigation', () => ({
  useSearchParams: () => searchParamsMock,
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), back: vi.fn() }),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: useAuthGuardMock,
}));

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: useWebSocketMock,
}));

const { useCountdownMock } = vi.hoisted(() => ({
  useCountdownMock: vi.fn().mockReturnValue({ remaining: 25, isExpired: false }),
}));

vi.mock('@/hooks/useCountdown', () => ({
  useCountdown: useCountdownMock,
}));

// Mock child components to isolate page-level tests
vi.mock('@/components/ResultDisplay', () => ({
  default: () => <div data-testid="result-display">ResultDisplay</div>,
}));

vi.mock('@/components/CountdownTimer', () => ({
  default: (props: { totalSeconds: number; remainingSeconds: number; isResolving?: boolean }) => (
    <div data-testid="countdown-timer" data-resolving={props.isResolving}>
      {props.isResolving ? 'Resolving…' : props.remainingSeconds}
    </div>
  ),
}));

vi.mock('@/components/ColorBetButtons', () => ({
  default: (props: { disabled: boolean }) => (
    <div data-testid="color-bet-buttons" data-disabled={props.disabled}>
      ColorBetButtons
    </div>
  ),
}));

vi.mock('@/components/NumberGrid', () => ({
  default: (props: { disabled: boolean }) => (
    <div data-testid="number-grid" data-disabled={props.disabled}>
      NumberGrid
    </div>
  ),
}));

vi.mock('@/components/WalletCard', () => ({
  default: () => <div data-testid="wallet-card">WalletCard</div>,
}));

vi.mock('@/components/AnnouncementBar', () => ({
  default: () => <div data-testid="announcement-bar">AnnouncementBar</div>,
}));

vi.mock('@/components/HistoryTable', () => ({
  default: (props: { gameModeId: string }) => (
    <div data-testid="history-table" data-mode-id={props.gameModeId}>HistoryTable</div>
  ),
}));

vi.mock('@/components/WinLossDialog', () => ({
  default: (props: { isOpen: boolean; isWin: boolean; onClose: () => void }) =>
    props.isOpen ? (
      <div data-testid="winloss-dialog" data-is-win={props.isWin}>
        WinLossDialog
        <button data-testid="winloss-close" onClick={props.onClose}>Close</button>
      </div>
    ) : null,
}));

vi.mock('@/components/BigSmallButtons', () => ({
  default: (props: { disabled: boolean }) => (
    <div data-testid="big-small-buttons" data-disabled={props.disabled}>BigSmallButtons</div>
  ),
}));

vi.mock('@/components/BetConfirmationSheet', () => ({
  default: () => <div data-testid="bet-confirmation-sheet">BetConfirmationSheet</div>,
}));

vi.mock('@/components/SoundToggle', () => ({
  default: () => <div data-testid="sound-toggle">SoundToggle</div>,
}));

vi.mock('@/lib/sound-manager', () => ({
  soundManager: {
    initialize: vi.fn(),
    playTick: vi.fn(),
    playLastSecond: vi.fn(),
    playBetConfirm: vi.fn(),
    playWinCelebration: vi.fn(),
    setMuted: vi.fn(),
    getIsMuted: vi.fn().mockReturnValue(false),
  },
}));

vi.mock('@/components/GameModeTabs', () => ({
  default: (props: { modes: unknown[]; activeMode: string; onModeChange: (id: string) => void }) => (
    <div data-testid="game-mode-tabs" data-active-mode={props.activeMode}>
      GameModeTabs
    </div>
  ),
}));

vi.mock('@/components/RulesModal', () => ({
  default: (props: { isOpen: boolean; onClose: () => void }) =>
    props.isOpen ? (
      <div data-testid="rules-modal">
        RulesModal
        <button data-testid="rules-modal-close" onClick={props.onClose}>Close</button>
      </div>
    ) : null,
}));

// Mock API client
vi.mock('@/lib/api-client', () => ({
  apiClient: { post: vi.fn(), get: vi.fn().mockResolvedValue({ data: [] }) },
  parseApiError: vi.fn(),
  getErrorMessage: vi.fn(),
}));

// Mock game store with controllable state
const mockActions = {
  addPlacedBet: vi.fn(),
  setBetAmount: vi.fn(),
  setGameModes: vi.fn(),
  setActiveGameMode: vi.fn(),
  openBetSheet: vi.fn(),
  closeBetSheet: vi.fn(),
  openWinLossDialog: vi.fn(),
  closeWinLossDialog: vi.fn(),
};

let mockGameState: Record<string, unknown> = {};

function resetGameState() {
  mockGameState = {
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
    placedBets: [],
    result: null,
    lastResult: null,
    connectionStatus: 'connected',
    betAmount: '10',
    roundHistory: [],
    gameModes: [],
    activeGameModeId: null,
    periodNumber: null,
    showBetSheet: false,
    betSheetType: null,
    showWinLossDialog: false,
    ...mockActions,
  };
}

vi.mock('@/stores/game-store', () => ({
  useGameStore: (selector: (s: Record<string, unknown>) => unknown) => selector(mockGameState),
}));

vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ balance: '500.00', updateBalance: vi.fn() }),
}));

import GameViewPage from './page';

describe('GameViewPage — Casino Layout', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    resetGameState();
    useCountdownMock.mockReturnValue({ remaining: 25, isExpired: false });
  });

  // ── Auth & routing ──

  it('calls useAuthGuard for route protection', () => {
    render(<GameViewPage />);
    expect(useAuthGuardMock).toHaveBeenCalled();
  });

  it('uses default roundId when no search param provided', () => {
    searchParamsMock.get.mockReturnValue(null);
    render(<GameViewPage />);
    expect(useWebSocketMock).toHaveBeenCalledWith('current');
  });

  it('uses roundId from search params when provided', () => {
    searchParamsMock.get.mockReturnValue('round-42');
    render(<GameViewPage />);
    expect(useWebSocketMock).toHaveBeenCalledWith('round-42');
  });

  // ── Layout composition ──

  it('renders the casino dark gradient background', () => {
    const { container } = render(<GameViewPage />);
    const main = container.querySelector('main');
    expect(main?.classList.contains('casino-bg')).toBe(true);
  });

  it('renders all core casino sub-components in new layout', () => {
    render(<GameViewPage />);
    expect(screen.getByTestId('wallet-card')).toBeInTheDocument();
    expect(screen.getByTestId('announcement-bar')).toBeInTheDocument();
    expect(screen.getByTestId('result-display')).toBeInTheDocument();
    expect(screen.getByTestId('countdown-timer')).toBeInTheDocument();
    expect(screen.getByTestId('color-bet-buttons')).toBeInTheDocument();
    expect(screen.getByTestId('number-grid')).toBeInTheDocument();
    expect(screen.getByTestId('history-table')).toBeInTheDocument();
  });

  it('displays round info (period number fallback to round ID, total players, total pool)', () => {
    render(<GameViewPage />);
    // When periodNumber is null, falls back to roundId
    expect(screen.getByTestId('period-number-display')).toHaveTextContent('round-1');
    expect(screen.getByTestId('total-players')).toHaveTextContent('5');
    expect(screen.getByTestId('total-pool')).toHaveTextContent('$500.00');
  });

  // ── Phase-dependent behavior ──

  it('enables betting components during betting phase', () => {
    render(<GameViewPage />);
    expect(screen.getByTestId('color-bet-buttons').dataset.disabled).toBe('false');
    expect(screen.getByTestId('number-grid').dataset.disabled).toBe('false');
  });

  it('disables betting components during resolution phase', () => {
    mockGameState.phase = 'resolution';
    render(<GameViewPage />);
    expect(screen.getByTestId('color-bet-buttons').dataset.disabled).toBe('true');
    expect(screen.getByTestId('number-grid').dataset.disabled).toBe('true');
  });

  it('passes isResolving to CountdownTimer during resolution phase', () => {
    mockGameState.phase = 'resolution';
    render(<GameViewPage />);
    expect(screen.getByTestId('countdown-timer').dataset.resolving).toBe('true');
    expect(screen.getByText('Resolving…')).toBeInTheDocument();
  });

  it('shows countdown seconds during betting phase', () => {
    render(<GameViewPage />);
    expect(screen.getByTestId('countdown-timer')).toHaveTextContent('25');
  });

  // ── Connection status ──

  it('shows reconnecting banner when connection is reconnecting', () => {
    mockGameState.connectionStatus = 'reconnecting';
    render(<GameViewPage />);
    expect(screen.getByText(/reconnecting to game server/i)).toBeInTheDocument();
  });

  it('shows disconnected banner when connection is disconnected', () => {
    mockGameState.connectionStatus = 'disconnected';
    render(<GameViewPage />);
    expect(screen.getByText(/disconnected from game server/i)).toBeInTheDocument();
  });

  it('does not show connection banner when connected', () => {
    mockGameState.connectionStatus = 'connected';
    render(<GameViewPage />);
    expect(screen.queryByText(/reconnecting/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/disconnected/i)).not.toBeInTheDocument();
  });

  // ── Period number display (Requirement 5.1) ──

  it('displays period number when available from game store', () => {
    mockGameState.periodNumber = '20250429100051058';
    render(<GameViewPage />);
    expect(screen.getByTestId('period-number-display')).toHaveTextContent('20250429100051058');
  });

  it('falls back to round ID when period number is null', () => {
    mockGameState.periodNumber = null;
    render(<GameViewPage />);
    expect(screen.getByTestId('period-number-display')).toHaveTextContent('round-1');
  });

  it('displays dash when both period number and round ID are unavailable', () => {
    mockGameState.periodNumber = null;
    mockGameState.currentRound = null;
    render(<GameViewPage />);
    expect(screen.getByTestId('period-number-display')).toHaveTextContent('—');
  });

  // ── How to Play button (Requirements 10.1, 10.2) ──

  it('renders a "How to Play" button in the timer area', () => {
    render(<GameViewPage />);
    expect(screen.getByTestId('how-to-play-btn')).toBeInTheDocument();
    expect(screen.getByLabelText('How to Play')).toBeInTheDocument();
  });

  it('opens RulesModal when "How to Play" button is clicked', async () => {
    const { user } = await import('@testing-library/user-event').then((m) => ({
      user: m.default.setup(),
    }));
    render(<GameViewPage />);
    expect(screen.queryByTestId('rules-modal')).not.toBeInTheDocument();
    await user.click(screen.getByTestId('how-to-play-btn'));
    expect(screen.getByTestId('rules-modal')).toBeInTheDocument();
  });

  it('closes RulesModal when close button is clicked', async () => {
    const { user } = await import('@testing-library/user-event').then((m) => ({
      user: m.default.setup(),
    }));
    render(<GameViewPage />);
    await user.click(screen.getByTestId('how-to-play-btn'));
    expect(screen.getByTestId('rules-modal')).toBeInTheDocument();
    await user.click(screen.getByTestId('rules-modal-close'));
    expect(screen.queryByTestId('rules-modal')).not.toBeInTheDocument();
  });
});
