import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// --- Hoisted mocks ---
const {
  replaceMock,
  fetchBalanceMock,
  fetchTransactionsMock,
  depositMock,
  withdrawMock,
} = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  fetchBalanceMock: vi.fn(),
  fetchTransactionsMock: vi.fn(),
  depositMock: vi.fn(),
  withdrawMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: vi.fn(),
}));

let mockStoreState: Record<string, unknown> = {};

vi.mock('@/stores/wallet-store', () => ({
  useWalletStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector(mockStoreState),
}));

vi.mock('@/lib/api-client', () => ({
  parseApiError: (err: unknown) => {
    const data = (
      err as {
        response?: {
          data?: {
            error?: { code: string; message: string; details?: Record<string, unknown> };
          };
        };
      }
    )?.response?.data;
    return data?.error ?? null;
  },
  getErrorMessage: (code: string, msg?: string) => {
    const map: Record<string, string> = {
      INSUFFICIENT_BALANCE: 'Insufficient balance',
      DEPOSIT_LIMIT_EXCEEDED: 'Deposit limit exceeded',
    };
    return map[code] ?? msg ?? 'An unexpected error occurred';
  },
}));

import WalletPage from './page';

function setupStore(overrides: Partial<Record<string, unknown>> = {}) {
  mockStoreState = {
    balance: '150.00',
    transactions: [],
    hasMoreTransactions: false,
    transactionPage: 1,
    isLoading: false,
    fetchBalance: fetchBalanceMock,
    fetchTransactions: fetchTransactionsMock,
    deposit: depositMock,
    withdraw: withdrawMock,
    ...overrides,
  };
}

