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
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: useAuthGuardMock,
}));

vi.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: useWebSocketMock,
}));

// We need to mock useCountdown to control timer values
const { useCountdownMock } = vi.hoisted(() => ({
  useCountdownMock: vi.fn().mockReturnValue({ remaining: 25, isExpired: false }),
}));

vi.mock('@/hooks/useCountdown', () => ({
  useCountdown: useCountdownMock,
}));

// Mock game store with controllable state
let mockGameState = {
  phase: 'betting' as const,
  timerRemaining: 30,
  currentRound: { roundId: 'round-1', phase: 'betting' as const, timer: 30, totalPlayers: 5, totalPool: '500.00', gameMode: 'classic' },
  colorOptions: [
    { color: 'red', odds: '2.0' },
    { color: 'blue', odds: '3.0' },
    { color: 'green', odds: '5.0' },
  ],
  placedBets: [] as Array<{ id: string; color: string; amount: string; oddsAtPlacement: string; potentialPayout: string }>,
  result: null as null | { winningColor: string; playerPayouts: Array<{ betId: string; amount: string; isWinner: boolean }> },
  connectionStatus: 'connected' as string,
};

vi.mock('@/stores/game-store', () => ({
  useGameStore: (selector: (s: typeof mockGameState) => unknown) => selector(mockGameState),
}));

import GameViewPage from './page';

describe('GameViewPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGameState = {
      phase: 'betting',
      timerRemaining: 30,
      currentRound: { roundId: 'round-1', phase: 'betting', timer: 30, totalPlayers: 5, totalPool: '500.00', gameMode: 'classic' },
      colorOptions: [
        { color: 'red', odds: '2.0' },
        { color: 'blue', odds: '3.0' },
        { color: 'green', odds: '5.0' },
      ],
      placedBets: [],
      result: null,
      connectionStatus: 'connected',
    };
    useCountdownMock.mockReturnValue({ remaining: 25, isExpired: false });
  });

  it('calls useAuthGuard for route protection', () => {
    render(<GameViewPage />);
    expect(useAuthGuardMock).toHaveBeenCalled();
  });

  it('displays round info (round number, total players, total pool)', () => {
    render(<GameViewPage />);
    expect(screen.getByText(/round round-1/i)).toBeInTheDocument();
    expect(screen.getByTestId('total-players')).toHaveTextContent('5');
    expect(screen.getByTestId('total-pool')).toHaveTextContent('$500.00');
  });

  it('displays color chips with odds during betting phase', () => {
    render(<GameViewPage />);
    expect(screen.getByRole('button', { name: /red — odds 2\.0x/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /blue — odds 3\.0x/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /green — odds 5\.0x/i })).toBeInTheDocument();
  });

  it('enables color chip buttons during betting phase', () => {
    render(<GameViewPage />);
    const redBtn = screen.getByRole('button', { name: /red — odds 2\.0x/i });
    expect(redBtn).not.toBeDisabled();
  });

  it('displays countdown timer during betting phase', () => {
    render(<GameViewPage />);
    expect(screen.getByRole('timer')).toHaveTextContent('25');
    expect(screen.getByText(/seconds remaining/i)).toBeInTheDocument();
  });

  it('shows "Resolving…" animation during resolution phase', () => {
    mockGameState.phase = 'resolution';
    render(<GameViewPage />);
    expect(screen.getByText(/resolving/i)).toBeInTheDocument();
    // Timer should not be visible
    expect(screen.queryByRole('timer')).not.toBeInTheDocument();
  });

  it('disables color chips during resolution phase', () => {
    mockGameState.phase = 'resolution';
    render(<GameViewPage />);
    const redBtn = screen.getByRole('button', { name: /red — odds 2\.0x/i });
    expect(redBtn).toBeDisabled();
  });

  it('highlights winning color during result phase', () => {
    mockGameState.phase = 'result';
    mockGameState.result = {
      winningColor: 'red',
      playerPayouts: [{ betId: 'b1', amount: '20.00', isWinner: true }],
    };
    render(<GameViewPage />);
    expect(screen.getByText(/winning color/i)).toBeInTheDocument();
    // The winning color label appears in both the result banner and the color chip
    const redElements = screen.getAllByText('red');
    expect(redElements.length).toBeGreaterThanOrEqual(2);
  });

  it('displays payout info during result phase', () => {
    mockGameState.phase = 'result';
    mockGameState.result = {
      winningColor: 'red',
      playerPayouts: [
        { betId: 'b1', amount: '20.00', isWinner: true },
        { betId: 'b2', amount: '10.00', isWinner: false },
      ],
    };
    render(<GameViewPage />);
    expect(screen.getByText(/won \$20\.00/i)).toBeInTheDocument();
    expect(screen.getByText(/lost \$10\.00/i)).toBeInTheDocument();
  });

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

  it('displays placed bets summary', () => {
    mockGameState.placedBets = [
      { id: 'b1', color: 'red', amount: '10.00', oddsAtPlacement: '2.0', potentialPayout: '20.00' },
    ];
    render(<GameViewPage />);
    expect(screen.getByText(/your bets/i)).toBeInTheDocument();
    expect(screen.getByText('$10.00 →')).toBeInTheDocument();
    expect(screen.getByText('$20.00')).toBeInTheDocument();
  });

  it('does not display bets section when no bets placed', () => {
    mockGameState.placedBets = [];
    render(<GameViewPage />);
    expect(screen.queryByText(/your bets/i)).not.toBeInTheDocument();
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
});
