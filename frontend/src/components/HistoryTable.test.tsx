import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import HistoryTable from './HistoryTable';
import type { PaginatedResponse, GameHistoryEntry, MyHistoryEntry } from './HistoryTable';

// ---------------------------------------------------------------------------
// Mock apiClient
// ---------------------------------------------------------------------------

const mockGet = vi.fn();

vi.mock('@/lib/api-client', () => ({
  apiClient: { get: (...args: unknown[]) => mockGet(...args) },
}));

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeGameHistory(count: number, page = 1): PaginatedResponse<GameHistoryEntry> {
  const items: GameHistoryEntry[] = Array.from({ length: count }, (_, i) => ({
    period_number: `202504291000000${page}${i}`,
    winning_number: i % 10,
    winning_color: i % 2 === 0 ? 'red' : 'green',
    big_small_label: (i % 10) >= 5 ? 'Big' : 'Small',
    completed_at: new Date().toISOString(),
  }));
  return { items, total: 25, page, size: 10, has_more: page < 3 };
}

function makeMyHistory(count: number, page = 1): PaginatedResponse<MyHistoryEntry> {
  const items: MyHistoryEntry[] = Array.from({ length: count }, (_, i) => ({
    period_number: `202504291000000${page}${i}`,
    bet_type: i % 2 === 0 ? 'green' : 'big',
    bet_amount: '100.00',
    is_winner: i % 2 === 0,
    payout_amount: i % 2 === 0 ? '196.00' : '0.00',
    created_at: new Date().toISOString(),
  }));
  return { items, total: 15, page, size: 10, has_more: page < 2 };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe('HistoryTable', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Default: game history returns data, my-history returns data
    mockGet.mockImplementation((url: string) => {
      if (url === '/game/history') {
        return Promise.resolve({ data: makeGameHistory(10) });
      }
      if (url === '/game/my-history') {
        return Promise.resolve({ data: makeMyHistory(5) });
      }
      return Promise.reject(new Error('Unknown endpoint'));
    });
  });

  // -----------------------------------------------------------------------
  // Tab rendering
  // -----------------------------------------------------------------------

  it('renders three sub-tabs', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Game history' })).toBeInTheDocument();
    });
    expect(screen.getByRole('tab', { name: 'Chart' })).toBeInTheDocument();
    expect(screen.getByRole('tab', { name: 'My history' })).toBeInTheDocument();
  });

  it('defaults to Game history tab selected', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Game history' })).toHaveAttribute(
        'aria-selected',
        'true',
      );
    });
  });

  // -----------------------------------------------------------------------
  // Tab switching
  // -----------------------------------------------------------------------

  it('switches to Chart tab on click', async () => {
    const user = userEvent.setup();
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Game history' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'Chart' }));
    expect(screen.getByRole('tab', { name: 'Chart' })).toHaveAttribute(
      'aria-selected',
      'true',
    );
    expect(screen.getByText('Chart view coming soon')).toBeInTheDocument();
  });

  it('switches to My history tab and fetches data', async () => {
    const user = userEvent.setup();
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Game history' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'My history' }));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/game/my-history', {
        params: { page: 1, size: 10 },
      });
    });
  });

  // -----------------------------------------------------------------------
  // Game history tab content
  // -----------------------------------------------------------------------

  it('renders game history table with correct columns', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByText('Period')).toBeInTheDocument();
    });
    expect(screen.getByText('Number')).toBeInTheDocument();
    expect(screen.getByText('Big/Small')).toBeInTheDocument();
    expect(screen.getByText('Color')).toBeInTheDocument();
  });

  it('fetches game history with correct params', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/game/history', {
        params: { page: 1, size: 10, mode_id: 'mode-1' },
      });
    });
  });

  it('renders period numbers in game history rows', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByText('20250429100000010')).toBeInTheDocument();
    });
  });

  it('renders color-coded number cells', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/game/history') {
        return Promise.resolve({
          data: {
            items: [
              {
                period_number: '20250429100000001',
                winning_number: 3,
                winning_color: 'green',
                big_small_label: 'Small',
                completed_at: new Date().toISOString(),
              },
            ],
            total: 1,
            page: 1,
            size: 10,
            has_more: false,
          },
        });
      }
      return Promise.reject(new Error('Unknown'));
    });

    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      const numberCell = screen.getByText('3');
      expect(numberCell).toBeInTheDocument();
      // The number should have a green background class
      expect(numberCell.className).toContain('bg-casino-green');
    });
  });

  it('renders Big/Small labels correctly', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/game/history') {
        return Promise.resolve({
          data: {
            items: [
              {
                period_number: '20250429100000001',
                winning_number: 7,
                winning_color: 'green',
                big_small_label: 'Big',
                completed_at: new Date().toISOString(),
              },
              {
                period_number: '20250429100000002',
                winning_number: 2,
                winning_color: 'red',
                big_small_label: 'Small',
                completed_at: new Date().toISOString(),
              },
            ],
            total: 2,
            page: 1,
            size: 10,
            has_more: false,
          },
        });
      }
      return Promise.reject(new Error('Unknown'));
    });

    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByText('Big')).toBeInTheDocument();
      expect(screen.getByText('Small')).toBeInTheDocument();
    });
  });

  it('renders multiple color dots for dual-color numbers (0 and 5)', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/game/history') {
        return Promise.resolve({
          data: {
            items: [
              {
                period_number: '20250429100000001',
                winning_number: 0,
                winning_color: 'red',
                big_small_label: 'Small',
                completed_at: new Date().toISOString(),
              },
            ],
            total: 1,
            page: 1,
            size: 10,
            has_more: false,
          },
        });
      }
      return Promise.reject(new Error('Unknown'));
    });

    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      // Number 0 has both red and violet colors
      const redDot = screen.getByLabelText('red');
      const violetDot = screen.getByLabelText('violet');
      expect(redDot).toBeInTheDocument();
      expect(violetDot).toBeInTheDocument();
    });
  });

  it('shows empty state when no game history', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/game/history') {
        return Promise.resolve({
          data: { items: [], total: 0, page: 1, size: 10, has_more: false },
        });
      }
      return Promise.reject(new Error('Unknown'));
    });

    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByText('No history yet')).toBeInTheDocument();
    });
  });

  it('shows error state when game history fetch fails', async () => {
    mockGet.mockImplementation((url: string) => {
      if (url === '/game/history') {
        return Promise.reject(new Error('Network error'));
      }
      return Promise.reject(new Error('Unknown'));
    });

    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByText('Failed to load game history')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Pagination
  // -----------------------------------------------------------------------

  it('renders pagination controls when total exceeds page size', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByLabelText('Pagination')).toBeInTheDocument();
    });
    expect(screen.getByLabelText('Previous page')).toBeInTheDocument();
    expect(screen.getByLabelText('Next page')).toBeInTheDocument();
  });

  it('navigates to next page on click', async () => {
    const user = userEvent.setup();
    mockGet.mockImplementation((url: string, opts?: { params?: Record<string, unknown> }) => {
      if (url === '/game/history') {
        const p = (opts?.params?.page as number) ?? 1;
        return Promise.resolve({ data: makeGameHistory(10, p) });
      }
      return Promise.reject(new Error('Unknown'));
    });

    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByLabelText('Next page')).toBeInTheDocument();
    });

    await user.click(screen.getByLabelText('Next page'));
    await waitFor(() => {
      expect(mockGet).toHaveBeenCalledWith('/game/history', {
        params: { page: 2, size: 10, mode_id: 'mode-1' },
      });
    });
  });

  it('disables previous button on first page', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByLabelText('Previous page')).toBeDisabled();
    });
  });

  // -----------------------------------------------------------------------
  // My history tab content
  // -----------------------------------------------------------------------

  it('renders my history table with correct columns', async () => {
    const user = userEvent.setup();
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'My history' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'My history' }));
    await waitFor(() => {
      const panel = screen.getByRole('tabpanel', { name: 'My history' });
      expect(within(panel).getByText('Period')).toBeInTheDocument();
      expect(within(panel).getByText('Type')).toBeInTheDocument();
      expect(within(panel).getByText('Amount')).toBeInTheDocument();
      expect(within(panel).getByText('Result')).toBeInTheDocument();
      expect(within(panel).getByText('Payout')).toBeInTheDocument();
    });
  });

  it('renders win/loss styling in my history', async () => {
    const user = userEvent.setup();
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'My history' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'My history' }));
    await waitFor(() => {
      const wins = screen.getAllByText('Win');
      const losses = screen.getAllByText('Loss');
      expect(wins.length).toBeGreaterThan(0);
      expect(losses.length).toBeGreaterThan(0);
      // Win should have green styling
      expect(wins[0].className).toContain('text-casino-green');
      // Loss should have red styling
      expect(losses[0].className).toContain('text-casino-red');
    });
  });

  it('shows empty state when no bets in my history', async () => {
    const user = userEvent.setup();
    mockGet.mockImplementation((url: string) => {
      if (url === '/game/history') {
        return Promise.resolve({ data: makeGameHistory(10) });
      }
      if (url === '/game/my-history') {
        return Promise.resolve({
          data: { items: [], total: 0, page: 1, size: 10, has_more: false },
        });
      }
      return Promise.reject(new Error('Unknown'));
    });

    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'My history' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'My history' }));
    await waitFor(() => {
      expect(screen.getByText('No bets yet')).toBeInTheDocument();
    });
  });

  // -----------------------------------------------------------------------
  // Chart tab
  // -----------------------------------------------------------------------

  it('renders chart placeholder', async () => {
    const user = userEvent.setup();
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('tab', { name: 'Chart' })).toBeInTheDocument();
    });

    await user.click(screen.getByRole('tab', { name: 'Chart' }));
    expect(screen.getByText('Chart view coming soon')).toBeInTheDocument();
  });

  // -----------------------------------------------------------------------
  // ARIA / accessibility
  // -----------------------------------------------------------------------

  it('has proper ARIA label on the section', async () => {
    render(<HistoryTable gameModeId="mode-1" />);
    await waitFor(() => {
      expect(screen.getByRole('region', { name: 'History table' })).toBeInTheDocument();
    });
  });
});
