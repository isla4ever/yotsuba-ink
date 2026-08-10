import type { StoryBriefArtifact, OutlineArtifactVnext } from './artifactsVnext';
import type { CharacterBibleArtifact } from './characterBibleArtifact';

export type DetailObligationKind = 'character' | 'thread' | 'world_rule' | 'promise';
export type DetailObligationOption = {
  id: string;
  kind: DetailObligationKind;
  label: string;
};

export function buildDetailObligationOptions(
  story: StoryBriefArtifact | null,
  characters: CharacterBibleArtifact | null,
  outline: OutlineArtifactVnext | null,
): DetailObligationOption[] {
  const characterOptions: DetailObligationOption[] = [
    ...(characters?.characters.map((item) => ({ id: item.id, kind: 'character' as const, label: item.name })) ?? []),
    ...(characters?.npc_slots.map((item) => ({ id: item.id, kind: 'character' as const, label: `NPC: ${item.function}` })) ?? []),
  ];
  const threads = new Map<string, string>();
  outline?.volumes.forEach((volume) => volume.thread_windows.forEach((item) => {
    if (!threads.has(item.thread_id)) threads.set(item.thread_id, item.action);
  }));
  return [
    ...characterOptions,
    ...Array.from(threads).sort(([left], [right]) => left.localeCompare(right)).map(([id, label]) => ({ id, kind: 'thread' as const, label })),
    ...(story?.world_rules.map((label, index) => ({ id: `world-rule-${index + 1}`, kind: 'world_rule' as const, label })) ?? []),
    ...(story ? [
      { id: 'thematic-question', kind: 'promise' as const, label: story.thematic_question },
      { id: 'ending-promise', kind: 'promise' as const, label: story.ending_promise },
    ] : []),
  ];
}

export function detailObligationRefIds(options: DetailObligationOption[]) {
  const result: Record<DetailObligationKind, Set<string>> = {
    character: new Set(),
    thread: new Set(),
    world_rule: new Set(),
    promise: new Set(),
  };
  options.forEach((item) => result[item.kind].add(item.id));
  return result;
}
