import type { WorkflowStage } from '../contracts';

type StageType = WorkflowStage['type'];

export type DecisionFinding = {
  claim: string;
  code: string;
  evidence: string;
  gate: 'blocking' | 'warning';
};

export type DecisionQualityGuidance = {
  allowedActions: string[];
  blockingFindings: DecisionFinding[];
  regenerationLimit: number;
  regenerationUsed: number;
  recommendedDirection: string;
  warningFindings: DecisionFinding[];
};

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

export function decisionQualityGuidance(payload: Record<string, unknown> | null | undefined): DecisionQualityGuidance {
  const reason = recordValue(payload?.reason);
  const blockingFindings = readFindings(reason?.blocking_findings, 'blocking');
  const warningFindings = readFindings(reason?.warning_findings, 'warning');
  const findings = blockingFindings.length ? blockingFindings : warningFindings;
  return {
    allowedActions: stringArray(payload?.allowed_actions),
    blockingFindings,
    regenerationLimit: nonNegativeInteger(payload?.regeneration_limit, 1),
    regenerationUsed: nonNegativeInteger(payload?.regeneration_used, 0),
    recommendedDirection: textValue(reason?.recommended_revision_direction) || directionFromFindings(findings),
    warningFindings,
  };
}

function directionFromFindings(findings: DecisionFinding[]) {
  if (!findings.length) return '';
  const items = findings.slice(0, 3).map((finding, index) => {
    const evidence = finding.evidence ? `；证据：${finding.evidence.slice(0, 80)}` : '';
    return `${index + 1}. ${finding.claim || finding.code || '审校问题'}${evidence}`;
  });
  return `只修复以下审校问题，不改变冻结章名、细纲场景顺序、主体职责或未点名情节：${items.join(' ')}。修改后核对本章结尾与下一章 handoff。`;
}

function readFindings(value: unknown, gate: DecisionFinding['gate']) {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    const finding = recordValue(item);
    if (!finding) return [];
    return [{
      claim: textValue(finding.claim),
      code: textValue(finding.code),
      evidence: textValue(finding.evidence),
      gate,
    }];
  });
}

function recordValue(value: unknown): Record<string, unknown> | undefined {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : undefined;
}

function stringArray(value: unknown) {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : [];
}

function nonNegativeInteger(value: unknown, fallback: number) {
  const numeric = Number(value);
  return Number.isInteger(numeric) && numeric >= 0 ? numeric : fallback;
}

function textValue(value: unknown) {
  return typeof value === 'string' ? value.trim() : '';
}
