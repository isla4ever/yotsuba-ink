import { AnimatePresence } from 'motion/react';
import { useEffect, useMemo, useState } from 'react';
import { CharacterArcDeepeningDialog } from './SummaryCharacterArcDialog';
import { SummaryContextBar } from './SummaryContextBar';
import { SummaryManuscriptPane } from './SummaryManuscriptPane';
import { SummaryMiniEditDialog } from './SummaryStructureDialogs';
import { SummarySupportWorkbench } from './SummarySupportWorkbench';
import { summaryArtifact, type SummaryArtifact } from './stageArtifacts';
import { StageToast } from './StageToast';
import { summaryInfoBaseline, summaryReadiness } from './summaryArtifactModel';
import type { QualityMode } from '../contracts';

type Props = {
  baseline?: string;
  deltas?: Array<{ section: string; delta: string }>;
  generating?: boolean;
  onArtifactChange?: (artifact: SummaryArtifact) => void;
  qualityMode: QualityMode;
  readOnly?: boolean;
  result: string;
  sourceResult?: string;
};

export function SummaryStageView({
  baseline = '',
  deltas = [],
  generating,
  onArtifactChange,
  qualityMode,
  readOnly = false,
  result,
  sourceResult = result,
}: Props) {
  const [artifact, setArtifact] = useState(() => summaryArtifact(result));
  const [editingArcs, setEditingArcs] = useState(false);
  const [activeArcIndex, setActiveArcIndex] = useState(0);
  const [activeBeatIndex, setActiveBeatIndex] = useState<number | null>(null);
  const [activeTurnIndex, setActiveTurnIndex] = useState<number | null>(null);
  const [toast, setToast] = useState('');
  useEffect(() => setArtifact(summaryArtifact(result)), [result]);
  const baselineInfo = useMemo(() => summaryInfoBaseline(baseline), [baseline]);
  const readiness = summaryReadiness(artifact, baselineInfo.characters.map((character) => character.name));
  const showToast = (message: string) => {
    setToast(message);
  };
  const updateArtifact = (updater: (current: SummaryArtifact) => SummaryArtifact) => {
    const next = updater(artifact);
    setArtifact(next);
    onArtifactChange?.(next);
  };
  return (
    <div className="stage-contract-board summary-board">
      <StageToast durationMs={1500} message={toast} onDismiss={() => setToast('')} />
      <SummaryContextBar
        generating={Boolean(generating)}
        onOneLinerChange={(one_liner) => updateArtifact((current) => ({ ...current, one_liner }))}
        oneLiner={artifact.one_liner}
        readOnly={readOnly}
        readiness={readiness}
      />
      <SummaryManuscriptPane
        artifact={artifact}
        deltas={deltas}
        generating={Boolean(generating)}
        onArtifactChange={(patch) => updateArtifact((current) => ({ ...current, ...patch }))}
        onDraftSaved={showToast}
        qualityMode={qualityMode}
        readOnly={readOnly}
        sourceKey={sourceResult}
      />
      <SummarySupportWorkbench
        artifact={artifact}
        baseline={baselineInfo}
        onOpenArc={(index) => {
          setActiveArcIndex(index);
          setEditingArcs(true);
        }}
        onOpenArcs={() => setEditingArcs(true)}
        onOpenBeat={setActiveBeatIndex}
        onOpenTurn={setActiveTurnIndex}
        readOnly={readOnly}
      />
      <AnimatePresence>
      {editingArcs ? (
        <CharacterArcDeepeningDialog
          activeIndex={activeArcIndex}
          arcs={artifact.character_arcs}
          baselineCharacters={baselineInfo.characters}
          baselineRelationships={baselineInfo.relationships}
          baselineSynopsis={baselineInfo.synopsis}
          onClose={() => setEditingArcs(false)}
          readOnly={readOnly}
          onSave={(nextArcs) => {
            updateArtifact((current) => ({ ...current, character_arcs: nextArcs }));
            setEditingArcs(false);
            showToast('人物深化已保存到当前稿，定稿后写回');
          }}
          onSelect={setActiveArcIndex}
        />
      ) : null}
      {activeBeatIndex !== null && artifact.act_structure[activeBeatIndex] ? (
        <SummaryMiniEditDialog
          index={activeBeatIndex}
          kind="beat"
          onClose={() => setActiveBeatIndex(null)}
          readOnly={readOnly}
          onSave={(next) => {
            updateArtifact((current) => ({
              ...current,
              act_structure: updateListItem(current.act_structure, activeBeatIndex, {
                ...current.act_structure[activeBeatIndex],
                title: next.title,
                goal: next.goal,
                turn: next.turn,
              }),
            }));
            setActiveBeatIndex(null);
            showToast('结构节拍已保存到当前稿');
          }}
          value={artifact.act_structure[activeBeatIndex]}
        />
      ) : null}
      {activeTurnIndex !== null && artifact.key_turns[activeTurnIndex] ? (
        <SummaryMiniEditDialog
          index={activeTurnIndex}
          kind="turn"
          onClose={() => setActiveTurnIndex(null)}
          readOnly={readOnly}
          onSave={(next) => {
            updateArtifact((current) => ({
              ...current,
              key_turns: updateListItem(current.key_turns, activeTurnIndex, {
                ...current.key_turns[activeTurnIndex],
                label: next.label,
                detail: next.detail,
              }),
            }));
            setActiveTurnIndex(null);
            showToast('关键转折已保存到当前稿');
          }}
          value={artifact.key_turns[activeTurnIndex]}
        />
      ) : null}
      </AnimatePresence>
    </div>
  );
}

function updateListItem<T>(items: T[], index: number, next: T) {
  return items.map((item, itemIndex) => itemIndex === index ? next : item);
}
