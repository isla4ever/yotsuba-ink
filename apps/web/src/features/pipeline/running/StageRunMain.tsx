import { BookOpenText } from 'lucide-react';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { QualityProcessStrip } from './QualityProcessStrip';
import { DetailStageView, InfoStageView, PlanningStageView, WritingStageView } from './StageRunViews';
import { currentStep, latestResult, stageConfig, statusText } from './stageRunUtils';

type Props = {
  approvalDraft: string;
  approvalPending: boolean;
  events: RunEvent[];
  onApprovalDraftChange: (value: string) => void;
  onApproveBrief: (artifact: string) => void;
  onRegenerateBrief: () => void;
  stage: WorkflowStage;
  workflow: WorkflowDefinition;
};

export function StageRunMain({
  approvalDraft,
  approvalPending,
  events,
  onApprovalDraftChange,
  onApproveBrief,
  onRegenerateBrief,
  stage,
  workflow,
}: Props) {
  const config = stageConfig(stage.type);
  const result = latestResult(events, stage.id);
  const referenceEvents = events.filter((event) => event.type.startsWith('rag_') || event.type.startsWith('web_') || event.type.startsWith('reference_'));
  return (
    <>
      <div className="stage-run-head">
        <div>
          <p className="eyebrow">Stage Workspace</p>
          <h2>{config.icon}{stage.label}</h2>
        </div>
        <div className="writing-metrics">
          <span>{workflow.quality_mode === 'deep' ? '深度精修' : workflow.quality_mode === 'fast' ? '极速预览' : '平衡创作'}</span>
          <span>{statusText(stage.id, events)}</span>
          <span>Q {stage.quality_policy.min_score.toFixed(2)}</span>
        </div>
      </div>
      <div className="stage-thinking-strip">
        {config.steps.map((step, index) => (
          <article className={index <= currentStep(stage.id, events, config.steps.length) ? 'active' : ''} key={step}>
            <b>{String(index + 1).padStart(2, '0')}</b>
            <span>{step}</span>
          </article>
        ))}
      </div>
      <QualityProcessStrip events={events} stageId={stage.id} />
      {stage.type === 'info_recommend' ? (
        <InfoStageView
          approvalDraft={approvalDraft || result}
          approvalPending={approvalPending}
          referenceEvents={referenceEvents}
          stage={stage}
          onApprovalDraftChange={onApprovalDraftChange}
          onApproveBrief={onApproveBrief}
          onRegenerateBrief={onRegenerateBrief}
        />
      ) : null}
      {stage.type === 'summary' ? <PlanningStageView title="全书主线生成" sections={['一句话卖点', '三幕结构', '角色弧', '结局方向']} result={result} /> : null}
      {stage.type === 'outline' ? <PlanningStageView title="分卷大纲生成" sections={['卷级目标', '卷冲突', '章节范围', '伏笔分布']} result={result} /> : null}
      {stage.type === 'detail_outline' ? <DetailStageView stage={stage} result={result} /> : null}
      {stage.type === 'chapter_text' ? <WritingStageView events={events} workflow={workflow} /> : null}
      {stage.type === 'cover_image' ? <PlanningStageView title="封面产物生成" sections={['视觉关键词', '构图方向', '封面提示词', '预览产物']} result={result} /> : null}
      {stage.type === 'export_artifact' ? <PlanningStageView title="导出产物整理" sections={['小说资产', '质量报告', 'Wiki 摘要', '导出包']} result={result} /> : null}
      {!['info_recommend', 'summary', 'outline', 'detail_outline', 'chapter_text', 'cover_image', 'export_artifact'].includes(stage.type) ? (
        <section className="stage-run-card"><BookOpenText size={16} />暂未定义该阶段展示。</section>
      ) : null}
    </>
  );
}
