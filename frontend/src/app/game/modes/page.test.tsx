import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import type { GameMode } from '@/types';

// --- Hoisted mocks ---
const { useAuthGuardMock, routerPushMock, apiGetMock } = vi.hoisted(() => ({
  useAuthGuardMock: vi.fn(),
  routerPushMock: vi.fn(),
  apiGetMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: routerPushMock }),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: useAuthGuardMock,
}));

vi.mock('@/lib/api-client', () => ({
  default: { get: apiGetMock },
}));

import GameModesPage from './page';

const MOCK_MODES: GameMode[] = [
  {
    id: 'mode-1',
    name: 'Classic Mode',
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
    name: 'Speed Round',
    mode_type: 'timed_challenge',
    color_options: ['red', 'blue'],
    odds: { red: '1.5', blue: '2.5' },
    min_bet: '5.00',
    max_bet: '500.00',
    round_duration_seconds: 15,
    is_active: true,
  },
  {
    id: 'mode-3',
    name: 'Grand Tournament',
    mode_type: 'tournament',
    color_options: ['red', 'blue', 'green', 'yellow'],
    odds: { red: '2.0', blue: '3.0', green: '5.0', yellow: '10.0' },
    min_bet: '10.00',
    max_bet: '1000.00',
    round_duration_seconds: 60,
    is_active: false,
  },
];

describe('GameModesPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    apiGetMock.mockResolvedValue({ data: MOCK_MODES });
  });

  it('calls useAuthGuard for route protection', async () => {
    render(<GameModesPage />);
    expect(useAuthGuardMock).toHaveBeenCalled();
  });

  it('shows loading skeleton while fetching modes', () => {
    // Never resolve the promise to keep loading state
    apiGetMock.mockReturnValue(new Promise(() => {}));
    render(<GameModesPage />);
    expect(screen.getByRole('status')).toBeInTheDocument();
    expect(screen.getByText(/loading game modes/i)).toBeInTheDocument();
  });

  it('fetches game modes from /game/modes on mount', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(apiGetMock).toHaveBeenCalledWith('/game/modes');
    });
  });

  it('displays all fetched game modes with names', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic Mode')).toBeInTheDocument();
    });
    expect(screen.getByText('Speed Round')).toBeInTheDocument();
    expect(screen.getByText('Grand Tournament')).toBeInTheDocument();
  });

  it('displays mode type badges with correct labels', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByTestId('mode-type-mode-1')).toHaveTextContent('Classic');
    });
    expect(screen.getByTestId('mode-type-mode-2')).toHaveTextContent('Timed Challenge');
    expect(screen.getByTestId('mode-type-mode-3')).toHaveTextContent('Tournament');
  });

  it('displays active/inactive status for each mode', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getAllByText('Active')).toHaveLength(2);
    });
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('displays color options with odds for each mode', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic Mode')).toBeInTheDocument();
    });
    // 2.0x appears in both Classic and Tournament modes
    expect(screen.getAllByText('2.0x').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('3.0x').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('5.0x').length).toBeGreaterThanOrEqual(1);
    // Timed challenge specific odds
    expect(screen.getByText('1.5x')).toBeInTheDocument();
    expect(screen.getByText('2.5x')).toBeInTheDocument();
  });

  it('displays betting limits (min_bet, max_bet) for each mode', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('$1.00')).toBeInTheDocument();
    });
    expect(screen.getByText('$100.00')).toBeInTheDocument();
    expect(screen.getByText('$5.00')).toBeInTheDocument();
    expect(screen.getByText('$500.00')).toBeInTheDocument();
  });

  it('displays round duration for each mode', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('30s')).toBeInTheDocument();
    });
    expect(screen.getByText('15s')).toBeInTheDocument();
    expect(screen.getByText('60s')).toBeInTheDocument();
  });

  it('navigates to /game?mode={mode_id} when an active mode is selected', async () => {
    const user = userEvent.setup();
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic Mode')).toBeInTheDocument();
    });

    const playBtn = screen.getByRole('button', { name: /select classic mode game mode/i });
    await user.click(playBtn);

    expect(routerPushMock).toHaveBeenCalledWith('/game?mode=mode-1');
  });

  it('disables the select button for inactive modes', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('Grand Tournament')).toBeInTheDocument();
    });

    const unavailableBtn = screen.getByRole('button', { name: /select grand tournament game mode/i });
    expect(unavailableBtn).toBeDisabled();
    expect(unavailableBtn).toHaveTextContent('Unavailable');
  });

  it('shows error message when API call fails', async () => {
    apiGetMock.mockRejectedValue(new Error('Network error'));
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(screen.getByText(/failed to load game modes/i)).toBeInTheDocument();
    expect(screen.getByText(/retry/i)).toBeInTheDocument();
  });

  it('does not show loading skeleton after modes are loaded', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic Mode')).toBeInTheDocument();
    });
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('renders semantic HTML with proper ARIA attributes', async () => {
    render(<GameModesPage />);
    await waitFor(() => {
      expect(screen.getByText('Classic Mode')).toBeInTheDocument();
    });
    expect(screen.getByRole('list', { name: /available game modes/i })).toBeInTheDocument();
    expect(screen.getAllByRole('listitem')).toHaveLength(3);
  });
});
