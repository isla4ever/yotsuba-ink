import { CheckCircle2, GitCompareArrows, History, RefreshCw, Sparkles } from 'lucide-react';
import { useState } from 'react';
import type { RunEvent, WorkflowDefinition, WorkflowStage } from '../contracts';
import { DraftRegenerationDialog } from './DraftRegenerationDialog';
import { candidatePreviewText } from './stageCandidatePreview';
import { StageFinalizeTray } from './StageFinalizeTray';
import { TERM } from '../lib/terminology';

type DecisionProps = {
  artifactMissingLabels?: string[];
  artifactReady?: boolean;
  completed: boolean;
  events: RunEvent[];
  onConfirmStageArtifact: (stageId: string) => Promise<boolean>;
  onRegenerateStageDraft: (stageId: string, direction: string) => void;
  onRequestVariantCompare: (stageId: string) => void;
  stage: WorkflowStage;
  workflow: WorkflowDefinition;
};

export function StageDecisionControls({
  artifactMissingLabels = [],
  artifactReady = true,
  completed,
  events,
  onConfirmStageArtifact,
  onRegenerateStageDraft,
  onRequestVariantCompare,
  stage,
  workflow,
}: DecisionProps) {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const confirmed = events.some((event) => event.type === 'stage_artifact_confirmed' && event.node_id === stage.id);
  const selectedDraft = events.some((event) => event.type === 'draft_candidate_selected' && event.node_id === stage.id);
  const latestDraftRequestIndex = events.findIndex((event) => event.type === 'draft_regeneration_requested' && event.node_id === stage.id);
  const latestDraftSelectedIndex = events.findIndex((event) => event.type === 'draft_candidate_selected' && event.node_id === stage.id);
  const latestDraftFailedIndex = events.findIndex((event) => event.type === 'draft_regeneration_failed' && event.node_id === stage.id);
  const draftSettled = (latestDraftSelectedIndex >= 0 && latestDraftSelectedIndex < latestDraftRequestIndex)
    || (latestDraftFailedIndex >= 0 && latestDraftFailedIndex < latestDraftRequestIndex);
  const draftGenerating = latestDraftRequestIndex >= 0 && !draftSettled;
  const variantJudging = events.some((event) => event.type === 'variant_judged' && event.node_id === stage.id)
    && !events.some((event) => event.type === 'best_variant_selected' && event.node_id === stage.id);
  const canDraft = workflow.quality_mode === 'deep' && !['info_recommend', 'export_artifact'].includes(stage.type) && completed && !confirmed && !draftGenerating && !variantJudging;
  const canConfirm = workflow.quality_mode === 'deep' && !['info_recommend', 'export_artifact'].includes(stage.type) && completed && !confirmed && !draftGenerating && !variantJudging && artifactReady && !confirming;
  const canCompare = workflow.quality_mode === 'balanced'
    && completed
    && stage.variant_policy.enabled
    && !events.some((event) => event.type === 'variant_compare_requested' && event.node_id === stage.id)
    && !events.some((event) => event.type === 'best_variant_selected' && event.node_id === stage.id);
  const showDeepControls = workflow.quality_mode === 'deep' && !['info_recommend', 'export_artifact'].includes(stage.type) && !confirmed;
  const showDecisionBar = showDeepControls || canCompare;
  return (
    <>
      <StageFinalizeTray className="stage-decision-slot" open={showDecisionBar}>
        <section className={`stage-decision-bar stage-${stage.type}`}>
          <div>
            <p className="eyebrow">{workflow.quality_mode === 'deep' ? '人工定稿' : '可选对比'}</p>
            <strong>{workflow.quality_mode === 'deep' ? stageDecisionTitle(stage, completed, draftGenerating, selectedDraft, artifactReady) : '当前产物已完成，可主动进入版本对比'}</strong>
            <span>{workflow.quality_mode === 'deep' ? stageDecisionHint(stage, completed, draftGenerating, artifactMissingLabels) : '不对比则沿用当前稿继续。'}</span>
          </div>
          <div className="stage-decision-actions">
            {canCompare ? (
              <button className="ghost tiny-action" onClick={() => onRequestVariantCompare(stage.id)} type="button">
                <GitCompareArrows size={14} />对比择优
              </button>
            ) : null}
            {workflow.quality_mode === 'deep' ? (
              <>
                <button className="ghost tiny-action" disabled={!canDraft} onClick={() => setDialogOpen(true)} type="button">
                  <RefreshCw size={14} />{TERM.redraft}
                </button>
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
                  <CheckCircle2 size={14} />{confirming ? '提交中' : stage.type === 'chapter_text' ? '确认正文定稿' : TERM.confirmFinal}
                </button>
              </>
            ) : null}
          </div>
        </section>
      </StageFinalizeTray>
      <DraftRegenerationDialog
        mode={workflow.quality_mode}
        open={dialogOpen}
        stage={stage}
        onClose={() => setDialogOpen(false)}
        onConfirm={(direction) => {
          onRegenerateStageDraft(stage.id, direction);
          setDialogOpen(false);
        }}
      />
    </>
  );
}

