import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import type { ColorOption } from '@/types';

// --- Hoisted mocks ---
const { apiClientMock, parseApiErrorMock, getErrorMessageMock } = vi.hoisted(() => ({
  apiClientMock: { post: vi.fn() },
  parseApiErrorMock: vi.fn(),
  getErrorMessageMock: vi.fn().mockReturnValue('An unexpected error occurred'),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: apiClientMock,
  parseApiError: parseApiErrorMock,
  getErrorMessage: getErrorMessageMock,
}));

// Mock game store
const mockGameActions = vi.hoisted(() => ({
  setBetSelection: vi.fn(),
  removeBetSelection: vi.fn(),
  addPlacedBet: vi.fn(),
}));

let mockGameState = vi.hoisted(() => ({
  selectedBets: {} as Record<string, string>,
  placedBets: [] as Array<{
    id: string;
    color: string;
    amount: string;
    oddsAtPlacement: string;
    potentialPayout: string;
  }>,
}));

vi.mock('@/stores/game-store', () => ({
  useGameStore: (selector: (s: typeof mockGameState.value & typeof mockGameActions) => unknown) =>
    selector({ ...mockGameState.value, ...mockGameActions }),
}));

// Mock wallet store
const mockWalletActions = vi.hoisted(() => ({
  updateBalance: vi.fn(),
}));

let mockWalletState = vi.hoisted(() => ({
  balance: '100.00' as string | null,
}));

vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector: (s: typeof mockWalletState.value & typeof mockWalletActions) => unknown) =>
    selector({ ...mockWalletState.value, ...mockWalletActions }),
}));

vi.mock('@/lib/utils', () => ({
  calculatePotentialPayout: (amount: string, odds: string) => {
    return (parseFloat(amount) * parseFloat(odds)).toFixed(2);
  },
}));

import BettingControls from './BettingControls';

const defaultColorOptions: ColorOption[] = [
  { color: 'red', odds: '2.0' },
  { color: 'blue', odds: '3.0' },
  { color: 'green', odds: '5.0' },
];

const defaultProps = {
  colorOptions: defaultColorOptions,
  minBet: '1.00',
  maxBet: '100.00',
  roundId: 'round-1',
  phase: 'betting',
};

