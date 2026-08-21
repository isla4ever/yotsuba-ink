import type {
  CharacterBibleArtifact,
  VolumeContract,
  VolumeLengthHint,
} from "../contracts/artifacts"

const LENGTH_LABELS: Record<VolumeLengthHint, string> = {
  short: "紧凑卷",
  medium: "标准卷",
  long: "长卷",
}

export function volumeLengthLabel(value: VolumeLengthHint) {
  return LENGTH_LABELS[value]
}

export function volumeTurnRange(volume: VolumeContract) {
  if (volume.turn_refs.length === 1)
    return volume.turn_refs[0].replace("turn-", "T")
  return `${volume.turn_refs[0].replace("turn-", "T")} - ${volume.turn_refs.at(-1)?.replace("turn-", "T")}`
}

export function volumeCastNames(
  volume: VolumeContract,
  cast: CharacterBibleArtifact | null,
) {
  const names = new Map(
    cast?.subjects.map((subject) => [subject.id, subject.name]) ?? [],
  )
  return volume.cast_ids.map((id) => ({ id, name: names.get(id) ?? id }))
}

export function detailChapterCounts(value: unknown) {
  if (!isRecord(value) || !Array.isArray(value.chapters))
    return new Map<string, number>()
  const counts = new Map<string, number>()
  value.chapters.forEach((chapter) => {
    if (!isRecord(chapter) || typeof chapter.volume_ref !== "string") return
    counts.set(chapter.volume_ref, (counts.get(chapter.volume_ref) ?? 0) + 1)
  })
  return counts
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}
