import { CheckCircle2, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { DraftRegenerationDialog } from './DraftRegenerationDialog';
import { StageFinalizeTray } from './StageFinalizeTray';
import { TERM } from '../lib/terminology';

type DecisionProps = {
  artifactMissingLabels?: string[];
  artifactReady?: boolean;
  chapterId?: string;
  completed: boolean;
  events: RunEvent[];
  onConfirmStageArtifact: (stageId: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string, chapterId?: string) => void;
  stage: WorkflowStage;
  workflow: WorkflowDefinition;
};

export function StageDecisionControls({
  artifactMissingLabels = [],
  artifactReady = true,
  chapterId = '',
  completed,
  events,
  onConfirmStageArtifact,
  onRegenerateStageDraft,
  stage,
  workflow,
}: DecisionProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const pendingDecision = events.find((event) => (
    event.type === 'decision.required'
    && event.stage_id === stage.id
    && (stage.type !== 'text' || event.chapter_id === chapterId)
  ));
  const confirmed = events.some((event) => (
    event.type === 'artifact.committed'
    && event.stage_id === stage.id
    && (stage.type !== 'text' || event.chapter_id === chapterId)
  ));
  const targetReady = stage.type !== 'text' || Boolean(chapterId);
  const decisionEnabled = workflow.quality_mode !== 'fast';
  const canDraft = decisionEnabled && completed && !confirmed && targetReady && Boolean(pendingDecision);
  const canConfirm = decisionEnabled && completed && !confirmed && artifactReady && !confirming && Boolean(pendingDecision);
  const showDecisionBar = decisionEnabled && !confirmed;
  return (
    <>
      <StageFinalizeTray className="stage-decision-slot" open={showDecisionBar}>
        <section className={`stage-decision-bar stage-${stage.type}`}>
          <div>
            <p className="eyebrow">人工定稿</p>
            <strong>{stageDecisionTitle(stage, completed, artifactReady)}</strong>
            <span>{stageDecisionHint(stage, completed, artifactMissingLabels)}</span>
          </div>
          <div className="stage-decision-actions">
            {stage.type === 'export' ? null : (
              <button className="ghost tiny-action" disabled={!canDraft} onClick={() => setDialogOpen(true)} type="button">
                <RefreshCw size={14} />{TERM.redraft}
              </button>
            )}
            <button
              className="tech-button"
              disabled={!canConfirm}
              onClick={async () => {
                setConfirming(true);
                await onConfirmStageArtifact(stage.id);
                setConfirming(false);
              }}
              type="button"
            >
              <CheckCircle2 size={14} />{confirming ? '提交中' : stage.type === 'text' ? '确认正文定稿' : TERM.confirmFinal}
            </button>
          </div>
        </section>
      </StageFinalizeTray>
      <DraftRegenerationDialog
        mode={workflow.quality_mode}
        open={dialogOpen}
        stage={stage}
        onClose={() => setDialogOpen(false)}
        onConfirm={(direction) => {
          onRegenerateStageDraft(stage.id, direction, chapterId);
          setDialogOpen(false);
        }}
      />
    </>
  );
}

function stageDecisionTitle(stage: WorkflowStage, completed: boolean, artifactReady: boolean) {
  if (!completed) return '阶段内容生成中，暂不可定稿';
  if (!artifactReady) {
    if (stage.type === 'text') return '正文审校尚未完成';
    if (stage.type === 'cover') return '封面资产尚未就绪';
    return '阶段产物仍有必填内容待补充';
  }
  if (stage.type === 'text') return '当前章节已完成审校，可保存本章版本';
  if (stage.type === 'cover') return '正式封面已选，可进行定稿';
  if (stage.type === 'export') return '交付格式与元数据已确认，可生成正式文件';
  return '本阶段已生成，等待人工定稿';
}

function stageDecisionHint(stage: WorkflowStage, completed: boolean, missingLabels: string[]) {
  if (!completed) return '生成完成后即可换一稿或确认定稿。';
  if (missingLabels.length) {
    const visible = missingLabels.slice(0, 2).join('、');
    const remaining = missingLabels.length > 2 ? `，另 ${missingLabels.length - 2} 项` : '';
    return `请先处理：${visible}${remaining}。`;
  }
  if (stage.type === 'text') return '保存当前章节版本后继续下一章；末章完成后自动进入封面。';
  if (stage.type === 'cover') return '确认定稿后，正式封面将用于导出。';
  if (stage.type === 'export') return '确认后按已接受章节版本物化不可变交付文件。';
  return '确认定稿后自动进入下一阶段。';
}
