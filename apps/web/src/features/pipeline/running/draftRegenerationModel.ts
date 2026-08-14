import type { WorkflowStage } from '../contracts';

type StageType = WorkflowStage['type'];

const DEFAULT_SUGGESTIONS = [
  '让结果更紧凑，减少过程性解释。',
  '增强当前阶段核心冲突。',
  '提高后续阶段可继承的结构清晰度。',
] as const;

const STAGE_SUGGESTIONS: Partial<Record<StageType, readonly [string, string, string]>> = {
  text: ['增加现场感和声纹细节，让正文更有画面。', '压缩解释段落，把信息藏进行动和对话。', '强化段尾追读，让每章结尾有明确悬念。'],
  cover: ['强化旧港夜雾和磁带光痕，封面更悬疑。', '降低元素数量，突出蓝潮警戒线主视觉。', '增强投稿封面识别度，标题区留白更明确。'],
  detail: ['重分配场景变化：避免信息在同一章堆积。', '强化章末交接：让每章自然进入下一章。', '压缩无动作说明：把设定转成选择、阻力和结果。'],
  brief: ['强化读者承诺：让作品的核心期待更明确。', '收紧世界硬规则：只保留会影响人物选择的约束。', '校准长度包络：让篇幅目标与故事野心匹配。'],
  spine: ['强化因果链：让每个转折都由前一变化触发。', '核对结局兑现：让结局回应立项阶段的读者承诺。', '控制开放问题：只保留真正服务后续卷的悬念。'],
  cast: ['消除功能重复：合并没有独立戏剧职责的人物。', '降低角色过载：拆分互相冲突的职责或弧线。', '优化首次出场：避免同一叙事窗口集中引入过多人。'],
  volumes: ['强化本卷闭合：承诺、冲突、高潮和余波要形成完整故事。', '调整自然卷界：不要把不可逆高潮切到下一卷。', '收紧卷内线程：只保留服务本卷承诺的角色和线索。'],
};

export function regenerationSuggestionsForStage(stage?: Pick<WorkflowStage, 'type'>) {
  return [...(stage ? STAGE_SUGGESTIONS[stage.type] : STAGE_SUGGESTIONS.brief) ?? DEFAULT_SUGGESTIONS];
}

export function resolveRegenerationDirection(selectedSuggestion: string, customDirection: string) {
  return customDirection.trim() || selectedSuggestion.trim();
}
