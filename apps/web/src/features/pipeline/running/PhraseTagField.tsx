import { Plus, X } from 'lucide-react';
import { useState } from 'react';

type Props = {
  addLabel: string;
  ariaLabel: string;
  onChange: (values: string[]) => void;
  placeholder?: string;
  readOnly: boolean;
  values: string[];
};

/** Short-phrase tag editor for list fields such as cover negative_constraints. */
export function PhraseTagField({ addLabel, ariaLabel, onChange, placeholder, readOnly, values }: Props) {
  const [draft, setDraft] = useState('');
  const commit = () => {
    const value = draft.trim();
    if (!value || values.includes(value)) { setDraft(''); return; }
    onChange([...values, value]);
    setDraft('');
  };
  return (
    <div aria-label={ariaLabel} className="vnext-phrase-tags" role="group">
      {values.map((value) => (
        <span className="vnext-phrase-tag" key={value}>
          {value}
          {!readOnly ? (
            <button aria-label={`删除 ${value}`} onClick={() => onChange(values.filter((item) => item !== value))} type="button">
              <X size={12} />
            </button>
          ) : null}
        </span>
      ))}
      {!readOnly ? (
        <span className="vnext-phrase-tag-input">
          <input
            aria-label={addLabel}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key !== 'Enter') return;
              event.preventDefault();
              commit();
            }}
            placeholder={placeholder ?? addLabel}
            value={draft}
          />
          <button aria-label={addLabel} disabled={!draft.trim()} onClick={commit} type="button"><Plus size={13} /></button>
        </span>
      ) : null}
    </div>
  );
}
