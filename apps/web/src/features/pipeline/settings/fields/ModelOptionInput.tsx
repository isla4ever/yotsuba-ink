import { Plus } from 'lucide-react';
import { useMemo, useState } from 'react';
import type { ProviderProfile } from '../../contracts';
import { modelNameForUi } from '../../lib/display';
import { OptionField } from './OptionField';

type Props = {
  disabled?: boolean;
  label: string;
  value: string;
  providerId: string;
  providers: ProviderProfile[];
  onChange: (value: string) => void;
  onAddOption?: (providerId: string, value: string) => void;
};

export function ModelOptionInput({ disabled = false, label, value, providerId, providers, onChange, onAddOption }: Props) {
  const [draft, setDraft] = useState('');
  const provider = providers.find((item) => item.id === providerId);
  const options = useMemo(() => {
    const values = new Set<string>(provider?.model_options ?? []);
    if (provider?.default_model) values.add(provider.default_model);
    if (value) values.add(value);
    return Array.from(values);
  }, [provider, value]);
  const commitDraft = () => {
    const next = draft.trim();
    if (!next || disabled || !onAddOption) return;
    onAddOption(providerId, next);
    onChange(next);
    setDraft('');
  };

  return (
    <div className="model-option-field">
      <div className="model-option-row">
        <OptionField
          disabled={disabled}
          label={label}
          options={options.map((option) => ({ value: option, label: modelNameForUi(option) }))}
          placeholder="选择已发现的模型"
          searchPlaceholder="搜索模型"
          value={value}
          onValueChange={onChange}
        />
        {onAddOption ? (
          <div className="model-option-custom">
            <label>
              自定义模型
              <input
                disabled={disabled}
                placeholder="例如 model-name"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key !== 'Enter' || event.nativeEvent.isComposing) return;
                  event.preventDefault();
                  commitDraft();
                }}
              />
            </label>
            <button aria-label={`添加${label}`} disabled={disabled || !draft.trim()} type="button" onClick={commitDraft}>
              <Plus size={14} />添加
            </button>
          </div>
        ) : null}
      </div>
      <small>选择已发现的模型，或录入后显式添加自定义模型。</small>
    </div>
  );
}
