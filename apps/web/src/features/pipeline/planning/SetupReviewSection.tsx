import { useState, type ReactNode } from 'react';
import { AlertTriangle, CheckCircle2, ChevronDown, Pencil } from 'lucide-react';
import type { KnowledgeDocument, SetupStep, SetupStepId, WorkflowDefinition, WorkflowStage } from '../contracts';
import { qualityModeProfiles } from '../lib/qualityModes';
import { referenceSummary, reviewCreationModeCardId, reviewReferenceCardId } from '../lib/setupProgress';
import { updateStageInputDefault } from '../lib/stageConfig';
import { CreationModeSetupSection } from './CreationModeSetupSection';
import { ReferenceSetupSection } from './ReferenceSetupSection';

type Props = {
  knowledgeDocuments: KnowledgeDocument[];
  stage?: WorkflowStage;
  steps: SetupStep[];
  workflow: WorkflowDefinition;
  onOpenKnowledgeManager: () => void;
  onQualityModeChange: (mode: WorkflowDefinition['quality_mode']) => void;
  onStageChange: (stage: WorkflowStage) => void;
  onStepRequest: (stepId: SetupStepId, fieldId?: string) => void;
};

/** 参考摘要编辑回写：确认页 textarea 直接写回 info 阶段的 reference_summary 输入。 */
export function withReferenceSummary(stage: WorkflowStage, value: string): WorkflowStage {
  return updateStageInputDefault(stage, 'reference_summary', value);
}

/** Phase 12 A4: 确认启动 — 默认卡（参考方式/创作模式）+ 就绪清单，不要求重新输入。 */
export function SetupReviewSection({
  knowledgeDocuments,
  onOpenKnowledgeManager,
  onQualityModeChange,
  onStageChange,
  onStepRequest,
  stage,
  steps,
  workflow,
}: Props) {
  const review = steps.find((step) => step.id === 'review');
  const blocked = review?.issues.filter((issue) => issue.severity === 'blocking') ?? [];
  const cardIssue = (cardId: string) => review?.issues.find((issue) => issue.target.fieldId === cardId);
  const summaryValue = String(stage?.input_schema.find((field) => field.key === 'reference_summary')?.default ?? '');
  // An out-of-contract mode is reported as a blocking card issue; the page
  // itself falls back to the balanced profile copy instead of crashing.
  const mode = qualityModeProfiles[workflow.quality_mode] ?? qualityModeProfiles.balanced;
  return (
    <section aria-labelledby="setup-step-title-review" className="setup-form-section setup-review-section">
      <header>
        <p className="eyebrow">第 3 步</p>
        <h2 id="setup-step-title-review" tabIndex={-1}>确认启动</h2>
        <p>参考方式与创作模式已使用推荐默认，点开卡片即可修改。开始后会按当前快照创建运行。</p>
      </header>
      <div className="setup-default-cards">
        <ReviewDefaultCard
          cardId={reviewReferenceCardId}
          issue={cardIssue(reviewReferenceCardId)}
          summary={stage ? referenceSummary(stage, knowledgeDocuments) : '参考方式配置缺失'}
          detail={summaryValue.trim() ? `已生成参考摘要 ${summaryValue.trim().length} 字` : '尚未生成参考摘要，可直接开始'}
          title="参考方式"
        >
          <ReferenceSetupSection
            knowledgeDocuments={knowledgeDocuments}
            stage={stage}
            onChange={onStageChange}
            onOpenKnowledgeManager={onOpenKnowledgeManager}
          />
          {stage ? (
            <label className="setup-reference-summary-field" htmlFor="setup-review-reference-summary">
              <span>参考资料摘要<small>该摘要将进入创作立项阶段的输入，可直接修改。</small></span>
              <textarea
                id="setup-review-reference-summary"
                placeholder="生成参考摘要后会出现在这里；也可以手动填写要交给创作立项的参考要点。"
                value={summaryValue}
                onChange={(event) => onStageChange(withReferenceSummary(stage, event.target.value))}
              />
            </label>
          ) : null}
        </ReviewDefaultCard>
        <ReviewDefaultCard
          cardId={reviewCreationModeCardId}
          issue={cardIssue(reviewCreationModeCardId)}
          summary={`${mode.title} · ${mode.intervention}`}
          detail={mode.useCase}
          title="创作模式"
        >
          <CreationModeSetupSection context="review" value={workflow.quality_mode} onChange={onQualityModeChange} />
        </ReviewDefaultCard>
      </div>
      <div className="setup-review-ledger">
        {steps.filter((step) => step.id !== 'review').map((step) => {
          const blocking = step.issues.find((issue) => issue.severity === 'blocking');
          return (
            <div data-status={blocking ? 'blocked' : 'ready'} key={step.id}>
              {blocking ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
              <span><strong>{step.label}</strong><small>{blocking?.label || step.summary}</small></span>
              <button aria-label={`修改${step.label}`} type="button" onClick={() => onStepRequest(step.id, blocking?.target.fieldId)}><Pencil size={14} /></button>
            </div>
          );
        })}
      </div>
      <div className={blocked.length ? 'setup-launch-status blocked' : 'setup-launch-status ready'} role={blocked.length ? 'alert' : 'status'}>
        {blocked.length ? (
          <><AlertTriangle size={17} /><span><strong>还有 {blocked.length} 项启动条件需要处理</strong><small>先处理上方标记的问题；已填写内容会继续自动保存。</small></span></>
        ) : (
          <><CheckCircle2 size={17} /><span><strong>可以开始创作</strong><small>{mode.intervention}；运行会持续到下一决策点或完成。</small></span></>
        )}
      </div>
    </section>
  );
}

function ReviewDefaultCard({ cardId, children, detail, issue, summary, title }: {
  cardId: string;
  children: ReactNode;
  detail: string;
  issue?: SetupStep['issues'][number];
  summary: string;
  title: string;
}) {
  // The step panel remounts on navigation, so the initial state re-derives:
  // a card with an outstanding issue opens itself for fixing.
  const [open, setOpen] = useState(() => Boolean(issue));
  return (
    <section className="setup-default-card" data-open={open} data-status={issue?.severity === 'blocking' ? 'blocked' : 'ready'} id={cardId} tabIndex={-1}>
      <button aria-expanded={open} className="setup-default-card-head" type="button" onClick={() => setOpen((current) => !current)}>
        {issue?.severity === 'blocking' ? <AlertTriangle size={16} /> : <CheckCircle2 size={16} />}
        <span>
          <strong>{title}<em>已用默认</em></strong>
          <small>{issue ? issue.label : `${summary} · ${detail}`}</small>
        </span>
        <ChevronDown className="setup-default-card-chevron" size={15} />
      </button>
      {open ? <div className="setup-default-card-body">{children}</div> : null}
    </section>
  );
}
