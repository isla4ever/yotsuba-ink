import type { ArtifactParseResult, CoverArtifactVnext, DetailArtifactVnext, OutlineArtifactVnext, SummaryArtifactVnext } from './artifactsVnext';
import type { CharacterBibleArtifact } from './characterBibleArtifact';
import type { DetailObligationKind } from './detailObligationRegistry';

export type SemanticReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

type SemanticContext = {
  characterBible: CharacterBibleArtifact | null;
  coverAssetIds?: Set<string>;
  obligationRefIds?: Record<DetailObligationKind, Set<string>>;
  requireFrozenScale?: boolean;
  totalChapters?: number;
};

export function characterBibleSemanticReadiness(
  artifact: CharacterBibleArtifact | null,
  context: SemanticContext,
): SemanticReadiness {
  const errors: string[] = [];
  if (!artifact) errors.push('有效的人物圣经');
  if (artifact && !artifact.characters.some((item) => item.tier === 'protagonist')) errors.push('至少一名主角');
  if (context.requireFrozenScale && !context.totalChapters) errors.push('冻结体量计划');
  if (artifact && context.totalChapters && appearanceEnds(artifact).some((end) => end > context.totalChapters!)) {
    errors.push('首次出现窗口必须位于全书章节范围内');
  }
  return readiness(errors);
}

export function summarySemanticReadiness(
  result: ArtifactParseResult<SummaryArtifactVnext>,
  context: SemanticContext,
): SemanticReadiness {
  const errors = parseErrors(result);
  const known = characterIds(context.characterBible);
  if (result.artifact && result.artifact.character_outcomes.some((item) => !known.has(item.character_id))) {
    errors.push('人物结局只能引用人物圣经');
  }
  const required = new Set(
    context.characterBible?.characters
      .filter((item) => item.tier === 'protagonist' || item.tier === 'major')
      .map((item) => item.id) ?? [],
  );
  if (result.artifact && [...required].some((id) => !result.artifact?.character_outcomes.some((item) => item.character_id === id))) {
    errors.push('主角与重要配角必须完成结局对账');
  }
  return readiness(errors);
}

export function outlineSemanticReadiness(
  result: ArtifactParseResult<OutlineArtifactVnext>,
  context: SemanticContext,
): SemanticReadiness {
  const errors = parseErrors(result);
  const known = characterIds(context.characterBible);
  if (result.artifact && result.artifact.volumes.some((volume) => volume.character_windows.some((item) => !known.has(item.character_id)))) {
    errors.push('人物窗口只能引用人物圣经');
  }
  if (result.artifact && !outlineStructureValid(result.artifact)) {
    errors.push('分卷、转折与线索窗口必须连续且引用有效');
  }
  if (context.requireFrozenScale && !context.totalChapters) errors.push('冻结体量计划');
  if (result.artifact && context.totalChapters && outlineEnd(result.artifact) !== context.totalChapters) {
    errors.push(`分卷范围必须精确覆盖 1-${context.totalChapters} 章`);
  }
  return readiness(errors);
}

export function detailSemanticReadiness(
  result: ArtifactParseResult<DetailArtifactVnext>,
  context: SemanticContext,
): SemanticReadiness {
  const errors = parseErrors(result);
  const characters = characterIds(context.characterBible);
  const registered = new Set([...characters, ...(context.characterBible?.npc_slots.map((item) => item.id) ?? [])]);
  if (result.artifact && result.artifact.chapters.some((chapter) => !characters.has(chapter.pov_character_id))) {
    errors.push('POV 只能引用正式角色');
  }
  if (result.artifact && result.artifact.chapters.some((chapter) => chapter.obligations.some((item) => item.kind === 'character' && !registered.has(item.ref_id)))) {
    errors.push('人物义务只能引用正式角色或冻结 NPC 槽位');
  }
  if (result.artifact && context.obligationRefIds && result.artifact.chapters.some((chapter) => (
    chapter.obligations.some((item) => !context.obligationRefIds?.[item.kind].has(item.ref_id))
  ))) {
    errors.push('章节义务只能引用冻结的上游职责');
  }
  if (result.artifact && !detailStructureValid(result.artifact)) {
    errors.push('章节编号、ID 与场景 ID 必须连续且唯一');
  }
  if (context.requireFrozenScale && !context.totalChapters) errors.push('冻结体量计划');
  if (result.artifact && context.totalChapters && result.artifact.chapters.length !== context.totalChapters) {
    errors.push(`施工图必须精确覆盖 ${context.totalChapters} 章`);
  }
  return readiness(errors);
}

