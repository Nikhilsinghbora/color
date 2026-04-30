import { describe, it, expect } from 'vitest';
import fc from 'fast-check';

describe('Project setup verification', () => {
  it('vitest runs correctly', () => {
    expect(1 + 1).toBe(2);
  });

  it('fast-check works', () => {
    fc.assert(
      fc.property(fc.integer(), fc.integer(), (a, b) => {
        expect(a + b).toBe(b + a);
      })
    );
  });

  it('path alias @/types resolves', async () => {
    const types = await import('@/types/index');
    expect(types).toBeDefined();
  });
});
