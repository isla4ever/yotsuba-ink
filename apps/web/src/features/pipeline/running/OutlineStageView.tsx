import { AnimatePresence } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { OutlineBeatDialog } from './OutlineBeatDialog';
import { OutlineContextBar } from './OutlineContextBar';
import {
  OutlineCharacterCarryDialog,
  OutlineForeshadowLedgerDialog,
  OutlineWorldCarryDialog,
} from './OutlineDependencyDialogs';
import type { OutlineBaseline, OutlineReadiness } from './outlineArtifactModel';
import type { OutlineFocusKey } from './outlinePresentation';
import { OutlineVolumeWorkspace } from './OutlineVolumeWorkspace';
import { outlineArtifact, type OutlineArtifact } from './stageArtifacts';
import { activeIndexFor, deltasBySection } from './stageViewData';
import { StageToast } from './StageToast';

type Props = {
  baseline: OutlineBaseline;
  deltas?: Array<{ section: string; delta: string }>;
  generating?: boolean;
  onArtifactChange?: (artifact: OutlineArtifact) => void;
  readiness: OutlineReadiness;
  readOnly?: boolean;
  result: string;
  sourceResult?: string;
};

export function OutlineStageView({
  baseline,
  deltas = [],
  generating,
  onArtifactChange,
  readiness,
  readOnly = false,
  result,
  sourceResult = result,
}: Props) {
  const [artifact, setArtifact] = useState(() => outlineArtifact(result));
  const [selectedVolumeIndex, setSelectedVolumeIndex] = useState<number | null>(null);
  const [editingVolumeIndex, setEditingVolumeIndex] = useState<number | null>(null);
  const [editingFocusKey, setEditingFocusKey] = useState<OutlineFocusKey>('overview');
  const [dependencyDialog, setDependencyDialog] = useState<'character' | 'worldbuilding' | 'foreshadow' | null>(null);
  const [toast, setToast] = useState('');
  useEffect(() => setArtifact(outlineArtifact(result)), [result]);
  useEffect(() => {
    setDependencyDialog(null);
    setEditingVolumeIndex(null);
  }, [sourceResult]);
  const deltaBySection = useMemo(() => deltasBySection(deltas), [deltas]);
  const liveIndex = generating
    ? activeIndexFor(artifact.volumes.map((volume) => volume.title), deltaBySection)
    : artifact.volumes.length - 1;
  const visibleVolumes = generating
    ? artifact.volumes.slice(0, Math.max(1, liveIndex + 1))
    : artifact.volumes;
  const activeVolumeIndex = Math.max(0, Math.min(
    selectedVolumeIndex ?? liveIndex,
    visibleVolumes.length - 1,
  ));
  const activeVolume = visibleVolumes[activeVolumeIndex] ?? artifact.volumes[0] ?? null;
  const editingTarget = editingVolumeIndex === null || !artifact.volumes[editingVolumeIndex]
    ? null
    : { index: editingVolumeIndex, volume: artifact.volumes[editingVolumeIndex] };
  const showToast = (message: string) => {
    setToast(message);
  };
  const updateVolume = (index: number, patch: Partial<OutlineArtifact['volumes'][number]>) => {
    const next = {
      volumes: artifact.volumes.map((volume, volumeIndex) => volumeIndex === index ? { ...volume, ...patch } : volume),
    };
    setArtifact(next);
    onArtifactChange?.(next);
  };
  const activeDelta = activeVolume ? deltaBySection.get(activeVolume.title) ?? '' : '';
  const legacyFinalized = readOnly && !generating && !readiness.ready;
  return (
    <div className="volume-outline-board outline-workbench-v3 outline-workbench-phase84">
      <StageToast durationMs={1500} message={toast} onDismiss={() => setToast('')} />
      <OutlineContextBar activeVolume={activeVolume} generating={Boolean(generating)} legacyFinalized={legacyFinalized} readiness={readiness} volumeCount={artifact.volumes.length} />
      {activeVolume ? (
        <OutlineVolumeWorkspace
          activeDelta={activeDelta}
          activeVolume={activeVolume}
          activeVolumeIndex={activeVolumeIndex}
          artifact={artifact}
          baseline={baseline}
          generating={Boolean(generating)}
          liveIndex={liveIndex}
          onEditVolume={(focusKey) => {
            setEditingFocusKey(focusKey);
            setEditingVolumeIndex(activeVolumeIndex);
          }}
          onOpenDependency={setDependencyDialog}
          onSelectVolume={setSelectedVolumeIndex}
          readOnly={readOnly}
        />
      ) : null}
      <AnimatePresence>
        {editingTarget ? (
          <OutlineBeatDialog
            initialFocusKey={editingFocusKey}
            onClose={() => setEditingVolumeIndex(null)}
            readOnly={readOnly}
            onSave={(next) => {
              updateVolume(editingTarget.index, {
                ...next,
                volume_goal: next.volume_goal ?? editingTarget.volume.volume_goal,
                mid_twist: next.midpoint ?? editingTarget.volume.mid_twist,
                volume_cliffhanger: next.resolution ?? editingTarget.volume.volume_cliffhanger,
              });
              setSelectedVolumeIndex(editingTarget.index);
              setEditingVolumeIndex(null);
              showToast('分卷大纲已保存到当前稿');
            }}
            typing={generating && Boolean(deltaBySection.get(editingTarget.volume.title))}
            volume={editingTarget.volume}
          />
        ) : null}
        {activeVolume && dependencyDialog === 'character' ? (
          <OutlineCharacterCarryDialog
            baseline={baseline}
            onClose={() => setDependencyDialog(null)}
            readOnly={readOnly}
            onSave={(next) => {
              const value = next.character_progression ?? [];
              updateVolume(activeVolumeIndex, { character_progression: value });
              setDependencyDialog(null);
              showToast('角色承接已保存到当前稿，定稿后写回');
            }}
            volume={activeVolume}
          />
        ) : null}
        {activeVolume && dependencyDialog === 'worldbuilding' ? (
          <OutlineWorldCarryDialog
            baseline={baseline}
            onClose={() => setDependencyDialog(null)}
            readOnly={readOnly}
            onSave={(next) => {
              const value = next.world_reveal ?? [];
              updateVolume(activeVolumeIndex, { world_reveal: value });
              setDependencyDialog(null);
              showToast('世界观承接已保存到当前稿，定稿后写回');
            }}
            volume={activeVolume}
          />
        ) : null}
        {activeVolume && dependencyDialog === 'foreshadow' ? (
          <OutlineForeshadowLedgerDialog
            baseline={baseline}
            onClose={() => setDependencyDialog(null)}
            readOnly={readOnly}
            onSave={(next) => {
              const value = next.foreshadow_plan ?? [];
              updateVolume(activeVolumeIndex, { foreshadow_plan: value });
              setDependencyDialog(null);
              showToast('伏笔计划已保存到当前稿，定稿后写回');
            }}
            volume={activeVolume}
          />
        ) : null}
      </AnimatePresence>
    </div>
  );
}
