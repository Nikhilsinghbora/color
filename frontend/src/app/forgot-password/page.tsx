'use client';

import { useState, FormEvent } from 'react';
import Link from 'next/link';
import { apiClient, parseApiError, getErrorMessage } from '@/lib/api-client';
import { validateEmail } from '@/lib/utils';

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);

  function validateForm(): boolean {
    const eErr = validateEmail(email);
    setEmailError(eErr);
    return !eErr;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);

    if (!validateForm()) return;

    setIsSubmitting(true);

    try {
      await apiClient.post('/auth/password-reset-request', { email });
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
            Check Your Email
          </h1>
          <p className="mb-6 text-sm text-muted-foreground">
            If an account exists with that email, we&apos;ve sent password reset instructions.
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
          Forgot Password
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

          <button
            type="submit"
            disabled={isSubmitting}
            className="w-full rounded-md bg-primary px-4 py-2 font-medium text-primary-foreground transition-colors hover:bg-primary/90 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSubmitting ? 'Sending…' : 'Send Reset Link'}
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
