import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// --- Hoisted mocks (available inside vi.mock factories) ---
const { pushMock, setTokensMock, postMock } = vi.hoisted(() => ({
  pushMock: vi.fn(),
  setTokensMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ push: pushMock }),
}));

vi.mock('@/stores/auth-store', () => ({
  useAuthStore: (selector: (s: Record<string, unknown>) => unknown) =>
    selector({ setTokens: setTokensMock }),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { post: postMock },
  parseApiError: (err: unknown) => {
    const data = (err as { response?: { data?: { error?: { code: string; message: string; details?: Record<string, unknown> } } } })
      ?.response?.data;
    return data?.error ?? null;
  },
  getErrorMessage: (code: string, msg?: string) => {
    const map: Record<string, string> = {
      INVALID_CREDENTIALS: 'Invalid email or password',
      ACCOUNT_LOCKED: 'Account is locked',
    };
    return map[code] ?? msg ?? 'An unexpected error occurred';
  },
}));

import LoginPage from './page';

describe('LoginPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the login form with email and password fields', () => {
    render(<LoginPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /sign in/i })).toBeInTheDocument();
  });

  it('shows validation error for empty email', async () => {
    render(<LoginPage />);
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
  });

  it('shows validation error for empty password', async () => {
    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'test@example.com' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));
    expect(await screen.findByText(/password is required/i)).toBeInTheDocument();
  });

  it('submits login and redirects on success', async () => {
    postMock.mockResolvedValueOnce({
      data: { access_token: 'at-123', refresh_token: 'rt-456' },
    });

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@test.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'secret123' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/auth/login', {
        email: 'user@test.com',
        password: 'secret123',
      });
    });

    expect(setTokensMock).toHaveBeenCalledWith('at-123', 'rt-456');
    expect(pushMock).toHaveBeenCalledWith('/game');
  });

  it('displays error for invalid credentials (401)', async () => {
    postMock.mockRejectedValueOnce({
      response: {
        status: 401,
        data: { error: { code: 'INVALID_CREDENTIALS', message: 'Invalid email or password' } },
      },
    });

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'bad@test.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'wrong' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText(/invalid email or password/i)).toBeInTheDocument();
    expect(setTokensMock).not.toHaveBeenCalled();
    expect(pushMock).not.toHaveBeenCalled();
  });

  it('displays account locked error (423)', async () => {
    postMock.mockRejectedValueOnce({
      response: {
        status: 423,
        data: {
          error: {
            code: 'ACCOUNT_LOCKED',
            message: 'Account is locked',
            details: { remaining_seconds: 300 },
          },
        },
      },
    });

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'locked@test.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    expect(await screen.findByText(/account is locked.*5 minute/i)).toBeInTheDocument();
  });

  it('has links to register and forgot password', () => {
    render(<LoginPage />);
    const registerLink = screen.getByRole('link', { name: /register/i });
    const forgotLink = screen.getByRole('link', { name: /forgot password/i });
    expect(registerLink).toHaveAttribute('href', '/register');
    expect(forgotLink).toHaveAttribute('href', '/forgot-password');
  });

  it('disables submit button while submitting', async () => {
    let resolvePost!: (v: unknown) => void;
    postMock.mockReturnValueOnce(
      new Promise((resolve) => { resolvePost = resolve; }),
    );

    render(<LoginPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'pass' } });
    fireEvent.click(screen.getByRole('button', { name: /sign in/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /signing in/i })).toBeDisabled();
    });

    resolvePost({ data: { access_token: 'a', refresh_token: 'r' } });

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /sign in/i })).not.toBeDisabled();
    });
  });
});
