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

import AdminAuditPage from './page';

const mockLogs = {
  items: [
    {
      id: 'log-1',
      event_type: 'login',
      actor_id: 'admin-1',
      target_id: null,
      details: {},
      ip_address: '192.168.1.1',
      created_at: '2024-03-01T10:00:00Z',
    },
    {
      id: 'log-2',
      event_type: 'bet_placed',
      actor_id: 'player-1',
      target_id: 'round-1',
      details: { amount: '50.00' },
      ip_address: '10.0.0.1',
      created_at: '2024-03-01T11:00:00Z',
    },
  ],
  total: 2,
  page: 1,
  size: 20,
  has_more: false,
};

describe('AdminAuditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: mockLogs });
  });

  it('renders the page title', async () => {
    render(<AdminAuditPage />);
    expect(screen.getByText('Audit Logs')).toBeInTheDocument();
    await waitFor(() => expect(getMock).toHaveBeenCalled());
  });

  it('fetches audit logs on mount', async () => {
    render(<AdminAuditPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/audit-logs', { params: { page: 1 } });
    });
  });

  it('displays audit log entries', async () => {
    render(<AdminAuditPage />);
    await waitFor(() => {
      expect(screen.getByText('login')).toBeInTheDocument();
    });
    expect(screen.getByText('bet_placed')).toBeInTheDocument();
    expect(screen.getByText('admin-1')).toBeInTheDocument();
    expect(screen.getByText('player-1')).toBeInTheDocument();
    expect(screen.getByText('192.168.1.1')).toBeInTheDocument();
  });

  it('displays dash for null target_id', async () => {
    render(<AdminAuditPage />);
    await waitFor(() => {
      expect(screen.getByText('login')).toBeInTheDocument();
    });
    // The first log has null target_id, should show '—'
    const cells = screen.getAllByText('—');
    expect(cells.length).toBeGreaterThan(0);
  });

  it('filters by event type', async () => {
    render(<AdminAuditPage />);
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText(/filter by event type/i), {
      target: { value: 'login' },
    });

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/audit-logs', {
        params: expect.objectContaining({ type: 'login', page: 1 }),
      });
    });
  });

  it('filters by date range', async () => {
    render(<AdminAuditPage />);
    await waitFor(() => expect(getMock).toHaveBeenCalledTimes(1));

    fireEvent.change(screen.getByLabelText(/filter from date/i), {
      target: { value: '2024-03-01' },
    });

    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/audit-logs', {
        params: expect.objectContaining({ from: '2024-03-01', page: 1 }),
      });
    });
  });

  it('shows empty state when no logs', async () => {
    getMock.mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, size: 20, has_more: false } });
    render(<AdminAuditPage />);
    await waitFor(() => {
      expect(screen.getByText(/no audit logs found/i)).toBeInTheDocument();
    });
  });

  it('shows error on API failure', async () => {
    getMock.mockRejectedValueOnce(new Error('Network error'));
    render(<AdminAuditPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load audit logs/i)).toBeInTheDocument();
    });
  });

  it('renders filter controls', () => {
    render(<AdminAuditPage />);
    expect(screen.getByLabelText(/filter by event type/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/filter from date/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/filter to date/i)).toBeInTheDocument();
  });

  it('renders pagination controls', async () => {
    render(<AdminAuditPage />);
    await waitFor(() => {
      expect(screen.getByText('login')).toBeInTheDocument();
    });
    expect(screen.getByText('Previous')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText('Page 1')).toBeInTheDocument();
  });
});
