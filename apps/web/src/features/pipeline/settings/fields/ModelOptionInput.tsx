import { useMemo, useState } from 'react';
import type { ProviderProfile } from '../../contracts';
import { modelNameForUi } from '../../lib/display';

type Props = {
  label: string;
  value: string;
  providerId: string;
  providers: ProviderProfile[];
  onChange: (value: string) => void;
  onAddOption?: (providerId: string, value: string) => void;
};

export function ModelOptionInput({ label, value, providerId, providers, onChange, onAddOption }: Props) {
  const [draft, setDraft] = useState('');
  const provider = providers.find((item) => item.id === providerId);
  const options = useMemo(() => {
    const values = new Set<string>(provider?.model_options ?? []);
    if (provider?.default_model) values.add(provider.default_model);
    if (value) values.add(value);
    return Array.from(values);
  }, [provider, value]);

  return (
    <label className="model-option-field">
      {label}
      <div className="model-option-row">
        <select value={value} onChange={(event) => onChange(event.target.value)}>
          {options.map((option) => (
            <option value={option} key={option}>{modelNameForUi(option)}</option>
          ))}
        </select>
        <input
          placeholder="录入新模型"
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          onKeyDown={(event) => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            const next = draft.trim();
            if (!next) return;
            onAddOption?.(providerId, next);
            onChange(next);
            setDraft('');
          }}
        />
      </div>
      <small>回车即可加入当前 Provider 的模型选项。</small>
    </label>
  );
}
