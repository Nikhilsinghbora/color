import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import { parseApiError, getErrorMessage, ERROR_MESSAGES } from '@/lib/api-client';
import { AxiosError, AxiosHeaders } from 'axios';
import type { ApiError } from '@/types';

/**
 * Property 9: API error response parsing
 *
 * For any API error response body conforming to the structure
 * { error: { code: string, message: string, details?: object } },
 * the error parser SHALL extract the code and message fields correctly.
 *
 * For any known error code (INSUFFICIENT_BALANCE, BET_BELOW_MIN, BET_ABOVE_MAX,
 * BETTING_CLOSED, RATE_LIMIT_EXCEEDED), the parser SHALL map it to the
 * corresponding human-readable display message.
 *
 * **Validates: Requirements 4.5, 11.1**
 */

const KNOWN_ERROR_CODES = [
  'INSUFFICIENT_BALANCE',
  'BET_BELOW_MIN',
  'BET_ABOVE_MAX',
  'BETTING_CLOSED',
  'RATE_LIMIT_EXCEEDED',
] as const;

/**
 * Helper: build a fake AxiosError whose response.data matches the ApiError shape.
 */
function makeAxiosError(data: ApiError, status = 400): AxiosError<ApiError> {
  const headers = new AxiosHeaders();
  const error = new AxiosError<ApiError>(
    'Request failed',
    'ERR_BAD_REQUEST',
    undefined,
    undefined,
    {
      data,
      status,
      statusText: 'Bad Request',
      headers,
      config: { headers } as any,
    },
  );
  return error;
}

describe('Property 9: API error response parsing', () => {
  it('parseApiError extracts code and message from any well-formed error response', () => {
    fc.assert(
      fc.property(
        fc.record({
          code: fc.string({ minLength: 1 }),
          message: fc.string({ minLength: 1 }),
          details: fc.option(
            fc.dictionary(fc.string({ minLength: 1, maxLength: 20 }), fc.jsonValue()),
            { nil: undefined },
          ),
        }),
        ({ code, message, details }) => {
          const apiError: ApiError = {
            error: details !== undefined
              ? { code, message, details: details as Record<string, unknown> }
              : { code, message },
          };
          const axiosErr = makeAxiosError(apiError);
          const parsed = parseApiError(axiosErr);

          expect(parsed).not.toBeNull();
          expect(parsed!.code).toBe(code);
          expect(parsed!.message).toBe(message);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('getErrorMessage maps every known error code to its human-readable message', () => {
    fc.assert(
      fc.property(
        fc.constantFrom(...KNOWN_ERROR_CODES),
        (code) => {
          const result = getErrorMessage(code);
          expect(result).toBe(ERROR_MESSAGES[code]);
          // Must be a non-empty string
          expect(result.length).toBeGreaterThan(0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('getErrorMessage falls back to serverMessage for unknown codes', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1 }).filter((s) => !(s in ERROR_MESSAGES)),
        fc.string({ minLength: 1 }),
        (unknownCode, serverMessage) => {
          const result = getErrorMessage(unknownCode, serverMessage);
          expect(result).toBe(serverMessage);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('getErrorMessage returns generic fallback when code is unknown and no serverMessage', () => {
    fc.assert(
      fc.property(
        fc.string({ minLength: 1 }).filter((s) => !(s in ERROR_MESSAGES)),
        (unknownCode) => {
          const result = getErrorMessage(unknownCode);
          expect(result).toBe('An unexpected error occurred');
        },
      ),
      { numRuns: 100 },
    );
  });

  it('parseApiError returns null for non-conforming response bodies', () => {
    fc.assert(
      fc.property(
        fc.oneof(
          fc.constant(null),
          fc.constant(undefined),
          fc.string(),
          fc.integer(),
          // Object without 'error' key
          fc.dictionary(
            fc.string({ minLength: 1, maxLength: 10 }).filter((s) => s !== 'error'),
            fc.jsonValue(),
          ),
        ),
        (badData) => {
          const headers = new AxiosHeaders();
          const axiosErr = new AxiosError(
            'Request failed',
            'ERR_BAD_REQUEST',
            undefined,
            undefined,
            {
              data: badData as any,
              status: 400,
              statusText: 'Bad Request',
              headers,
              config: { headers } as any,
            },
          );
          const parsed = parseApiError(axiosErr);
          expect(parsed).toBeNull();
        },
      ),
      { numRuns: 100 },
    );
  });
});


/**
 * Property 17: Validation error field mapping
 *
 * For any API validation error response containing field-level error details
 * (a mapping of field names to error messages), the form error handler SHALL
 * map each field error to the corresponding form input. Every field name
 * present in the error response that has a matching form input SHALL display
 * its error message.
 *
 * **Validates: Requirements 11.5**
 */

import { mapFieldErrors } from '@/lib/utils';

describe('Property 17: Validation error field mapping', () => {
  it('maps every field present in both details and formFields', () => {
    const fieldNameArb = fc.stringMatching(/^[a-z][a-z_]{0,19}$/);
    const errorMsgArb = fc.string({ minLength: 1, maxLength: 100 });

    fc.assert(
      fc.property(
        // Generate a details object: field name → error message
        fc.array(fc.tuple(fieldNameArb, errorMsgArb), { minLength: 1, maxLength: 10 }),
        // Generate form fields: some overlap with details, some not
        fc.array(fieldNameArb, { minLength: 1, maxLength: 10 }),
        (detailPairs, extraFormFields) => {
          const details: Record<string, string> = {};
          for (const [key, val] of detailPairs) {
            details[key] = val;
          }

          // Form fields = some from details + some extra
          const detailKeys = Object.keys(details);
          const formFields = [...new Set([...detailKeys, ...extraFormFields])];

          const result = mapFieldErrors(details, formFields);

          // Every field in details that is also in formFields should be mapped
          for (const field of formFields) {
            if (field in details) {
              expect(result[field]).toBe(String(details[field]));
            } else {
              expect(result[field]).toBeUndefined();
            }
          }

          // No extra fields should appear in result
          for (const key of Object.keys(result)) {
            expect(formFields).toContain(key);
            expect(key in details).toBe(true);
          }
        },
      ),
      { numRuns: 100 },
    );
  });

  it('returns empty mapping when no form fields match the error details', () => {
    fc.assert(
      fc.property(
        fc.dictionary(
          fc.stringMatching(/^field_[a-z]{1,5}$/),
          fc.string({ minLength: 1, maxLength: 50 }),
        ),
        fc.array(
          fc.stringMatching(/^other_[a-z]{1,5}$/),
          { minLength: 1, maxLength: 5 },
        ),
        (details, formFields) => {
          // Ensure no overlap
          const nonOverlapping = formFields.filter((f) => !(f in details));
          if (nonOverlapping.length === 0) return; // skip if accidentally overlapping

          const result = mapFieldErrors(details, nonOverlapping);
          expect(Object.keys(result).length).toBe(0);
        },
      ),
      { numRuns: 100 },
    );
  });

  it('handles non-string values in details by converting to string', () => {
    fc.assert(
      fc.property(
        fc.stringMatching(/^[a-z]{1,10}$/),
        fc.oneof(
          fc.integer(),
          fc.boolean(),
          fc.float(),
        ),
        (fieldName, value) => {
          const details: Record<string, unknown> = { [fieldName]: value };
          const formFields = [fieldName];

          const result = mapFieldErrors(details, formFields);
          expect(result[fieldName]).toBe(String(value));
        },
      ),
      { numRuns: 100 },
    );
  });
});
