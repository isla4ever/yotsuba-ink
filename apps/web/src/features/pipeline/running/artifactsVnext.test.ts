import { describe, expect, it } from 'vitest';
import { parseDetailArtifact, parseSpineArtifact, parseStoryBriefArtifact, parseVolumesArtifact } from './artifactsVnext';

describe('Phase 27 Artifact strict parsing', () => {
  it('keeps Brief length intent minimal and rejects runtime capacity fields', () => {
    const result = parseStoryBriefArtifact(JSON.stringify({
      title: '雾港母带',
      premise: '修复师追查一卷失踪母带。',
      promise: '每次取证都改变她对旧案的理解。',
      world_rules: ['广播会覆盖被标记的记忆'],
      theme: '真相的代价',
      ending_promise: '母带来源会被公开。',
      voice: '第三人称有限视角',
      length_envelope: { word_target_soft: 80_000, chapter_target_soft: 24, chapter_min_reasonable: 18 },
    }));

    expect(result.artifact).toBeNull();
    expect(result.errors.join(' ')).toContain('chapter_min_reasonable');
  });

  it('rejects the retired Summary contract', () => {
    const result = parseSpineArtifact(JSON.stringify({ one_liner: '旧字段', full_synopsis: '旧梗概' }));
    expect(result.artifact).toBeNull();
    expect(result.errors.join(' ')).toContain('未支持字段');
  });

  it('accepts the minimal causal Spine contract', () => {
    const result = parseSpineArtifact(JSON.stringify({
      turns: [{ id: 'turn-1', cause: '母带失踪', change: '调查开始' }],
      ending: '港区公开原始录音',
      open_questions: [],
      progress_types: ['information'],
    }));
    expect(result.errors).toEqual([]);
    expect(result.artifact?.turns).toHaveLength(1);
  });

  it('rejects Detail v1-v3 keys and non-contiguous chapter references', () => {
    const retired = parseDetailArtifact(JSON.stringify({ schema_version: 3, chapters: [] }));
    expect(retired.artifact).toBeNull();
    expect(retired.errors.join(' ')).toContain('schema_version');

    const nonContiguous = parseDetailArtifact(JSON.stringify({
      chapters: [{
        ref: 'chapter-2',
        volume_ref: 'volume-1',
        purpose: '找到母带',
        pov: 'subject-lin',
        cast_ids: ['subject-lin'],
        scenes: [{ place: '仓库', objective: '取回母带', conflict: '封锁', turn: '发现副本', result: '带走副本' }],
        handoff: '追兵接近',
      }],
    }));
    expect(nonContiguous.artifact).toBeNull();
    expect(nonContiguous.errors).toContain('chapters 的 ID 必须连续');

    const missingVolume = parseDetailArtifact(JSON.stringify({
      chapters: [{
        ref: 'chapter-1',
        purpose: '找到母带',
        pov: 'subject-lin',
        cast_ids: ['subject-lin'],
        scenes: [{ place: '仓库', objective: '取回母带', conflict: '封锁', turn: '发现副本', result: '带走副本' }],
        handoff: '追兵接近',
      }],
    }));
    expect(missingVolume.artifact).toBeNull();
    expect(missingVolume.errors.join(' ')).toContain('volume_ref');
  });

  it('accepts complete-story Volumes and rejects retired Outline fields', () => {
    const valid = parseVolumesArtifact(JSON.stringify({
      volumes: [{
        id: 'volume-1',
        promise: '找到母带来源',
        conflict: '广播站封锁证据',
        climax: '公开原始录音',
        closure: '调查者共同作证',
        turn_refs: ['turn-1'],
        cast_ids: ['subject-lin'],
        thread_ids: ['thread-tape'],
        length_hint: 'short',
      }],
    }));
    expect(valid.errors).toEqual([]);

    const retired = parseVolumesArtifact(JSON.stringify({
      volumes: [{
        id: 'volume-1',
        chapter_window: 'chapter:1-2',
        objective: '取回母带',
        turns: [],
        ending_state: '离开港区',
      }],
    }));
    expect(retired.artifact).toBeNull();
    expect(retired.errors.join(' ')).toContain('chapter_window');
  });
});
