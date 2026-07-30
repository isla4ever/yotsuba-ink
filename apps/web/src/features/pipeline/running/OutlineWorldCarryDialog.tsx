import { Globe2 } from 'lucide-react';
import { useMemo, useState } from 'react';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import {
  OutlineDependencyDialogFooter,
  OutlineDependencyDialogShell,
  type OutlineDependencyDialogProps,
  useOutlinePortalModeClass,
} from './OutlineDependencyDialogShell';
import type { OutlineWorldReveal } from './stageArtifacts';
import { ArtifactDraftField } from './ArtifactDraftField';
import { draftErrorCount, requiredDraftFieldErrors } from './artifactDraftValidation';
import { saveWorldReveal } from './outlineDependencyDrafts';

export function OutlineWorldCarryDialog({ baseline, onClose, onSave, readOnly = false, volume }: OutlineDependencyDialogProps) {
  const anchors = useMemo(() => Array.from(new Set([
    ...volume.world_reveal.map((item) => item.anchor).filter((anchor) => baseline.worldbuildingDetail.includes(anchor)),
    ...baseline.worldAnchors,
  ])), [baseline, volume.world_reveal]);
  const initialAnchor = volume.world_reveal[0]?.anchor ?? anchors[0] ?? '';
  const valuesForAnchor = (next: string) => {
    const current = volume.world_reveal.find((item) => item.anchor === next);
    return { impact: current?.impact ?? '', reveal: current?.reveal ?? '', rule: current?.rule ?? '' };
  };
  const [anchor, setAnchor] = useState(initialAnchor);
  const [baselineDraft, setBaselineDraft] = useState(() => valuesForAnchor(initialAnchor));
  const [draft, setDraft] = useState(() => structuredClone(baselineDraft));
  const dirty = !draftsEqual(baselineDraft, draft);
  const modeClass = useOutlinePortalModeClass();
  const scopeLabel = '世界观承接当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);

  const selectAnchor = (next: string) => {
    if (next === anchor) return;
    draftGuard.requestAction({ destinationLabel: next, kind: 'switch', scopeLabel }, () => {
      const nextDraft = valuesForAnchor(next);
      setAnchor(next);
      setBaselineDraft(nextDraft);
      setDraft(structuredClone(nextDraft));
    });
  };
  const ready = Boolean(anchor.trim() && Object.values(draft).every((item) => item.trim()));
  const errors = requiredDraftFieldErrors([
    { key: 'reveal', label: '本卷揭示内容', value: draft.reveal },
    { key: 'rule', label: '硬规则限制', value: draft.rule },
    { key: 'impact', label: '后续影响', value: draft.impact },
  ]);
  const invalidCount = anchor ? draftErrorCount(errors) : 1;
  const save = () => {
    if (!ready) return;
    const item: OutlineWorldReveal = { anchor, reveal: draft.reveal.trim(), rule: draft.rule.trim(), impact: draft.impact.trim() };
    onSave({ world_reveal: saveWorldReveal(volume.world_reveal, item) });
  };

  return (
    <>
    <OutlineDependencyDialogShell icon={<Globe2 size={18} />} kicker="设定承接" modeClass={modeClass} onClose={requestClose} readOnly={readOnly} suspended={Boolean(draftGuard.intent)} title="世界观承接">
      <div className="outline-carry-grid world">
        <aside className="outline-source-rail" aria-label="选择世界观锚点">
          {anchors.map((item) => (
            <button className={anchor === item ? 'active' : ''} key={item} onClick={() => selectAnchor(item)} type="button">
              <span>承接 Info 已定稿世界观</span><b>{item}</b><small>定稿后写入本卷揭示计划</small>
            </button>
          ))}
          {!anchors.length ? <p>Info 定稿中还没有可引用的世界观锚点。</p> : null}
        </aside>
        {anchor ? (
          <section className="outline-carry-editor world">
            <div className="outline-world-anchor"><b>{anchor}</b><span>来源：Info 世界观</span></div>
            <ArtifactDraftField error={errors.reveal} id="outline-world-reveal" label="本卷揭示内容" required>
              {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={draft.reveal} onChange={(event) => setDraft((current) => ({ ...current, reveal: event.target.value }))} />}
            </ArtifactDraftField>
            <ArtifactDraftField error={errors.rule} id="outline-world-rule" label="硬规则限制" required>
              {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={draft.rule} onChange={(event) => setDraft((current) => ({ ...current, rule: event.target.value }))} />}
            </ArtifactDraftField>
            <ArtifactDraftField error={errors.impact} id="outline-world-impact" label="后续影响" required>
              {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={draft.impact} onChange={(event) => setDraft((current) => ({ ...current, impact: event.target.value }))} />}
            </ArtifactDraftField>
          </section>
        ) : null}
      </div>
      <OutlineDependencyDialogFooter dirty={dirty} disabled={!anchor} invalidCount={invalidCount} label="保存到当前稿" onClose={requestClose} onSave={save} readOnly={readOnly} />
    </OutlineDependencyDialogShell>
    {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={modeClass} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}
