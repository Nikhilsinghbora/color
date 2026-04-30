import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { replaceMock, getMock, postMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock('@/hooks/useAdminGuard', () => ({
  useAdminGuard: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { get: getMock, post: postMock },
}));

import AdminPlayersPage from './page';

const mockPlayers = {
  items: [
    { id: 'p1', email: 'alice@test.com', username: 'alice', is_active: true, created_at: '2024-01-15T10:00:00Z' },
    { id: 'p2', email: 'bob@test.com', username: 'bob', is_active: false, created_at: '2024-02-20T12:00:00Z' },
  ],
  total: 2,
  page: 1,
  size: 20,
  has_more: false,
};

describe('AdminPlayersPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: mockPlayers });
    postMock.mockResolvedValue({ data: { message: 'OK' } });
  });

  it('renders the page title', async () => {
    render(<AdminPlayersPage />);
    expect(screen.getByText('Player Management')).toBeInTheDocument();
    await waitFor(() => expect(getMock).toHaveBeenCalled());
  });

  it('fetches players on mount', async () => {
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/players', { params: { search: undefined, page: 1 } });
    });
  });

  it('displays player list with details', async () => {
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
    });
    expect(screen.getByText('bob')).toBeInTheDocument();
    expect(screen.getByText('alice@test.com')).toBeInTheDocument();
    expect(screen.getByText('Active')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('searches players when typing in search box', async () => {
    render(<AdminPlayersPage />);
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText(/search players/i), {
      target: { value: 'alice' },
    });

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/players', { params: { search: 'alice', page: 1 } });
    });
  });

  it('calls suspend action on player', async () => {
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/suspend alice/i));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/admin/players/p1/suspend');
    });
  });

  it('calls ban action on player', async () => {
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(screen.getByText('bob')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/ban bob/i));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/admin/players/p2/ban');
    });
  });

  it('shows success message after action', async () => {
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
    });

    fireEvent.click(screen.getByLabelText(/suspend alice/i));

    await waitFor(() => {
      expect(screen.getByText(/player suspended successfully/i)).toBeInTheDocument();
    });
  });

  it('shows empty state when no players found', async () => {
    getMock.mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, size: 20, has_more: false } });
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(screen.getByText(/no players found/i)).toBeInTheDocument();
    });
  });

  it('shows error on API failure', async () => {
    getMock.mockRejectedValueOnce(new Error('Network error'));
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load players/i)).toBeInTheDocument();
    });
  });

  it('renders pagination controls', async () => {
    render(<AdminPlayersPage />);
    await waitFor(() => {
      expect(screen.getByText('alice')).toBeInTheDocument();
    });
    expect(screen.getByText('Previous')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText('Page 1')).toBeInTheDocument();
  });
});
