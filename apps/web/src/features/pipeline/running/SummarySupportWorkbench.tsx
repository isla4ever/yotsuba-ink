import { BookOpenText, Edit3, Layers3, Route } from 'lucide-react';
import { useState } from 'react';
import { CharacterArcSwimlanes } from './CharacterArcSwimlanes';
import type { SummaryArtifact } from './stageArtifacts';
import type { SummaryInfoBaseline } from './summaryArtifactModel';

type Props = {
  artifact: SummaryArtifact;
  baseline: SummaryInfoBaseline;
  onOpenArc: (index: number) => void;
  onOpenArcs: () => void;
  onOpenBeat: (index: number) => void;
  onOpenTurn: (index: number) => void;
  readOnly: boolean;
};

export function SummarySupportWorkbench({ artifact, baseline, onOpenArc, onOpenArcs, onOpenBeat, onOpenTurn, readOnly }: Props) {
  const [activeTrack, setActiveTrack] = useState<'beats' | 'turns'>('beats');
  return (
    <div className="summary-side-workbench">
      <div className="summary-side-top" data-active-track={activeTrack}>
        <div aria-label="梗概结构视图" className="summary-support-tabs" role="group">
          <button aria-pressed={activeTrack === 'beats'} onClick={() => setActiveTrack('beats')} type="button">
            <Route size={13} />结构节拍 <span>{artifact.act_structure.length}</span>
          </button>
          <button aria-pressed={activeTrack === 'turns'} onClick={() => setActiveTrack('turns')} type="button">
            <Layers3 size={13} />关键转折 <span>{artifact.key_turns.length}</span>
          </button>
        </div>
        <section aria-label="结构节拍" className="summary-structure-pane">
          <div className="summary-pane-head compact">
            <h3><Route size={15} />结构节拍</h3>
            <span>{artifact.act_structure.length} 幕</span>
          </div>
          <div className="summary-beat-timeline">
            {artifact.act_structure.map((act, index) => (
              <button className="summary-beat-step summary-beat-card" key={`${act.title}-${index}`} onClick={() => onOpenBeat(index)} type="button">
                <span>{String(index + 1).padStart(2, '0')}</span>
                <div className="summary-beat-content">
                  <strong>{act.title}</strong>
                  <p><em>推进</em>{act.goal}</p>
                  <p><em>转折</em>{act.turn}</p>
                </div>
              </button>
            ))}
          </div>
        </section>
        <section aria-label="关键转折" className="summary-turning-pane">
          <div className="summary-pane-head compact">
            <h3><Layers3 size={15} />关键转折</h3>
            <span>{artifact.key_turns.length} 处</span>
          </div>
          <div className="summary-turn-ladder">
            {artifact.key_turns.map((item, index) => (
              <button className="summary-turn-step summary-turn-card" key={`${item.label}-${index}`} onClick={() => onOpenTurn(index)} type="button">
                <b>{String(index + 1).padStart(2, '0')}</b>
                <div>
                  <strong>{item.label}</strong>
                  <p>{item.detail}</p>
                </div>
              </button>
            ))}
          </div>
        </section>
      </div>
      <section aria-label="人物弧泳道" className="summary-relationship-sync">
        <div className="summary-relationship-head">
          <div>
            <p className="eyebrow">定稿后写回</p>
            <h3><BookOpenText size={15} />人物弧泳道</h3>
          </div>
          <button className="icon-title-action" onClick={onOpenArcs} type="button">
            <Edit3 size={13} />{readOnly ? '预览' : '深化'}
          </button>
        </div>
        <div className="summary-relationship-content with-arc-swimlanes">
          <CharacterArcSwimlanes artifact={artifact} identities={baseline.characters} onOpenArc={onOpenArc} />
        </div>
      </section>
    </div>
  );
}
