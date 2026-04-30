import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { replaceMock, getMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  getMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: vi.fn(),
}));

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({
      player: { id: 'player-1', username: 'testuser', email: 'test@test.com', isAdmin: false },
      isAuthenticated: true,
    }),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { get: getMock },
  parseApiError: () => null,
  getErrorMessage: (_code: string, msg?: string) => msg ?? 'An unexpected error occurred',
}));

import LeaderboardPage from './page';

const mockEntries = [
  { rank: 1, player_id: 'p1', username: 'alice', metric_value: '5000.00' },
  { rank: 2, player_id: 'player-1', username: 'testuser', metric_value: '3000.00' },
  { rank: 3, player_id: 'p3', username: 'charlie', metric_value: '1000.00' },
];

describe('LeaderboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({
      data: {
        entries: mockEntries,
        player_rank: { rank: 2, player_id: 'player-1', username: 'testuser', metric_value: '3000.00' },
        metric: 'total_winnings',
        period: 'all_time',
      },
    });
  });

  it('renders the leaderboard page with title', async () => {
    render(<LeaderboardPage />);
    expect(screen.getByText('Leaderboard')).toBeInTheDocument();
    await waitFor(() => {
      expect(getMock).toHaveBeenCalled();
    });
  });

  it('fetches leaderboard data on mount', async () => {
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/leaderboard/total_winnings', { params: { period: 'all_time' } });
    });
  });

  it('displays leaderboard entries with rank, username, and metric value', async () => {
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
    });
    expect(screen.getByText('testuser')).toBeInTheDocument();
    expect(screen.getByText('charlie')).toBeInTheDocument();
    expect(screen.getByText('$5000.00')).toBeInTheDocument();
    expect(screen.getByText('$3000.00')).toBeInTheDocument();
  });

  it('highlights the current player row', async () => {
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(screen.getByText('testuser')).toBeInTheDocument();
    });
    const playerRow = screen.getByText('testuser').closest('tr');
    expect(playerRow).toHaveAttribute('aria-current', 'true');
  });

  it('displays player rank summary', async () => {
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/your rank/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/#2/)).toBeInTheDocument();
  });

  it('fetches new data when metric filter changes', async () => {
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/select leaderboard metric/i), {
      target: { value: 'win_rate' },
    });

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/leaderboard/win_rate', { params: { period: 'all_time' } });
    });
  });

  it('fetches new data when period filter changes', async () => {
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText(/select leaderboard period/i), {
      target: { value: 'weekly' },
    });

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/leaderboard/total_winnings', { params: { period: 'weekly' } });
    });
  });

  it('shows empty state when no entries', async () => {
    getMock.mockResolvedValueOnce({
      data: { entries: [], player_rank: null, metric: 'total_winnings', period: 'all_time' },
    });
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/no leaderboard data available/i)).toBeInTheDocument();
    });
  });

  it('shows error message on API failure', async () => {
    getMock.mockRejectedValueOnce(new Error('Network error'));
    render(<LeaderboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load leaderboard/i)).toBeInTheDocument();
    });
  });

  it('renders filter controls for metric and period', () => {
    render(<LeaderboardPage />);
    expect(screen.getByLabelText(/select leaderboard metric/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/select leaderboard period/i)).toBeInTheDocument();
  });
});
