import type { GraphRunEnvelope } from "../contracts/run"

export type TextDecisionAction =
  | "accept"
  | "regenerate"
  | "retry_evidence"
  | "cancel"

export type TextQualityFinding = {
  claim: string
  code: string
  evidence: string
}

export type TextQualityDecision = {
  accepted: boolean
  blockers: TextQualityFinding[]
  evidenceDegraded: boolean
  evidenceStatus: "pending" | "succeeded" | "needs_action"
  regenerationLimit: number
  regenerationUsed: number
  recommendation: string
  structureContract: "passed" | "blocked"
  warnings: TextQualityFinding[]
}

export type TextDecision = {
  allowedActions: TextDecisionAction[]
  artifactRef: string
  chapterId: string
  chapterVersionId: string
  decisionId: string
  domainRevision: number
  evidenceError: string
  kind: "author" | "evidence"
  quality: TextQualityDecision | null
}

export function textDecisionFor(
  envelope: GraphRunEnvelope | null,
  chapterId?: string,
): TextDecision | null {
  const pending = envelope?.read_model.pending_decisions.find((item) => {
    const nodeId = text(item.node_id)
    const itemChapterId = text(item.chapter_id)
    return (
      nodeId.startsWith("text.") &&
      (!chapterId || itemChapterId === chapterId)
    )
  })
  if (!pending) return null
  const type = text(pending.type)
  if (
    type !== "chapter_author_decision" &&
    type !== "evidence_recovery_decision"
  ) {
    return null
  }
  const decisionId = text(pending.decision_id)
  const domainRevision = Number(pending.domain_revision)
  const selectedChapterId = text(pending.chapter_id)
  if (
    !decisionId ||
    !selectedChapterId ||
    !Number.isInteger(domainRevision) ||
    domainRevision < 0
  ) {
    return null
  }
  return {
    allowedActions: actions(pending.allowed_actions),
    artifactRef: text(pending.artifact_ref),
    chapterId: selectedChapterId,
    chapterVersionId:
      text(pending.chapter_version_id) || text(pending.artifact_ref),
    decisionId,
    domainRevision,
    evidenceError: text(record(pending.evidence_detail)?.contract_error),
    kind: type === "chapter_author_decision" ? "author" : "evidence",
    quality: qualityDecision(pending.quality_decision),
  }
}

function qualityDecision(value: unknown): TextQualityDecision | null {
  const source = record(value)
  if (!source) return null
  const structureContract = source.structure_contract
  const evidenceStatus = source.evidence_status
  if (
    (structureContract !== "passed" && structureContract !== "blocked") ||
    (evidenceStatus !== "pending" &&
      evidenceStatus !== "succeeded" &&
      evidenceStatus !== "needs_action") ||
    typeof source.evidence_degraded !== "boolean" ||
    typeof source.accepted !== "boolean"
  ) {
    return null
  }
  return {
    accepted: source.accepted,
    blockers: findings(source.contract_blockers),
    evidenceDegraded: source.evidence_degraded,
    evidenceStatus,
    regenerationLimit: integer(source.regeneration_limit),
    regenerationUsed: integer(source.regeneration_used),
    recommendation: text(record(source.regeneration_recommendation)?.direction),
    structureContract,
    warnings: findings(source.review_warnings),
  }
}

function findings(value: unknown): TextQualityFinding[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    const finding = record(item)
    if (!finding) return []
    const code = text(finding.code)
    const claim = text(finding.claim)
    const evidence = text(finding.evidence)
    return code || claim || evidence ? [{ code, claim, evidence }] : []
  })
}

function actions(value: unknown): TextDecisionAction[] {
  if (!Array.isArray(value)) return []
  return value.filter(
    (item): item is TextDecisionAction =>
      item === "accept" ||
      item === "regenerate" ||
      item === "retry_evidence" ||
      item === "cancel",
  )
}

function record(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function text(value: unknown) {
  return typeof value === "string" ? value.trim() : ""
}

function integer(value: unknown) {
  const number = Number(value)
  return Number.isInteger(number) && number >= 0 ? number : 0
}
