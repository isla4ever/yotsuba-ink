import { Clock3, KeyRound, ScrollText } from 'lucide-react';
import { CharacterGraphPanel } from './CharacterGraphPanel';
import { ChapterProgressPanel } from './ChapterProgressPanel';
import { QualityMonitorPanel } from './QualityMonitorPanel';
import { StageInspector } from './StageInspector';
import { WikiMemoryPanel } from './WikiMemoryPanel';
import type { RunEvent, WorkflowDefinition, WorkflowStage, WorkspaceKey } from '../types/workflow';
import { modelNameForUi, providerKindForUi, providerNameForUi, runtimeTextForUi } from '../utils/display';

type Props = {
  active: WorkspaceKey;
  selectedStage: WorkflowStage;
  workflow: WorkflowDefinition;
  events: RunEvent[];
  onStageChange: (stage: WorkflowStage) => void;
};

export function InsightPanel({ active, selectedStage, workflow, events, onStageChange }: Props) {
  if (active === 'wiki') return <PanelShell title="Wiki / 素材库"><WikiMemoryPanel events={events} /></PanelShell>;
  if (active === 'quality') return <PanelShell title="质量监控"><QualityMonitorPanel events={events} stages={workflow.nodes} /></PanelShell>;
  if (active === 'characters') return <PanelShell title="人物关系网"><CharacterGraphPanel events={events} /></PanelShell>;
  if (active === 'chapters') return <PanelShell title="正文进度"><ChapterProgressPanel events={events} /></PanelShell>;
  if (active === 'providers') return <PanelShell title="Provider / API"><ProviderPanel workflow={workflow} /></PanelShell>;
  if (active === 'prompts') return <PanelShell title="Prompt 模板"><PromptPanel workflow={workflow} /></PanelShell>;
  if (active === 'history') return <PanelShell title="运行历史"><HistoryPanel events={events} /></PanelShell>;
  return (
    <StageInspector
      stage={selectedStage}
      providers={workflow.provider_profiles}
      prompts={workflow.prompt_templates}
      onChange={onStageChange}
      onAddModelOption={() => undefined}
    />
  );
}

function PanelShell({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <aside className="inspector">
      <div className="inspector-head">
        <p className="eyebrow">Insight Panel</p>
        <h2>{title}</h2>
      </div>
      {children}
    </aside>
  );
}

function ProviderPanel({ workflow }: { workflow: WorkflowDefinition }) {
  return (
    <div className="insight-stack">
      <section className="config-section">
        <h3><KeyRound size={16} />可用 Provider</h3>
        <div className="field-list">
          {workflow.provider_profiles.map((provider) => (
            <article key={provider.id}>
              <strong>{providerNameForUi(provider)}</strong>
              <span>{providerKindForUi(provider.kind)} · 默认模型 {modelNameForUi(provider.default_model)}</span>
              <small>{provider.api_key_env ? `API Key: ${provider.api_key_env}` : '本地演示通道'}</small>
            </article>
          ))}
        </div>
      </section>
      <section className="config-section">
        <h3>阶段模型覆盖</h3>
        <div className="field-list">
          {workflow.nodes.map((stage) => (
            <article key={stage.id}>
              <strong>{stage.label}</strong>
              <span>{providerNameForUi(stage.provider_profile_id)} · {modelNameForUi(stage.model_settings.model)}</span>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function PromptPanel({ workflow }: { workflow: WorkflowDefinition }) {
  return (
    <div className="insight-stack">
      <section className="config-section">
        <h3><ScrollText size={16} />Prompt 模板</h3>
        <div className="field-list">
          {workflow.prompt_templates.map((prompt) => (
            <article key={prompt.id}>
              <strong>{prompt.name}</strong>
              <span>{prompt.stage_type} · {prompt.variables.join(' / ') || '无变量'}</span>
              <small>{prompt.content}</small>
            </article>
          ))}
        </div>
      </section>
    </div>
  );
}

function HistoryPanel({ events }: { events: RunEvent[] }) {
  return (
    <div className="insight-stack">
      <section className="config-section">
        <h3><Clock3 size={16} />运行历史</h3>
        <div className="field-list">
          {events.slice(0, 16).map((event, index) => (
            <article key={`${event.type}-${event.node_id}-${index}`}>
              <strong>{runtimeTextForUi(event.type)}</strong>
              <span>{event.label ?? event.node_id ?? event.run_id}</span>
            </article>
          ))}
          {!events.length ? <p className="muted">开始创作后，这里会保留节点、Wiki、质量、章节和人物网更新事件。</p> : null}
        </div>
      </section>
    </div>
  );
}
