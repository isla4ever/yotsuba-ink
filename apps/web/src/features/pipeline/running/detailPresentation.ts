import type { DetailOutlineArtifact } from './stageArtifacts';

export type DetailChapter = DetailOutlineArtifact['chapters'][number];

export function detailFactSummary(chapter: DetailChapter) {
  return chapter.wiki_candidates[0]?.title || chapter.fact_reveals[0]?.fact || '事实 / Wiki 待补齐';
}

export function detailClueSummary(chapter: DetailChapter) {
  const clue = chapter.foreshadow[0];
  return clue ? `${clue.name} · ${clue.status}` : chapter.hook || '伏笔动作待补齐';
}

export function detailMemoryCounts(artifact: DetailOutlineArtifact) {
  return artifact.chapters.reduce((counts, chapter) => ({
    character: counts.character + (chapter.character_shift.character ? 1 : 0),
    clue: counts.clue + chapter.foreshadow.length,
    fact: counts.fact + chapter.fact_reveals.length + chapter.wiki_candidates.length,
  }), { character: 0, clue: 0, fact: 0 });
}
