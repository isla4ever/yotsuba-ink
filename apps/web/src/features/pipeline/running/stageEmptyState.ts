import type { StageType } from '../contracts';

/**
 * Phase 12 A2: /run/* empty states must explain the stage precondition and
 * offer an exit instead of a dead end. One writer-language sentence per stage;
 * the CTA label depends on whether a run has started yet.
 */
const stageEmptyStateHints: Record<StageType, string> = {
  info_recommend: '创作立项会在启动创作后自动生成，先回到创作规划完善故事起点。',
  summary: '全书梗概会在创作立项定稿后自动生成。',
  outline: '分卷大纲会在全书梗概定稿后自动生成。',
  detail_outline: '章节细纲会在分卷大纲定稿后自动生成。',
  chapter_text: '章节正文会在全部章节细纲完成并定稿后自动开始创作。',
  cover_image: '封面方案会在章节正文定稿后自动生成。',
  export_artifact: '导出文件会在封面定稿后自动整理生成。',
};

export function stageEmptyStateHint(type: StageType): string {
  return stageEmptyStateHints[type] ?? '当前阶段的内容会在上一阶段定稿后自动生成。';
}

export function stageEmptyStateAction(runStarted: boolean): string {
  return runStarted ? '回到创作规划' : '回到创作规划并启动';
}
