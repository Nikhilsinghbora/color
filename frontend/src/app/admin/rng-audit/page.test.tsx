import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

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

import AdminRNGAuditPage from './page';

const mockEntries = {
  items: [
    {
      id: 'rng-1',
      round_id: 'round-100',
      algorithm: 'SHA-256',
      raw_value: 0.7531,
      num_options: 3,
      selected_color: 'red',
      created_at: '2024-03-01T10:00:00Z',
    },
    {
      id: 'rng-2',
      round_id: 'round-101',
      algorithm: 'SHA-256',
      raw_value: 0.2145,
      num_options: 5,
      selected_color: 'blue',
      created_at: '2024-03-01T11:00:00Z',
    },
  ],
  total: 2,
  page: 1,
  size: 20,
  has_more: false,
};

describe('AdminRNGAuditPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: mockEntries });
  });

  it('renders the page title', async () => {
    render(<AdminRNGAuditPage />);
    expect(screen.getByText('RNG Audit')).toBeInTheDocument();
    await waitFor(() => expect(getMock).toHaveBeenCalled());
  });

  it('fetches RNG audit entries on mount', async () => {
    render(<AdminRNGAuditPage />);
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/admin/rng-audit', { params: { page: 1 } });
    });
  });

  it('displays RNG audit entries with all fields', async () => {
    render(<AdminRNGAuditPage />);
    await waitFor(() => {
      expect(screen.getByText('round-100')).toBeInTheDocument();
    });
    expect(screen.getByText('round-101')).toBeInTheDocument();
    expect(screen.getAllByText('SHA-256')).toHaveLength(2);
    expect(screen.getByText('0.7531')).toBeInTheDocument();
    expect(screen.getByText('0.2145')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('5')).toBeInTheDocument();
    expect(screen.getByText('red')).toBeInTheDocument();
    expect(screen.getByText('blue')).toBeInTheDocument();
  });

  it('displays table headers', async () => {
    render(<AdminRNGAuditPage />);
    await waitFor(() => {
      expect(screen.getByText('round-100')).toBeInTheDocument();
    });
    expect(screen.getByText('Round ID')).toBeInTheDocument();
    expect(screen.getByText('Algorithm')).toBeInTheDocument();
    expect(screen.getByText('Raw Value')).toBeInTheDocument();
    expect(screen.getByText('Options')).toBeInTheDocument();
    expect(screen.getByText('Selected Color')).toBeInTheDocument();
    expect(screen.getByText('Timestamp')).toBeInTheDocument();
  });

  it('shows empty state when no entries', async () => {
    getMock.mockResolvedValueOnce({ data: { items: [], total: 0, page: 1, size: 20, has_more: false } });
    render(<AdminRNGAuditPage />);
    await waitFor(() => {
      expect(screen.getByText(/no rng audit entries found/i)).toBeInTheDocument();
    });
  });

  it('shows error on API failure', async () => {
    getMock.mockRejectedValueOnce(new Error('Network error'));
    render(<AdminRNGAuditPage />);
    await waitFor(() => {
      expect(screen.getByText(/failed to load rng audit entries/i)).toBeInTheDocument();
    });
  });

  it('renders pagination controls', async () => {
    render(<AdminRNGAuditPage />);
    await waitFor(() => {
      expect(screen.getByText('round-100')).toBeInTheDocument();
    });
    expect(screen.getByText('Previous')).toBeInTheDocument();
    expect(screen.getByText('Next')).toBeInTheDocument();
    expect(screen.getByText('Page 1')).toBeInTheDocument();
  });
});
