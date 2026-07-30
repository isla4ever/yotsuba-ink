import { describe, expect, it } from 'vitest';
import type { RunEvent } from '../contracts';
import { infoArtifactSource } from './infoArtifactSource';

describe('infoArtifactSource', () => {
  it('keeps the current approval draft while Info is waiting for confirmation', () => {
    expect(infoArtifactSource(events(), 'current draft', true)).toBe('current draft');
  });

  it('uses the confirmed artifact for completed and historical runs even when storage has an empty draft', () => {
    expect(infoArtifactSource(events(), '', false)).toContain('confirmed title');
  });

  it('falls back to the generated result when approval has not produced a local draft', () => {
    const generated: RunEvent[] = [{ type: 'node_completed', run_id: 'run-info', node_id: 'info', result: { selected_title: 'generated title' } }];
    expect(infoArtifactSource(generated, '', true)).toContain('generated title');
  });
});

function events(): RunEvent[] {
  return [{ type: 'artifact_approved', run_id: 'run-info', node_id: 'info', artifact: { selected_title: 'confirmed title' } }];
}