describe('BettingControls', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockGameState.value = {
      selectedBets: {},
      placedBets: [],
    };
    mockWalletState.value = { balance: '100.00' };
  });

  it('renders color chips with odds', () => {
    render(<BettingControls {...defaultProps} />);
    expect(screen.getByRole('button', { name: /red — odds 2\.0x/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /blue — odds 3\.0x/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /green — odds 5\.0x/i })).toBeInTheDocument();
  });

  it('enables color chips during betting phase', () => {
    render(<BettingControls {...defaultProps} />);
    const redBtn = screen.getByRole('button', { name: /red — odds 2\.0x/i });
    expect(redBtn).not.toBeDisabled();
  });

  it('disables color chips when phase is not betting', () => {
    render(<BettingControls {...defaultProps} phase="resolution" />);
    const redBtn = screen.getByRole('button', { name: /red — odds 2\.0x/i });
    expect(redBtn).toBeDisabled();
  });

  it('disables color chips during result phase', () => {
    render(<BettingControls {...defaultProps} phase="result" />);
    const redBtn = screen.getByRole('button', { name: /red — odds 2\.0x/i });
    expect(redBtn).toBeDisabled();
  });

  it('calls setBetSelection when a color chip is clicked', () => {
    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /red — odds 2\.0x/i }));
    expect(mockGameActions.setBetSelection).toHaveBeenCalledWith('red', '');
  });

  it('calls removeBetSelection when a selected chip is clicked again', () => {
    mockGameState.value.selectedBets = { red: '10' };
    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByRole('button', { name: /red — odds 2\.0x/i }));
    expect(mockGameActions.removeBetSelection).toHaveBeenCalledWith('red');
  });

  it('shows bet input field for selected color', () => {
    mockGameState.value.selectedBets = { red: '' };
    render(<BettingControls {...defaultProps} />);
    expect(screen.getByLabelText(/bet amount for red/i)).toBeInTheDocument();
    expect(screen.getByText(/place bet/i)).toBeInTheDocument();
  });

  it('displays min/max bet amounts', () => {
    mockGameState.value.selectedBets = { red: '' };
    render(<BettingControls {...defaultProps} />);
    expect(screen.getByText(/min: \$1\.00/i)).toBeInTheDocument();
    expect(screen.getByText(/max: \$100\.00/i)).toBeInTheDocument();
  });

  it('shows potential payout when amount is entered', () => {
    mockGameState.value.selectedBets = { red: '10' };
    render(<BettingControls {...defaultProps} />);
    // 10 * 2.0 = 20.00
    expect(screen.getByText(/potential payout/i)).toBeInTheDocument();
    expect(screen.getByText('$20.00')).toBeInTheDocument();
  });

  it('shows inline error for amount below minimum', async () => {
    mockGameState.value.selectedBets = { red: '0.50' };
    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByText(/place bet/i));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Minimum bet is $1.00');
    });
  });

  it('shows inline error for amount above maximum', async () => {
    mockGameState.value.selectedBets = { red: '200' };
    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByText(/place bet/i));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Maximum bet is $100.00');
    });
  });

  it('shows inline error for insufficient balance', async () => {
    mockWalletState.value.balance = '5.00';
    mockGameState.value.selectedBets = { red: '10' };
    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByText(/place bet/i));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Insufficient balance');
    });
  });

  it('shows inline error for empty amount', async () => {
    mockGameState.value.selectedBets = { red: '' };
    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByText(/place bet/i));
    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Enter a valid bet amount');
    });
  });

  it('places bet successfully and shows toast', async () => {
    mockGameState.value.selectedBets = { red: '10' };
    apiClientMock.post.mockResolvedValueOnce({
      data: {
        id: 'bet-1',
        color: 'red',
        amount: '10.00',
        odds_at_placement: '2.0',
        balance_after: '90.00',
      },
    });

    const onBetPlaced = vi.fn();
    render(<BettingControls {...defaultProps} onBetPlaced={onBetPlaced} />);
    fireEvent.click(screen.getByText(/place bet/i));

    await waitFor(() => {
      expect(apiClientMock.post).toHaveBeenCalledWith('/game/bet', {
        round_id: 'round-1',
        color: 'red',
        amount: '10',
      });
    });

    await waitFor(() => {
      expect(mockGameActions.addPlacedBet).toHaveBeenCalledWith({
        id: 'bet-1',
        color: 'red',
        amount: '10.00',
        oddsAtPlacement: '2.0',
        potentialPayout: '20.00',
      });
    });

    expect(mockWalletActions.updateBalance).toHaveBeenCalledWith('90.00');
    expect(mockGameActions.removeBetSelection).toHaveBeenCalledWith('red');
    expect(onBetPlaced).toHaveBeenCalledWith('red', '10.00');
    expect(screen.getByText(/bet placed: \$10\.00 on red/i)).toBeInTheDocument();
  });

  it('handles API validation error (BET_BELOW_MIN)', async () => {
    mockGameState.value.selectedBets = { red: '5' };
    const apiError = new Error('Request failed');
    (apiError as any).response = {
      data: { error: { code: 'BET_BELOW_MIN', message: 'Bet amount is below the minimum' } },
    };
    (apiError as any).isAxiosError = true;
    apiClientMock.post.mockRejectedValueOnce(apiError);
    parseApiErrorMock.mockReturnValueOnce({ code: 'BET_BELOW_MIN', message: 'Bet amount is below the minimum' });
    getErrorMessageMock.mockReturnValueOnce('Bet amount is below the minimum');

    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByText(/place bet/i));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Bet amount is below the minimum');
    });
  });

  it('handles BETTING_CLOSED error', async () => {
    mockGameState.value.selectedBets = { red: '10' };
    const apiError = new Error('Request failed');
    apiClientMock.post.mockRejectedValueOnce(apiError);
    parseApiErrorMock.mockReturnValueOnce({ code: 'BETTING_CLOSED', message: 'Betting is closed for this round' });
    getErrorMessageMock.mockReturnValueOnce('Betting is closed for this round');

    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByText(/place bet/i));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('Betting is closed for this round');
    });
  });

  it('handles unknown API error gracefully', async () => {
    mockGameState.value.selectedBets = { red: '10' };
    apiClientMock.post.mockRejectedValueOnce(new Error('Network error'));
    parseApiErrorMock.mockReturnValueOnce(null);

    render(<BettingControls {...defaultProps} />);
    fireEvent.click(screen.getByText(/place bet/i));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toHaveTextContent('An unexpected error occurred');
    });
  });

  it('displays bet summary with placed bets', () => {
    mockGameState.value.placedBets = [
      { id: 'b1', color: 'red', amount: '10.00', oddsAtPlacement: '2.0', potentialPayout: '20.00' },
      { id: 'b2', color: 'blue', amount: '5.00', oddsAtPlacement: '3.0', potentialPayout: '15.00' },
    ];
    render(<BettingControls {...defaultProps} />);
    expect(screen.getByText(/your bets/i)).toBeInTheDocument();
    expect(screen.getByText('$10.00 →')).toBeInTheDocument();
    expect(screen.getByText('$20.00')).toBeInTheDocument();
    expect(screen.getByText('$5.00 →')).toBeInTheDocument();
    expect(screen.getByText('$15.00')).toBeInTheDocument();
  });

  it('does not show bet summary when no bets placed', () => {
    mockGameState.value.placedBets = [];
    render(<BettingControls {...defaultProps} />);
    expect(screen.queryByText(/your bets/i)).not.toBeInTheDocument();
  });

  it('marks color chip as "Bet placed" for already-placed colors', () => {
    mockGameState.value.placedBets = [
      { id: 'b1', color: 'red', amount: '10.00', oddsAtPlacement: '2.0', potentialPayout: '20.00' },
    ];
    render(<BettingControls {...defaultProps} />);
    expect(screen.getByText('Bet placed')).toBeInTheDocument();
  });

  it('does not show bet inputs when phase is not betting', () => {
    mockGameState.value.selectedBets = { red: '10' };
    render(<BettingControls {...defaultProps} phase="resolution" />);
    expect(screen.queryByLabelText(/bet amount for red/i)).not.toBeInTheDocument();
  });

  it('sets aria-pressed on selected chip', () => {
    mockGameState.value.selectedBets = { red: '10' };
    render(<BettingControls {...defaultProps} />);
    const redBtn = screen.getByRole('button', { name: /red — odds 2\.0x/i });
    expect(redBtn).toHaveAttribute('aria-pressed', 'true');
  });

  it('sets aria-pressed false on unselected chip', () => {
    render(<BettingControls {...defaultProps} />);
    const blueBtn = screen.getByRole('button', { name: /blue — odds 3\.0x/i });
    expect(blueBtn).toHaveAttribute('aria-pressed', 'false');
  });
});
