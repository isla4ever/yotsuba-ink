import type { ExportFormat } from "./runHistory"

export type CoverBrief = {
  concept: string
  image_prompt: string
  palette: string[]
  negative_constraints: string[]
}

export type CoverArtifact = {
  brief: CoverBrief
  selected_asset_id: string
}

export type ExportMetadata = {
  title: string
  author: string
  version_note: string
}

export type ExportVolume = {
  title: string
  chapter_count: number
}

export type ExportArtifact = {
  format: ExportFormat
  chapter_version_ids: string[]
  cover_asset_id: string
  metadata: ExportMetadata
  volumes: ExportVolume[]
}
