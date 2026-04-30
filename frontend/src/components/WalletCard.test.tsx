import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import WalletCard from './WalletCard';

// Mock next/navigation
const mockPush = vi.fn();
vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: mockPush }),
}));

// Mock wallet store
const mockWalletState = { balance: '250.00' };
vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector?: (s: typeof mockWalletState) => unknown) =>
    selector ? selector(mockWalletState) : mockWalletState,
}));

describe('WalletCard', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockWalletState.balance = '250.00';
  });

  it('renders balance with ₹ symbol', () => {
    render(<WalletCard />);
    expect(screen.getByTestId('wallet-balance')).toHaveTextContent('₹250.00');
  });

  it('renders default balance when balance is null', () => {
    mockWalletState.balance = null as unknown as string;
    render(<WalletCard />);
    expect(screen.getByTestId('wallet-balance')).toHaveTextContent('₹0.00');
  });

  it('renders Withdraw and Deposit buttons', () => {
    render(<WalletCard />);
    expect(screen.getByRole('button', { name: /withdraw/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /deposit/i })).toBeInTheDocument();
  });

  it('navigates to /wallet when Withdraw is clicked', async () => {
    const user = userEvent.setup();
    render(<WalletCard />);
    await user.click(screen.getByRole('button', { name: /withdraw/i }));
    expect(mockPush).toHaveBeenCalledWith('/wallet');
  });

  it('navigates to /wallet when Deposit is clicked', async () => {
    const user = userEvent.setup();
    render(<WalletCard />);
    await user.click(screen.getByRole('button', { name: /deposit/i }));
    expect(mockPush).toHaveBeenCalledWith('/wallet');
  });

  it('displays wallet icon', () => {
    render(<WalletCard />);
    expect(screen.getByText('💰')).toBeInTheDocument();
  });

  it('has proper ARIA label on the section', () => {
    render(<WalletCard />);
    expect(screen.getByRole('region', { name: 'Wallet card' })).toBeInTheDocument();
  });

  it('updates displayed balance when store value changes', () => {
    const { rerender } = render(<WalletCard />);
    expect(screen.getByTestId('wallet-balance')).toHaveTextContent('₹250.00');

    mockWalletState.balance = '100.50';
    rerender(<WalletCard />);
    expect(screen.getByTestId('wallet-balance')).toHaveTextContent('₹100.50');
  });
});
