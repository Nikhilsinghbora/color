'use client';

import { useState, FormEvent } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import { validatePassword } from '@/lib/utils';

export default function ResetPasswordPage() {
  const params = useParams();
  const token = params.token as string;

  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [passwordError, setPasswordError] = useState<string | null>(null);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  function validateForm(): boolean {
    let valid = true;

    const pErr = validatePassword(password);
    setPasswordError(pErr);
    if (pErr) valid = false;

    if (!confirmPassword) {
      setConfirmError('Please confirm your password');
      valid = false;
    } else if (password !== confirmPassword) {
      setConfirmError('Passwords do not match');
      valid = false;
    } else {
      setConfirmError(null);
    }

    return valid;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      await apiClient.post('/auth/password-reset', { token, new_password: password });
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
            Password Reset Successful
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            Your password has been reset. You can now sign in with your new password.
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
          Reset Password
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
          <div>
            <label
              htmlFor="password"
              className="mb-1 block text-sm font-medium text-card-foreground"
            >
              New Password
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
              placeholder="Enter new password"
            />
            {passwordError && (
              <p id="password-error" className="mt-1 text-sm text-destructive" role="alert">
                {passwordError}
              </p>
            )}
          </div>

          <div>
            <label
              htmlFor="confirm-password"
              className="mb-1 block text-sm font-medium text-card-foreground"
            >
              Confirm Password
            </label>
            <input
              id="confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => {
                setConfirmPassword(e.target.value);
                if (confirmError) setConfirmError(null);
              }}
              aria-invalid={!!confirmError}
              aria-describedby={confirmError ? 'confirm-error' : undefined}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
              placeholder="Confirm new password"
            />
            {confirmError && (
              <p id="confirm-error" className="mt-1 text-sm text-destructive" role="alert">
                {confirmError}
              </p>
            )}
          </div>

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? 'Resetting…' : 'Reset Password'}
          </button>
        </form>

        <div className="mt-6 text-center text-sm text-muted-foreground">
          <p>
            <Link href="/login" className="font-medium text-primary hover:underline">
              Back to Sign In
            </Link>
          </p>
        </div>
      </div>
    </main>
  );
}
