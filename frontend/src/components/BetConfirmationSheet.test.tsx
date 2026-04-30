import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import BetConfirmationSheet, { type BetConfirmationSheetProps } from './BetConfirmationSheet';

const defaultProps: BetConfirmationSheetProps = {
  isOpen: true,
  betType: 'green',
  gameModeName: 'Win Go 1Min',
  balance: '500.00',
  onConfirm: vi.fn(),
  onCancel: vi.fn(),
};

function renderSheet(overrides: Partial<BetConfirmationSheetProps> = {}) {
  const props = { ...defaultProps, ...overrides };
  return render(<BetConfirmationSheet {...props} />);
}

describe('BetConfirmationSheet', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ── Visibility ──

  it('renders nothing when isOpen is false', () => {
    renderSheet({ isOpen: false });
    expect(screen.queryByTestId('bet-confirmation-sheet')).not.toBeInTheDocument();
  });

  it('renders the bottom sheet when isOpen is true', () => {
    renderSheet();
    expect(screen.getByTestId('bet-confirmation-sheet')).toBeInTheDocument();
  });

  // ── Header ──

  it('displays game mode name and bet type in the header', () => {
    renderSheet({ gameModeName: 'Win Go 1Min', betType: 'green' });
    expect(screen.getByTestId('bet-sheet-header')).toHaveTextContent('Win Go 1Min — Select Green');
  });

  it('displays correct header for number bet type', () => {
    renderSheet({ betType: '7' });
    expect(screen.getByTestId('bet-sheet-header')).toHaveTextContent('Win Go 1Min — Select 7');
  });

  it('displays correct header for big bet type', () => {
    renderSheet({ betType: 'big' });
    expect(screen.getByTestId('bet-sheet-header')).toHaveTextContent('Win Go 1Min — Select Big');
  });

  it('displays correct header for small bet type', () => {
    renderSheet({ betType: 'small' });
    expect(screen.getByTestId('bet-sheet-header')).toHaveTextContent('Win Go 1Min — Select Small');
  });

  it('displays correct header for violet bet type', () => {
    renderSheet({ betType: 'violet' });
    expect(screen.getByTestId('bet-sheet-header')).toHaveTextContent('Win Go 1Min — Select Violet');
  });

  it('displays correct header for red bet type', () => {
    renderSheet({ betType: 'red' });
    expect(screen.getByTestId('bet-sheet-header')).toHaveTextContent('Win Go 1Min — Select Red');
  });

  // ── Balance Preset Buttons ──

  it('renders all four balance preset buttons', () => {
    renderSheet();
    expect(screen.getByTestId('preset-1')).toHaveTextContent('₹1');
    expect(screen.getByTestId('preset-10')).toHaveTextContent('₹10');
    expect(screen.getByTestId('preset-100')).toHaveTextContent('₹100');
    expect(screen.getByTestId('preset-1000')).toHaveTextContent('₹1000');
  });

  it('defaults to ₹1 preset selected', () => {
    renderSheet();
    expect(screen.getByTestId('preset-1')).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('preset-10')).toHaveAttribute('aria-checked', 'false');
  });

  it('selects a different preset when clicked', async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByTestId('preset-100'));
    expect(screen.getByTestId('preset-100')).toHaveAttribute('aria-checked', 'true');
    expect(screen.getByTestId('preset-1')).toHaveAttribute('aria-checked', 'false');
  });

  it('updates total amount when preset changes', async () => {
    const user = userEvent.setup();
    renderSheet();

    // Default: ₹1 × 1 = ₹1.00
    expect(screen.getByTestId('confirm-button')).toHaveTextContent('Total amount ₹1.00');

    await user.click(screen.getByTestId('preset-100'));
    // ₹100 × 1 = ₹100.00
    expect(screen.getByTestId('confirm-button')).toHaveTextContent('Total amount ₹100.00');
  });

  // ── Quantity Controls ──

  it('renders quantity controls with default value of 1', () => {
    renderSheet();
    const input = screen.getByTestId('quantity-input') as HTMLInputElement;
    expect(input.value).toBe('1');
  });

  it('increments quantity when plus button is clicked', async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByRole('button', { name: /increase quantity/i }));
    const input = screen.getByTestId('quantity-input') as HTMLInputElement;
    expect(input.value).toBe('2');
  });

  it('decrements quantity when minus button is clicked', async () => {
    const user = userEvent.setup();
    renderSheet();

    // First increase to 2, then decrease back to 1
    await user.click(screen.getByRole('button', { name: /increase quantity/i }));
    await user.click(screen.getByRole('button', { name: /decrease quantity/i }));
    const input = screen.getByTestId('quantity-input') as HTMLInputElement;
    expect(input.value).toBe('1');
  });

  it('does not go below 1', () => {
    renderSheet();
    const minusBtn = screen.getByRole('button', { name: /decrease quantity/i });
    expect(minusBtn).toBeDisabled();
  });

  it('does not go above 100', async () => {
    const user = userEvent.setup();
    renderSheet();

    // Set quantity to 100 via multiplier
    await user.click(screen.getByTestId('multiplier-X100'));
    const plusBtn = screen.getByRole('button', { name: /increase quantity/i });
    expect(plusBtn).toBeDisabled();
  });

  it('updates total when quantity changes', async () => {
    const user = userEvent.setup();
    renderSheet();

    // Select ₹10 preset
    await user.click(screen.getByTestId('preset-10'));
    // Increase quantity to 2
    await user.click(screen.getByRole('button', { name: /increase quantity/i }));
    // ₹10 × 2 = ₹20.00
    expect(screen.getByTestId('confirm-button')).toHaveTextContent('Total amount ₹20.00');
  });

  // ── Quick Multiplier Row ──

  it('renders all multiplier buttons', () => {
    renderSheet();
    expect(screen.getByTestId('multiplier-Random')).toBeInTheDocument();
    expect(screen.getByTestId('multiplier-X1')).toBeInTheDocument();
    expect(screen.getByTestId('multiplier-X5')).toBeInTheDocument();
    expect(screen.getByTestId('multiplier-X10')).toBeInTheDocument();
    expect(screen.getByTestId('multiplier-X20')).toBeInTheDocument();
    expect(screen.getByTestId('multiplier-X50')).toBeInTheDocument();
    expect(screen.getByTestId('multiplier-X100')).toBeInTheDocument();
  });

  it('defaults to X1 multiplier selected', () => {
    renderSheet();
    expect(screen.getByTestId('multiplier-X1')).toHaveAttribute('aria-checked', 'true');
  });

  it('sets quantity to multiplier value when a multiplier is clicked', async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByTestId('multiplier-X5'));
    const input = screen.getByTestId('quantity-input') as HTMLInputElement;
    expect(input.value).toBe('5');
    expect(screen.getByTestId('multiplier-X5')).toHaveAttribute('aria-checked', 'true');
  });

  it('sets quantity to X10 when X10 multiplier is clicked', async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByTestId('multiplier-X10'));
    const input = screen.getByTestId('quantity-input') as HTMLInputElement;
    expect(input.value).toBe('10');
  });

  it('sets quantity to X50 when X50 multiplier is clicked', async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByTestId('multiplier-X50'));
    const input = screen.getByTestId('quantity-input') as HTMLInputElement;
    expect(input.value).toBe('50');
  });

  it('sets a random quantity between 1 and 100 when Random is clicked', async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByTestId('multiplier-Random'));
    const input = screen.getByTestId('quantity-input') as HTMLInputElement;
    const val = Number(input.value);
    expect(val).toBeGreaterThanOrEqual(1);
    expect(val).toBeLessThanOrEqual(100);
    expect(screen.getByTestId('multiplier-Random')).toHaveAttribute('aria-checked', 'true');
  });

  it('updates total immediately when multiplier changes', async () => {
    const user = userEvent.setup();
    renderSheet();

    // Select ₹10 preset, then X5 multiplier → ₹10 × 5 = ₹50.00
    await user.click(screen.getByTestId('preset-10'));
    await user.click(screen.getByTestId('multiplier-X5'));
    expect(screen.getByTestId('confirm-button')).toHaveTextContent('Total amount ₹50.00');
  });

  // ── Agree to Rules Checkbox ──

  it('renders the agree checkbox unchecked by default', () => {
    renderSheet();
    const checkbox = screen.getByTestId('agree-checkbox') as HTMLInputElement;
    expect(checkbox.checked).toBe(false);
  });

  it('confirm button is disabled when checkbox is unchecked', () => {
    renderSheet();
    expect(screen.getByTestId('confirm-button')).toBeDisabled();
  });

  it('confirm button is enabled when checkbox is checked', async () => {
    const user = userEvent.setup();
    renderSheet();

    await user.click(screen.getByTestId('agree-checkbox'));
    expect(screen.getByTestId('confirm-button')).not.toBeDisabled();
  });

  // ── Confirm and Cancel ──

  it('calls onConfirm with amount and quantity when confirm is clicked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderSheet({ onConfirm, balance: '500.00' });

    // Select ₹10 preset, X5 multiplier, agree to rules
    await user.click(screen.getByTestId('preset-10'));
    await user.click(screen.getByTestId('multiplier-X5'));
    await user.click(screen.getByTestId('agree-checkbox'));
    await user.click(screen.getByTestId('confirm-button'));

    expect(onConfirm).toHaveBeenCalledWith(10, 5);
  });

  it('does not call onConfirm when checkbox is not checked', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderSheet({ onConfirm });

    await user.click(screen.getByTestId('confirm-button'));
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('calls onCancel when cancel button is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    renderSheet({ onCancel });

    await user.click(screen.getByTestId('cancel-button'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  it('calls onCancel when backdrop is clicked', async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    renderSheet({ onCancel });

    await user.click(screen.getByTestId('bet-sheet-backdrop'));
    expect(onCancel).toHaveBeenCalledTimes(1);
  });

  // ── Balance Validation ──

  it('shows inline error when total exceeds balance', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderSheet({ onConfirm, balance: '50.00' });

    // ₹100 × 1 = ₹100 > ₹50 balance
    await user.click(screen.getByTestId('preset-100'));
    await user.click(screen.getByTestId('agree-checkbox'));
    await user.click(screen.getByTestId('confirm-button'));

    expect(screen.getByTestId('balance-error')).toBeInTheDocument();
    expect(screen.getByTestId('balance-error')).toHaveTextContent(/insufficient balance/i);
    expect(onConfirm).not.toHaveBeenCalled();
  });

  it('does not show error when total is within balance', async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    renderSheet({ onConfirm, balance: '500.00' });

    await user.click(screen.getByTestId('preset-100'));
    await user.click(screen.getByTestId('agree-checkbox'));
    await user.click(screen.getByTestId('confirm-button'));

    expect(screen.queryByTestId('balance-error')).not.toBeInTheDocument();
    expect(onConfirm).toHaveBeenCalled();
  });

  it('clears balance error when preset changes', async () => {
    const user = userEvent.setup();
    renderSheet({ balance: '50.00' });

    // Trigger error: ₹100 > ₹50
    await user.click(screen.getByTestId('preset-100'));
    await user.click(screen.getByTestId('agree-checkbox'));
    await user.click(screen.getByTestId('confirm-button'));
    expect(screen.getByTestId('balance-error')).toBeInTheDocument();

    // Change preset to ₹1 — error should clear
    await user.click(screen.getByTestId('preset-1'));
    expect(screen.queryByTestId('balance-error')).not.toBeInTheDocument();
  });

  // ── State Reset on Open ──

  it('resets state when sheet reopens', async () => {
    const user = userEvent.setup();
    const { rerender } = render(
      <BetConfirmationSheet {...defaultProps} isOpen={true} betType="green" />,
    );

    // Change some state
    await user.click(screen.getByTestId('preset-100'));
    await user.click(screen.getByTestId('multiplier-X10'));
    await user.click(screen.getByTestId('agree-checkbox'));

    // Close and reopen with different bet type
    rerender(<BetConfirmationSheet {...defaultProps} isOpen={false} betType="green" />);
    rerender(<BetConfirmationSheet {...defaultProps} isOpen={true} betType="red" />);

    // State should be reset
    expect(screen.getByTestId('preset-1')).toHaveAttribute('aria-checked', 'true');
    expect((screen.getByTestId('quantity-input') as HTMLInputElement).value).toBe('1');
    expect(screen.getByTestId('multiplier-X1')).toHaveAttribute('aria-checked', 'true');
    expect((screen.getByTestId('agree-checkbox') as HTMLInputElement).checked).toBe(false);
  });

  // ── Accessibility ──

  it('has proper dialog role and aria attributes', () => {
    renderSheet();
    const dialog = screen.getByRole('dialog');
    expect(dialog).toHaveAttribute('aria-modal', 'true');
    expect(dialog).toHaveAttribute('aria-label', 'Bet confirmation');
  });

  it('balance presets have radiogroup role', () => {
    renderSheet();
    expect(screen.getByRole('radiogroup', { name: /balance preset/i })).toBeInTheDocument();
  });

  it('multiplier row has radiogroup role', () => {
    renderSheet();
    expect(screen.getByRole('radiogroup', { name: /quick multiplier/i })).toBeInTheDocument();
  });
});
