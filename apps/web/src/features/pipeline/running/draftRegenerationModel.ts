import type { WorkflowStage } from '../contracts';

type StageType = WorkflowStage['type'];

const DEFAULT_SUGGESTIONS = [
  '让结果更紧凑，减少过程性解释。',
  '增强当前阶段核心冲突。',
  '提高后续阶段可继承的结构清晰度。',
] as const;

const STAGE_SUGGESTIONS: Partial<Record<StageType, readonly [string, string, string]>> = {
  chapter_text: ['增加现场感和声纹细节，让正文更有画面。', '压缩解释段落，把信息藏进行动和对话。', '强化段尾追读，让每章结尾有明确悬念。'],
  cover_image: ['强化旧港夜雾和磁带光痕，封面更悬疑。', '降低元素数量，突出蓝潮警戒线主视觉。', '增强投稿封面识别度，标题区留白更明确。'],
  detail_outline: ['重分配事实增量：避免信息在同一章堆积。', '强化章末钩子：让每章自然进入下一章。', '提高 Wiki 清晰度：事实、伏笔、人物状态分开。'],
  info_recommend: ['强化悬疑钩子：让开篇问题更尖锐，增强追读冲动。', '增强人物关系：让主角、盟友和隐瞒者之间的张力更清楚。', '降低设定复杂度：减少解释负担，把设定转成行动线索。'],
  outline: ['重排卷内节拍：开端、发展、中点、高潮、结局更清楚。', '强化卷尾钩子：让蓝潮禁区成为明确爆点。', '减少支线干扰：保留三章投稿项主链闭环。'],
  summary: ['强化完整梗概弧线：补足开端、发展、高潮和结局承诺。', '增强人物变化：让主角选择更有代价，关系压力更清楚。', '压缩设定解释：把世界规则转成可验证物证。'],
};

export function regenerationSuggestionsForStage(stage?: Pick<WorkflowStage, 'type'>) {
  return [...(stage ? STAGE_SUGGESTIONS[stage.type] : STAGE_SUGGESTIONS.info_recommend) ?? DEFAULT_SUGGESTIONS];
}

export function resolveRegenerationDirection(selectedSuggestion: string, customDirection: string) {
  return customDirection.trim() || selectedSuggestion.trim();
}
