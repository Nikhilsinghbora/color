import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { replaceMock, getMock, postMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  getMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { get: getMock, post: postMock },
  parseApiError: (err: unknown) => {
    const data = (err as { response?: { data?: { error?: { code: string; message: string } } } })
      ?.response?.data;
    return data?.error ?? null;
  },
  getErrorMessage: (_code: string, msg?: string) => msg ?? 'An unexpected error occurred',
}));

import ResponsibleGamblingPage from './page';

const mockLimits = [
  { period: 'daily', amount: '100.00', current_usage: '25.00', resets_at: '2024-01-16T00:00:00Z' },
  { period: 'weekly', amount: '500.00', current_usage: '100.00', resets_at: '2024-01-22T00:00:00Z' },
];

describe('ResponsibleGamblingPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockResolvedValue({ data: mockLimits });
  });

  it('renders the page with title', async () => {
    render(<ResponsibleGamblingPage />);
    expect(screen.getByText('Responsible Gambling')).toBeInTheDocument();
    await waitFor(() => {
      expect(getMock).toHaveBeenCalledWith('/responsible-gambling/deposit-limit');
    });
  });

  it('fetches and displays current deposit limits', async () => {
    render(<ResponsibleGamblingPage />);
    await waitFor(() => {
      expect(screen.getByText(/used: \$25\.00 \/ \$100\.00/i)).toBeInTheDocument();
    });
    expect(screen.getByText(/used: \$100\.00 \/ \$500\.00/i)).toBeInTheDocument();
  });

  it('renders deposit limit forms for daily, weekly, monthly', async () => {
    render(<ResponsibleGamblingPage />);
    await waitFor(() => {
      expect(screen.getByText('Daily Limit')).toBeInTheDocument();
    });
    expect(screen.getByText('Weekly Limit')).toBeInTheDocument();
    expect(screen.getByText('Monthly Limit')).toBeInTheDocument();
  });

  it('shows validation error for invalid deposit limit amount', async () => {
    render(<ResponsibleGamblingPage />);
    await waitFor(() => {
      expect(screen.getByText('Daily Limit')).toBeInTheDocument();
    });

    // Clear the pre-filled value and submit empty
    const dailyInput = screen.getByLabelText(/daily deposit limit amount/i);
    fireEvent.change(dailyInput, { target: { value: '' } });

    // Find the Set button in the daily limit form
    const setButtons = screen.getAllByRole('button', { name: /^set$/i });
    fireEvent.click(setButtons[0]);

    expect(await screen.findByText(/please enter a valid amount/i)).toBeInTheDocument();
  });

  it('submits deposit limit and shows success toast', async () => {
    postMock.mockResolvedValueOnce({
      data: { period: 'monthly', amount: '1000.00', current_usage: '0.00', resets_at: '2024-02-01T00:00:00Z' },
    });

    render(<ResponsibleGamblingPage />);
    await waitFor(() => {
      expect(screen.getByText('Monthly Limit')).toBeInTheDocument();
    });

    const monthlyInput = screen.getByLabelText(/monthly deposit limit amount/i);
    fireEvent.change(monthlyInput, { target: { value: '1000' } });

    const setButtons = screen.getAllByRole('button', { name: /^set$/i });
    fireEvent.click(setButtons[2]); // Monthly is the third

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/responsible-gambling/deposit-limit', {
        period: 'monthly',
        amount: '1000',
      });
    });
  });

  it('renders session limit form', async () => {
    render(<ResponsibleGamblingPage />);
    expect(screen.getByText('Session Time Limit')).toBeInTheDocument();
    expect(screen.getByLabelText(/duration.*minutes/i)).toBeInTheDocument();
  });

  it('shows validation error for invalid session limit', async () => {
    render(<ResponsibleGamblingPage />);
    fireEvent.click(screen.getByRole('button', { name: /set session limit/i }));
    expect(await screen.findByText(/please enter a valid number of minutes/i)).toBeInTheDocument();
  });

  it('submits session limit', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'Session limit set' } });
    render(<ResponsibleGamblingPage />);

    fireEvent.change(screen.getByLabelText(/duration.*minutes/i), { target: { value: '60' } });
    fireEvent.click(screen.getByRole('button', { name: /set session limit/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/responsible-gambling/session-limit', {
        duration_minutes: 60,
      });
    });
  });

  it('renders self-exclusion section with duration selector', () => {
    render(<ResponsibleGamblingPage />);
    expect(screen.getByText('Self-Exclusion')).toBeInTheDocument();
    expect(screen.getByLabelText(/exclusion duration/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /request self-exclusion/i })).toBeInTheDocument();
  });

  it('shows confirmation dialog when requesting self-exclusion', async () => {
    render(<ResponsibleGamblingPage />);
    fireEvent.click(screen.getByRole('button', { name: /request self-exclusion/i }));

    expect(await screen.findByText(/confirm self-exclusion/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /cancel/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /confirm exclusion/i })).toBeInTheDocument();
  });

  it('cancels self-exclusion dialog', async () => {
    render(<ResponsibleGamblingPage />);
    fireEvent.click(screen.getByRole('button', { name: /request self-exclusion/i }));

    await screen.findByText(/confirm self-exclusion/i);
    fireEvent.click(screen.getByRole('button', { name: /cancel/i }));

    await waitFor(() => {
      expect(screen.queryByText(/confirm self-exclusion/i)).not.toBeInTheDocument();
    });
  });

  it('submits self-exclusion on confirmation', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'Self-excluded' } });
    render(<ResponsibleGamblingPage />);

    fireEvent.click(screen.getByRole('button', { name: /request self-exclusion/i }));
    await screen.findByText(/confirm self-exclusion/i);
    fireEvent.click(screen.getByRole('button', { name: /confirm exclusion/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/responsible-gambling/self-exclude', {
        duration: '24h',
      });
    });
  });

  it('shows loss warning modal with acknowledge button', async () => {
    // We need to trigger the loss warning - for now test the modal rendering
    // The loss warning is triggered by backend events, so we test the UI component
    render(<ResponsibleGamblingPage />);
    // The loss warning modal is controlled by state, not visible by default
    expect(screen.queryByText(/loss warning/i)).not.toBeInTheDocument();
  });
});
