import * as Dialog from '@radix-ui/react-dialog';
import * as Tabs from '@radix-ui/react-tabs';
import * as Switch from '@radix-ui/react-switch';
import { motion } from 'motion/react';
import { AlertTriangle, CheckCircle2, KeyRound, Layers3, Settings, X } from 'lucide-react';
import { ModelOptionInput } from './fields/ModelOptionInput';
import type { ProviderProfile, WorkflowDefinition, WorkflowStage } from '../contracts';
import { modelNameForUi, providerKindForUi, providerNameForUi } from '../lib/display';

type Props = {
  open: boolean;
  apiWarning?: string;
  workflow: WorkflowDefinition;
  onOpenChange: (open: boolean) => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

export function SettingsDialog({ open, apiWarning, workflow, onOpenChange, onWorkflowChange }: Props) {
  const globalText = workflow.provider_profiles.find((item) => item.is_global_default) ?? workflow.provider_profiles.find((item) => item.kind !== 'image-mock') ?? workflow.provider_profiles[0];
  const globalImage = workflow.provider_profiles.find((item) => item.kind === 'image-mock') ?? workflow.provider_profiles[0];

  const updateProvider = (provider: ProviderProfile) => {
    onWorkflowChange({
      ...workflow,
      provider_profiles: workflow.provider_profiles.map((item) => (item.id === provider.id ? provider : item)),
    });
  };

  const updateStage = (stage: WorkflowStage) => {
    onWorkflowChange({
      ...workflow,
      nodes: workflow.nodes.map((item) => (item.id === stage.id ? stage : item)),
    });
  };

  const addModelOption = (providerId: string, model: string) => {
    const provider = workflow.provider_profiles.find((item) => item.id === providerId);
    if (!provider) return;
    updateProvider({ ...provider, model_options: Array.from(new Set([...(provider.model_options ?? []), model])) });
  };

  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="settings-overlay" />
        <Dialog.Content asChild>
          <section className="settings-dialog">
            <motion.div
              animate={{ opacity: 1, scale: 1, y: 0 }}
              className="settings-dialog-inner"
              initial={{ opacity: 0, scale: 0.96, y: 10 }}
              transition={{ duration: 0.18 }}
            >
            <div className="settings-head">
              <div>
                <p className="eyebrow">Settings Center</p>
                <Dialog.Title>模型与运行设置</Dialog.Title>
                <Dialog.Description>配置全局 API、阶段覆盖和运行策略。API Key 只保存环境变量名，不在前端明文保存。</Dialog.Description>
              </div>
              <Dialog.Close className="modal-close settings-close"><X size={15} /></Dialog.Close>
            </div>

            {apiWarning ? (
              <div className="settings-warning">
                <AlertTriangle size={16} />
                <span>{apiWarning}</span>
              </div>
            ) : null}

            <Tabs.Root className="settings-tabs" defaultValue="global">
              <Tabs.List className="settings-tab-list">
                <Tabs.Trigger value="global">全局模型</Tabs.Trigger>
                <Tabs.Trigger value="providers">Provider/API</Tabs.Trigger>
                <Tabs.Trigger value="stages">阶段覆盖</Tabs.Trigger>
                <Tabs.Trigger value="runtime">运行策略</Tabs.Trigger>
              </Tabs.List>

              <Tabs.Content value="global" className="settings-tab-content">
                <section className="settings-section">
                  <h3><Settings size={16} />默认模型策略</h3>
                  <label>
                    默认文本 Provider
                    <select value={globalText?.id} onChange={(event) => setGlobalDefault(workflow, event.target.value, onWorkflowChange)}>
                      {workflow.provider_profiles.filter((provider) => provider.kind !== 'image-mock').map((provider) => (
                        <option value={provider.id} key={provider.id}>{providerNameForUi(provider)}</option>
                      ))}
                    </select>
                  </label>
                  {globalText ? (
                    <ModelOptionInput
                      label="默认文本模型"
                      providerId={globalText.id}
                      providers={workflow.provider_profiles}
                      value={globalText.default_model}
                      onAddOption={addModelOption}
                      onChange={(model: string) => updateProvider({ ...globalText, default_model: model })}
                    />
                  ) : null}
                  {globalImage ? (
                    <ModelOptionInput
                      label="默认图像模型"
                      providerId={globalImage.id}
                      providers={workflow.provider_profiles}
                      value={globalImage.default_model}
                      onAddOption={addModelOption}
                      onChange={(model: string) => updateProvider({ ...globalImage, default_model: model })}
                    />
                  ) : null}
                  <div className="settings-note">阶段未单独配置时默认继承全局文本 Provider；封面阶段默认继承图像 Provider。</div>
                </section>
              </Tabs.Content>

              <Tabs.Content value="providers" className="settings-tab-content">
                <section className="settings-section">
                  <h3><KeyRound size={16} />Provider/API</h3>
                  <div className="provider-editor-list">
                    {workflow.provider_profiles.map((provider) => (
                      <article className="provider-editor" key={provider.id}>
                        <div className="provider-editor-head">
                          <strong>{providerNameForUi(provider)}</strong>
                          <label className="switch-line">
                            <Switch.Root className="switch-root" checked={provider.enabled} onCheckedChange={(enabled) => updateProvider({ ...provider, enabled })}>
                              <Switch.Thumb className="switch-thumb" />
                            </Switch.Root>
                            启用
                          </label>
                        </div>
                        <div className="settings-grid">
                          <label>名称<input value={providerNameForUi(provider)} readOnly={provider.kind === 'mock' || provider.kind === 'image-mock'} onChange={(event) => updateProvider({ ...provider, name: event.target.value })} /></label>
                          <label>类型<input value={providerKindForUi(provider.kind)} readOnly /></label>
                          <label>Base URL<input value={provider.base_url} onChange={(event) => updateProvider({ ...provider, base_url: event.target.value })} placeholder="https://api.example.com/v1" /></label>
                          <label>API Key 环境变量<input value={provider.api_key_env} onChange={(event) => updateProvider({ ...provider, api_key_env: event.target.value })} placeholder="NOVEL_LLM_API_KEY" /></label>
                        </div>
                        <ModelOptionInput
                          label="默认模型"
                          providerId={provider.id}
                          providers={workflow.provider_profiles}
                          value={provider.default_model}
                          onAddOption={addModelOption}
                          onChange={(model: string) => updateProvider({ ...provider, default_model: model })}
                        />
                      </article>
                    ))}
                  </div>
                </section>
              </Tabs.Content>

              <Tabs.Content value="stages" className="settings-tab-content">
                <section className="settings-section">
                  <h3><Layers3 size={16} />阶段覆盖</h3>
                  <div className="stage-override-list">
                    {workflow.nodes.map((stage) => {
                      const provider = workflow.provider_profiles.find((item) => item.id === stage.provider_profile_id) ?? globalText;
                      return (
                        <article key={stage.id}>
                          <strong>{stage.label}</strong>
                          <select value={stage.provider_profile_id} onChange={(event) => {
                            const nextProvider = workflow.provider_profiles.find((item) => item.id === event.target.value);
                            updateStage({ ...stage, provider_profile_id: event.target.value, model_settings: { ...stage.model_settings, model: nextProvider?.default_model ?? stage.model_settings.model } });
                          }}>
                            {workflow.provider_profiles.map((item) => (
                              <option value={item.id} key={item.id}>{providerNameForUi(item)}</option>
                            ))}
                          </select>
                          <ModelOptionInput
                            label="阶段模型"
                            providerId={provider?.id ?? stage.provider_profile_id}
                            providers={workflow.provider_profiles}
                            value={stage.model_settings.model}
                            onAddOption={addModelOption}
                            onChange={(model: string) => updateStage({ ...stage, model_settings: { ...stage.model_settings, model } })}
                          />
                        </article>
                      );
                    })}
                  </div>
                </section>
              </Tabs.Content>

              <Tabs.Content value="runtime" className="settings-tab-content">
                <section className="settings-section">
                  <h3><CheckCircle2 size={16} />运行策略</h3>
                  <div className="runtime-options">
                    <label><input type="checkbox" checked readOnly />开启自动保存配置</label>
                    <label><input type="checkbox" checked readOnly />运行前检查线上 API 配置</label>
                    <label><input type="checkbox" checked readOnly />允许本地演示通道验证流程</label>
                  </div>
                  <div className="settings-note">正文多版本比对会按候选版本数放大生成成本，并额外调用评审模型。后续接入真实执行链路时会在运行前展示 token 成本估算。</div>
                </section>
              </Tabs.Content>
            </Tabs.Root>
            </motion.div>
          </section>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

function setGlobalDefault(workflow: WorkflowDefinition, providerId: string, onChange: (workflow: WorkflowDefinition) => void) {
  onChange({
    ...workflow,
    provider_profiles: workflow.provider_profiles.map((provider) => ({
      ...provider,
      is_global_default: provider.id === providerId,
    })),
  });
}
