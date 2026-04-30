'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import { validateEmail, validateUsername, validatePassword } from '@/lib/utils';
import type { RegisterRequest } from '@/types';

export default function RegisterPage() {
  const [email, setEmail] = useState('');
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  function validateForm(): boolean {
    let valid = true;

    const eErr = validateEmail(email);
    setEmailError(eErr);
    if (eErr) valid = false;

    const uErr = validateUsername(username);
    setUsernameError(uErr);
    if (uErr) valid = false;

    const pErr = validatePassword(password);
    setPasswordError(pErr);
    if (pErr) valid = false;

    return valid;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      const payload: RegisterRequest = { email, username, password };
      await apiClient.post('/auth/register', payload);
      setIsSuccess(true);
    } catch (err: unknown) {
      const apiErr = parseApiError(err);
      if (apiErr) {
        setFormError(getErrorMessage(apiErr.code, apiErr.message));
      } else {
        setFormError('An unexpected error occurred. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  }

  if (isSuccess) {
    return (
      <main className="flex min-h-screen items-center justify-center bg-background px-4">
        <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 shadow-sm text-center">
          <h1 className="mb-4 text-2xl font-bold text-card-foreground">
            Registration Successful
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            Please check your email to verify your account before signing in.
          </p>
          <Link
            href="/login"
            className="font-medium text-primary hover:underline"
          >
            Back to Sign In
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="flex min-h-screen items-center justify-center bg-background px-4">
      <div className="w-full max-w-md rounded-lg border border-border bg-card p-8 shadow-sm">
        <h1 className="mb-6 text-center text-2xl font-bold text-card-foreground">
          Create Account
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

          {/* Username field */}
          <div>
            <label
              htmlFor="username"
              className="mb-1 block text-sm font-medium text-card-foreground"
            >
              Username
            </label>
            <input
              id="username"
              type="text"
              autoComplete="username"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                if (usernameError) setUsernameError(null);
              }}
              aria-invalid={!!usernameError}
              aria-describedby={usernameError ? 'username-error' : undefined}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Choose a username"
            />
            {usernameError && (
              <p id="username-error" className="mt-1 text-sm text-destructive" role="alert">
                {usernameError}
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
              autoComplete="new-password"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                if (passwordError) setPasswordError(null);
              }}
              aria-invalid={!!passwordError}
              aria-describedby={passwordError ? 'password-error' : undefined}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Create a password"
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
            {isSubmitting ? 'Creating account…' : 'Create Account'}
          </button>
        </form>

        {/* Link back to login */}
        <div className="mt-6 text-center text-sm text-muted-foreground">
          <p>
            Already have an account?{' '}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
