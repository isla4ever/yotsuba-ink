import { AlertTriangle, CheckCircle2, KeyRound, RefreshCw, Wand2 } from 'lucide-react';
import { useState } from 'react';
import type { WorkflowDefinition } from '../contracts';
import { ButtonLoadingIndicator } from '../layout/ButtonLoadingIndicator';
import { LoadingButton } from '../layout/LoadingButton';
import {
  connectedProvider,
  stagesNeedingRebind,
  withStagesBoundToConnectedProviders,
} from '../lib/providerBinding';
import { providerReadinessSummary } from '../lib/setupProgress';
import type { ProviderReadinessState } from './useProviderReadiness';
import { ProviderManagerSheet } from './ProviderManagerSheet';
import { useProviderAvailability } from './useProviderAvailability';

type Props = {
  readiness: ProviderReadinessState;
  workflow: WorkflowDefinition;
  onReadinessRefresh: () => void;
  onWorkflowChange: (workflow: WorkflowDefinition) => void;
};

export function AiServiceSetupSection({ readiness, workflow, onReadinessRefresh, onWorkflowChange }: Props) {
  const [managerOpen, setManagerOpen] = useState(false);
  const availability = useProviderAvailability(true);
  const failedChecks = readiness.report?.checks.filter((check) => !check.ready) ?? [];
  // Secret flags only exist on the live profile list, so binding repair reads
  // connection state from there rather than from the workflow's snapshot.
  const liveWorkflow = { ...workflow, provider_profiles: availability.profiles };
  const unboundStages = availability.status === 'ready' ? stagesNeedingRebind(liveWorkflow) : [];
  const repairTarget = unboundStages.length ? connectedProvider(availability.profiles, 'openai-compatible') : undefined;
  const statusLabel = readiness.status === 'loading'
    ? '正在检查配置'
    : readiness.status === 'failed'
      ? 'AI 服务检查失败'
      : readiness.report
        ? providerReadinessSummary(readiness.report)
        : 'AI 服务状态尚未确认';
  return (
    <section aria-labelledby="setup-step-title-ai-service" className="setup-form-section ai-service-setup-section">
      <header>
        <p className="eyebrow">第 2 步</p>
        <h2 id="setup-step-title-ai-service" tabIndex={-1}>连接用于创作的 AI 服务</h2>
        <p>连接信息只填写一次。所有阶段默认继承文本和封面服务，有特殊需求时再在阶段检查器设置例外。</p>
      </header>

      <div className="ai-service-readiness" data-status={readiness.status}>
        <div>
          {readiness.status === 'loading' ? <ButtonLoadingIndicator size="medium" /> : readiness.report?.ok ? <CheckCircle2 size={17} /> : <AlertTriangle size={17} />}
          <span>
            <strong>{statusLabel}</strong>
            <small>{readiness.error ? `检查失败：${readiness.error}。现有配置和密钥草稿未被清除。` : '这里只检查配置完整性；真实连接由你主动点击“检查连接”验证。'}</small>
          </span>
        </div>
        {failedChecks.length ? (
          <ul>{failedChecks.slice(0, 4).map((check) => <li key={`${check.provider_id}-${check.expected_kind}`}>
            {check.model ? <strong>{check.model} · </strong> : null}{check.message}
          </li>)}</ul>
        ) : null}
        {readiness.report?.ok ? (
          <ul className="ai-service-model-assignments">
            {readiness.report.checks.filter((check) => check.model).map((check) => (
              <li key={`${check.provider_id}-${check.expected_kind}-model`}><span>{check.used_by.join('、')}</span><strong>{check.model}</strong></li>
            ))}
          </ul>
        ) : null}
      </div>

      <div className="ai-service-actions">
        {repairTarget ? (
          <button
            className="tech-button"
            type="button"
            onClick={() => {
              onWorkflowChange({
                ...withStagesBoundToConnectedProviders(liveWorkflow),
                provider_profiles: workflow.provider_profiles,
              });
              onReadinessRefresh();
            }}
          >
            <Wand2 size={15} />把 {unboundStages.length} 个阶段切到「{repairTarget.name}」
          </button>
        ) : null}
        <button className="tech-button ghost" id="setup-ai-service-manager" type="button" onClick={() => setManagerOpen(true)}><KeyRound size={15} />管理 AI 服务</button>
        <LoadingButton className="ghost" loading={readiness.status === 'loading'} loadingLabel="检查中" onClick={onReadinessRefresh}><RefreshCw size={14} />重新检查配置</LoadingButton>
      </div>
      <ProviderManagerSheet
        open={managerOpen}
        workflow={workflow}
        onOpenChange={setManagerOpen}
        onReadinessRefresh={onReadinessRefresh}
        onWorkflowChange={onWorkflowChange}
      />
    </section>
  );
}
