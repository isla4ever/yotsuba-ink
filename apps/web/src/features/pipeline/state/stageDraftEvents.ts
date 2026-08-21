export const STAGE_DRAFT_UPDATED_EVENT = "yotsuba:stage-draft-updated"

export type StageDraftUpdatedDetail = {
  runId: string
  stageId: string
}

export function announceStageDraftUpdated(detail: StageDraftUpdatedDetail) {
  window.dispatchEvent(
    new CustomEvent<StageDraftUpdatedDetail>(STAGE_DRAFT_UPDATED_EVENT, {
      detail,
    }),
  )
}
