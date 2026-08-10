import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { runEvent } from '../contracts/runEventTestFactory';
import { infoArtifactSource } from './infoArtifactSource';

describe('infoArtifactSource', () => {
  it('keeps the current approval draft while Info is waiting for confirmation', () => {
    expect(infoArtifactSource(events(), 'current draft', true)).toBe('current draft');
  });

  it('uses the confirmed artifact for completed and historical runs even when storage has an empty draft', () => {
    expect(infoArtifactSource(events(), '', false)).toContain('confirmed title');
  });

  it('falls back to the generated result when approval has not produced a local draft', () => {
    const generated: RunEvent[] = [runEvent('artifact.candidate_ready', { run_id: 'run-info', stage_id: 'info', node_id: 'info.generate_candidate', payload: { title: 'generated title', premise: 'p', world_rules: ['r'] } })];
    expect(infoArtifactSource(generated, '', true)).toContain('generated title');
  });
});

function events(): RunEvent[] {
  return [runEvent('artifact.committed', { run_id: 'run-info', stage_id: 'info', node_id: 'info.commit_artifact', payload: { title: 'confirmed title', premise: 'p', world_rules: ['r'] } })];
}
