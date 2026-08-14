import type { CharacterGraph, RunEvent, WorkflowDefinition } from '../../contracts';
import { parseStoryBriefArtifact } from '../artifactsVnext';
import { latestApprovedArtifact, latestResult } from '../stageRunUtils';
import { runtimeArtifactProjection } from '../runtimeArtifactProjection';

const sourceStageLabels: Record<string, string> = {
  brief: '创作立项',
  spine: '故事脊柱',
  cast: '人物编排',
  volumes: '分卷架构',
  detail: '章节施工图',
  text: '正文定稿',
};

export function bibleSourceStageLabel(nodeId: string) {
  return sourceStageLabels[nodeId] ?? nodeId;
}

function stageArtifactValue(events: RunEvent[], stageId: string) {
  return latestApprovedArtifact(events, stageId) || latestResult(events, stageId);
}

export type BibleGraphSource = 'committed' | 'derived' | 'empty';

export function bibleCharacterGraph(
  events: RunEvent[],
  workflow: WorkflowDefinition,
): { graph: CharacterGraph; source: BibleGraphSource } {
  void workflow;
  const graph = runtimeArtifactProjection({
    activeStageType: 'cast',
    brief: stageArtifactValue(events, 'brief'),
    cast: stageArtifactValue(events, 'cast'),
    detail: '',
    events,
    spine: '',
    volumes: '',
  }).characterGraph;
  return graph
    ? { graph, source: 'committed' }
    : { graph: { edges: [], nodes: [], updated_by: '' }, source: 'empty' };
}

export type BibleWorldRule = { text: string; source: string };
export type BibleWorldAnchor = { anchor: string; reveal: string; rule: string; source: string };
export type BibleWorldView = { rules: BibleWorldRule[]; anchors: BibleWorldAnchor[] };

export function bibleWorldView(events: RunEvent[]): BibleWorldView {
  const brief = parseStoryBriefArtifact(stageArtifactValue(events, 'brief')).artifact;
  const rules = (brief?.world_rules ?? []).map((text) => ({ source: '创作立项 Artifact', text }));
  return { anchors: [], rules };
}

export type ForeshadowStatus = '投放' | '推进' | '回收' | '延后';

export type BibleForeshadowRow = {
  key: string;
  name: string;
  status: ForeshadowStatus;
  chapterRange: string;
  note: string;
  source: string;
  open: boolean;
};

export function bibleForeshadowRows(events: RunEvent[]): BibleForeshadowRow[] {
  return events.filter((event) => event.type === 'evidence.proposed' && event.payload?.kind === 'foreshadow').map((event, index) => ({
    chapterRange: event.chapter_id,
    key: event.event_id || `evidence-${index}`,
    name: String(event.payload?.subject_ref ?? event.payload_ref),
    note: String(event.payload?.claim ?? ''),
    open: true,
    source: 'Evidence proposal',
    status: '推进',
  }));
}

export type BibleCanonStatus = 'active' | 'superseded' | 'pending';

export type BibleCanonRow = {
  key: string;
  target: string;
  claim: string;
  status: BibleCanonStatus;
  chapter: string;
  detail: string;
};

export function bibleCanonRows(events: RunEvent[]): BibleCanonRow[] {
  return events
    .filter((event) => ['writeback.queued', 'writeback.committed', 'writeback.failed'].includes(event.type))
    .map((event, index) => {
      const transactionId = typeof event.payload?.transaction_id === 'string'
        ? event.payload.transaction_id
        : event.payload_ref || '';
      const evidenceCount = Number(event.payload?.evidence_count ?? 0);
      return {
        chapter: event.chapter_id || '',
        claim: event.type === 'writeback.committed' ? 'Canon / Wiki 事务已提交' : event.type === 'writeback.queued' ? 'Canon / Wiki 事务排队中' : 'Canon / Wiki 事务失败',
        detail: evidenceCount > 0 ? `${evidenceCount} 条证据提案` : '',
        key: event.event_id || `writeback-${index}`,
        status: event.type === 'writeback.committed' ? 'active' : 'pending',
        target: transactionId,
      } satisfies BibleCanonRow;
    });
}
