import { useMemo } from "react"
import { parsePhase32Cover, phase32CoverAssetError } from "../lib/phase32Cover"
import { useCoverAssets } from "./useCoverAssets"
import { usePhase32ArtifactDraft } from "./usePhase32ArtifactDraft"

export function usePhase32Cover(
  runId: string,
  authorityRevision: string,
  enabled: boolean,
) {
  const draft = usePhase32ArtifactDraft(
    runId,
    "cover",
    authorityRevision,
    enabled,
  )
  const assetState = useCoverAssets(runId, enabled, authorityRevision)
  const parsed = useMemo(
    () => parsePhase32Cover(draft.payload),
    [draft.payload],
  )
  const assetError = phase32CoverAssetError(parsed.artifact, assetState.assets)

  const selectAsset = (assetRef: string) => {
    if (
      !draft.current?.editable ||
      !parsed.artifact ||
      !parsed.artifact.candidates.some(
        (candidate) => candidate.asset_ref === assetRef,
      ) ||
      !assetState.assets.some((asset) => asset.asset_id === assetRef)
    )
      return
    draft.change({ ...parsed.artifact, selected_asset_ref: assetRef })
  }

  return {
    ...draft,
    artifact: parsed.artifact,
    artifactError: parsed.error,
    assetError,
    assets: assetState.assets,
    assetStatus: assetState.status,
    generationAttempt: assetState.generationAttempt,
    selectAsset,
  }
}
