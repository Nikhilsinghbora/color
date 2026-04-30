import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import RulesModal, { RulesModalProps } from './RulesModal';

const defaultProps: RulesModalProps = {
  isOpen: true,
  onClose: vi.fn(),
};

describe('RulesModal', () => {
  // --- Visibility ---
  it('renders nothing when isOpen is false', () => {
    render(<RulesModal isOpen={false} onClose={vi.fn()} />);
    expect(screen.queryByTestId('rules-dialog')).not.toBeInTheDocument();
  });

  it('renders the dialog when isOpen is true', () => {
    render(<RulesModal {...defaultProps} />);
    expect(screen.getByTestId('rules-dialog')).toBeInTheDocument();
  });

  // --- Header ---
  it('displays "How to Play" header', () => {
    render(<RulesModal {...defaultProps} />);
    expect(screen.getByTestId('rules-header')).toHaveTextContent('How to Play');
  });

  // --- Color bet payouts (Req 10.3) ---
  it('explains Green pays 2x', () => {
    render(<RulesModal {...defaultProps} />);
    const section = screen.getByTestId('rules-color-section');
    expect(section).toHaveTextContent('Green pays 2x');
  });

  it('explains Red pays 2x', () => {
    render(<RulesModal {...defaultProps} />);
    const section = screen.getByTestId('rules-color-section');
    expect(section).toHaveTextContent('Red pays 2x');
  });

  it('explains Violet pays 4.8x', () => {
    render(<RulesModal {...defaultProps} />);
    const section = screen.getByTestId('rules-color-section');
    expect(section).toHaveTextContent('Violet pays 4.8x');
  });

  // --- Number bet payouts (Req 10.4) ---
  it('explains number bet pays 9.6x', () => {
    render(<RulesModal {...defaultProps} />);
    const section = screen.getByTestId('rules-number-section');
    expect(section).toHaveTextContent('9.6x');
  });

  // --- Big/Small bet payouts (Req 10.5) ---
  it('explains Big (5–9) pays 2x', () => {
    render(<RulesModal {...defaultProps} />);
    const section = screen.getByTestId('rules-bigsmall-section');
    expect(section).toHaveTextContent('Big (5–9) pays 2x');
  });

  it('explains Small (0–4) pays 2x', () => {
    render(<RulesModal {...defaultProps} />);
    const section = screen.getByTestId('rules-bigsmall-section');
    expect(section).toHaveTextContent('Small (0–4) pays 2x');
  });

  // --- Service fee (Req 10.6) ---
  it('explains the 2% service fee on winning payouts', () => {
    render(<RulesModal {...defaultProps} />);
    const section = screen.getByTestId('rules-fee-section');
    expect(section).toHaveTextContent('2%');
    expect(section).toHaveTextContent('service fee');
    expect(section).toHaveTextContent('winning payouts');
  });

  // --- Close button (Req 10.7) ---
  it('renders a close button at the bottom', () => {
    render(<RulesModal {...defaultProps} />);
    expect(screen.getByTestId('rules-close-btn')).toBeInTheDocument();
    expect(screen.getByTestId('rules-close-btn')).toHaveTextContent('Close');
  });

  it('calls onClose when close button is clicked', () => {
    const onClose = vi.fn();
    render(<RulesModal isOpen={true} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('rules-close-btn'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('calls onClose when backdrop is clicked', () => {
    const onClose = vi.fn();
    render(<RulesModal isOpen={true} onClose={onClose} />);
    fireEvent.click(screen.getByTestId('rules-backdrop'));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  // --- Accessibility ---
  it('has proper ARIA attributes for the dialog', () => {
    render(<RulesModal {...defaultProps} />);
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-label', 'How to Play');
  });
});
