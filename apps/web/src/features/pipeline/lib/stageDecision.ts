import type { GraphRunEnvelope, NarrativeStageId } from "../contracts/run"

export type StageDecision = {
  allowedActions: Array<"accept" | "regenerate" | "cancel">
  artifactRef: string
  decisionId: string
  domainRevision: number
  regenerationLimit: number
  regenerationUsed: number
  stageId: NarrativeStageId
}

export function stageDecisionFor(
  envelope: GraphRunEnvelope | null,
  stageId: NarrativeStageId,
): StageDecision | null {
  const pending = envelope?.read_model.pending_decisions.find((item) => {
    const nodeId = typeof item.node_id === "string" ? item.node_id : ""
    return (
      item.type === "stage_artifact_decision" &&
      nodeId.split(".")[0] === stageId
    )
  })
  if (!pending) return null
  const decisionId = text(pending.decision_id)
  const artifactRef = text(pending.artifact_ref)
  const domainRevision = Number(pending.domain_revision)
  if (
    !decisionId ||
    !artifactRef ||
    !Number.isInteger(domainRevision) ||
    domainRevision < 0
  )
    return null
  const allowedActions = Array.isArray(pending.allowed_actions)
    ? pending.allowed_actions.filter(
        (action): action is StageDecision["allowedActions"][number] =>
          action === "accept" || action === "regenerate" || action === "cancel",
      )
    : []
  return {
    allowedActions,
    artifactRef,
    decisionId,
    domainRevision,
    regenerationLimit: integer(pending.regeneration_limit),
    regenerationUsed: integer(pending.regeneration_used),
    stageId,
  }
}

function text(value: unknown) {
  return typeof value === "string" ? value : ""
}

function integer(value: unknown) {
  const number = Number(value)
  return Number.isInteger(number) && number >= 0 ? number : 0
}
