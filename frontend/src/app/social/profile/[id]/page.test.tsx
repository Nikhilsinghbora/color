import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

const { replaceMock, getMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  getMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
  useParams: () => ({ id: 'player-42' }),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { get: getMock },
  parseApiError: () => null,
  getErrorMessage: (_code: string, msg?: string) => msg ?? 'An unexpected error occurred',
}));

import PlayerProfilePage from './page';

const mockProfile = {
  id: 'player-42',
  username: 'alice',
  total_games: 150,
  win_rate: '62.50',
  leaderboard_rank: 5,
};

describe('PlayerProfilePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: mockProfile });
  });

  it('fetches and displays player profile', async () => {
    render(<PlayerProfilePage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/social/profile/player-42');
    });
    expect(await screen.findByText('alice')).toBeInTheDocument();
  });

  it('displays total games, win rate, and leaderboard rank', async () => {
    render(<PlayerProfilePage />);
    await waitFor(() => {
      expect(screen.getByTestId('total-games')).toHaveTextContent('150');
    });
    expect(screen.getByTestId('win-rate')).toHaveTextContent('62.50%');
    expect(screen.getByTestId('leaderboard-rank')).toHaveTextContent('#5');
  });

  it('shows "Unranked" when leaderboard_rank is null', async () => {
    getMock.mockResolvedValueOnce({
      data: { ...mockProfile, leaderboard_rank: null },
    });
    render(<PlayerProfilePage />);
    await waitFor(() => {
      expect(screen.getByTestId('leaderboard-rank')).toHaveTextContent('Unranked');
    });
  });

  it('shows error on API failure', async () => {
    getMock.mockRejectedValueOnce(new Error('Network error'));
    render(<PlayerProfilePage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load profile/i)).toBeInTheDocument();
    });
  });
});
