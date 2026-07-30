import type { OutlineCharacterProgression, OutlineWorldReveal } from './stageArtifacts';

export function saveCharacterProgression(
  entries: OutlineCharacterProgression[],
  item: OutlineCharacterProgression,
) {
  return replaceOrAppend(
    entries,
    item,
    (entry) => relationKey(entry.character, entry.related_to) === relationKey(item.character, item.related_to),
  );
}

export function saveWorldReveal(entries: OutlineWorldReveal[], item: OutlineWorldReveal) {
  return replaceOrAppend(entries, item, (entry) => entry.anchor === item.anchor);
}

function replaceOrAppend<T>(entries: T[], item: T, matches: (entry: T) => boolean) {
  const index = entries.findIndex(matches);
  if (index < 0) return [...entries, item];
  return entries.map((entry, entryIndex) => (entryIndex === index ? item : entry));
}

function relationKey(left: string, right: string) {
  return [left.trim(), right.trim()].sort().join('::');
}
