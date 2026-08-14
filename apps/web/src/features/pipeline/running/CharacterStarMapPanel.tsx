import { Focus, ZoomIn, ZoomOut } from 'lucide-react';
import { lazy, Suspense, useMemo, useState } from 'react';
import type { CharacterNode } from '../contracts';
import type { CharacterBibleArtifact, CharacterKind } from './characterBibleArtifact';
import { projectCharacterBibleGraph } from './characterBibleGraphProjection';

const CharacterNetwork3DView = lazy(() =>
  import('./bible/CharacterNetwork3DView').then((module) => ({ default: module.CharacterNetwork3DView })),
);

type CameraRequest = { id: string; key: number; kind: 'fit' | 'focus' | 'zoom-in' | 'zoom-out' };

type Props = {
  artifact: CharacterBibleArtifact;
  onSelect: (id: string) => void;
  selectedId: string;
};

const tierColors: Record<CharacterKind, string> = {
  functional: '#9babb2',
  historical_record: '#c88955',
  major: '#edbd68',
  npc: '#c88955',
  protagonist: '#4edbe7',
};

const subjectLegend = [
  { color: tierColors.protagonist, label: '主角' },
  { color: tierColors.major, label: '重要配角' },
  { color: tierColors.functional, label: '功能角色' },
  { color: '#c88955', label: 'NPC / 历史主体' },
];

const graphTierColors: Record<CharacterNode['tier'], string> = {
  major: tierColors.major,
  minor: tierColors.functional,
  npc: '#c88955',
  protagonist: tierColors.protagonist,
  supporting: tierColors.functional,
};

export function CharacterStarMapPanel({ artifact, onSelect, selectedId }: Props) {
  const graph = useMemo(() => projectCharacterBibleGraph(artifact), [artifact]);
  const [cameraRequest, setCameraRequest] = useState<CameraRequest>();
  const requestCamera = (kind: CameraRequest['kind']) => {
    setCameraRequest((current) => ({ id: selectedId, key: (current?.key ?? 0) + 1, kind }));
  };

  return (
    <section className="character-star-map-stage">
      <header className="character-star-map-toolbar">
        <strong>人物星图</strong>
        <div aria-label="人物星图视角" className="character-star-map-controls" role="group">
          <button aria-label="缩小人物星图" onClick={() => requestCamera('zoom-out')} title="缩小" type="button"><ZoomOut size={15} /></button>
          <button aria-label="适配人物星图" onClick={() => requestCamera('fit')} title="适配全景" type="button"><Focus size={15} /></button>
          <button aria-label="放大人物星图" onClick={() => requestCamera('zoom-in')} title="放大" type="button"><ZoomIn size={15} /></button>
        </div>
      </header>
      <div className="character-star-map-viewport">
        <Suspense fallback={<p className="character-star-map-loading">正在建立人物星图…</p>}>
          <CharacterNetwork3DView
            accentColor="#4edbe7"
            autoFocusSelected={false}
            cameraRequest={cameraRequest}
            graph={graph}
            isNodeDimmed={() => false}
            nodeColor={(node) => graphTierColors[node.tier]}
            onSelectNode={(id) => id && onSelect(id)}
            selectedId={selectedId}
            showNodeLabels={false}
            showRelationshipLabels={false}
            showStarfield
          />
        </Suspense>
        <div aria-label="人物层级图例" className="character-star-map-legend">
          {subjectLegend.map(({ color, label }) => (
            <span key={label}><i style={{ backgroundColor: color }} />{label}</span>
          ))}
        </div>
      </div>
    </section>
  );
}
