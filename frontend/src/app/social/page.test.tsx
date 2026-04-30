import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

const { replaceMock, postMock } = vi.hoisted(() => ({
  replaceMock: vi.fn(),
  postMock: vi.fn(),
}));

vi.mock('next/navigation', () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock('@/hooks/useAuthGuard', () => ({
  useAuthGuard: vi.fn(),
}));

vi.mock('@/lib/api-client', () => ({
  apiClient: { post: postMock },
  parseApiError: (err: unknown) => {
    const data = (err as { response?: { data?: { error?: { code: string; message: string } } } })
      ?.response?.data;
    return data?.error ?? null;
  },
  getErrorMessage: (_code: string, msg?: string) => msg ?? 'An unexpected error occurred',
}));

import SocialPage from './page';

describe('SocialPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders the social page with title', () => {
    render(<SocialPage />);
    expect(screen.getByText('Social')).toBeInTheDocument();
  });

  it('renders friend search and invite code sections', () => {
    render(<SocialPage />);
    expect(screen.getByText('Find Friends')).toBeInTheDocument();
    expect(screen.getByText('Join Game')).toBeInTheDocument();
  });

  it('shows validation error for empty friend search', async () => {
    render(<SocialPage />);
    fireEvent.click(screen.getByRole('button', { name: /send friend request/i }));
    expect(await screen.findByText(/please enter a username/i)).toBeInTheDocument();
  });

  it('sends friend request on valid username', async () => {
    postMock.mockResolvedValueOnce({ data: { message: 'Request sent' } });
    render(<SocialPage />);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'alice' } });
    fireEvent.click(screen.getByRole('button', { name: /send friend request/i }));

    await waitFor(() => {
      expect(postMock).toHaveBeenCalledWith('/social/friends', { username: 'alice' });
    });
    expect(await screen.findByText(/friend request sent to alice/i)).toBeInTheDocument();
  });

  it('shows error on friend request failure', async () => {
    postMock.mockRejectedValueOnce({
      response: { data: { error: { code: 'NOT_FOUND', message: 'User not found' } } },
    });
    render(<SocialPage />);

    fireEvent.change(screen.getByLabelText(/username/i), { target: { value: 'nobody' } });
    fireEvent.click(screen.getByRole('button', { name: /send friend request/i }));

    expect(await screen.findByText(/user not found/i)).toBeInTheDocument();
  });

  it('shows validation error for empty invite code', async () => {
    render(<SocialPage />);
    fireEvent.click(screen.getByRole('button', { name: /join round/i }));
    expect(await screen.findByText(/please enter an invite code/i)).toBeInTheDocument();
  });

  it('shows error on invite code failure', async () => {
    postMock.mockRejectedValueOnce({
      response: { data: { error: { code: 'INVALID_CODE', message: 'Invalid invite code' } } },
    });
    render(<SocialPage />);

    fireEvent.change(screen.getByLabelText(/invite code/i, { selector: '#invite-code' }), { target: { value: 'BAD' } });
    fireEvent.click(screen.getByRole('button', { name: /join round/i }));

    expect(await screen.findByText(/invalid invite code/i)).toBeInTheDocument();
  });
});
