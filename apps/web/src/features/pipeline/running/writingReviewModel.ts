import type {
  ChapterQualityRepairTarget,
  ChapterWritebackProposal,
  QualityFinding,
} from '../contracts';
import type { WritingChapter } from './writingArtifactModel';

export type WritingReviewStepState = 'done' | 'active' | 'blocked' | 'pending';

export type WritingReviewStep = {
  id: 'draft' | 'summary' | 'quality' | 'writeback';
  label: string;
  state: WritingReviewStepState;
};

export type WritingFindingView = {
  finding: QualityFinding;
  target: ChapterQualityRepairTarget | null;
};

export type WritingProposalEntry = {
  detail: string;
  id: string;
  kind: 'wiki' | 'character' | 'foreshadow';
  label: string;
  meta: string;
};

const DIMENSION_LABELS: Record<string, string> = {
  chapter_handoff: '章节承接',
  character_consistency: '人物一致性',
  foreshadowing: '伏笔推进',
  language: '语言质感',
  structure: '叙事结构',
  world_consistency: '世界观一致性',
};

export function writingReviewSteps(chapter: WritingChapter): WritingReviewStep[] {
  const proposal = chapter.writeback_proposal;
  const qualityPassed = chapter.quality_recheck?.status === 'passed'
    || Boolean(proposal && proposal.status !== 'blocked');
  const qualityBlocked = chapter.quality_recheck?.status === 'blocked' || proposal?.status === 'blocked';
  const proposalDone = proposal?.status === 'accepted'
    || proposal?.status === 'rejected'
    || proposal?.status === 'not_required';
  return [
    { id: 'draft', label: '正文', state: chapter.status === 'completed' && Boolean(chapter.content.trim()) ? 'done' : 'active' },
    { id: 'summary', label: '摘要', state: chapter.summary_dirty ? 'active' : chapter.summary.trim() ? 'done' : 'pending' },
    { id: 'quality', label: '复检', state: qualityBlocked ? 'blocked' : qualityPassed ? 'done' : chapter.summary_dirty ? 'pending' : 'active' },
    { id: 'writeback', label: '写回', state: qualityBlocked ? 'blocked' : proposalDone ? 'done' : proposal?.status === 'pending' ? 'active' : 'pending' },
  ];
}

export function writingQualityFindings(chapter: WritingChapter): WritingFindingView[] {
  const recheck = chapter.quality_recheck;
  return (recheck?.report.findings ?? []).map((finding) => ({
    finding,
    target: recheck?.repair_targets?.find((item) => item.finding_id === finding.id) ?? null,
  }));
}

export function writingQualityScore(chapter: WritingChapter) {
  const score = Number(chapter.quality_recheck?.report.score ?? chapter.quality_report.score);
  return Number.isFinite(score) ? score : null;
}

export function writingReviewDefaultTab(chapter: WritingChapter): 'quality' | 'writeback' {
  if (chapter.summary_dirty || chapter.quality_recheck?.status === 'blocked') return 'quality';
  return chapter.writeback_proposal ? 'writeback' : 'quality';
}

export function writingProposalEntries(proposal: ChapterWritebackProposal | null): WritingProposalEntry[] {
  if (!proposal) return [];
  const wiki = proposal.wiki_writebacks.map((item, index) => ({
    id: `wiki-${index}-${text(item.target, '未命名事实')}`,
    kind: 'wiki' as const,
    label: text(item.target, '未命名事实'),
    detail: text(item.fact, '事实内容待补充'),
    meta: text(item.claim_key, '事实候选'),
  }));
  const characterRecord = record(proposal.character_shift);
  const character = characterRecord && Object.keys(characterRecord).length ? [{
    id: `character-${text(characterRecord.character, '人物变化')}`,
    kind: 'character' as const,
    label: text(characterRecord.character, '人物变化'),
    detail: text(characterRecord.change ?? characterRecord.status ?? characterRecord.motivation, '人物状态发生变化'),
    meta: [characterRecord.related_to, characterRecord.relation].filter(Boolean).map(String).join(' · ') || '人物关系网',
  }] : [];
  const foreshadow = proposal.foreshadow_updates.map((item, index) => ({
    id: `foreshadow-${index}-${text(item.name, '未命名线索')}`,
    kind: 'foreshadow' as const,
    label: text(item.name, '未命名线索'),
    detail: text(item.note, '伏笔状态更新'),
    meta: text(item.status, '待处理'),
  }));
  return [...wiki, ...character, ...foreshadow];
}

export function qualityDimensionLabel(dimension: string) {
  return DIMENSION_LABELS[dimension] ?? '综合质量';
}

export function proposalStatusText(status: ChapterWritebackProposal['status']) {
  return {
    pending: '等待本章决策',
    accepted: '已采纳，定稿后写入正典',
    rejected: '已拒绝，不写入正典',
    blocked: '质量复检未通过',
    not_required: '当前版本没有需要写回的内容',
  }[status];
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : null;
}

function text(value: unknown, fallback: string) {
  return typeof value === 'string' && value.trim() ? value.trim() : fallback;
}
