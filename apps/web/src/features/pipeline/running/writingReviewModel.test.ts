import { describe, expect, it } from 'vitest';
import type { ChapterWritebackProposal } from '../contracts';
import type { WritingChapter } from './writingArtifactModel';
import {
  writingProposalEntries,
  writingQualityFindings,
  writingReviewDefaultTab,
  writingReviewSteps,
} from './writingReviewModel';

describe('writingReviewModel', () => {
  it('keeps every quality finding and binds only exact repair targets', () => {
    const chapter = reviewedChapter();
    const findings = writingQualityFindings(chapter);

    expect(findings).toHaveLength(3);
    expect(findings[0].target?.finding_id).toBe('finding-1');
    expect(findings[1].target).toBeNull();
    expect(writingReviewDefaultTab(chapter)).toBe('quality');
  });

  it('renders formal proposal entries without exposing record serialization', () => {
    const entries = writingProposalEntries(proposal());

    expect(entries).toEqual([
      expect.objectContaining({ kind: 'wiki', label: '旧港航道', detail: '声纹授权可以开启闸门' }),
      expect.objectContaining({ kind: 'character', label: '顾遥', detail: '开始接受林澈协作' }),
      expect.objectContaining({ kind: 'foreshadow', label: '失真童声', meta: '推进' }),
    ]);
    expect(entries.map((item) => item.detail).join('')).not.toContain('{');
  });

  it('separates chapter review steps from the final stage confirmation', () => {
    const chapter = reviewedChapter();
    chapter.quality_recheck!.status = 'passed';
    chapter.quality_recheck!.report.passed = true;
    chapter.writeback_proposal = proposal();

    expect(writingReviewSteps(chapter).map((step) => [step.id, step.state])).toEqual([
      ['draft', 'done'],
      ['summary', 'done'],
      ['quality', 'done'],
      ['writeback', 'active'],
    ]);
    expect(writingReviewDefaultTab(chapter)).toBe('writeback');
  });
});

function reviewedChapter(): WritingChapter {
  return {
    id: 'chapter-1', title: '潮痕来信', generated_title: '潮痕来信', content: '正文', words: 2,
    status: 'completed', version: 2, commit_signature: 'signature', summary: '摘要', summary_dirty: false,
    context_packet: null, wiki_writebacks: [], character_shift: '', foreshadow_updates: [], quality_report: {},
    quality_recheck: {
      status: 'blocked', artifact_signature: 'signature', chapter_version: 2, request_id: 'review-1',
      report: {
        node_id: 'text', node_type: 'chapter_text', label: '正文', score: 0.72, passed: false, mode: 'deep',
        findings: [
          { id: 'finding-1', dimension: 'structure', severity: 'blocking', message: '承接不足', blocking: true },
          { id: 'finding-2', dimension: 'language', severity: 'warning', message: '句式重复', blocking: false },
          { id: 'finding-3', dimension: 'foreshadowing', severity: 'warning', message: '伏笔推进不足', blocking: false },
        ],
        constraint_hits: [], revision_required: true,
      },
      repair_targets: [{
        finding_id: 'finding-1', chapter_id: 'chapter-1', chapter: '潮痕来信', artifact_signature: 'signature',
        chapter_version: 2, dimension: 'structure', message: '承接不足', instruction: '补足前章证据', operation: 'rewrite',
        start: 0, end: 2, selected_text: '正文', locatable: true,
      }],
    },
    model_review: null, writeback_proposal: null, revision_history: [], version_history: [],
  };
}

function proposal(): ChapterWritebackProposal {
  return {
    id: 'proposal-1', chapter_id: 'chapter-1', chapter: '潮痕来信', version: 2,
    artifact_signature: 'signature', proposal_signature: 'proposal-signature', status: 'pending',
    wiki_writebacks: [{ target: '旧港航道', claim_key: 'access', fact: '声纹授权可以开启闸门' }],
    character_shift: { character: '顾遥', related_to: '林澈', relation: '协作', change: '开始接受林澈协作' },
    foreshadow_updates: [{ name: '失真童声', status: '推进', note: '声源范围缩小' }],
    counts: { wiki: 1, character: 1, foreshadow: 1 }, created_at: '2026-07-20T00:00:00Z',
    canon: { candidates: [], conflicts: [] },
  };
}
