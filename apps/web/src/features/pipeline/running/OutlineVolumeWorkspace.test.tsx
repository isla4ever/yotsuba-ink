import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';
import type { OutlineBaseline } from './outlineArtifactModel';
import type { OutlineArtifact } from './stageArtifacts';
import { OutlineVolumeWorkspace } from './OutlineVolumeWorkspace';

const baseline: OutlineBaseline = {
  characters: [],
  relationships: [],
  summaryArcs: [],
  worldAnchors: [],
  worldbuildingDetail: '',
};

describe('OutlineVolumeWorkspace', () => {
  it('selects exactly one volume when generated titles are duplicated', () => {
    const artifact: OutlineArtifact = { volumes: [volume('第1-3章'), volume('第4-6章')] };

    const html = renderToStaticMarkup(
      <OutlineVolumeWorkspace
        activeDelta=""
        activeVolume={artifact.volumes[1]}
        activeVolumeIndex={1}
        artifact={artifact}
        baseline={baseline}
        generating={false}
        liveIndex={1}
        onEditVolume={() => undefined}
        onOpenDependency={() => undefined}
        onSelectVolume={() => undefined}
        readOnly
      />,
    );

    expect(html.match(/aria-pressed="true"/g)).toHaveLength(1);
    expect(html).toContain('第4-6章');
  });
});

function volume(chapterRange: string): OutlineArtifact['volumes'][number] {
  return {
    chapter_range: chapterRange,
    character_progression: [],
    climax: '冲突爆发',
    development: '压力升级',
    foreshadow_plan: [],
    midpoint: '认知反转',
    opening: '建立问题',
    resolution: '留下钩子',
    rhythm: '发现-追踪-反转',
    title: '同名分卷',
    volume_goal: '推进主线',
    world_reveal: [],
  };
}
