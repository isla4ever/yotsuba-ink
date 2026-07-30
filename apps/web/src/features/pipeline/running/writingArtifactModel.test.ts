import { describe, expect, it } from 'vitest';
import type { ChapterContextPacket, RunEvent } from '../contracts';
import {
  contextForChapter,
  chapterReviewInsight,
  updateWritingChapter,
  writingArtifact,
  writingReadiness,
  type WritingArtifact,
} from './writingArtifactModel';

describe('writingArtifactModel', () => {
  it('matches context packets to the selected chapter instead of taking the latest packet', () => {
    const first = contextPacket('第1章', 1, '第一章目标');
    const second = contextPacket('第2章', 2, '第二章目标');
    const events: RunEvent[] = [
      runEvent('chapter_context_built', { chapter: '第2章', context_packet: second }),
      runEvent('chapter_context_built', { chapter: '第1章', context_packet: first }),
    ];

    expect(contextForChapter(events, '第1章')).toEqual(first);
    expect(contextForChapter(events, '第2章')).toEqual(second);
  });

  it('invalidates the commit signature and requires summary sync after a manual edit', () => {
    const artifact = writingArtifact(JSON.stringify(completeArtifact()), []);
    const edited = updateWritingChapter(artifact, 'chapter-1', { content: '人工修改后的正文内容。' });

    expect(edited.chapters[0].commit_signature).toBe('');
    expect(edited.chapters[0].summary_dirty).toBe(true);
    expect(edited.chapters[0].version).toBe(2);
    expect(edited.chapters[0].revision_history[edited.chapters[0].revision_history.length - 1]?.type).toBe('manual_edit');
    expect(writingReadiness(edited)).toMatchObject({ ready: false, missingLabels: ['第1章摘要同步'] });

    const synced = updateWritingChapter(edited, 'chapter-1', { summary: '与人工修改正文一致的新摘要。' });
    expect(synced.chapters[0].summary_dirty).toBe(true);
    expect(writingReadiness(synced).ready).toBe(false);
    expect(synced.chapter_summaries).toEqual([{ chapter: '第1章', summary: '与人工修改正文一致的新摘要。' }]);

    const continued = updateWritingChapter(edited, 'chapter-1', { content: '同一次人工修订继续输入。' });
    expect(continued.chapters[0].version).toBe(2);
  });

  it('blocks finalization until a passed recheck proposal is decided', () => {
    const artifact = writingArtifact(JSON.stringify(completeArtifact()), []);
    const chapter = artifact.chapters[0];
    const pending: WritingArtifact = {
      ...artifact,
      chapters: [{
        ...chapter,
        quality_recheck: {
          status: 'passed' as const,
          artifact_signature: 'review-signature',
          chapter_version: 1,
          request_id: 'review-request',
          report: { node_id: 'text', node_type: 'chapter_text' as const, label: '正文', score: 0.92, passed: true, mode: 'deep' as const, findings: [], constraint_hits: [], revision_required: false },
        },
        writeback_proposal: {
          id: 'proposal-1', chapter_id: 'chapter-1', chapter: '第1章', version: 1,
          artifact_signature: 'review-signature', proposal_signature: 'proposal-signature', status: 'pending' as const,
          wiki_writebacks: [], character_shift: '', foreshadow_updates: [],
          counts: { wiki: 0, character: 0, foreshadow: 0 }, created_at: '',
        },
      }],
    };

    expect(writingReadiness(pending).missingLabels).toContain('第1章写回提案决策');
    pending.chapters[0].writeback_proposal = { ...pending.chapters[0].writeback_proposal!, status: 'accepted' };
    expect(writingReadiness(pending).ready).toBe(true);
  });

  it('shows the most recently reviewed chapter in runtime insights', () => {
    const artifact = writingArtifact(JSON.stringify(completeArtifact()), []);
    const first = artifact.chapters[0];
    first.writeback_proposal = proposal('chapter-1', '第1章', '2026-07-19T01:00:00Z');
    artifact.chapters.push({
      ...first,
      id: 'chapter-2',
      title: '第2章',
      writeback_proposal: proposal('chapter-2', '第2章', '2026-07-19T02:00:00Z'),
    });

    expect(chapterReviewInsight(artifact)?.chapter).toBe('第2章');
    expect(chapterReviewInsight(artifact, 'chapter-1')?.chapter).toBe('第1章');
    expect(chapterReviewInsight(artifact, 'missing-chapter')?.chapter).toBe('第2章');
  });

  it('builds a live chapter artifact from progress, delta and exact context events', () => {
    const packet = contextPacket('第1章', 1, '追查母带来源');
    const events: RunEvent[] = [
      runEvent('chapter_delta', { chapter: '第1章', delta: '第二段。' }),
      runEvent('chapter_delta', { chapter: '第1章', delta: '第一段。' }),
      runEvent('chapter_context_built', { chapter: '第1章', context_packet: packet }),
      runEvent('chapter_progress_updated', {
        chapters: [{ volume: '第一卷', chapter: '第1章', status: 'running', words: 8, quality_score: 0, node_id: 'text' }],
      }),
    ];

    const artifact = writingArtifact('', events);

    expect(artifact.chapters[0].content).toBe('第一段。第二段。');
    expect(artifact.chapters[0].context_packet?.chapter_outline).toBe('追查母带来源');
    expect(artifact.status).toBe('running');
  });
});

function completeArtifact() {
  const context = contextPacket('第1章', 1, '确认母带异常');
  return {
    schema_version: 1,
    status: 'completed',
    target_chapters: 1,
    chapters: [{
      id: 'chapter-1',
      title: '第1章',
      generated_title: '第1章 7A-13 母带',
      content: '林澈在母带中发现异常声纹。',
      words: 14,
      status: 'completed',
      version: 1,
      commit_signature: 'signature',
      summary: '林澈发现母带异常。',
      context_packet: context,
      wiki_writebacks: [],
      character_shift: '',
      foreshadow_updates: [],
      quality_report: { score: 0.91 },
      revision_history: [],
      version_history: [],
    }],
  };
}

function contextPacket(chapter: string, chapterIndex: number, outline: string): ChapterContextPacket {
  return {
    chapter,
    chapter_index: chapterIndex,
    chapter_kind: chapterIndex === 1 ? 'first' : 'normal',
    story_brief: '故事立项',
    summary: '全书梗概',
    volume_goal: '第一卷目标',
    chapter_outline: outline,
    previous_chapter_summary: chapterIndex === 1 ? '' : '上一章摘要',
    previous_volume_ending: '',
    character_state: {},
    open_foreshadows: [],
    world_rules: ['硬设定不得被推翻'],
  };
}

function runEvent(type: string, patch: Partial<RunEvent>): RunEvent {
  return { type, run_id: 'run-writing-test', node_id: 'text', ...patch };
}

function proposal(chapterId: string, chapter: string, createdAt: string) {
  return {
    id: `proposal-${chapterId}`,
    chapter_id: chapterId,
    chapter,
    version: 2,
    artifact_signature: 'artifact-signature',
    proposal_signature: 'proposal-signature',
    status: 'pending' as const,
    wiki_writebacks: [],
    character_shift: '',
    foreshadow_updates: [],
    counts: { wiki: 0, character: 0, foreshadow: 0 },
    created_at: createdAt,
  };
}
