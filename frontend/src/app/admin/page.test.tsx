import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { replaceMock, getMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  getMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock('@/hooks/useAdminGuard', () => ({
  useAdminGuard: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { get: getMock },
}));

import AdminDashboardPage from './page';

const mockMetrics = {
  active_players: 42,
  total_bets: '125000.00',
  total_payouts: '100000.00',
  revenue: '25000.00',
  period: 'daily',
};

describe('AdminDashboardPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: mockMetrics });
  });

  it('renders the dashboard title', async () => {
    render(<AdminDashboardPage />);
    expect(screen.getByText('Admin Dashboard')).toBeInTheDocument();
    await waitFor(() => expect(getMock).toHaveBeenCalled());
  });

  it('fetches metrics on mount with default period', async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/dashboard', { params: { period: 'daily' } });
    });
  });

  it('displays all four metric cards', async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('42')).toBeInTheDocument();
    });
    expect(screen.getByText('$125000.00')).toBeInTheDocument();
    expect(screen.getByText('$100000.00')).toBeInTheDocument();
    expect(screen.getByText('$25000.00')).toBeInTheDocument();
  });

  it('displays metric labels', async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText('Active Players')).toBeInTheDocument();
    });
    expect(screen.getByText('Total Bets')).toBeInTheDocument();
    expect(screen.getByText('Total Payouts')).toBeInTheDocument();
    expect(screen.getByText('Revenue')).toBeInTheDocument();
  });

  it('fetches new data when period changes', async () => {
    render(<AdminDashboardPage />);
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText(/select dashboard period/i), {
      target: { value: 'weekly' },
    });

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/dashboard', { params: { period: 'weekly' } });
    });
  });

  it('shows error message on API failure', async () => {
    getMock.mockRejectedValueOnce(new Error('Network error'));
    render(<AdminDashboardPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load dashboard metrics/i)).toBeInTheDocument();
    });
  });

  it('renders period selector with all options', () => {
    render(<AdminDashboardPage />);
    const select = screen.getByLabelText(/select dashboard period/i);
    expect(select).toBeInTheDocument();
    expect(screen.getByText('Daily')).toBeInTheDocument();
    expect(screen.getByText('Weekly')).toBeInTheDocument();
    expect(screen.getByText('Monthly')).toBeInTheDocument();
    expect(screen.getByText('All Time')).toBeInTheDocument();
  });
});
