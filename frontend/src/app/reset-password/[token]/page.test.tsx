import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { postMock, paramsMock } = vi.hoisted(() => ({
  postMock: vi.fn(),
  paramsMock: { token: 'test-reset-token-123' },
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: vi.fn() }),
  useParams: () => paramsMock,
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { post: postMock },
  parseApiError: (err: unknown) => {
    const data = (err as { response?: { data?: { error?: { code: string; message: string } } } })
      ?.response?.data;
    return data?.error ?? null;
  },
  getErrorMessage: (code: string, msg?: string) => {
    const map: Record<string, string> = {
      INVALID_TOKEN: 'Invalid or expired reset token',
      TOKEN_EXPIRED: 'Reset token has expired',
    };
    return map[code] ?? msg ?? 'An unexpected error occurred';
  },
}));

import ResetPasswordPage from './page';

describe('ResetPasswordPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the reset password form with password and confirm fields', () => {
    render(<ResetPasswordPage />);
    expect(screen.getByLabelText(/new password/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/confirm password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /reset password/i })).toBeInTheDocument();
  });

  it('shows validation error for weak password', async () => {
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'short' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
  });

  it('shows validation error for empty confirm password', async () => {
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    expect(await screen.findByText(/confirm your password/i)).toBeInTheDocument();
  });

  it('shows validation error when passwords do not match', async () => {
    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Different!1' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));
    expect(await screen.findByText(/passwords do not match/i)).toBeInTheDocument();
  });

  it('submits and shows success message', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'Password reset successful' } });

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/auth/password-reset', {
        token: 'test-reset-token-123',
        new_password: 'Str0ng!Pass',
      });
    });

    expect(await screen.findByText(/password reset successful/i)).toBeInTheDocument();
    expect(screen.getByText(/sign in with your new password/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
  });

  it('displays error for invalid/expired token', async () => {
    postMock.mockRejectedValueOnce({
      response: {
        status: 400,
        data: { error: { code: 'INVALID_TOKEN', message: 'Invalid or expired reset token' } },
      },
    });

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

    expect(await screen.findByText(/invalid or expired/i)).toBeInTheDocument();
  });

  it('displays generic error for unexpected failures', async () => {
    postMock.mockRejectedValueOnce(new Error('Network error'));

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

    expect(await screen.findByText(/unexpected error/i)).toBeInTheDocument();
  });

  it('has a link back to login', () => {
    render(<ResetPasswordPage />);
    const loginLink = screen.getByRole('link', { name: /sign in/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });

  it('disables submit button while submitting', async () => {
    let resolvePost!: (v: unknown) => void;
    postMock.mockReturnValueOnce(
      new Promise((resolve) => { resolvePost = resolve; }),
    );

    render(<ResetPasswordPage />);
    fireEvent.change(screen.getByLabelText(/new password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.change(screen.getByLabelText(/confirm password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /reset password/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /resetting/i })).toBeDisabled();
    });

    resolvePost({ data: { message: 'ok' } });

    await waitFor(() => {
      expect(screen.getByText(/password reset successful/i)).toBeInTheDocument();
    });
  });
});
