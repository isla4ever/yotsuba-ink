import { useState } from 'react';
import type { InputField, WorkflowStage } from '../contracts';
import {
  addTagValue,
  coerceFieldValue,
  removeTagValue,
  updateStageInputDefault,
} from '../lib/stageConfig';
import { BookScaleTargetSection } from './BookScaleTargetSection';

type Props = {
  idPrefix?: string;
  stage: WorkflowStage;
  onChange: (stage: WorkflowStage) => void;
};

const briefFieldKeys = ['genre', 'audience', 'core_concept', 'keywords', 'taboos'];

export function StoryBriefFields({ idPrefix = 'brief', stage, onChange }: Props) {
  const fields = briefFieldKeys
    .map((key) => stage.input_schema.find((field) => field.key === key))
    .filter(Boolean) as InputField[];
  return (
    <div className="brief-field-grid">
      <BookScaleTargetSection idPrefix={idPrefix} stage={stage} onChange={onChange} />
      {fields.map((field) => (
        <BriefInput
          field={field}
          id={`${idPrefix}-${field.key}`}
          key={field.key}
          onChange={(value) => onChange(updateStageInputDefault(stage, field.key, value))}
        />
      ))}
    </div>
  );
}

function BriefInput({ field, id, onChange }: { field: InputField; id: string; onChange: (value: unknown) => void }) {
  return (
    <label className={field.type === 'textarea' ? 'stage-input-field wide brief-input' : 'stage-input-field brief-input'} htmlFor={id}>
      <span>{field.label}{field.required ? <b>必填</b> : null}</span>
      {field.hint ? <small className="brief-field-hint">{field.hint}</small> : null}
      {field.type === 'select' ? (
        <select id={id} value={String(field.default ?? '')} onChange={(event) => onChange(event.target.value)}>
          {(field.options ?? []).map((option) => <option key={option} value={option}>{option}</option>)}
        </select>
      ) : null}
      {field.type === 'textarea' ? (
        <textarea
          id={id}
          className="stage-input-textarea"
          placeholder={field.placeholder || undefined}
          value={String(field.default ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : null}
      {field.type === 'tags' ? <TagInput field={field} id={id} onChange={onChange} /> : null}
      {field.type !== 'select' && field.type !== 'textarea' && field.type !== 'tags' ? (
        <input
          id={id}
          placeholder={field.placeholder || undefined}
          type={field.type === 'number' ? 'number' : 'text'}
          value={String(field.default ?? '')}
          onChange={(event) => onChange(coerceFieldValue(field, event.target.value))}
        />
      ) : null}
    </label>
  );
}

function TagInput({ field, id, onChange }: { field: InputField; id: string; onChange: (value: unknown) => void }) {
  const tags = Array.isArray(field.default) ? field.default.map(String) : [];
  const [draft, setDraft] = useState('');
  const commit = () => {
    if (!draft.trim()) return;
    onChange(addTagValue(field.default, draft));
    setDraft('');
  };
  return (
    <div className="tag-input-box">
      <div className="tag-chip-row">
        {tags.map((tag) => (
          <button type="button" key={tag} onClick={() => onChange(removeTagValue(field.default, tag))}>{tag}<span>×</span></button>
        ))}
      </div>
      <input
        id={id}
        value={draft}
        placeholder={field.placeholder || '输入后按回车添加'}
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ',' || event.key === '，' || event.key === '、') {
            event.preventDefault();
            commit();
          }
        }}
        onBlur={commit}
      />
    </div>
  );
}
