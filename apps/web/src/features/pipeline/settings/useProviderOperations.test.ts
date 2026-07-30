import { describe, expect, it, vi } from 'vitest';
import { ProviderOperationGate } from './useProviderOperations';

describe('ProviderOperationGate', () => {
  it('rejects a duplicate operation before the first promise settles', async () => {
    const gate = new ProviderOperationGate();
    let release!: () => void;
    const pending = new Promise<void>((resolve) => { release = resolve; });
    const firstOperation = vi.fn(() => pending);
    const duplicateOperation = vi.fn(async () => undefined);

    const first = gate.run('provider-a', firstOperation);
    const duplicate = await gate.run('provider-a', duplicateOperation);

    expect(duplicate).toBe(false);
    expect(duplicateOperation).not.toHaveBeenCalled();
    release();
    await expect(first).resolves.toBe(true);
  });

  it('releases the provider after failure so the user can retry', async () => {
    const gate = new ProviderOperationGate();

    await expect(gate.run('provider-a', async () => { throw new Error('failed'); })).rejects.toThrow('failed');
    await expect(gate.run('provider-a', async () => undefined)).resolves.toBe(true);
  });
});
