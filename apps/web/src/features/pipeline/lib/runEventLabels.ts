/** Writer-language labels for the stable Phase 26 Graph event contract. */
const runEventLabels: Record<string, string> = {
  'run.started': '创作启动',
  'run.completed': '创作完成',
  'run.failed': '运行失败',
  'node.started': '节点开始',
  'node.completed': '节点完成',
  'node.failed': '节点失败',
  'provider.delta': '内容生成中',
  'artifact.candidate_ready': '候选产物就绪',
  'artifact.committed': '产物已正式写回',
  'decision.required': '等待人工决定',
  'decision.resolved': '人工决定已确认',
  'review.started': '审稿开始',
  'review.completed': '审稿完成',
  'review.unavailable': '审稿角色不可用',
  'evidence.proposed': '证据提案已生成',
  'writeback.queued': '写回事务已排队',
  'writeback.committed': '写回事务已提交',
  'writeback.failed': '写回事务失败',
  'checkpoint.saved': '运行检查点已保存',
};

export function runEventLabel(type?: string) {
  return (type && runEventLabels[type]) || '运行事件';
}

export function runEventEntryLabel(event: { type?: string }): string {
  return runEventLabel(event.type);
}
