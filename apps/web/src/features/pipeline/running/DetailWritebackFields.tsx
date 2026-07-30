import { Plus, Trash2 } from 'lucide-react';
import type { ReactNode } from 'react';
import type { DetailBaseline } from './detailArtifactModel';
import type { DetailFieldErrors } from './detailDraftValidation';
import { detailFieldErrorId } from './detailValidationFocus';
import {
  appendDetailDraftRow,
  removeDetailDraftRow,
  updateDetailDraftRow,
  type DetailDraftRow,
} from './detailWritebackRows';
import type { DetailCharacterShift, DetailFactReveal, DetailForeshadow, DetailWikiCandidate } from './stageArtifacts';

export function CharacterShiftFields({ baseline, errors = {}, readOnly, value, onChange }: {
  baseline: DetailBaseline;
  errors?: DetailFieldErrors;
  readOnly: boolean;
  value: DetailCharacterShift;
  onChange: (value: DetailCharacterShift) => void;
}) {
  const update = (key: keyof DetailCharacterShift, next: string) => onChange({
    ...value,
    [key]: next,
    ...(key === 'related_to' && !next ? { relation: '' } : {}),
  });
  return (
    <div className="detail-structured-editor character">
      <div className="detail-field-row">
        <SelectField error={errors.character} field="character" label="变化人物" options={baseline.characters.map((item) => item.name)} readOnly={readOnly} value={value.character} onChange={(next) => update('character', next)} />
        <SelectField error={errors.related_to} field="related_to" label="关系对象（可选）" options={baseline.characters.filter((item) => item.name !== value.character).map((item) => item.name)} readOnly={readOnly} value={value.related_to} onChange={(next) => update('related_to', next)} optional />
      </div>
      <TextField error={errors.relation} field="relation" label="关系定义" readOnly={readOnly || !value.related_to} value={value.relation} onChange={(next) => update('relation', next)} />
      <TextField error={errors.pressure} field="pressure" label="本章压力" readOnly={readOnly} value={value.pressure} onChange={(next) => update('pressure', next)} />
      <TextField error={errors.motivation} field="motivation" label="行动动机" readOnly={readOnly} value={value.motivation} onChange={(next) => update('motivation', next)} />
      <TextField error={errors.change} field="change" label="状态变化" readOnly={readOnly} value={value.change} onChange={(next) => update('change', next)} />
      <TextField error={errors.impact} field="impact" label="后续影响" readOnly={readOnly} value={value.impact} onChange={(next) => update('impact', next)} />
    </div>
  );
}

export function WorldWikiFields({ baseline, errors = {}, facts, onFactsChange, wiki, onWikiChange, readOnly }: {
  baseline: DetailBaseline;
  errors?: DetailFieldErrors;
  facts: DetailDraftRow<DetailFactReveal>[];
  onFactsChange: (value: DetailDraftRow<DetailFactReveal>[]) => void;
  wiki: DetailDraftRow<DetailWikiCandidate>[];
  onWikiChange: (value: DetailDraftRow<DetailWikiCandidate>[]) => void;
  readOnly: boolean;
}) {
  return (
    <div className="detail-structured-editor world-wiki">
      <EntryList
        addLabel="添加事实"
        items={facts}
        onAdd={() => onFactsChange(appendDetailDraftRow(facts, 'fact', { anchor: baseline.worldAnchors[0] ?? '', fact: '', impact: '' }))}
        onRemove={(id) => onFactsChange(removeDetailDraftRow(facts, id))}
        readOnly={readOnly}
        title="事实揭示"
        error={errors.fact_reveals}
        render={(row, index) => (
          <>
            <SelectField error={errors[`fact_reveals.${index}.anchor`]} field={`fact_reveals.${index}.anchor`} label="已确认锚点" options={baseline.worldAnchors} readOnly={readOnly} value={row.value.anchor} onChange={(anchor) => onFactsChange(updateDetailDraftRow(facts, row.id, { ...row.value, anchor }))} />
            <TextField error={errors[`fact_reveals.${index}.fact`]} field={`fact_reveals.${index}.fact`} label="本章确认事实" readOnly={readOnly} value={row.value.fact} onChange={(fact) => onFactsChange(updateDetailDraftRow(facts, row.id, { ...row.value, fact }))} />
            <TextField error={errors[`fact_reveals.${index}.impact`]} field={`fact_reveals.${index}.impact`} label="对后续影响" readOnly={readOnly} value={row.value.impact} onChange={(impact) => onFactsChange(updateDetailDraftRow(facts, row.id, { ...row.value, impact }))} />
          </>
        )}
      />
      <EntryList
        addLabel="添加 Wiki 候选"
        items={wiki}
        onAdd={() => onWikiChange(appendDetailDraftRow(wiki, 'wiki', { title: '', fact: '', source_anchor: baseline.worldAnchors[0] ?? '' }))}
        onRemove={(id) => onWikiChange(removeDetailDraftRow(wiki, id))}
        readOnly={readOnly}
        title="Wiki 候选"
        error={errors.wiki_candidates}
        render={(row, index) => (
          <>
            <TextField error={errors[`wiki_candidates.${index}.title`]} field={`wiki_candidates.${index}.title`} label="条目标题" readOnly={readOnly} value={row.value.title} onChange={(title) => onWikiChange(updateDetailDraftRow(wiki, row.id, { ...row.value, title }))} />
            <TextField error={errors[`wiki_candidates.${index}.fact`]} field={`wiki_candidates.${index}.fact`} label="可沉淀事实" readOnly={readOnly} value={row.value.fact} onChange={(fact) => onWikiChange(updateDetailDraftRow(wiki, row.id, { ...row.value, fact }))} />
            <SelectField error={errors[`wiki_candidates.${index}.source_anchor`]} field={`wiki_candidates.${index}.source_anchor`} label="事实来源锚点" options={baseline.worldAnchors} readOnly={readOnly} value={row.value.source_anchor} onChange={(source_anchor) => onWikiChange(updateDetailDraftRow(wiki, row.id, { ...row.value, source_anchor }))} />
          </>
        )}
      />
    </div>
  );
}

