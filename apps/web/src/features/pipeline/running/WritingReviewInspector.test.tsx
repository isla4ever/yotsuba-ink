import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { WritingChapter } from './writingArtifactModel';
import { WritingQualityInspector } from './WritingQualityInspector';
import { WritingReviewInspector } from './WritingReviewInspector';
import { WritingWritebackInspector } from './WritingWritebackInspector';

describe('WritingReviewInspector panels', () => {
  it('renders the complete finding list instead of truncating the review', () => {
    const chapter = chapterWithReview();
    const html = renderToStaticMarkup(
      <WritingQualityInspector
        busy={null}
        chapter={chapter}
        error=""
        onClearError={() => undefined}
        onRepair={() => undefined}
        onSync={() => undefined}
        readOnly={false}
      />,
    );

    expect(html).toContain('承接不足');
    expect(html).toContain('句式重复');
    expect(html).toContain('伏笔推进不足');
    expect(html).toContain('定位正文');
    expect(html.match(/修订方向：/g)).toHaveLength(3);
    expect(html).toContain('无法可靠定位，仅提供修订方向');
  });

  it('exposes one roving tab stop for keyboard review navigation', () => {
    const html = renderToStaticMarkup(
      <WritingReviewInspector
        busy={null}
        chapter={chapterWithReview()}
        error=""
        events={[]}
        onClearError={() => undefined}
        onDecide={() => undefined}
        onOpenCharacter={() => undefined}
        onOpenWorldbuilding={() => undefined}
        onRepair={() => undefined}
        onSync={() => undefined}
        qualityMode="deep"
        readOnly={false}
      />,
    );

    expect(html.match(/tabindex="0"/g)).toHaveLength(1);
    expect(html.match(/tabindex="-1"/g)).toHaveLength(1);
  });

  it('keeps proposal acceptance disabled until every Canon conflict is resolved', () => {
    const chapter = chapterWithReview();
    chapter.quality_recheck!.status = 'passed';
    chapter.writeback_proposal = {
      id: 'proposal-1', chapter_id: chapter.id, chapter: chapter.title, version: 2,
      artifact_signature: 'signature', proposal_signature: 'proposal-signature', status: 'pending',
      wiki_writebacks: [{ target: '旧港航道', fact: '声纹授权可以开启闸门' }],
      character_shift: { character: '顾遥', change: '开始接受协作' },
      foreshadow_updates: [{ name: '失真童声', status: '推进', note: '声源范围缩小' }],
      counts: { wiki: 1, character: 1, foreshadow: 1 }, created_at: '',
      canon: { candidates: [], conflicts: [{
        id: 'conflict-1', status: 'pending', target: '旧港航道', claim_key: '开放时间',
        existing_fact: '只在退潮后开放', incoming_fact: '可由声纹授权随时开启',
      }] },
    };
    const html = renderToStaticMarkup(
      <WritingWritebackInspector
        busy={null}
        chapter={chapter}
        error=""
        onClearError={() => undefined}
        onDecide={() => undefined}
        readOnly={false}
      />,
    );

    expect(html).toContain('既有事实');
    expect(html).toContain('本章提案');
    expect(html).toMatch(/<button[^>]*disabled=""[^>]*>.*接受提案/);
  });
});

function chapterWithReview(): WritingChapter {
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
