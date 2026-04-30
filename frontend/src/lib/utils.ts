import Decimal from 'decimal.js';

// ---------------------------------------------------------------------------
// Potential payout calculation (string-based decimal arithmetic)
// ---------------------------------------------------------------------------

/**
 * Calculate the potential payout for a bet.
 * Uses Decimal.js to avoid JavaScript floating-point precision issues.
 *
 * @param amount - Bet amount as a decimal string
 * @param odds - Odds multiplier as a decimal string
 * @returns The product rounded to exactly 2 decimal places
 */
export function calculatePotentialPayout(amount: string, odds: string): string {
  return new Decimal(amount).mul(new Decimal(odds)).toFixed(2);
}

// ---------------------------------------------------------------------------
// Registration validation helpers
// ---------------------------------------------------------------------------

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

/**
 * Validate an email address.
 * @returns `null` if valid, or an error message string if invalid.
 */
export function validateEmail(email: string): string | null {
  if (!email || !EMAIL_REGEX.test(email)) {
    return 'Please enter a valid email address';
  }
  return null;
}

/**
 * Validate a username (1–50 characters).
 * @returns `null` if valid, or an error message string if invalid.
 */
export function validateUsername(username: string): string | null {
  if (!username || username.length < 1) {
    return 'Username is required';
  }
  if (username.length > 50) {
    return 'Username must be 50 characters or fewer';
  }
  return null;
}

/**
 * Validate password complexity.
 * Requires: ≥ 8 characters, at least one uppercase letter, one lowercase
 * letter, one digit, and one special character.
 * @returns `null` if valid, or an error message string if invalid.
 */
export function validatePassword(password: string): string | null {
  if (!password || password.length < 8) {
    return 'Password must be at least 8 characters';
  }
  if (!/[A-Z]/.test(password)) {
    return 'Password must contain at least one uppercase letter';
  }
  if (!/[a-z]/.test(password)) {
    return 'Password must contain at least one lowercase letter';
  }
  if (!/\d/.test(password)) {
    return 'Password must contain at least one digit';
  }
  if (!/[^A-Za-z0-9]/.test(password)) {
    return 'Password must contain at least one special character';
  }
  return null;
}

// ---------------------------------------------------------------------------
// API validation error field mapping
// ---------------------------------------------------------------------------

/**
 * Map API validation error details to form field names.
 *
 * Given a `details` object from an API error response and a list of form
 * field names, returns a record of `fieldName → error message` for every
 * field that appears in both `details` and `formFields`.
 */
export function mapFieldErrors(
  details: Record<string, unknown>,
  formFields: string[],
): Record<string, string> {
  const mapped: Record<string, string> = {};
  for (const field of formFields) {
    if (field in details) {
      const value = details[field];
      mapped[field] = typeof value === 'string' ? value : String(value);
    }
  }
  return mapped;
}

// Re-export error helpers from api-client for convenience
export { ERROR_MESSAGES, getErrorMessage } from './api-client';
