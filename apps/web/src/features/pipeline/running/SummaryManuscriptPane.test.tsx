import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import { SummaryManuscriptPane } from './SummaryManuscriptPane';
import type { SummaryArtifact } from './stageArtifacts';

describe('SummaryManuscriptPane', () => {
  it('starts in reading mode without rendering a duplicate textarea', () => {
    const html = renderToStaticMarkup(
      <SummaryManuscriptPane
        artifact={fixture()}
        deltas={[]}
        generating={false}
        onArtifactChange={() => undefined}
        qualityMode="deep"
        readOnly={false}
        sourceKey="source-a"
      />,
    );

    expect(html).toContain('aria-label="完整梗概正文"');
    expect(html).toContain('编辑主稿');
    expect(html).not.toContain('aria-label="编辑完整梗概"');
  });

  it('keeps confirmed artifacts readable without an editing command', () => {
    const html = renderToStaticMarkup(
      <SummaryManuscriptPane
        artifact={fixture()}
        deltas={[]}
        generating={false}
        onArtifactChange={() => undefined}
        qualityMode="deep"
        readOnly
        sourceKey="source-a"
      />,
    );

    expect(html).toContain('aria-label="完整梗概正文"');
    expect(html).not.toContain('编辑主稿');
  });

  it('shows the skeleton during the pre-first-token window without a caret', () => {
    const html = renderToStaticMarkup(
      <SummaryManuscriptPane
        artifact={{ ...fixture(), full_synopsis: '' }}
        deltas={[]}
        generating
        onArtifactChange={() => undefined}
        qualityMode="deep"
        readOnly={false}
        sourceKey="source-a"
      />,
    );

    expect(html).toContain('stream-skeleton');
    expect(html).not.toContain('writing-caret-tail');
  });

  it('marks the streaming tail with the caret once deltas arrive', () => {
    const html = renderToStaticMarkup(
      <SummaryManuscriptPane
        artifact={{ ...fixture(), full_synopsis: '' }}
        deltas={[{ delta: '顾遥沿声音锚点追查旧案。', section: 'full_synopsis' }]}
        generating
        onArtifactChange={() => undefined}
        qualityMode="deep"
        readOnly={false}
        sourceKey="source-a"
      />,
    );

    expect(html).not.toContain('stream-skeleton');
    expect(html).toContain('writing-caret-tail');
  });

  it('settles without any streaming animation nodes', () => {
    const html = renderToStaticMarkup(
      <SummaryManuscriptPane
        artifact={fixture()}
        deltas={[]}
        generating={false}
        onArtifactChange={() => undefined}
        qualityMode="deep"
        readOnly
        sourceKey="source-a"
      />,
    );

    expect(html).not.toContain('stream-skeleton');
    expect(html).not.toContain('writing-caret-tail');
    expect(html).not.toContain('stream-word');
  });
});

function fixture(): SummaryArtifact {
  return {
    act_structure: [{ goal: '找到母带来源', title: '退潮', turn: '听见自己的童声' }],
    character_arcs: [{ arc: '接受共同见证', name: '顾遥', next: '共同追查', pressure: '记忆失真' }],
    consistency_checks: ['记忆规则一致'],
    core_conflict: '记忆与证据冲突。',
    ending_resolution: '真相公开。',
    full_synopsis: '顾遥沿声音锚点追查旧案，并承担公开真相的代价。',
    key_turns: [{ detail: '名单中有人仍活着。', label: '第一次反转' }],
    one_liner: '一盘母带重新打开旧案。',
  };
}
