import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { WorkflowDefinition } from '../contracts';
import { StreamingProse } from './StreamingProse';
import { WritingManuscriptEditor } from './WritingManuscriptEditor';
import type { WritingChapter } from './writingArtifactModel';

const CONTENT = '雾港的旧声在电台里复活。顾遥沿着声音锚点追查旧案。';

describe('StreamingProse', () => {
  it('renders word spans with the streaming caret while calm', () => {
    const html = renderToStaticMarkup(<StreamingProse pace="steady" text={CONTENT} />);
    expect(html).toContain('stream-word');
    expect(html).toContain('writing-caret-tail');
    expect(html).not.toContain('stream-word-blur');
  });

  it('mounts new words with the blur variant while backlog boost is active', () => {
    const html = renderToStaticMarkup(<StreamingProse pace="boost" text={CONTENT} />);
    expect(html).toContain('stream-word-blur');
  });
});

describe('WritingManuscriptEditor streaming states', () => {
  it('shows the width-decaying skeleton only before the first token arrives', () => {
    const html = render({ streaming: true, visibleText: '' });
    expect(html).toContain('stream-skeleton');
    expect(html).not.toContain('stream-word');
    expect(html).not.toContain('writing-caret-tail');
  });

  it('replaces the skeleton with word spans and caret once text streams in', () => {
    const html = render({ streaming: true, visibleText: CONTENT });
    expect(html).not.toContain('stream-skeleton');
    expect(html).toContain('stream-word');
    expect(html).toContain('writing-caret-tail');
    expect(html).not.toContain('<textarea');
  });

  it('strips every animation node and the caret after the stream ends', () => {
    const html = render({ streaming: false, visibleText: '' });
    expect(html).toContain('<textarea');
    expect(html).toContain('雾港的旧声在电台里复活');
    expect(html).not.toContain('stream-word');
    expect(html).not.toContain('writing-caret-tail');
    expect(html).not.toContain('stream-skeleton');
  });
});

function render({ streaming, visibleText }: { streaming: boolean; visibleText: string }) {
  return renderToStaticMarkup(
    <WritingManuscriptEditor
      chapter={chapterFixture()}
      dirty={false}
      editorLocked={streaming}
      followingStream
      onCancelRepair={() => undefined}
      onCaptureSelection={() => undefined}
      onChange={() => undefined}
      onClearRevisionError={() => undefined}
      onGenerateRevision={() => undefined}
      onResumeStream={() => undefined}
      onScroll={() => undefined}
      qualityRepairTarget={null}
      readOnly={false}
      readerRef={{ current: null }}
      readiness={{ completed: 1, missingLabels: [], ready: true, total: 1 }}
      repairError=""
      revisionBusy={false}
      revisionError=""
      selection={null}
      streaming={streaming}
      streamPace="steady"
      visibleText={visibleText}
      workflow={{ quality_mode: 'balanced' } as WorkflowDefinition}
    />,
  );
}

function chapterFixture(): WritingChapter {
  return {
    id: 'ch-1',
    title: '第一章',
    generated_title: '雾港旧声',
    content: CONTENT,
    words: CONTENT.length,
    status: 'drafting',
    version: 1,
    commit_signature: '',
    summary: '',
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
