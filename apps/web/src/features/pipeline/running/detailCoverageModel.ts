import { detailChapterReadiness, type DetailBaseline } from './detailArtifactModel';
import type { DetailChapter } from './detailPresentation';

export type CoverageCell = {
  completed: number;
  index: number;
  label: string;
  missingGroups: string[];
  total: number;
};

/**
 * Detail 覆盖热力条数据（Phase 10.3b）。
 * 每格 = 一章，完成数来自 `detailChapterReadiness` —— 与施工表行内 5/5 徽标、
 * Context Bar 合同完整度是同一个 Phase 8.4C 派生函数，这里不做第二套实现，
 * 因此热力条与表格数字永远一致。
 */
export function buildCoverageCells(chapters: DetailChapter[], baseline: DetailBaseline): CoverageCell[] {
  const chapterNames = chapters.map((chapter) => chapter.chapter);
  return chapters.map((chapter, index) => {
    const readiness = detailChapterReadiness(chapter, baseline, index, chapterNames);
    const label = chapter.chapter || `第 ${index + 1} 章`;
    return {
      completed: readiness.completed,
      index,
      label,
      missingGroups: readiness.missingLabels.map((item) => (item.startsWith(label) ? item.slice(label.length) : item)),
      total: readiness.total,
    };
  });
}

export function coverageCellDescription(cell: CoverageCell, legacyFinalized = false): string {
  const prefix = legacyFinalized ? `${cell.label} 新版结构覆盖` : `${cell.label} 覆盖`;
  return cell.missingGroups.length
    ? `${prefix} ${cell.completed}/${cell.total}：缺${cell.missingGroups.join('、')}`
    : `${prefix} ${cell.completed}/${cell.total}，五组检查已闭合，可施工`;
}

export function coverageSummary(cells: CoverageCell[], legacyFinalized = false): string {
  const ready = cells.filter((cell) => cell.completed === cell.total).length;
  if (legacyFinalized) return `历史稿已完成 · 新版结构覆盖 ${ready}/${cells.length}`;
  return ready === cells.length
    ? `全部 ${cells.length} 章五组检查 5/5，可进入正文施工`
    : `${ready}/${cells.length} 章可施工`;
}
