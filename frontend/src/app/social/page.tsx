'use client';

import { useState, FormEvent } from 'react';
import { useAuthGuard } from '@/hooks/useAuthGuard';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';

export default function SocialPage() {
  useAuthGuard();

  // Friend search
  const [searchUsername, setSearchUsername] = useState('');
  const [searchError, setSearchError] = useState('');
  const [searchSuccess, setSearchSuccess] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  // Invite code
  const [inviteCode, setInviteCode] = useState('');
  const [inviteError, setInviteError] = useState('');
  const [isJoining, setIsJoining] = useState(false);

  async function handleFriendSearch(e: FormEvent) {
    e.preventDefault();
    setSearchError('');
    setSearchSuccess('');

    const username = searchUsername.trim();
    if (!username) {
      setSearchError('Please enter a username');
      return;
    }

    setIsSearching(true);
    try {
      await apiClient.post('/social/friends', { username });
      setSearchSuccess(`Friend request sent to ${username}`);
      setSearchUsername('');
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        setSearchError(getErrorMessage(apiErr.code, apiErr.message));
      } else {
        setSearchError('Failed to send friend request. Please try again.');
      }
    } finally {
      setIsSearching(false);
    }
  }

  async function handleJoinInvite(e: FormEvent) {
    e.preventDefault();
    setInviteError('');

    const code = inviteCode.trim();
    if (!code) {
      setInviteError('Please enter an invite code');
      return;
    }

    setIsJoining(true);
    try {
      const { data } = await apiClient.post<{ round_id: string }>('/social/join', { code });
      // Navigate to the game round
      window.location.href = `/game?roundId=${data.round_id}`;
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        setInviteError(getErrorMessage(apiErr.code, apiErr.message));
      } else {
        setInviteError('Failed to join with invite code. Please try again.');
      }
    } finally {
      setIsJoining(false);
    }
  }

  return (
    <main className="min-h-screen bg-background px-4 py-6">
      <section aria-label="Social features" className="mx-auto max-w-2xl">
        <h1 className="text-2xl font-bold text-foreground text-center mb-6">Social</h1>

        <div className="grid gap-6 md:grid-cols-2">
          {/* Friend search */}
          <section aria-label="Find friends" className="rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-card-foreground">Find Friends</h2>
            <form onSubmit={handleFriendSearch}>
              <label htmlFor="friend-username" className="block text-sm font-medium text-muted-foreground">
                Username
              </label>
              <input
                id="friend-username"
                type="text"
                value={searchUsername}
                onChange={(e) => setSearchUsername(e.target.value)}
                placeholder="Enter username"
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                aria-describedby={searchError ? 'search-error' : searchSuccess ? 'search-success' : undefined}
              />
              {searchError && (
                <p id="search-error" role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
                  {searchError}
                </p>
              )}
              {searchSuccess && (
                <p id="search-success" role="status" className="mt-2 text-sm text-green-600 dark:text-green-400">
                  {searchSuccess}
                </p>
              )}
              <button
                type="submit"
                disabled={isSearching}
                className="mt-4 w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isSearching ? 'Sending…' : 'Send Friend Request'}
              </button>
            </form>
          </section>

          {/* Invite code */}
          <section aria-label="Join with invite code" className="rounded-lg border border-border bg-card p-6">
            <h2 className="mb-4 text-lg font-semibold text-card-foreground">Join Game</h2>
            <form onSubmit={handleJoinInvite}>
              <label htmlFor="invite-code" className="block text-sm font-medium text-muted-foreground">
                Invite Code
              </label>
              <input
                id="invite-code"
                type="text"
                value={inviteCode}
                onChange={(e) => setInviteCode(e.target.value)}
                placeholder="Enter invite code"
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
                aria-describedby={inviteError ? 'invite-error' : undefined}
              />
              {inviteError && (
                <p id="invite-error" role="alert" className="mt-2 text-sm text-red-600 dark:text-red-400">
                  {inviteError}
                </p>
              )}
              <button
                type="submit"
                disabled={isJoining}
                className="mt-4 w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground hover:bg-primary/90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {isJoining ? 'Joining…' : 'Join Round'}
              </button>
            </form>
          </section>
        </div>
      </section>
    </main>
  );
}
