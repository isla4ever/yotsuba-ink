import type {
  ArtifactParseResult,
  CoverArtifactVnext,
  DetailArtifactVnext,
  StorySpineArtifact,
  VolumeArchitectureArtifact,
} from './artifactsVnext';
import type { CharacterBibleArtifact } from './characterBibleArtifact';

export type SemanticReadiness = {
  completed: number;
  missingLabels: string[];
  ready: boolean;
  total: number;
};

export type SemanticContext = {
  characterBible: CharacterBibleArtifact | null;
  coverAssetIds?: Set<string>;
  spine?: StorySpineArtifact | null;
};

export function characterBibleSemanticReadiness(artifact: CharacterBibleArtifact | null): SemanticReadiness {
  return readiness(artifact ? [] : ['有效的人物圣经']);
}

export function spineSemanticReadiness(result: ArtifactParseResult<StorySpineArtifact>): SemanticReadiness {
  return readiness(parseErrors(result));
}

export function volumeSemanticReadiness(
  result: ArtifactParseResult<VolumeArchitectureArtifact>,
  context: SemanticContext,
): SemanticReadiness {
  const errors = parseErrors(result);
  const castIds = new Set(context.characterBible?.subjects.map((item) => item.id) ?? []);
  const turnIds = new Set(context.spine?.turns.map((item) => item.id) ?? []);
  if (result.artifact && result.artifact.volumes.some((volume) => volume.cast_ids.some((id) => !castIds.has(id)))) {
    errors.push('每卷人物只能引用人物圣经中的主体');
  }
  if (result.artifact && result.artifact.volumes.some((volume) => volume.turn_refs.some((id) => !turnIds.has(id)))) {
    errors.push('每卷转折只能引用已冻结的故事脊柱');
  }
  if (result.artifact && !turnCoverageValid(result.artifact, turnIds)) {
    errors.push('分卷必须按顺序完整覆盖故事脊柱，不能重叠或漏掉转折');
  }
  return readiness(errors);
}

export function detailSemanticReadiness(
  result: ArtifactParseResult<DetailArtifactVnext>,
  context: SemanticContext,
): SemanticReadiness {
  const errors = parseErrors(result);
  const subjects = new Set(context.characterBible?.subjects.map((item) => item.id) ?? []);
  if (result.artifact && result.artifact.chapters.some((chapter) => chapter.cast_ids.some((id) => !subjects.has(id)))) {
    errors.push('本章出场人物只能引用人物圣经中的主体');
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

function turnCoverageValid(artifact: VolumeArchitectureArtifact, known: Set<string>) {
  const flattened = artifact.volumes.flatMap((volume) => volume.turn_refs);
  if (flattened.length !== known.size || new Set(flattened).size !== flattened.length) return false;
  return flattened.every((id, index) => id === `turn-${index + 1}` && known.has(id));
}

function parseErrors<T>(result: ArtifactParseResult<T>) {
  return result.artifact ? [] : [result.errors[0] ?? '有效阶段产物'];
}

function readiness(errors: string[]): SemanticReadiness {
  const missingLabels = [...new Set(errors)];
  return { completed: missingLabels.length ? 0 : 1, missingLabels, ready: !missingLabels.length, total: 1 };
}