export function coverSemanticReadiness(
  result: ArtifactParseResult<CoverArtifactVnext>,
  context: SemanticContext,
): SemanticReadiness {
  const errors = parseErrors(result);
  const selected = result.artifact?.selected_asset_id ?? '';
  if (!selected) errors.push('正式封面候选');
  else if (!context.coverAssetIds?.has(selected)) errors.push('正式封面必须来自当前不可变候选');
  return readiness(errors);
}

function appearanceEnds(artifact: CharacterBibleArtifact) {
  return [...artifact.characters, ...artifact.npc_slots].map((item) => chapterWindowEnd(item.first_appearance_window));
}

function characterIds(artifact: CharacterBibleArtifact | null) {
  return new Set(artifact?.characters.map((item) => item.id) ?? []);
}

function outlineEnd(artifact: OutlineArtifactVnext) {
  const finalVolume = artifact.volumes[artifact.volumes.length - 1];
  return finalVolume ? chapterWindowEnd(finalVolume.chapter_window) : 0;
}

function outlineStructureValid(artifact: OutlineArtifactVnext) {
  let expectedStart = 1;
  const volumeIds = new Set<string>();
  for (const volume of artifact.volumes) {
    const bounds = chapterWindowBounds(volume.chapter_window);
    if (!bounds || bounds.start !== expectedStart || volumeIds.has(volume.id)) return false;
    volumeIds.add(volume.id);
    expectedStart = bounds.end + 1;
    const turnIds = volume.turns.map((item) => item.id);
    const knownTurns = new Set(turnIds);
    if (knownTurns.size !== turnIds.length) return false;
    const characterIds = volume.character_windows.map((item) => item.character_id);
    if (new Set(characterIds).size !== characterIds.length) return false;
    if (volume.character_windows.some((item) => !knownTurns.has(item.turn_id))) return false;
    if (volume.thread_windows.some((item) => {
      const thread = chapterWindowBounds(item.chapter_window);
      return !thread || thread.start < bounds.start || thread.end > bounds.end;
    })) return false;
  }
  return true;
}

function detailStructureValid(artifact: DetailArtifactVnext) {
  const ids = new Set<string>();
  return artifact.chapters.every((chapter, index) => {
    const number = index + 1;
    if (chapter.number !== number || chapter.id !== `chapter-${number}` || ids.has(chapter.id)) return false;
    ids.add(chapter.id);
    const sceneIds = chapter.scenes.map((item) => item.id);
    return new Set(sceneIds).size === sceneIds.length;
  });
}

function chapterWindowEnd(value: string) {
  return chapterWindowBounds(value)?.end ?? 0;
}

function chapterWindowBounds(value: string) {
  const match = /^chapter:([1-9]\d*)(?:-([1-9]\d*))?$/.exec(value);
  if (!match) return null;
  const start = Number(match[1]);
  const end = Number(match[2] ?? match[1]);
  return end >= start ? { end, start } : null;
}

function parseErrors<T>(result: ArtifactParseResult<T>) {
  return result.artifact ? [] : [result.errors[0] ?? '有效阶段产物'];
}

function readiness(missingLabels: string[]): SemanticReadiness {
  return { completed: missingLabels.length ? 0 : 1, missingLabels, ready: missingLabels.length === 0, total: 1 };
}
