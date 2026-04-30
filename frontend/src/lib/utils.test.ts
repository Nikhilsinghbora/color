import { describe, it, expect } from 'vitest';
import {
  calculatePotentialPayout,
  validateEmail,
  validateUsername,
  validatePassword,
  mapFieldErrors,
} from './utils';

// ---------------------------------------------------------------------------
// calculatePotentialPayout
// ---------------------------------------------------------------------------

describe('calculatePotentialPayout', () => {
  it('multiplies amount by odds and returns 2 decimal places', () => {
    expect(calculatePotentialPayout('10', '2.5')).toBe('25.00');
  });

  it('handles fractional amounts', () => {
    expect(calculatePotentialPayout('7.50', '3')).toBe('22.50');
  });

  it('rounds to 2 decimal places', () => {
    // 1.11 * 1.11 = 1.2321 → "1.23"
    expect(calculatePotentialPayout('1.11', '1.11')).toBe('1.23');
  });

  it('returns "0.00" for zero amount', () => {
    expect(calculatePotentialPayout('0', '5')).toBe('0.00');
  });

  it('handles large values without floating-point drift', () => {
    expect(calculatePotentialPayout('999999.99', '1.01')).toBe('1009999.99');
  });
});

// ---------------------------------------------------------------------------
// validateEmail
// ---------------------------------------------------------------------------

describe('validateEmail', () => {
  it('returns null for a valid email', () => {
    expect(validateEmail('user@example.com')).toBeNull();
  });

  it('returns error for empty string', () => {
    expect(validateEmail('')).toBe('Please enter a valid email address');
  });

  it('returns error for missing @', () => {
    expect(validateEmail('userexample.com')).toBe('Please enter a valid email address');
  });

  it('returns error for missing domain', () => {
    expect(validateEmail('user@')).toBe('Please enter a valid email address');
  });

  it('returns error for spaces', () => {
    expect(validateEmail('user @example.com')).toBe('Please enter a valid email address');
  });
});

// ---------------------------------------------------------------------------
// validateUsername
// ---------------------------------------------------------------------------

describe('validateUsername', () => {
  it('returns null for a valid username', () => {
    expect(validateUsername('alice')).toBeNull();
  });

  it('returns null for single character', () => {
    expect(validateUsername('a')).toBeNull();
  });

  it('returns null for 50 characters', () => {
    expect(validateUsername('a'.repeat(50))).toBeNull();
  });

  it('returns error for empty string', () => {
    expect(validateUsername('')).toBe('Username is required');
  });

  it('returns error for 51 characters', () => {
    expect(validateUsername('a'.repeat(51))).toBe('Username must be 50 characters or fewer');
  });
});

// ---------------------------------------------------------------------------
// validatePassword
// ---------------------------------------------------------------------------

describe('validatePassword', () => {
  it('returns null for a valid password', () => {
    expect(validatePassword('Abcdef1!')).toBeNull();
  });

  it('returns error for short password', () => {
    expect(validatePassword('Ab1!')).toBe('Password must be at least 8 characters');
  });

  it('returns error for missing uppercase', () => {
    expect(validatePassword('abcdef1!')).toBe('Password must contain at least one uppercase letter');
  });

  it('returns error for missing lowercase', () => {
    expect(validatePassword('ABCDEF1!')).toBe('Password must contain at least one lowercase letter');
  });

  it('returns error for missing digit', () => {
    expect(validatePassword('Abcdefg!')).toBe('Password must contain at least one digit');
  });

  it('returns error for missing special character', () => {
    expect(validatePassword('Abcdefg1')).toBe('Password must contain at least one special character');
  });

  it('returns error for empty string', () => {
    expect(validatePassword('')).toBe('Password must be at least 8 characters');
  });
});

// ---------------------------------------------------------------------------
// mapFieldErrors
// ---------------------------------------------------------------------------

describe('mapFieldErrors', () => {
  it('maps matching fields from details to form fields', () => {
    const details = { email: 'Already taken', username: 'Too short' };
    const formFields = ['email', 'username', 'password'];
    expect(mapFieldErrors(details, formFields)).toEqual({
      email: 'Already taken',
      username: 'Too short',
    });
  });

  it('ignores detail keys not in formFields', () => {
    const details = { email: 'Invalid', extra: 'Ignored' };
    const formFields = ['email'];
    expect(mapFieldErrors(details, formFields)).toEqual({ email: 'Invalid' });
  });

  it('returns empty object when no fields match', () => {
    const details = { foo: 'bar' };
    const formFields = ['email', 'password'];
    expect(mapFieldErrors(details, formFields)).toEqual({});
  });

  it('converts non-string values to strings', () => {
    const details = { email: 123 };
    const formFields = ['email'];
    expect(mapFieldErrors(details, formFields)).toEqual({ email: '123' });
  });

  it('returns empty object for empty details', () => {
    expect(mapFieldErrors({}, ['email'])).toEqual({});
  });
});
