'use client';

import { useState, FormEvent } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import { useAuthStore } from '@/stores/auth-store';
import { validateEmail } from '@/lib/utils';
import type { LoginRequest, TokenPair } from '@/types';

export default function LoginPage() {
  const router = useRouter();
  const setTokens = useAuthStore((s) => s.setTokens);

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  function validateForm(): boolean {
    let valid = true;

    const eErr = validateEmail(email);
    setEmailError(eErr);
    if (eErr) valid = false;

    if (!password) {
      setPasswordError('Password is required');
      valid = false;
    } else {
      setPasswordError(null);
    }

    return valid;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      const payload: LoginRequest = { email, password };
      const { data } = await apiClient.post<TokenPair>('/auth/login', payload);
      setTokens(data.access_token, data.refresh_token);
      router.push('/game');
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        if (apiErr.code === 'ACCOUNT_LOCKED') {
          const remaining = apiErr.details?.remaining_seconds;
          setFormError(
            remaining
              ? `Account is locked. Try again in ${Math.ceil(Number(remaining) / 60)} minute(s).`
              : 'Account is locked. Please try again later.',
          );
        } else {
          setFormError(getErrorMessage(apiErr.code, apiErr.message));
        }
      } else {
        setFormError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 shadow-sm">
        <h1 className="mb-6 text-center text-2xl font-bold text-card-foreground">
          Sign In
        </h1>

        {formError && (
          <div
            role="alert"
            className="mb-4 rounded-md bg-destructive/10 p-3 text-sm text-destructive"
          >
            {formError}
          </div>
        )}

        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          {/* Email field */}
          <div>
            <label
              htmlFor="email"
              className="mb-1 block text-sm font-medium text-card-foreground"
            >
              Email
            </label>
            <input
              id="email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => {
                setEmail(e.target.value);
                if (emailError) setEmailError(null);
              }}
              aria-invalid={!!emailError}
              aria-describedby={emailError ? 'email-error' : undefined}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="you@example.com"
            />
            {emailError && (
              <p id="email-error" className="mt-1 text-sm text-destructive" role="alert">
                {emailError}
              </p>
            )}
          </div>

          {/* Password field */}
          <div>
            <label
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-card-foreground"
            >
              Password
            </label>
            <input
              id="password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (passwordError) setPasswordError(null);
              }}
              aria-invalid={!!passwordError}
              aria-describedby={passwordError ? 'password-error' : undefined}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Enter your password"
            />
            {passwordError && (
              <p id="password-error" className="mt-1 text-sm text-destructive" role="alert">
                {passwordError}
              </p>
            )}
          </div>

          {/* Submit button */}
          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? 'Signing in…' : 'Sign In'}
          </button>
        </form>

        {/* Links */}
        <div className="mt-6 space-y-2 text-center text-sm text-muted-foreground">
          <p>
            Don&apos;t have an account?{' '}
            <Link href="/register" className="font-medium text-primary hover:underline">
              Register
            </Link>
          </p>
          <p>
            <Link href="/forgot-password" className="font-medium text-primary hover:underline">
              Forgot password?
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
