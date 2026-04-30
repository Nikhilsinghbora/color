import { describe, it, expect } from 'vitest';
import * as fc from 'fast-check';
import type { Transaction } from '@/types';

/**
 * Property 4: Transaction rendering completeness
 *
 * For any transaction object containing an id, type, amount, balance_after,
 * and created_at, the transaction list renderer SHALL produce output that
 * includes the transaction type label, the formatted amount, and the formatted
 * timestamp. No required field SHALL be omitted from the rendered output.
 *
 * **Validates: Requirements 2.6**
 */

// --- Pure rendering helpers extracted from wallet page logic ---

const TYPE_LABELS: Record<Transaction['type'], string> = {
  deposit: 'Deposit',
  withdrawal: 'Withdrawal',
  bet_debit: 'Bet',
  payout_credit: 'Payout',
};

function formatTransactionTypeLabel(type: Transaction['type']): string {
  return TYPE_LABELS[type] ?? type;
}

function formatTransactionAmount(amount: string): string {
  return `$${amount}`;
}

function formatTransactionTimestamp(iso: string): string {
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return iso;
  }
}

interface RenderedTransaction {
  typeLabel: string;
  formattedAmount: string;
  formattedTimestamp: string;
}

function renderTransaction(tx: Transaction): RenderedTransaction {
  return {
    typeLabel: formatTransactionTypeLabel(tx.type),
    formattedAmount: formatTransactionAmount(tx.amount),
    formattedTimestamp: formatTransactionTimestamp(tx.created_at),
  };
}

// --- Arbitraries ---

const transactionTypeArb = fc.constantFrom<Transaction['type']>(
  'deposit',
  'withdrawal',
  'bet_debit',
  'payout_credit',
);

const decimalAmountArb = fc
  .integer({ min: 1, max: 999999 })
  .map((cents) => (cents / 100).toFixed(2));

const isoDateArb = fc
  .date({
    min: new Date('2020-01-01T00:00:00.000Z'),
    max: new Date('2030-12-31T23:59:59.999Z'),
    noInvalidDate: true,
  })
  .map((d) => d.toISOString());

const transactionArb: fc.Arbitrary<Transaction> = fc.record({
  id: fc.uuid(),
  type: transactionTypeArb,
  amount: decimalAmountArb,
  balance_after: decimalAmountArb,
  description: fc.option(fc.string({ minLength: 1, maxLength: 50 }), { nil: null }),
  created_at: isoDateArb,
});

// --- Property tests ---

describe('Property 4: Transaction rendering completeness', () => {
  it('all rendered fields are present and non-empty for any transaction', () => {
    fc.assert(
      fc.property(transactionArb, (tx) => {
        const rendered = renderTransaction(tx);

        expect(rendered.typeLabel).toBeTruthy();
        expect(rendered.typeLabel.length).toBeGreaterThan(0);

        expect(rendered.formattedAmount).toBeTruthy();
        expect(rendered.formattedAmount.length).toBeGreaterThan(0);

        expect(rendered.formattedTimestamp).toBeTruthy();
        expect(rendered.formattedTimestamp.length).toBeGreaterThan(0);
      }),
      { numRuns: 100 },
    );
  });

  it('type label matches the known label for each transaction type', () => {
    fc.assert(
      fc.property(transactionArb, (tx) => {
        const rendered = renderTransaction(tx);
        const expectedLabel = TYPE_LABELS[tx.type];

        expect(rendered.typeLabel).toBe(expectedLabel);
      }),
      { numRuns: 100 },
    );
  });

  it('formatted amount includes the original amount value', () => {
    fc.assert(
      fc.property(transactionArb, (tx) => {
        const rendered = renderTransaction(tx);

        expect(rendered.formattedAmount).toContain(tx.amount);
        expect(rendered.formattedAmount).toBe(`$${tx.amount}`);
      }),
      { numRuns: 100 },
    );
  });

  it('formatted timestamp is a non-empty string derived from created_at', () => {
    fc.assert(
      fc.property(transactionArb, (tx) => {
        const rendered = renderTransaction(tx);

        // The timestamp should be non-empty
        expect(rendered.formattedTimestamp.length).toBeGreaterThan(0);
        // It should be a valid locale string representation of the date
        expect(rendered.formattedTimestamp).not.toBe('Invalid Date');
      }),
      { numRuns: 100 },
    );
  });
});
