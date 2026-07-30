import { useState } from 'react';
import type { InputField } from '../contracts';
import { addTagValue, coerceFieldValue, removeTagValue } from '../lib/stageConfig';

type Props = {
  field: InputField;
  idPrefix?: string;
  onChange: (value: unknown) => void;
};

export function StageInputField({ field, idPrefix = 'stage-input', onChange }: Props) {
  const inputId = `${idPrefix}-${field.key}`;
  const helpId = field.help ? `${inputId}-help` : undefined;
  const common = {
    'aria-describedby': helpId,
    'aria-required': field.required || undefined,
    id: inputId,
    name: field.key,
  };
  const wide = field.type === 'textarea' || field.type === 'tags';

  return (
    <div className={wide ? 'stage-input-field wide' : 'stage-input-field'}>
      <label className="stage-input-label" htmlFor={common.id}>
        {field.label}
        {field.required ? <b>必填</b> : null}
      </label>
      {field.type === 'select' ? (
        <select {...common} required={field.required} value={String(field.default ?? '')} onChange={(event) => onChange(event.target.value)}>
          {(field.options ?? []).map((option) => <option value={option} key={option}>{option}</option>)}
        </select>
      ) : null}
      {field.type === 'textarea' ? (
        <textarea
          {...common}
          className="stage-input-textarea"
          required={field.required}
          value={String(field.default ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : null}
      {field.type === 'boolean' ? (
        <label className="inline-switch" htmlFor={common.id}>
          <input
            {...common}
            checked={Boolean(field.default)}
            type="checkbox"
            onChange={(event) => onChange(event.target.checked)}
          />
          <span>{Boolean(field.default) ? '已开启' : '已关闭'}</span>
        </label>
      ) : null}
      {field.type !== 'select' && field.type !== 'textarea' && field.type !== 'boolean' ? (
        field.type === 'tags' ? (
          <TagInput describedBy={helpId} field={field} inputId={common.id} onChange={onChange} />
        ) : (
          <input
            {...common}
            required={field.required}
            type={field.type === 'number' ? 'number' : 'text'}
            value={String(field.default ?? '')}
            onChange={(event) => onChange(coerceFieldValue(field, event.target.value))}
          />
        )
      ) : null}
      {field.help ? <small id={helpId}>{field.help}</small> : null}
    </div>
  );
}

function TagInput({ describedBy, field, inputId, onChange }: Props & { describedBy?: string; inputId: string }) {
  const tags = Array.isArray(field.default) ? field.default.map(String) : [];
  const [draft, setDraft] = useState('');

  const commit = (raw: string) => {
    if (!raw.trim()) return;
    onChange(addTagValue(field.default, raw));
    setDraft('');
  };

  return (
    <div className="tag-input-box">
      <div className="tag-chip-row">
        {tags.map((tag) => (
          <button type="button" key={tag} onClick={() => onChange(removeTagValue(field.default, tag))}>
            {tag}<span>×</span>
          </button>
        ))}
      </div>
      <input
        aria-describedby={describedBy}
        aria-required={field.required || undefined}
        id={inputId}
        name={field.key}
        value={draft}
        placeholder="输入后按回车添加"
        onChange={(event) => setDraft(event.target.value)}
        onKeyDown={(event) => {
          if (event.key === 'Enter' || event.key === ',' || event.key === '，' || event.key === '、') {
            event.preventDefault();
            commit(draft);
          }
          if (event.key === 'Backspace' && !draft && tags.length) {
            onChange(tags.slice(0, -1));
          }
        }}
        onBlur={() => commit(draft)}
      />
    </div>
  );
}
