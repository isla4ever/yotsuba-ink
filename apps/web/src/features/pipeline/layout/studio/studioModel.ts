import type { ProjectRecord, ProjectSummary } from '../../contracts';
import { canonicalStageOrder } from '../../lib/stageRoutes';

/** Pure derivations for the Studio Shell (Phase 11.2). */

export const studioStageLabels: Record<string, string> = {
  brief: '立项',
  spine: '故事脊柱',
  cast: '人物编排',
  volumes: '分卷架构',
  detail: '细纲',
  text: '正文',
  cover: '封面',
  export: '交付',
};

export type StageDotStatus = 'completed' | 'current' | 'pending';

export type StageDot = { id: string; label: string; status: StageDotStatus };

/** Eight-stage progress dots derived from real Run read-model facts. */
export function stageProgressDots(summary: Pick<ProjectSummary, 'completed_stage_ids' | 'current_stage'> | null): StageDot[] {
  const completed = new Set(summary?.completed_stage_ids ?? []);
  const currentId = String(summary?.current_stage?.id ?? '');
  return canonicalStageOrder.map((id) => ({
    id,
    label: studioStageLabels[id] ?? id,
    status: completed.has(id) ? 'completed' : id === currentId ? 'current' : 'pending',
  }));
}

export const projectRunStatusLabels: Record<string, string> = {
  created: '已创建',
  running: '运行中',
  awaiting_decision: '待决策',
  failed: '失败',
  completed: '已完成',
  cancelled: '已取消',
};

export function runStatusLabel(status: string): string {
  return projectRunStatusLabels[status] ?? '';
}

export function relativeTimeLabel(iso: string, now = Date.now()): string {
  const time = new Date(iso).getTime();
  if (!iso || Number.isNaN(time)) return '时间未知';
  const diff = Math.max(0, now - time);
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < minute) return '刚刚';
  if (diff < hour) return `${Math.floor(diff / minute)} 分钟前`;
  if (diff < day) return `${Math.floor(diff / hour)} 小时前`;
  if (diff < 30 * day) return `${Math.floor(diff / day)} 天前`;
  return new Date(time).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' });
}

export function formatWordCount(words: number): string {
  if (!Number.isFinite(words) || words <= 0) return '0 字';
  if (words >= 10_000) return `${(words / 10_000).toFixed(1)} 万字`;
  return `${Math.round(words)} 字`;
}

export type StudioLibraryStats = {
  completedProjects: number;
  projectCount: number;
  stageCoverage: number;
  totalWords: number;
};

/** Library-level figures derived only from persisted project/run read models. */
export function studioLibraryStats(
  projects: ProjectRecord[],
  summaries: Record<string, ProjectSummary>,
): StudioLibraryStats {
  const projectSummaries = projects.map((project) => summaries[project.id] ?? null);
  const completedStages = projectSummaries.reduce(
    (total, summary) => total + stageProgressDots(summary).filter((stage) => stage.status === 'completed').length,
    0,
  );
  const totalStageSlots = projects.length * canonicalStageOrder.length;
  return {
    completedProjects: projectSummaries.filter((summary) => summary?.status === 'completed').length,
    projectCount: projects.length,
    stageCoverage: totalStageSlots ? Math.round((completedStages / totalStageSlots) * 100) : 0,
    totalWords: projectSummaries.reduce((total, summary) => total + Math.max(0, summary?.words ?? 0), 0),
  };
}

/** Ordered map with bounded concurrency for project read-model fan-out. */
export async function mapWithConcurrency<T, R>(
  items: T[],
  limit: number,
  task: (item: T, index: number) => Promise<R>,
): Promise<Array<R | null>> {
  const results: Array<R | null> = new Array(items.length).fill(null);
  let cursor = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    while (cursor < items.length) {
      const index = cursor;
      cursor += 1;
      try {
        results[index] = await task(items[index], index);
      } catch {
        results[index] = null;
      }
    }
  });
  await Promise.all(workers);
  return results;
}
