import type { StageType } from '../contracts';

/**
 * Phase 12 A2: /run/* empty states must explain the stage precondition and
 * offer an exit instead of a dead end. One writer-language sentence per stage;
 * the CTA label depends on whether a run has started yet.
 */
const stageEmptyStateHints: Record<StageType, string> = {
  info: '创作契约会在启动创作后生成，先回到创作规划完善故事起点。',
  characters: '人物圣经会在创作契约冻结后生成。',
  summary: '故事脊柱会在人物圣经冻结后生成。',
  outline: '分卷方案会在故事脊柱冻结后生成。',
  detail: '章节施工图会在分卷方案冻结后生成。',
  text: '章节正文会在章节施工图冻结后按顺序开始创作。',
  cover: '封面方案会在章节正文定稿后生成。',
  export: '导出产物会在封面资产选定后由系统整理。',
};

export function stageEmptyStateHint(type: StageType): string {
  return stageEmptyStateHints[type] ?? '当前阶段的内容会在上一阶段定稿后自动生成。';
}

export function stageEmptyStateAction(runStarted: boolean): string {
  return runStarted ? '回到创作规划' : '回到创作规划并启动';
}