describe('WalletPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setupStore();
  });

  it('renders the wallet page with balance displayed', () => {
    render(<WalletPage />);
    expect(screen.getByText('Wallet')).toBeInTheDocument();
    expect(screen.getByTestId('wallet-balance')).toHaveTextContent('$150.00');
  });

  it('fetches balance and transactions on mount', () => {
    render(<WalletPage />);
    expect(fetchBalanceMock).toHaveBeenCalled();
    expect(fetchTransactionsMock).toHaveBeenCalledWith(1);
  });

  it('shows dash when balance is null', () => {
    setupStore({ balance: null });
    render(<WalletPage />);
    expect(screen.getByTestId('wallet-balance')).toHaveTextContent('$—');
  });

  it('renders deposit and withdrawal forms', () => {
    render(<WalletPage />);
    expect(screen.getByLabelText(/amount.*\$/i, { selector: '#deposit-amount' })).toBeInTheDocument();
    expect(screen.getByLabelText(/amount.*\$/i, { selector: '#withdraw-amount' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /deposit/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /withdraw/i })).toBeInTheDocument();
  });

  it('shows validation error for empty deposit amount', async () => {
    render(<WalletPage />);
    fireEvent.click(screen.getByRole('button', { name: /^deposit$/i }));
    expect(await screen.findByText(/valid deposit amount/i)).toBeInTheDocument();
  });

  it('submits deposit and shows success toast', async () => {
    depositMock.mockResolvedValueOnce(undefined);
    render(<WalletPage />);

    fireEvent.change(screen.getByLabelText(/amount.*\$/i, { selector: '#deposit-amount' }), {
      target: { value: '50' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^deposit$/i }));

    await waitFor(() => {
      expect(depositMock).toHaveBeenCalledWith('50', 'mock_stripe_token');
    });

    expect(await screen.findByText(/successfully deposited \$50/i)).toBeInTheDocument();
  });

  it('shows deposit error from API', async () => {
    depositMock.mockRejectedValueOnce({
      response: {
        data: {
          error: { code: 'DEPOSIT_LIMIT_EXCEEDED', message: 'Deposit limit exceeded' },
        },
      },
    });

    render(<WalletPage />);
    fireEvent.change(screen.getByLabelText(/amount.*\$/i, { selector: '#deposit-amount' }), {
      target: { value: '10000' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^deposit$/i }));

    expect(await screen.findByText(/deposit limit exceeded/i)).toBeInTheDocument();
  });

  it('shows validation error for empty withdrawal amount', async () => {
    render(<WalletPage />);
    fireEvent.click(screen.getByRole('button', { name: /^withdraw$/i }));
    expect(await screen.findByText(/valid withdrawal amount/i)).toBeInTheDocument();
  });

  it('submits withdrawal and shows success toast', async () => {
    withdrawMock.mockResolvedValueOnce(undefined);
    fetchBalanceMock.mockResolvedValueOnce(undefined);
    fetchTransactionsMock.mockResolvedValueOnce(undefined);

    render(<WalletPage />);
    fireEvent.change(screen.getByLabelText(/amount.*\$/i, { selector: '#withdraw-amount' }), {
      target: { value: '25' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^withdraw$/i }));

    await waitFor(() => {
      expect(withdrawMock).toHaveBeenCalledWith('25');
    });

    expect(await screen.findByText(/successfully withdrew \$25/i)).toBeInTheDocument();
  });

  it('shows insufficient balance error with current balance', async () => {
    withdrawMock.mockRejectedValueOnce({
      response: {
        data: {
          error: { code: 'INSUFFICIENT_BALANCE', message: 'Insufficient balance' },
        },
      },
    });

    render(<WalletPage />);
    fireEvent.change(screen.getByLabelText(/amount.*\$/i, { selector: '#withdraw-amount' }), {
      target: { value: '999' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^withdraw$/i }));

    const errorMsg = await screen.findByText(/insufficient balance.*current balance.*\$150\.00/i);
    expect(errorMsg).toBeInTheDocument();
  });

  it('renders transaction history with type, amount, and timestamp', () => {
    setupStore({
      transactions: [
        {
          id: 'tx-1',
          type: 'deposit',
          amount: '100.00',
          balance_after: '250.00',
          description: null,
          created_at: '2024-01-15T10:30:00Z',
        },
        {
          id: 'tx-2',
          type: 'withdrawal',
          amount: '50.00',
          balance_after: '200.00',
          description: null,
          created_at: '2024-01-14T08:00:00Z',
        },
        {
          id: 'tx-3',
          type: 'bet_debit',
          amount: '10.00',
          balance_after: '190.00',
          description: null,
          created_at: '2024-01-13T12:00:00Z',
        },
        {
          id: 'tx-4',
          type: 'payout_credit',
          amount: '25.00',
          balance_after: '215.00',
          description: null,
          created_at: '2024-01-13T12:05:00Z',
        },
      ],
    });

    render(<WalletPage />);

    // Check transaction type badges within the list
    const list = screen.getByRole('list');
    const items = list.querySelectorAll('li');
    expect(items).toHaveLength(4);

    // Verify type badges exist in the transaction list
    expect(list).toHaveTextContent('Deposit');
    expect(list).toHaveTextContent('Withdrawal');
    expect(list).toHaveTextContent('Bet');
    expect(list).toHaveTextContent('Payout');

    // Verify amounts
    expect(screen.getByText('$100.00')).toBeInTheDocument();
    expect(screen.getByText('$50.00')).toBeInTheDocument();
    expect(screen.getByText('$10.00')).toBeInTheDocument();
    expect(screen.getByText('$25.00')).toBeInTheDocument();
  });

  it('shows "No transactions yet" when list is empty', () => {
    setupStore({ transactions: [] });
    render(<WalletPage />);
    expect(screen.getByText(/no transactions yet/i)).toBeInTheDocument();
  });

  it('shows Load more button when hasMoreTransactions is true', () => {
    setupStore({ hasMoreTransactions: true });
    render(<WalletPage />);
    expect(screen.getByRole('button', { name: /load more/i })).toBeInTheDocument();
  });

  it('calls fetchTransactions with next page on Load more click', async () => {
    setupStore({ hasMoreTransactions: true, transactionPage: 1 });
    render(<WalletPage />);

    fireEvent.click(screen.getByRole('button', { name: /load more/i }));
    expect(fetchTransactionsMock).toHaveBeenCalledWith(2);
  });

  it('does not show Load more button when hasMoreTransactions is false', () => {
    setupStore({ hasMoreTransactions: false });
    render(<WalletPage />);
    expect(screen.queryByRole('button', { name: /load more/i })).not.toBeInTheDocument();
  });

  it('disables deposit button while processing', async () => {
    let resolveDeposit!: () => void;
    depositMock.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        resolveDeposit = resolve;
      }),
    );

    render(<WalletPage />);
    fireEvent.change(screen.getByLabelText(/amount.*\$/i, { selector: '#deposit-amount' }), {
      target: { value: '10' },
    });
    fireEvent.click(screen.getByRole('button', { name: /^deposit$/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /processing/i })).toBeDisabled();
    });

    resolveDeposit();

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /^deposit$/i })).not.toBeDisabled();
    });
  });
});
