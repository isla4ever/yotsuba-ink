import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

function source(relativePath: string) {
  return readFileSync(fileURLToPath(new URL(relativePath, import.meta.url)), 'utf8');
}

describe('run history action contract', () => {
  it('keeps resume and explicit checkpoint branching as separate commands', () => {
    const actions = source('./useRunHistoryActions.ts');
    const history = source('../layout/CreationHistoryPage.tsx');

    expect(actions).toContain('return restoreProjectRun(item);');
    expect(actions).toContain('await createRunBranch(item.run_id, source.read_model.checkpoint_id, targetRunId);');
    expect(history).toContain('继续当前运行');
    expect(history).toContain('从检查点新建分支');
  });
});
