import { X } from 'lucide-react';
import { AnimatePresence, motion } from 'motion/react';
import { useState, type CSSProperties } from 'react';
import { createPortal } from 'react-dom';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { backdropMotionVariants, dialogMotionVariants } from '../lib/motion';
import { useOverlayDialog } from '../state/useOverlayDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import { ArtifactDraftActions } from './ArtifactDraftActions';
import { ArtifactDraftField } from './ArtifactDraftField';
import { draftErrorCount, duplicateTrimmedValueIndexes, requiredDraftFieldErrors } from './artifactDraftValidation';

export type CharacterArcDraft = { name: string; arc: string; pressure?: string; next?: string };

type Props = {
  activeIndex: number;
  arcs: CharacterArcDraft[];
  baselineCharacters?: Array<{ name: string; identity: string }>;
  baselineRelationships?: Array<{ source: string; target: string; relation: string; strength?: number }>;
  baselineSynopsis?: string;
  onClose: () => void;
  onSave: (arcs: CharacterArcDraft[]) => void;
  onSelect: (index: number) => void;
  readOnly?: boolean;
};

export function CharacterArcDeepeningDialog({
  activeIndex,
  arcs,
  baselineCharacters = [],
  baselineRelationships = [],
  baselineSynopsis = '',
  onClose,
  onSave,
  onSelect,
  readOnly = false,
}: Props) {
  const [initialDrafts] = useState(() => mergeCharacterArcDrafts(arcs, baselineCharacters));
  const [drafts, setDrafts] = useState(() => structuredClone(initialDrafts));
  const [selectedRelation, setSelectedRelation] = useState(0);
  const dirty = !draftsEqual(initialDrafts, drafts);
  const modeClass = usePortalModeClass();
  const scopeLabel = '人物关系深化当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);
  const dialogRef = useOverlayDialog<HTMLElement>({ onClose: requestClose, open: true, suspended: Boolean(draftGuard.intent) });
  const active = drafts[activeIndex] ?? drafts[0];
  const duplicateNameIndexes = duplicateTrimmedValueIndexes(drafts.map((draft) => draft.name));
  const errorsByIndex = drafts.map((draft, index) => {
    const errors = requiredDraftFieldErrors([
      { key: 'name', label: 'Info 人物', value: draft.name },
      { key: 'arc', label: '人物弧线', value: draft.arc },
      { key: 'pressure', label: '关系压力', value: draft.pressure },
      { key: 'next', label: '后续影响', value: draft.next },
    ]);
    if (duplicateNameIndexes.has(index)) errors.name = '同一人物只能保留一条深化记录';
    if (baselineCharacters.length && draft.name.trim() && !baselineCharacters.some((character) => character.name === draft.name.trim())) {
      errors.name = '人物必须来自 Info 已定稿名单';
    }
    return errors;
  });
  const invalidCount = errorsByIndex.reduce((count, errors) => count + draftErrorCount(errors), 0);
  const activeErrors = errorsByIndex[activeIndex] ?? {};

  const updateActive = (patch: Partial<CharacterArcDraft>) => {
    if (readOnly) return;
    setDrafts((current) => current.map((item, index) => (index === activeIndex ? { ...item, ...patch } : item)));
  };
  const selectCharacter = (name: string) => {
    const arcIndex = drafts.findIndex((arc) => arc.name === name);
    if (arcIndex >= 0) onSelect(arcIndex);
  };
  const activeRelation = baselineRelationships[selectedRelation] ?? null;
  const relationTarget = activeRelation
    ? `${activeRelation.source} ↔ ${activeRelation.target}`
    : active?.name ?? '角色';

  return (
    <>
      {createPortal(
        <AnimatePresence>
          <motion.div animate="animate" className={`artifact-detail-backdrop app-overlay-backdrop character-arc-backdrop ${modeClass}`} exit="exit" initial="initial" onClick={requestClose} role="presentation" variants={backdropMotionVariants}>
            <motion.section
              animate="animate"
              aria-label="人物关系网深化"
              aria-modal="true"
              className={`artifact-detail-dialog app-dialog-surface character-deepening-dialog${readOnly ? ' readonly' : ''}`}
              exit="exit"
              initial="initial"
              onClick={(event) => event.stopPropagation()}
              ref={dialogRef}
              role="dialog"
              tabIndex={-1}
              variants={dialogMotionVariants}
            >
              <button aria-label="关闭人物深化编辑" className="modal-close" onClick={requestClose} type="button"><X size={22} /></button>
              <div className="character-deepening-title"><p className="eyebrow">关系深化</p><h2>梗概阶段 · 人物关系深化</h2></div>
              {baselineSynopsis ? <p className="artifact-dialog-lede">{baselineSynopsis}</p> : null}
              <div className="character-info-baseline">
                <strong>Info 定稿人物</strong>
                <div>
                  {(baselineCharacters.length ? baselineCharacters : drafts.map((item) => ({ name: item.name, identity: '身份待定' }))).map((character) => (
                    <b key={`${character.name}-${character.identity}`}>{character.name}<small>{character.identity}</small></b>
                  ))}
                </div>
              </div>
              <div className="character-baseline-relations" aria-label="Info 阶段人物关系">
                <div className="baseline-relations-head"><strong>Info 阶段人物关系</strong><span>{baselineRelationships.length || drafts.length} 个关系 / 角色入口</span></div>
                <div className="baseline-relation-map">
                  {baselineRelationships.length ? baselineRelationships.map((edge, index) => (
                    <button
                      aria-pressed={index === selectedRelation}
                      className={index === selectedRelation ? 'active' : ''}
                      key={`${edge.source}-${edge.target}-${index}`}
                      onClick={() => {
                        const arcIndex = drafts.findIndex((arc) => arc.name === edge.source || arc.name === edge.target);
                        setSelectedRelation(index);
                        if (arcIndex >= 0) onSelect(arcIndex);
                      }}
                      type="button"
                    >
                      <span>{edge.source}</span>
                      <i style={{ '--strength': `${Math.max(28, Math.min(100, Math.round((edge.strength ?? 0.58) * 100)))}%` } as CSSProperties} />
                      <span>{edge.target}</span>
                      <b>{edge.relation}</b>
                    </button>
                  )) : <p>Info 阶段还没有写入人物关系边。</p>}
                </div>
              </div>
              <div className="character-deepening-grid">
                <aside className="character-deepening-list" aria-label="角色列表">
                  <strong>单个角色</strong>
                  {drafts.map((arc, index) => (
                    <button className={index === activeIndex ? 'active' : ''} key={`${arc.name}-${index}`} onClick={() => { setSelectedRelation(-1); onSelect(index); }} type="button">
                      <strong>{arc.name}</strong><span>{arc.pressure || '待补关系压力'}</span>
                    </button>
                  ))}
                </aside>
                {active ? (
                  <section className="character-deepening-form">
                    <div className="relationship-focus-card">
                      <small>当前深化对象</small><strong>{relationTarget}</strong><span>{activeRelation ? activeRelation.relation : `${active.name} 的独立人物弧补充`}</span>
                      {activeRelation ? <div className="relationship-focus-people">{[activeRelation.source, activeRelation.target].map((name) => <button className={active.name === name ? 'active' : ''} key={name} onClick={() => selectCharacter(name)} type="button">{name}</button>)}</div> : null}
                    </div>
                    {activeErrors.name ? <p className="artifact-draft-source-error" role="alert">{activeErrors.name}</p> : null}
                    <ArtifactDraftField error={activeErrors.arc} id={`summary-character-${activeIndex}-arc`} label={`${active.name} · 人物弧线`} required>
                      {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={active.arc} onChange={(event) => updateActive({ arc: event.target.value })} />}
                    </ArtifactDraftField>
                    <ArtifactDraftField error={activeErrors.pressure} id={`summary-character-${activeIndex}-pressure`} label="关系压力 / 动机张力" required>
                      {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={active.pressure ?? ''} onChange={(event) => updateActive({ pressure: event.target.value })} />}
                    </ArtifactDraftField>
                    <ArtifactDraftField error={activeErrors.next} id={`summary-character-${activeIndex}-next`} label="后续影响 / 定稿后写回人物关系网" required>
                      {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={active.next ?? ''} onChange={(event) => updateActive({ next: event.target.value })} />}
                    </ArtifactDraftField>
                  </section>
                ) : null}
              </div>
              {readOnly ? null : (
                <ArtifactDraftActions
                  dirty={dirty}
                  invalidCount={invalidCount}
                  onClose={requestClose}
                  onSave={() => onSave(drafts.map((draft) => ({
                    arc: draft.arc.trim(),
                    name: draft.name.trim(),
                    next: draft.next?.trim(),
                    pressure: draft.pressure?.trim(),
                  })))}
                />
              )}
            </motion.section>
          </motion.div>
        </AnimatePresence>,
        document.body,
      )}
      {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={modeClass} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}

function mergeCharacterArcDrafts(arcs: CharacterArcDraft[], baselineCharacters: Array<{ name: string; identity: string }>) {
  const merged = structuredClone(arcs);
  baselineCharacters.forEach((character) => {
    if (!merged.some((arc) => arc.name === character.name)) {
      merged.push({
        arc: `${character.identity} 在梗概阶段等待补充新的选择、代价或立场变化。`,
        name: character.name,
        next: '后续章节会根据该变化继承人物状态。',
        pressure: '等待补充关系压力。',
      });
    }
  });
  return merged.length ? merged : arcs;
}

function usePortalModeClass() {
  const [modeClass] = useState(() => {
    if (typeof document === 'undefined') return '';
    const shell = document.querySelector('.product-shell');
    if (shell?.classList.contains('mode-fast')) return 'mode-fast';
    if (shell?.classList.contains('mode-balanced')) return 'mode-balanced';
    if (shell?.classList.contains('mode-deep')) return 'mode-deep';
    return '';
  });
  return modeClass;
}
