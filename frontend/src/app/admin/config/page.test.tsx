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

import AdminConfigPage from './page';

const mockModes = [
  {
    id: 'mode-1',
    name: 'Classic',
    mode_type: 'classic',
    color_options: ['red', 'blue', 'green'],
    odds: { red: '2.0', blue: '3.0', green: '5.0' },
    min_bet: '1.00',
    max_bet: '100.00',
    round_duration_seconds: 30,
    is_active: true,
  },
  {
    id: 'mode-2',
    name: 'Tournament',
    mode_type: 'tournament',
    color_options: ['red', 'blue'],
    odds: { red: '1.5', blue: '2.5' },
    min_bet: '5.00',
    max_bet: '500.00',
    round_duration_seconds: 60,
    is_active: true,
  },
];

describe('AdminConfigPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: mockModes });
    postMock.mockResolvedValue({ data: { message: 'Updated' } });
  });

  it('renders the page title', async () => {
    render(<AdminConfigPage />);
    expect(screen.getByText('Game Configuration')).toBeInTheDocument();
    await waitFor(() => expect(getMock).toHaveBeenCalled());
  });

  it('fetches game config on mount', async () => {
    render(<AdminConfigPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/game-config');
    });
  });

  it('displays config forms for each game mode', async () => {
    render(<AdminConfigPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic')).toBeInTheDocument();
    });
    expect(screen.getByText('Tournament')).toBeInTheDocument();
  });

  it('displays editable fields with current values', async () => {
    render(<AdminConfigPage />);
    await waitFor(() => {
      expect(screen.getByLabelText(/min bet/i, { selector: '#min-bet-mode-1' })).toHaveValue('1.00');
    });
    expect(screen.getByLabelText(/max bet/i, { selector: '#max-bet-mode-1' })).toHaveValue('100.00');
  });

  it('submits config changes for a mode', async () => {
    render(<AdminConfigPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic')).toBeInTheDocument();
    });

    const minBetInput = screen.getByLabelText(/min bet/i, { selector: '#min-bet-mode-1' });
    fireEvent.change(minBetInput, { target: { value: '2.00' } });

    const form = screen.getByLabelText(/configuration for classic/i);
    const saveBtn = form.querySelector('button[type="submit"]')!;
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/admin/game-config', expect.objectContaining({
        game_mode_id: 'mode-1',
        min_bet: '2.00',
      }));
    });
  });

  it('shows success message after saving', async () => {
    render(<AdminConfigPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic')).toBeInTheDocument();
    });

    const form = screen.getByLabelText(/configuration for classic/i);
    const saveBtn = form.querySelector('button[type="submit"]')!;
    fireEvent.click(saveBtn);

    await waitFor(() => {
      expect(screen.getByText(/changes take effect next round/i)).toBeInTheDocument();
    });
  });

  it('shows error on API failure', async () => {
    getMock.mockRejectedValueOnce(new Error('Network error'));
    render(<AdminConfigPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load game configuration/i)).toBeInTheDocument();
    });
  });
});
