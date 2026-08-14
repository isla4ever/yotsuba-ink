import { describe, expect, it } from 'vitest';
import { runPayloadAuthority } from './runPayloadRef';
import { runEvent } from '../contracts/runEventTestFactory';

describe('runPayloadAuthority', () => {
  it('routes text candidates and commits only through the chapter version store', () => {
    for (const type of ['artifact.candidate_ready', 'artifact.committed']) {
      expect(runPayloadAuthority(runEvent(type, {
        chapter_id: 'chapter-1',
        payload_ref: 'chapter-1-v1',
        stage_id: 'text',
        type,
      }))).toBe('chapter-version');
    }
  });

  it('routes planning artifacts through the artifact store', () => {
    expect(runPayloadAuthority(runEvent('artifact.candidate_ready', {
      payload_ref: 'detail-candidate-1',
      stage_id: 'detail',
      type: 'artifact.candidate_ready',
    }))).toBe('artifact-record');
  });

  it('does not fetch non-artifact references or already hydrated payloads', () => {
    expect(runPayloadAuthority(runEvent('cover.asset_ready', {
      payload_ref: 'cover-asset-1',
      stage_id: 'cover',
      type: 'cover.asset_ready',
    }))).toBeNull();
    expect(runPayloadAuthority(runEvent('artifact.candidate_ready', {
      payload: { content: '正文' },
      payload_ref: 'chapter-1-v1',
      stage_id: 'text',
      type: 'artifact.candidate_ready',
    }))).toBeNull();
  });
});
