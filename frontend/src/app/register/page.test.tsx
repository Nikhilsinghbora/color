import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

// --- Hoisted mocks ---
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
  getErrorMessage: (code: string, msg?: string) => {
    const map: Record<string, string> = {
      EMAIL_ALREADY_EXISTS: 'An account with this email already exists',
    };
    return map[code] ?? msg ?? 'An unexpected error occurred';
  },
}));

import RegisterPage from './page';

describe('RegisterPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the registration form with email, username, and password fields', () => {
    render(<RegisterPage />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/username/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/password/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /create account/i })).toBeInTheDocument();
  });

  it('shows validation error for invalid email', async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
  });

  it('shows validation error for empty username', async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(await screen.findByText(/username is required/i)).toBeInTheDocument();
  });

  it('shows validation error for weak password', async () => {
    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'test@example.com' } });
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'testuser' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'short' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));
    expect(await screen.findByText(/at least 8 characters/i)).toBeInTheDocument();
  });

  it('submits registration and shows success message', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'Registration successful' } });

    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'new@test.com' } });
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'newuser' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/auth/register', {
        email: 'new@test.com',
        username: 'newuser',
        password: 'Str0ng!Pass',
      });
    });

    expect(await screen.findByText(/registration successful/i)).toBeInTheDocument();
    expect(screen.getByText(/check your email/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /sign in/i })).toHaveAttribute('href', '/login');
  });

  it('displays API error on registration failure', async () => {
    postMock.mockRejectedValueOnce({
      response: {
        status: 409,
        data: { error: { code: 'EMAIL_ALREADY_EXISTS', message: 'An account with this email already exists' } },
      },
    });

    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'taken@test.com' } });
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'takenuser' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByText(/already exists/i)).toBeInTheDocument();
  });

  it('displays generic error for unexpected failures', async () => {
    postMock.mockRejectedValueOnce(new Error('Network error'));

    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'user@test.com' } });
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'user1' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    expect(await screen.findByText(/unexpected error/i)).toBeInTheDocument();
  });

  it('has a link back to login', () => {
    render(<RegisterPage />);
    const loginLink = screen.getByRole('link', { name: /sign in/i });
    expect(loginLink).toHaveAttribute('href', '/login');
  });

  it('disables submit button while submitting', async () => {
    let resolvePost!: (v: unknown) => void;
    postMock.mockReturnValueOnce(
      new Promise((resolve) => { resolvePost = resolve; }),
    );

    render(<RegisterPage />);
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: 'a@b.com' } });
    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'user1' } });
    fireEvent.change(screen.getByLabelText(/password/i), { target: { value: 'Str0ng!Pass' } });
    fireEvent.click(screen.getByRole('button', { name: /create account/i }));

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /creating account/i })).toBeDisabled();
    });

    resolvePost({ data: { message: 'ok' } });

    await waitFor(() => {
      expect(screen.getByText(/registration successful/i)).toBeInTheDocument();
    });
  });
});
