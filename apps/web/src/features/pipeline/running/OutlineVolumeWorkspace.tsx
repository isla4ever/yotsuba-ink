import { BookOpenCheck, Edit3, GitBranch, Globe2 } from 'lucide-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { outlineVolumeReadiness, type OutlineBaseline } from './outlineArtifactModel';
import {
  outlineBeatItems,
  outlineDependencyItems,
  volumeGoal,
  type OutlineFocusKey,
  type OutlineVolume,
} from './outlinePresentation';
import { RhythmCurve } from './RhythmCurve';
import type { OutlineBeatKey } from './rhythmCurveModel';
import type { OutlineArtifact } from './stageArtifacts';

type DependencyDialog = 'character' | 'worldbuilding' | 'foreshadow';

type Props = {
  activeDelta: string;
  activeVolume: OutlineVolume;
  activeVolumeIndex: number;
  artifact: OutlineArtifact;
  baseline: OutlineBaseline;
  generating: boolean;
  liveIndex: number;
  onEditVolume: (focusKey: OutlineFocusKey) => void;
  onOpenDependency: (dialog: DependencyDialog) => void;
  onSelectVolume: (index: number) => void;
  readOnly: boolean;
};

export function OutlineVolumeWorkspace({ activeDelta, activeVolume, activeVolumeIndex, artifact, baseline, generating, liveIndex, onEditVolume, onOpenDependency, onSelectVolume, readOnly }: Props) {
  const beats = outlineBeatItems(activeVolume);
  // 节奏折线 → Beat Board 联动：点击节拍点先切卷，再在渲染后聚焦并滚动到对应列。
  const beatTileRefs = useRef(new Map<OutlineBeatKey, HTMLButtonElement>());
  const [linkedBeat, setLinkedBeat] = useState<{ key: OutlineBeatKey; token: number } | null>(null);
  useEffect(() => {
    if (!linkedBeat) return;
    const tile = beatTileRefs.current.get(linkedBeat.key);
    tile?.scrollIntoView?.({ block: 'nearest', inline: 'nearest' });
    tile?.focus({ preventScroll: true });
  }, [linkedBeat]);
  return (
    <div className="outline-program-shell">
      <aside className="outline-volume-rail" aria-label="分卷导航">
        {artifact.volumes.map((volume, index) => {
          const readiness = outlineVolumeReadiness(volume, baseline, index);
          return (
            <button
              aria-pressed={activeVolumeIndex === index}
              className={`${activeVolumeIndex === index ? 'active' : ''} ${generating && index === liveIndex ? 'generating' : ''}`}
              key={`${volume.title}-${index}`}
              onClick={() => onSelectVolume(index)}
              type="button"
            >
              <b>{String(index + 1).padStart(2, '0')}</b>
              <span>{volume.title}</span>
              <small>{volume.chapter_range}</small>
              <em>{readiness.completed}/{readiness.total}</em>
            </button>
          );
        })}
      </aside>
      <section aria-label={`${activeVolume.title} 节拍板`} className={`outline-program-stage ${generating && activeVolumeIndex === liveIndex ? 'generating' : ''}`}>
        <div className="outline-program-head">
          <div><p className="eyebrow">当前分卷</p><h3>{activeVolume.title}</h3><span>{volumeGoal(activeVolume)}</span></div>
          <button className="tiny-action outline-edit-action" onClick={() => onEditVolume('overview')} type="button">
            <Edit3 size={13} />{readOnly ? '预览卷纲' : '编辑卷纲'}
          </button>
        </div>
        <RhythmCurve
          activeVolumeIndex={activeVolumeIndex}
          onSelectBeat={(volumeIndex, beatKey) => {
            onSelectVolume(volumeIndex);
            setLinkedBeat((current) => ({ key: beatKey, token: (current?.token ?? 0) + 1 }));
          }}
          volumes={artifact.volumes}
        />
        <div aria-label="五段节拍板" className="outline-beat-matrix">
          {beats.map((beat, index) => (
            <button
              className={`outline-beat-tile ${beat.tone}`}
              key={beat.key}
              onClick={() => onEditVolume(beat.key)}
              ref={(element) => {
                if (element) beatTileRefs.current.set(beat.key, element);
                else beatTileRefs.current.delete(beat.key);
              }}
              type="button"
            >
              <header><small>{String(index + 1).padStart(2, '0')}</small><b>{beat.label}</b></header>
              <span>{beat.value || '待补全'}</span>
            </button>
          ))}
        </div>
        <div className="outline-dependency-row">
          {outlineDependencyItems(activeVolume).map((item) => (
            <button aria-label={`${item.label}，${item.count} 条，定稿后写回${item.target}`} key={item.key} onClick={() => onOpenDependency(item.dialog)} type="button">
              <header>{dependencyIcon(item.dialog)}<b>{item.label}</b><em>{item.count} 条</em></header>
              <small>定稿后写回 {item.target}</small>
              <span>{item.value}</span>
            </button>
          ))}
        </div>
        {generating && activeVolumeIndex === liveIndex && activeDelta ? <p className="outline-live-line">{activeDelta}</p> : null}
      </section>
    </div>
  );
}

function dependencyIcon(dialog: DependencyDialog): ReactNode {
  if (dialog === 'character') return <GitBranch size={14} />;
  if (dialog === 'worldbuilding') return <Globe2 size={14} />;
  return <BookOpenCheck size={14} />;
}
