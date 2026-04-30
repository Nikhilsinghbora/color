import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { postMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { post: postMock },
  parseApiError: (err: unknown) => {
    const data = (err as { response?: { data?: { error?: { code: string; message: string } } } })
      ?.response?.data;
    return data?.error ?? null;
  },
  getErrorMessage: (code: string, msg?: string) => msg ?? 'An unexpected error occurred',
}));

import ForgotPasswordPage from './page';

describe('ForgotPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the forgot password form with email field', () => {
    render(<ForgotPasswordPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send reset link/i })).toBeInTheDocument();
  });

  it('shows validation error for empty email', async () => {
    render(<ForgotPasswordPage />);
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
  });

  it('shows validation error for invalid email format', async () => {
    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'not-an-email' } });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
  });

  it('submits and shows success message', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'Reset email sent' } });

    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@test.com' } });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/auth/password-reset-request', {
        email: 'user@test.com',
      });
    });

    expect(await screen.findByText(/check your email/i)).toBeInTheDocument();
    expect(screen.getByText(/password reset instructions/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
  });

  it('displays API error on failure', async () => {
    postMock.mockRejectedValueOnce({
      response: {
        status: 500,
        data: { error: { code: 'INTERNAL_ERROR', message: 'Something went wrong' } },
      },
    });

    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@test.com' } });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(await screen.findByText(/something went wrong/i)).toBeInTheDocument();
  });

  it('displays generic error for unexpected failures', async () => {
    postMock.mockRejectedValueOnce(new Error('Network error'));

    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@test.com' } });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    expect(await screen.findByText(/unexpected error/i)).toBeInTheDocument();
  });

  it('has a link back to login', () => {
    render(<ForgotPasswordPage />);
    const loginLink = screen.getByRole('link', { name: /sign in/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });

  it('disables submit button while submitting', async () => {
    let resolvePost!: (v: unknown) => void;
    postMock.mockReturnValueOnce(
      new Promise((resolve) => { resolvePost = resolve; }),
    );

    render(<ForgotPasswordPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.com' } });
    fireEvent.click(screen.getByRole('button', { name: /send reset link/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sending/i })).toBeDisabled();
    });

    resolvePost({ data: { message: 'ok' } });

    await waitFor(() => {
      expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    });
  });
});