type VariantFocusProps = {
  events: RunEvent[];
  onSelectBalancedVariant: (stageId: string, variantId: string, modelPicked?: boolean) => void;
  stage: WorkflowStage;
};

export function BalancedVariantFocus({ events, onSelectBalancedVariant, stage }: VariantFocusProps) {
  const variants = [...events]
    .reverse()
    .filter((event) => event.type === 'variant_generated' && event.node_id === stage.id)
    .slice(0, 3);
  return (
    <section className="variant-compare-focus">
      <div className="variant-compare-head">
        <span><GitCompareArrows size={16} />版本对比</span>
        <div>
          <button className="ghost tiny-action" type="button"><History size={13} />历史</button>
          <button className="ghost tiny-action" onClick={() => onSelectBalancedVariant(stage.id, String(variants[1]?.variant && 'variant_id' in variants[1].variant ? variants[1].variant.variant_id : 'balanced-auto'), true)} type="button">
            <Sparkles size={13} />模型对比择优
          </button>
        </div>
      </div>
      <div className={`variant-compare-grid count-${Math.max(1, variants.length)}`}>
        {variants.map((event, index) => {
          const variantId = String(event.variant && 'variant_id' in event.variant ? event.variant.variant_id : `variant-${index + 1}`);
          return (
            <article key={`${event.node_id}-${variantId}`}>
              <small>版本 {index + 1}</small>
              <strong>{event.chapter ?? stage.label}</strong>
              <p>{candidatePreviewText(event.variant, event.preview).slice(0, 720)}</p>
              <button className="tech-button" onClick={() => onSelectBalancedVariant(stage.id, variantId)} type="button">
                <CheckCircle2 size={14} />选择此版
              </button>
            </article>
          );
        })}
      </div>
      <div className="variant-compare-liquid">
        <span />
        <p>仅在你主动触发时进入对比；选好一版即可继续。</p>
      </div>
    </section>
  );
}


function stageDecisionTitle(stage: WorkflowStage, completed: boolean, generating: boolean, selectedDraft: boolean, artifactReady: boolean) {
  if (!completed) return '阶段内容生成中，暂不可定稿';
  if (generating) return '候选稿生成中';
  if (!artifactReady) {
    if (stage.type === 'chapter_text') return '正文审校尚未完成';
    if (stage.type === 'cover_image') return '封面资产尚未就绪';
    return '阶段产物仍有必填内容待补充';
  }
  if (selectedDraft) return '候选已选，可确认定稿';
  if (stage.type === 'chapter_text') return '全部章节已完成审校，可进行阶段定稿';
  if (stage.type === 'cover_image') return '正式封面已选，可进行定稿';
  return '本阶段已生成，等待人工定稿';
}

function stageDecisionHint(stage: WorkflowStage, completed: boolean, generating: boolean, missingLabels: string[]) {
  if (!completed) return '生成完成后即可换一稿或确认定稿。';
  if (generating) return '先选一稿，再确认定稿。';
  if (missingLabels.length) {
    const visible = missingLabels.slice(0, 2).join('、');
    const remaining = missingLabels.length > 2 ? `，另 ${missingLabels.length - 2} 项` : '';
    return `请先处理：${visible}${remaining}。`;
  }
  if (stage.type === 'chapter_text') return '确认定稿后，已采纳提案写入正典，并进入下一阶段。';
  if (stage.type === 'cover_image') return '确认定稿后，正式封面将用于导出。';
  return '确认定稿后自动进入下一阶段。';
}