export function ForeshadowFields({ baseline, errors = {}, onChange, readOnly, value }: {
  baseline: DetailBaseline;
  errors?: DetailFieldErrors;
  onChange: (value: DetailDraftRow<DetailForeshadow>[]) => void;
  readOnly: boolean;
  value: DetailDraftRow<DetailForeshadow>[];
}) {
  return (
    <div className="detail-structured-editor foreshadow">
      <datalist id="detail-foreshadow-options">{baseline.foreshadows.map((item) => <option key={item} value={item} />)}</datalist>
      <EntryList
        addLabel="添加伏笔动作"
        items={value}
        onAdd={() => onChange(appendDetailDraftRow(value, 'clue', { name: baseline.foreshadows[0] ?? '', status: '投放', note: '' }))}
        onRemove={(id) => onChange(removeDetailDraftRow(value, id))}
        readOnly={readOnly}
        title="伏笔动作"
        error={errors.foreshadow}
        render={(row, index) => (
          <>
            <label className={errors[`foreshadow.${index}.name`] ? 'detail-field-invalid' : ''}><span>伏笔名称</span><input {...validationProps(`foreshadow.${index}.name`, errors[`foreshadow.${index}.name`])} list="detail-foreshadow-options" readOnly={readOnly} value={row.value.name} onChange={(event) => onChange(updateDetailDraftRow(value, row.id, { ...row.value, name: event.target.value }))} /><FieldError error={errors[`foreshadow.${index}.name`]} field={`foreshadow.${index}.name`} /></label>
            <SelectField error={errors[`foreshadow.${index}.status`]} field={`foreshadow.${index}.status`} label="本章动作" options={['投放', '推进', '回收', '延后']} readOnly={readOnly} value={row.value.status} onChange={(status) => onChange(updateDetailDraftRow(value, row.id, { ...row.value, status: status as DetailForeshadow['status'] }))} />
            <TextField error={errors[`foreshadow.${index}.note`]} field={`foreshadow.${index}.note`} label="动作说明" readOnly={readOnly} value={row.value.note} onChange={(note) => onChange(updateDetailDraftRow(value, row.id, { ...row.value, note }))} />
          </>
        )}
      />
    </div>
  );
}

function EntryList<T>({ addLabel, error, items, onAdd, onRemove, readOnly, render, title }: {
  addLabel: string;
  error?: string;
  items: DetailDraftRow<T>[];
  onAdd: () => void;
  onRemove: (id: string) => void;
  readOnly: boolean;
  render: (row: DetailDraftRow<T>, index: number) => ReactNode;
  title: string;
}) {
  return (
    <section className="detail-entry-list">
      <header><h3>{title}</h3>{readOnly ? null : <button onClick={onAdd} type="button"><Plus size={14} />{addLabel}</button>}</header>
      {items.map((row, index) => (
        <div className="detail-entry-row" key={row.id}>
          <div>{render(row, index)}</div>
          {readOnly ? null : <button aria-label={`删除${title} ${index + 1}`} className="detail-entry-remove" onClick={() => onRemove(row.id)} type="button"><Trash2 size={15} /></button>}
        </div>
      ))}
      {!items.length ? <p aria-live="polite" className={`detail-empty-entry${error ? ' invalid' : ''}`}>{error || `尚无${title}，定稿前至少添加一条。`}</p> : null}
    </section>
  );
}

function SelectField({ error, field, label, onChange, optional, options, readOnly, value }: { error?: string; field: string; label: string; onChange: (value: string) => void; optional?: boolean; options: string[]; readOnly: boolean; value: string }) {
  return <label className={error ? 'detail-field-invalid' : ''}><span>{label}</span><select {...validationProps(field, error)} disabled={readOnly} value={value} onChange={(event) => onChange(event.target.value)}>{optional ? <option value="">不写关系</option> : <option value="">请选择</option>}{options.map((item) => <option key={item} value={item}>{item}</option>)}</select><FieldError error={error} field={field} /></label>;
}

function TextField({ error, field, label, onChange, readOnly, value }: { error?: string; field: string; label: string; onChange: (value: string) => void; readOnly: boolean; value: string }) {
  return <label className={error ? 'detail-field-invalid' : ''}><span>{label}</span><textarea {...validationProps(field, error)} readOnly={readOnly} value={value} onChange={(event) => onChange(event.target.value)} /><FieldError error={error} field={field} /></label>;
}

function FieldError({ error, field }: { error?: string; field: string }) {
  return error ? <small className="detail-field-error" id={detailFieldErrorId(field)}>{error}</small> : null;
}

function validationProps(field: string, error?: string) {
  return {
    'aria-describedby': error ? detailFieldErrorId(field) : undefined,
    'aria-invalid': Boolean(error),
    'data-detail-field': field,
  };
}
