import { ExternalLink } from 'lucide-react';
import type { ProviderProfile, ProviderTemplate } from '../contracts';
import { OptionField } from './fields/OptionField';
import { integrationTierLabel, providerTemplateOptionItems } from './providerOptionItems';
import { applyProviderTemplate } from './settingsWorkflow';

type Props = {
  busy: boolean;
  provider: ProviderProfile;
  templates: ProviderTemplate[];
  onChange: (provider: ProviderProfile) => void;
};

export function ProviderTemplateSelect({ busy, provider, templates, onChange }: Props) {
  const compatible = templates.filter((template) => template.kind === provider.kind);
  const selected = compatible.find((template) => template.id === provider.template_id);
  return (
    <div className="provider-template-field">
      <OptionField
        disabled={busy || compatible.length === 0}
        emptyLabel="当前类型没有匹配模板"
        forceSearchable
        label="厂商模板"
        options={providerTemplateOptionItems(compatible)}
        searchPlaceholder="搜索当前类型的厂商模板"
        status={selected ? 'ready' : 'warning'}
        value={provider.template_id}
        onValueChange={(templateId) => {
          const template = compatible.find((item) => item.id === templateId);
          if (template) onChange(applyProviderTemplate(provider, template));
        }}
      />
      {selected ? (
        <div className="provider-template-meta" data-tier={selected.integration_tier}>
          <span>{integrationTierLabel(selected.integration_tier)}</span>
          <p>{selected.description}</p>
          <a href={selected.docs_url} rel="noreferrer" target="_blank">
            官方文档 <ExternalLink aria-hidden size={12} />
          </a>
        </div>
      ) : null}
    </div>
  );
}
