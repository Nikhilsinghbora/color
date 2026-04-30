import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import WinLossDialog, { WinLossDialogProps } from './WinLossDialog';

const defaultWinProps: WinLossDialogProps = {
  isOpen: true,
  isWin: true,
  winningNumber: 7,
  winningColor: 'green',
  isBig: true,
  totalBonus: '196.00',
  periodNumber: '20250429100051058',
  onClose: vi.fn(),
};

const defaultLossProps: WinLossDialogProps = {
  ...defaultWinProps,
  isWin: false,
  winningNumber: 2,
  winningColor: 'red',
  isBig: false,
  totalBonus: '0.00',
};

describe('WinLossDialog', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('renders nothing when isOpen is false', () => {
    render(<WinLossDialog {...defaultWinProps} isOpen={false} />);
    expect(screen.queryByTestId('winloss-dialog')).not.toBeInTheDocument();
  });

  it('renders the dialog when isOpen is true', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-dialog')).toBeInTheDocument();
  });

  // --- Win state ---
  it('displays "Congratulations" header for a win', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-header')).toHaveTextContent('Congratulations');
  });

  it('applies gold/yellow styling to the win header', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    const header = screen.getByTestId('winloss-header');
    expect(header.className).toContain('text-yellow-400');
  });

  // --- Loss state ---
  it('displays "Sorry" header for a loss', () => {
    render(<WinLossDialog {...defaultLossProps} />);
    expect(screen.getByTestId('winloss-header')).toHaveTextContent('Sorry');
  });

  it('applies muted styling to the loss header', () => {
    render(<WinLossDialog {...defaultLossProps} />);
    const header = screen.getByTestId('winloss-header');
    expect(header.className).toContain('text-casino-text-muted');
  });

  // --- Lottery result ---
  it('displays the winning number', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-winning-number')).toHaveTextContent('7');
  });

  it('displays "Big" label when isBig is true', () => {
    render(<WinLossDialog {...defaultWinProps} isBig={true} />);
    expect(screen.getByTestId('winloss-big-small')).toHaveTextContent('Big');
  });

  it('displays "Small" label when isBig is false', () => {
    render(<WinLossDialog {...defaultWinProps} isBig={false} />);
    expect(screen.getByTestId('winloss-big-small')).toHaveTextContent('Small');
  });

  it('applies the correct color class for the winning number', () => {
    render(<WinLossDialog {...defaultWinProps} winningColor="red" />);
    const numberEl = screen.getByTestId('winloss-winning-number');
    expect(numberEl.className).toContain('bg-casino-red');
  });

  it('applies green color class for green winning color', () => {
    render(<WinLossDialog {...defaultWinProps} winningColor="green" />);
    const numberEl = screen.getByTestId('winloss-winning-number');
    expect(numberEl.className).toContain('bg-casino-green');
  });

  it('applies violet color class for violet winning color', () => {
    render(<WinLossDialog {...defaultWinProps} winningColor="violet" />);
    const numberEl = screen.getByTestId('winloss-winning-number');
    expect(numberEl.className).toContain('bg-casino-violet');
  });

  // --- Bonus and period ---
  it('displays the total bonus with ₹ symbol', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-bonus')).toHaveTextContent('₹196.00');
  });

  it('displays the period number', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-period')).toHaveTextContent('20250429100051058');
  });

  // --- Countdown timer ---
  it('displays initial countdown of 3 seconds', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-countdown')).toHaveTextContent('Closing in 3s');
  });

  it('decrements countdown each second', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-countdown')).toHaveTextContent('Closing in 3s');

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByTestId('winloss-countdown')).toHaveTextContent('Closing in 2s');

    act(() => {
      vi.advanceTimersByTime(1000);
    });
    expect(screen.getByTestId('winloss-countdown')).toHaveTextContent('Closing in 1s');
  });

  it('calls onClose when countdown reaches zero', () => {
    const onClose = vi.fn();
    render(<WinLossDialog {...defaultWinProps} onClose={onClose} />);

    act(() => {
      vi.advanceTimersByTime(3000);
    });

    expect(onClose).toHaveBeenCalledTimes(1);
  });

  // --- Close button ---
  it('renders a close button', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByTestId('winloss-close-btn')).toBeInTheDocument();
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(<WinLossDialog {...defaultWinProps} onClose={onClose} />);

    fireEvent.click(screen.getByTestId('winloss-close-btn'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when backdrop is clicked', () => {
    const onClose = vi.fn();
    render(<WinLossDialog {...defaultWinProps} onClose={onClose} />);

    fireEvent.click(screen.getByTestId('winloss-backdrop'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  // --- Accessibility ---
  it('has proper ARIA attributes for the dialog', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-label', 'Win result');
  });

  it('uses "Loss result" aria-label for loss state', () => {
    render(<WinLossDialog {...defaultLossProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-label', 'Loss result');
  });

  it('close button has accessible label', () => {
    render(<WinLossDialog {...defaultWinProps} />);
    expect(screen.getByRole('button', { name: /close dialog/i })).toBeInTheDocument();
  });
});
