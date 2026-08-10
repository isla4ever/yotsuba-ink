import { ExternalLink } from 'lucide-react';
import type { ProviderProfile, ProviderTemplate } from '../contracts';
import { OptionField } from './fields/OptionField';
import {
  integrationTierLabel,
  providerTemplateOptionItems,
  providerTemplateUsage,
  providerTemplateUsageLabel,
} from './providerOptionItems';
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
  const usage = selected ? providerTemplateUsage(selected) : null;
  const capabilityUrl = selected?.capability_docs?.find((url) => url !== selected.docs_url);
  return (
    <div className="provider-template-field">
      <OptionField
        disabled={busy || compatible.length === 0}
        emptyLabel="当前类型没有匹配模板"
        forceSearchable
        label="厂商模板"
        options={providerTemplateOptionItems(compatible)}
        searchPlaceholder="搜索当前类型的厂商模板"
        status={selected && usage === 'production' ? 'ready' : 'warning'}
        value={provider.template_id}
        onValueChange={(templateId) => {
          const template = compatible.find((item) => item.id === templateId);
          if (template) onChange(applyProviderTemplate(provider, template));
        }}
      />
      {selected ? (
        <div className="provider-template-meta" data-tier={selected.integration_tier}>
          <span>
            {providerTemplateUsageLabel(selected)} · {integrationTierLabel(selected.integration_tier)} · {structuredOutputLabel(selected)}
            {selected.supports_prompt_cache_key ? ' · 前缀缓存' : ''}
          </span>
          <p>{selected.description}</p>
          {selected.structured_output_notes ? <p>{selected.structured_output_notes}</p> : null}
          {selected.execution_allowed === false ? (
            <p className="provider-template-policy" role="note">{selected.execution_policy_note || '此模板仅可用于外部工具，不能作为应用后端运行。'}</p>
          ) : null}
          {selected.workflow_execution_allowed === false ? (
            <p className="provider-template-policy" role="note">{selected.workflow_execution_policy_note || '此模板只用于连接测试和模型评估，不能运行小说生产工作流。'}</p>
          ) : null}
          <a href={selected.docs_url} rel="noreferrer" target="_blank">
            接口文档 <ExternalLink aria-hidden size={12} />
          </a>
          {capabilityUrl ? (
            <a href={capabilityUrl} rel="noreferrer" target="_blank">
              能力说明 <ExternalLink aria-hidden size={12} />
            </a>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

function structuredOutputLabel(template: ProviderTemplate) {
  if (template.structured_output_mode === 'json_schema') return 'JSON Schema';
  if (template.structured_output_mode === 'json_object') return 'JSON Object';
  return 'Prompt 约束';
}
