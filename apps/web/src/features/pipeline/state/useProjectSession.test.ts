import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { describe, expect, it } from 'vitest';

describe('project session Run authority', () => {
  it('restores the project latest Run without using the history branch action', () => {
    const source = readFileSync(fileURLToPath(new URL('./useProjectSession.ts', import.meta.url)), 'utf8');
    const actions = readFileSync(fileURLToPath(new URL('./useRunHistoryActions.ts', import.meta.url)), 'utf8');
    const commands = readFileSync(fileURLToPath(new URL('./useRunCommands.ts', import.meta.url)), 'utf8');

    expect(source).toContain('restoreProjectRun: (item: RunHistoryItem) => Promise<string>');
    // Opening a book restores live AND terminal runs (read-only presentation).
    expect(source).toContain("['running', 'awaiting_decision', 'completed', 'failed', 'cancelled']");
    expect(source).toContain('RESTORABLE_RUN_STATUSES.includes(latestRun.status)');
    expect(source).toContain('latestRun.run_id !== facts.activeRunId');
    expect(source).toContain('deps.restoreProjectRun(latestRun)');
    expect(source).not.toContain('deps.openRun(latestRun)');
    expect(actions).toContain('void options.onRestore(resolution.hydrated, resolution.reconnect)');
    expect(commands).toContain("const source: RunSource = 'backend'");
    expect(commands).not.toContain('storedRunSource');
  });
});
