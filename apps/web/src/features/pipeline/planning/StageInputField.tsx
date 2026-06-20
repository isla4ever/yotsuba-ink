import { useState } from 'react';
import type { InputField } from '../contracts';
import { addTagValue, coerceFieldValue, removeTagValue } from '../lib/stageConfig';

type Props = {
  field: InputField;
  onChange: (value: unknown) => void;
};

export function StageInputField({ field, onChange }: Props) {
  const common = {
    id: `stage-input-${field.key}`,
    name: field.key,
  };

  return (
    <label className={field.type === 'textarea' ? 'stage-input-field wide' : 'stage-input-field'} htmlFor={common.id}>
      <span>
        {field.label}
        {field.required ? <b>必填</b> : null}
      </span>
      {field.type === 'select' ? (
        <select {...common} value={String(field.default ?? '')} onChange={(event) => onChange(event.target.value)}>
          {(field.options ?? []).map((option) => <option value={option} key={option}>{option}</option>)}
        </select>
      ) : null}
      {field.type === 'textarea' ? (
        <textarea
          {...common}
          className="stage-input-textarea"
          value={String(field.default ?? '')}
          onChange={(event) => onChange(event.target.value)}
        />
      ) : null}
      {field.type === 'boolean' ? (
        <label className="inline-switch">
          <input
            checked={Boolean(field.default)}
            type="checkbox"
            onChange={(event) => onChange(event.target.checked)}
          />
          <span>{Boolean(field.default) ? '已开启' : '已关闭'}</span>
        </label>
      ) : null}
      {field.type !== 'select' && field.type !== 'textarea' && field.type !== 'boolean' ? (
        field.type === 'tags' ? (
          <TagInput field={field} onChange={onChange} />
        ) : (
          <input
            {...common}
            type={field.type === 'number' ? 'number' : 'text'}
            value={String(field.default ?? '')}
            onChange={(event) => onChange(coerceFieldValue(field, event.target.value))}
          />
        )
      ) : null}
      <small>{field.key} · {field.type}{field.help ? ` · ${field.help}` : ''}</small>
    </label>
  );
}

function TagInput({ field, onChange }: Props) {
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
