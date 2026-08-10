import { describe, expect, it } from 'vitest';
import { parseDetailArtifact, parseOutlineArtifact, parseSummaryArtifact } from './artifactsVnext';

describe('Artifact vNext strict parsing', () => {
  it('rejects legacy Summary fields', () => {
    const result = parseSummaryArtifact(JSON.stringify({ one_liner: '旧字段', full_synopsis: '旧梗概' }));
    expect(result.artifact).toBeNull();
    expect(result.errors.join(' ')).toContain('未支持字段');
  });

  it('accepts the minimal Summary contract', () => {
    const result = parseSummaryArtifact(JSON.stringify({
      beats: [{ id: 'beat-1', phase: 'opening', event: '母带失踪', consequence: '开始调查' }],
      climax: '公开母带',
      resolution: '港区恢复公开记忆',
      character_outcomes: [],
    }));
    expect(result.errors).toEqual([]);
    expect(result.artifact?.beats).toHaveLength(1);
  });

  it('rejects Detail v1-v3 keys and non-contiguous chapters', () => {
    const result = parseDetailArtifact(JSON.stringify({
      schema_version: 3,
      chapters: [{
        id: 'chapter-2',
        number: 2,
        purpose: '找到母带',
        pov_character_id: 'character-1',
        scenes: [{ id: 'scene-1', location: '仓库', goal: '取回母带', obstacle: '封锁', turn: '发现副本', outcome: '带走副本' }],
        obligations: [],
        handoff: { unresolved_actions: [], emotional_carryover: [], next_pressure: '' },
      }],
    }));
    expect(result.artifact).toBeNull();
    expect(result.errors.join(' ')).toContain('schema_version');
    expect(result.errors).toContain('chapters 必须从 1 开始连续编号');
  });

  it('requires canonical contiguous outline chapter windows', () => {
    const valid = parseOutlineArtifact(JSON.stringify({
      volumes: [{
        id: 'volume-1',
        chapter_window: 'chapter:1-2',
        objective: '取回母带',
        turns: [{ id: 'turn-1', event: '发现副本', consequence: '追捕升级' }],
        ending_state: '带着副本逃离',
        character_windows: [],
        thread_windows: [{ thread_id: 'thread-1', kind: 'mystery', action: '确认副本', chapter_window: 'chapter:1-2' }],
      }],
    }));
    expect(valid.errors).toEqual([]);

    const legacyWindow = parseOutlineArtifact(JSON.stringify({
      ...valid.artifact,
      volumes: valid.artifact?.volumes.map((volume) => ({ ...volume, chapter_window: '1-2' })),
    }));
    expect(legacyWindow.errors.join(' ')).toContain('chapter:N');
  });
});
