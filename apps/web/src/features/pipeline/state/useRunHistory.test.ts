import { describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

describe('run history authority', () => {
  it('does not synthesize or persist history from local run events', () => {
    const source = readFileSync(fileURLToPath(new URL('./useRunHistory.ts', import.meta.url)), 'utf8');

    expect(source).not.toContain('localStorage');
    expect(source).not.toContain('historyItemFromEvents');
    expect(source).toContain('listRunHistory');
  });
});
