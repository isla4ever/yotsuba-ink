/**
 * Phase 12 C1: writer-language labels for run event types.
 * Raw event names (chapter_pipeline_step_completed, canon_facts_committed, ...)
 * must never reach creators; anything unmapped falls back to the generic
 * 「运行事件」 instead of leaking the internal type name.
 */
const runEventLabels: Record<string, string> = {
  approval_required: '等待人工定稿',
  artifact_approved: '产物已定稿',
  artifact_stream_delta: '内容生成中',
  artifact_validated: '结构检查通过',
  artifact_validation_failed: '结构检查未通过',
  asset_progress_updated: '素材进度更新',
  best_variant_selected: '最佳候选已选定',
  brief_regenerated: '立项草稿已更新',
  canon_facts_committed: '正典事实写回',
  chapter_completed: '章节完成',
  chapter_context_built: '章节上下文就绪',
  chapter_delta: '正文写入中',
  chapter_pipeline_step_completed: '章节工序完成',
  chapter_progress_updated: '章节进度更新',
  chapter_started: '章节开始',
  chapter_summary_synced: '章节摘要同步',
  chapter_version_restored: '章节版本恢复',
  chapter_writeback_proposal_generated: '章节写回提案',
  character_graph_updated: '人物关系更新',
  continuity_conflict_found: '连续性冲突提示',
  draft_candidate_generated: '候选稿生成',
  draft_candidate_selected: '候选稿已选',
  manual_intervention_required: '需要人工处理',
  memory_context_loaded: '事实层读取',
  memory_writeback_completed: '事实层写回',
  node_completed: '阶段完成',
  node_failed: '阶段失败',
  node_started: '阶段开始',
  provider_attempt_failed: 'AI 服务调用失败',
  provider_attempt_started: 'AI 服务调用中',
  provider_attempt_succeeded: 'AI 服务调用成功',
  provider_fallback_blocked: '备用服务不可用',
  provider_fallback_scheduled: '已切换备用服务',
  quality_check_completed: '质量检查完成',
  quality_check_started: '质量检查开始',
  quality_recheck_completed: '质量复检完成',
  revision_applied: '修订完成',
  revision_directive_created: '修订指令生成',
  run_completed: '创作完成',
  run_error: '运行出错',
  run_failed: '运行失败',
  run_paused: '已暂停',
  run_resumed: '已继续',
  run_started: '创作启动',
  stage_artifact_confirmed: '阶段定稿',
  stage_checkpoint_ready: '阶段检查点',
  stage_summary_ready: '阶段结算就绪',
  stage_usage_finalized: '用量结算',
  stage_usage_updated: '用量更新',
  story_bible_updated: '故事档案更新',
  variant_generated: '候选版本生成',
  worldbuilding_updated: '世界观更新',
};

export function runEventLabel(type?: string) {
  return (type && runEventLabels[type]) || '运行事件';
}

/**
 * Phase 12 D9: event-aware writer-language entry — provider retry/fallback
 * events surface with the attempt count (「AI 服务重试中（第 2 次）」) instead
 * of internal event names.
 */
export function runEventEntryLabel(event: { type?: string; attempt?: number }): string {
  const attempt = Number(event.attempt ?? 0);
  if (event.type === 'provider_attempt_started' && attempt > 1) return `AI 服务重试中（第 ${attempt} 次）`;
  if (event.type === 'provider_attempt_failed' && attempt > 0) return `AI 服务调用失败（第 ${attempt} 次）`;
  return runEventLabel(event.type);
}
