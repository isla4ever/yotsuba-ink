import { Plus } from 'lucide-react';
import { useState } from 'react';
import type { ProviderProfile, ProviderTemplate } from '../contracts';
import { OptionField } from './fields/OptionField';
import { providerTemplateOptionItems } from './providerOptionItems';
import { providerProfileFromTemplate } from './settingsWorkflow';

type Props = {
  existingIds: string[];
  templates: ProviderTemplate[];
  onCreate: (provider: ProviderProfile) => void;
};

export function ProviderCreateControl({ existingIds, templates, onCreate }: Props) {
  const [selectedId, setSelectedId] = useState('');
  const selected = templates.find((template) => template.id === selectedId) ?? templates[0];
  return (
    <div className="provider-action-row provider-create-control">
      <OptionField
        disabled={!selected}
        emptyLabel="没有匹配的厂商模板"
        forceSearchable
        label="厂商模板"
        options={providerTemplateOptionItems(templates)}
        placeholder="选择文本或图片服务"
        searchPlaceholder="搜索厂商、网关或模板"
        value={selected?.id ?? ''}
        onValueChange={setSelectedId}
      />
      <button
        className="provider-add-action"
        disabled={!selected}
        type="button"
        onClick={() => {
          if (selected) onCreate(providerProfileFromTemplate(selected, existingIds));
        }}
      >
        <Plus size={14} />
        添加接口
      </button>
    </div>
  );
}
