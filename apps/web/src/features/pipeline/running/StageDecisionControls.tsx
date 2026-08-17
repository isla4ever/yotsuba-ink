import { CheckCircle2, CloudAlert, CloudUpload, LoaderCircle, RefreshCw } from 'lucide-react';
import { useState } from 'react';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { DraftRegenerationDialog } from './DraftRegenerationDialog';
import { StageFinalizeTray } from './StageFinalizeTray';
import { TERM } from '../lib/terminology';
import { isFailureDecision, pendingStageDecision } from '../lib/runDecisionProjection';
import type { StageArtifactDraftSaveStatus } from '../state/useStageArtifactDraft';
import { decisionQualityGuidance } from './draftRegenerationModel';

type DecisionProps = {
  artifactMissingLabels?: string[];
  artifactReady?: boolean;
  chapterId?: string;
  completed: boolean;
  events: RunEvent[];
  onConfirmStageArtifact: (stageId: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string, chapterId?: string) => void;
  stage: WorkflowStage;
  stageArtifactDraftError?: string;
  stageArtifactDraftStatus?: StageArtifactDraftSaveStatus;
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
  stageArtifactDraftError = '',
  stageArtifactDraftStatus = 'idle',
  workflow,
}: DecisionProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const pendingDecision = pendingStageDecision(
    events,
    stage.id,
    stage.type === 'text' ? chapterId : undefined,
  );
  const confirmed = events.some((event) => (
    event.type === 'artifact.committed'
    && event.stage_id === stage.id
    && (stage.type !== 'text' || event.chapter_id === chapterId)
  ));
  const failureDecision = isFailureDecision(pendingDecision);
  const guidance = decisionQualityGuidance(pendingDecision?.payload);
  const allowedActions = guidance.allowedActions.length
    ? new Set(guidance.allowedActions)
    : new Set(['accept', 'regenerate', 'cancel']);
  const qualityFindings = [...guidance.blockingFindings, ...guidance.warningFindings];
  const hardBlocked = guidance.blockingFindings.length > 0;
  const regenerationExhausted = !allowedActions.has('regenerate') && guidance.regenerationUsed >= guidance.regenerationLimit;
  const targetReady = stage.type !== 'text' || Boolean(chapterId);
  const decisionEnabled = workflow.quality_mode !== 'fast' || failureDecision;
  const canDraft = decisionEnabled && allowedActions.has('regenerate') && (completed || failureDecision) && !confirmed && targetReady && Boolean(pendingDecision);
  const canConfirm = decisionEnabled && allowedActions.has('accept') && !failureDecision && completed && !confirmed && artifactReady && !confirming && Boolean(pendingDecision);
  const showDecisionBar = decisionEnabled && !confirmed;
  return (
    <>
      <StageFinalizeTray className="stage-decision-slot" open={showDecisionBar}>
        <section className={`stage-decision-bar stage-${stage.type}`}>
          <div>
            <p className="eyebrow">人工定稿</p>
            <strong>{failureDecision ? '本次生成未通过阶段合同' : decisionTitle(stage, completed, artifactReady, hardBlocked, guidance.warningFindings.length)}</strong>
            <span>{failureDecision ? '失败调用与输入快照已保留；重试会沿用冻结输入并创建新的独立调用记录。' : decisionHint(stage, completed, artifactMissingLabels, guidance, regenerationExhausted)}</span>
            <DraftSaveIndicator error={stageArtifactDraftError} status={stageArtifactDraftStatus} />
          </div>
          <div className="stage-decision-actions">
            {stage.type === 'export' ? null : (
              <button
                className="ghost tiny-action"
                disabled={!canDraft}
                onClick={() => {
                  if (failureDecision) {
                    onRegenerateStageDraft(stage.id, '', chapterId);
                    return;
                  }
                  setDialogOpen(true);
                }}
                type="button"
              >
                <RefreshCw size={14} />{failureDecision ? '重试本阶段' : regenerationExhausted ? '已换稿 1/1' : qualityFindings.length ? '推荐换稿' : TERM.redraft}
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
        findings={qualityFindings}
        mode={workflow.quality_mode}
        open={dialogOpen && !failureDecision}
        stage={stage}
        recommendedDirection={guidance.recommendedDirection}
        onClose={() => setDialogOpen(false)}
        onConfirm={(direction) => {
          onRegenerateStageDraft(stage.id, direction, chapterId);
          setDialogOpen(false);
        }}
      />
    </>
  );
}

function decisionTitle(
  stage: WorkflowStage,
  completed: boolean,
  artifactReady: boolean,
  hardBlocked: boolean,
  warningCount: number,
) {
  if (hardBlocked) return '发现明确硬冲突，当前稿不可定稿';
  if (warningCount) return `审稿有 ${warningCount} 项告警，可接受或定向换稿`;
  return stageDecisionTitle(stage, completed, artifactReady);
}

function decisionHint(
  stage: WorkflowStage,
  completed: boolean,
  missingLabels: string[],
  guidance: ReturnType<typeof decisionQualityGuidance>,
  regenerationExhausted: boolean,
) {
  const finding = guidance.blockingFindings[0] ?? guidance.warningFindings[0];
  if (finding) {
    const prefix = finding.gate === 'blocking' ? '必须先处理' : '不阻塞定稿';
    const suffix = regenerationExhausted ? '；本候选已用完一次换稿机会' : '；换稿窗口已自动带入证据与修订方向';
    return `${prefix}：${finding.claim || finding.code}${suffix}。`;
  }
  return stageDecisionHint(stage, completed, missingLabels);
}

function DraftSaveIndicator({ error, status }: { error: string; status: StageArtifactDraftSaveStatus }) {
  if (status === 'idle') return null;
  const content = {
    clean: { icon: <CloudUpload size={13} />, label: '当前稿已同步' },
    dirty: { icon: <CloudAlert size={13} />, label: '未保存' },
    error: { icon: <CloudAlert size={13} />, label: error || '保存失败' },
    loading: { icon: <LoaderCircle className="spin" size={13} />, label: '读取草稿' },
    saved: { icon: <CloudUpload size={13} />, label: '已保存' },
    saving: { icon: <LoaderCircle className="spin" size={13} />, label: '保存中' },
  }[status];
  return (
    <span className={`artifact-draft-status ${status}`} role="status">
      {content.icon}{content.label}
    </span>
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
