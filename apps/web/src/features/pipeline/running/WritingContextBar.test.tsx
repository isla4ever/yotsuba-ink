import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { WritingContextBar } from './WritingContextBar';
import { parallelDeliverySnapshot } from './parallelDeliveryModel';
import type { WritingArtifact, WritingChapter } from './writingArtifactModel';

describe('WritingContextBar', () => {
  it('shows real chapter position, total words, and the current review decision', () => {
    const chapters = [chapter('chapter-1', '第一章', 320), chapter('chapter-2', '第二章', 280)];
    chapters[1].summary_dirty = true;
    const artifact = artifactWith(chapters);
    const html = renderToStaticMarkup(
      <WritingContextBar
        artifact={artifact}
        chapter={chapters[1]}
        delivery={parallelDeliverySnapshot([], artifact)}
        onOpenDelivery={() => undefined}
        readOnly={false}
        readiness={{ completed: 1, missingLabels: ['第二章摘要同步'], ready: false, total: 2 }}
        streaming={false}
      />,
    );

    expect(html).toContain('第 2/2 章');
    expect(html).toContain('<b>600</b> 总字数');
    expect(html).toContain('摘要待同步');
    expect(html).toContain('待处理：第二章摘要同步');

    chapters[1].summary_dirty = false;
    chapters[1].writeback_proposal = {
      id: 'proposal-2', chapter_id: 'chapter-2', chapter: '第二章', version: 1,
      artifact_signature: 'signature', proposal_signature: 'proposal-signature', status: 'pending',
      wiki_writebacks: [], character_shift: '', foreshadow_updates: [],
      counts: { wiki: 0, character: 0, foreshadow: 0 }, created_at: '',
    };
    const proposalHtml = renderToStaticMarkup(
      <WritingContextBar artifact={artifact} chapter={chapters[1]} delivery={parallelDeliverySnapshot([], artifact)} onOpenDelivery={() => undefined} readOnly={false} readiness={{ completed: 2, missingLabels: ['第二章写回提案决策'], ready: false, total: 2 }} streaming={false} />,
    );
    expect(proposalHtml).toContain('复检通过');
    expect(proposalHtml).toContain('写回待决策');
  });
});

function chapter(id: string, title: string, words: number): WritingChapter {
  return {
    id,
    title,
    generated_title: `${title}标题`,
    content: '正文',
    words,
    status: 'completed',
    version: 1,
    commit_signature: 'signature',
    summary: '章节摘要',
    summary_dirty: false,
    context_packet: null,
    wiki_writebacks: [],
    character_shift: null,
    foreshadow_updates: [],
    quality_report: {},
    quality_recheck: null,
    model_review: null,
    writeback_proposal: null,
    revision_history: [],
    version_history: [],
  };
}

function artifactWith(chapters: WritingChapter[]): WritingArtifact {
  return {
    schema_version: 1,
    status: 'running',
    target_chapters: chapters.length,
    context_packet: {},
    context_packets: [],
    chapter_deltas: [],
    chapters,
    quality_reports: [],
    wiki_writebacks: [],
    chapter_summaries: [],
  };
}
