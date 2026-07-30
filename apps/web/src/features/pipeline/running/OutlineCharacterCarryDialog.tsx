import { GitBranch } from 'lucide-react';
import { useMemo, useState } from 'react';
import { UnsavedDraftDialog } from '../layout/UnsavedDraftDialog';
import { draftsEqual, useUnsavedDraftGuard } from '../state/useUnsavedDraftGuard';
import {
  OutlineDependencyDialogFooter,
  OutlineDependencyDialogShell,
  type OutlineDependencyDialogProps,
  useOutlinePortalModeClass,
} from './OutlineDependencyDialogShell';
import type { OutlineCharacterProgression } from './stageArtifacts';
import { ArtifactDraftField } from './ArtifactDraftField';
import { draftErrorCount, requiredDraftFieldErrors } from './artifactDraftValidation';
import { saveCharacterProgression } from './outlineDependencyDrafts';

export function OutlineCharacterCarryDialog({ baseline, onClose, onSave, readOnly = false, volume }: OutlineDependencyDialogProps) {
  const sources = useMemo(() => relationshipSources(baseline), [baseline]);
  const initial = volume.character_progression[0];
  const initialKey = initial ? relationKey(initial.character, initial.related_to) : sources[0]?.key ?? '';
  const [activeKey, setActiveKey] = useState(initialKey);
  const valuesForKey = (key: string) => {
    const source = sources.find((item) => item.key === key);
    const current = volume.character_progression.find((item) => relationKey(item.character, item.related_to) === key);
    const summaryArc = baseline.summaryArcs.find((item) => item.name === source?.character);
    return {
      change: current?.change ?? summaryArc?.arc ?? '',
      impact: current?.impact ?? summaryArc?.next ?? '',
      pressure: current?.pressure ?? summaryArc?.pressure ?? '',
      relation: current?.relation ?? source?.relation ?? '',
    };
  };
  const [baselineDraft, setBaselineDraft] = useState(() => valuesForKey(initialKey));
  const [draft, setDraft] = useState(() => structuredClone(baselineDraft));
  const active = sources.find((item) => item.key === activeKey) ?? sources[0];
  const dirty = !draftsEqual(baselineDraft, draft);
  const modeClass = useOutlinePortalModeClass();
  const scopeLabel = '角色承接当前稿';
  const draftGuard = useUnsavedDraftGuard({ dirty, readOnly, scopeLabel });
  const requestClose = () => draftGuard.requestAction({ kind: 'close', scopeLabel }, onClose);

  const selectSource = (key: string) => {
    if (key === activeKey) return;
    const nextSource = sources.find((item) => item.key === key);
    draftGuard.requestAction({ destinationLabel: nextSource ? `${nextSource.character} / ${nextSource.relatedTo}` : undefined, kind: 'switch', scopeLabel }, () => {
      const nextDraft = valuesForKey(key);
      setActiveKey(key);
      setBaselineDraft(nextDraft);
      setDraft(structuredClone(nextDraft));
    });
  };
  const ready = Boolean(active && Object.values(draft).every((item) => item.trim()));
  const errors = requiredDraftFieldErrors([
    { key: 'relation', label: '关系定义', value: draft.relation },
    { key: 'pressure', label: '本卷关系压力', value: draft.pressure },
    { key: 'change', label: '本卷角色变化', value: draft.change },
    { key: 'impact', label: '定稿写回影响', value: draft.impact },
  ]);
  const invalidCount = active ? draftErrorCount(errors) : 1;

  const save = () => {
    if (!active || !ready) return;
    const current = volume.character_progression.find((item) => relationKey(item.character, item.related_to) === active.key);
    const item: OutlineCharacterProgression = {
      character: active.character,
      related_to: active.relatedTo,
      relation: draft.relation.trim(),
      kind: current?.kind || active.kind,
      polarity: current?.polarity || active.polarity,
      strength: current?.strength ?? active.strength,
      pressure: draft.pressure.trim(),
      change: draft.change.trim(),
      impact: draft.impact.trim(),
    };
    onSave({ character_progression: saveCharacterProgression(volume.character_progression, item) });
  };

  return (
    <>
    <OutlineDependencyDialogShell icon={<GitBranch size={18} />} kicker="人物承接" modeClass={modeClass} onClose={requestClose} readOnly={readOnly} suspended={Boolean(draftGuard.intent)} title="角色承接">
      <div className="outline-carry-grid character">
        <aside className="outline-source-rail" aria-label="选择承接关系">
          {sources.map((item) => (
            <button className={active?.key === item.key ? 'active' : ''} key={item.key} onClick={() => selectSource(item.key)} type="button">
              <span>{item.source}</span><b>{item.character} / {item.relatedTo}</b><small>{item.relation}</small>
            </button>
          ))}
          {!sources.length ? <p>Info 定稿中还没有可承接的人物关系。</p> : null}
        </aside>
        {active ? (
          <section className="outline-carry-editor">
            <div className="outline-link-preview"><strong>{active.character}</strong><i /><strong>{active.relatedTo}</strong><span>{draft.relation || '关系待定'}</span></div>
            <ArtifactDraftField error={errors.relation} id="outline-character-relation" label="关系定义" required>
              {(controlProps) => <input {...controlProps} readOnly={readOnly} value={draft.relation} onChange={(event) => setDraft((current) => ({ ...current, relation: event.target.value }))} />}
            </ArtifactDraftField>
            <ArtifactDraftField error={errors.pressure} id="outline-character-pressure" label="本卷关系压力" required>
              {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={draft.pressure} onChange={(event) => setDraft((current) => ({ ...current, pressure: event.target.value }))} />}
            </ArtifactDraftField>
            <ArtifactDraftField error={errors.change} id="outline-character-change" label="本卷角色变化" required>
              {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={draft.change} onChange={(event) => setDraft((current) => ({ ...current, change: event.target.value }))} />}
            </ArtifactDraftField>
            <ArtifactDraftField error={errors.impact} id="outline-character-impact" label="定稿写回影响" required>
              {(controlProps) => <textarea {...controlProps} readOnly={readOnly} value={draft.impact} onChange={(event) => setDraft((current) => ({ ...current, impact: event.target.value }))} />}
            </ArtifactDraftField>
          </section>
        ) : null}
      </div>
      <OutlineDependencyDialogFooter dirty={dirty} disabled={!active} invalidCount={invalidCount} label="保存到当前稿" onClose={requestClose} onSave={save} readOnly={readOnly} />
    </OutlineDependencyDialogShell>
    {draftGuard.intent ? <UnsavedDraftDialog intent={draftGuard.intent} modeClass={modeClass} onCancel={draftGuard.cancelDiscard} onDiscard={draftGuard.confirmDiscard} /> : null}
    </>
  );
}

function relationshipSources(baseline: OutlineDependencyDialogProps['baseline']) {
  if (baseline.relationships.length) return baseline.relationships.map((item) => ({
    character: item.source,
    key: relationKey(item.source, item.target),
    kind: item.kind,
    polarity: item.polarity,
    relatedTo: item.target,
    relation: item.relation,
    strength: item.strength,
    source: '承接 Info 已定稿关系',
  }));
  const [first, ...others] = baseline.characters;
  if (!first) return [];
  return others.map((item) => ({
    character: first.name,
    key: relationKey(first.name, item.name),
    kind: undefined,
    polarity: undefined,
    relatedTo: item.name,
    relation: '关系待定',
    source: '承接 Info 已定稿人物',
    strength: undefined,
  }));
}

function relationKey(left: string, right: string) {
  return [left.trim(), right.trim()].sort().join('::');
}
