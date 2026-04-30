import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { NavBar } from './NavBar';

// Mock next/navigation
const mockPush = vi.fn();
const mockPathname = vi.fn(() => '/game');
vi.mock('next/navigation', () => ({
  usePathname: () => mockPathname(),
  useRouter: () => ({ push: mockPush }),
}));

// Mock stores
const mockAuthState = {
  isAuthenticated: true,
  player: { id: '1', email: 'test@test.com', username: 'testplayer', isAdmin: false },
  clearTokens: vi.fn(),
};
vi.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector?: (s: typeof mockAuthState) => unknown) =>
    selector ? selector(mockAuthState) : mockAuthState,
}));

const mockWalletState = { balance: '150.00' };
vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector?: (s: typeof mockWalletState) => unknown) =>
    selector ? selector(mockWalletState) : mockWalletState,
}));

describe('NavBar', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockAuthState.isAuthenticated = true;
    mockAuthState.player = { id: '1', email: 'test@test.com', username: 'testplayer', isAdmin: false };
    mockWalletState.balance = '150.00';
  });

  it('renders nothing when not authenticated', () => {
    mockAuthState.isAuthenticated = false;
    const { container } = render(<NavBar />);
    expect(container.innerHTML).toBe('');
  });

  it('renders nav links when authenticated', () => {
    render(<NavBar />);
    expect(screen.getByText('Game')).toBeInTheDocument();
    expect(screen.getByText('Wallet')).toBeInTheDocument();
    expect(screen.getByText('Leaderboard')).toBeInTheDocument();
    expect(screen.getByText('Social')).toBeInTheDocument();
    expect(screen.getByText('Settings')).toBeInTheDocument();
  });

  it('displays wallet balance', () => {
    render(<NavBar />);
    expect(screen.getByText('$150.00')).toBeInTheDocument();
  });

  it('displays player username in account button', () => {
    render(<NavBar />);
    expect(screen.getByLabelText('Account menu')).toHaveTextContent('testplayer');
  });

  it('opens account dropdown on click', async () => {
    const user = userEvent.setup();
    render(<NavBar />);
    await user.click(screen.getByLabelText('Account menu'));
    expect(screen.getByText('Profile Settings')).toBeInTheDocument();
    expect(screen.getByText('Responsible Gambling')).toBeInTheDocument();
    expect(screen.getByText('Logout')).toBeInTheDocument();
  });

  it('calls clearTokens and redirects on logout', async () => {
    const user = userEvent.setup();
    render(<NavBar />);
    await user.click(screen.getByLabelText('Account menu'));
    await user.click(screen.getByText('Logout'));
    expect(mockAuthState.clearTokens).toHaveBeenCalled();
    expect(mockPush).toHaveBeenCalledWith('/login');
  });

  it('has proper ARIA attributes on nav', () => {
    render(<NavBar />);
    expect(screen.getByRole('navigation', { name: 'Main navigation' })).toBeInTheDocument();
  });
});
