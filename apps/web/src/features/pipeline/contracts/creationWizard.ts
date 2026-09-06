export type CreationKind = "screenplay" | "novel"
export type NovelLengthClass = "short_novel" | "long_novel"
export type CreationRouteId = "screenplay_sample" | "short_novel" | "long_novel"

export type CreationIntentDraft = {
  creativeIntent: string
  creationKind: CreationKind
  novelLengthClass: NovelLengthClass | null
  requestedTarget: number | null
}

export type CreationRouteMeta = {
  id: CreationRouteId
  label: string
  shortLabel: string
  unit: "minutes" | "characters"
  unitLabel: string
  targetLabel: string
  minimum: number
  recommendedFloor: number
  recommended: number
  recommendedCeiling: number
  maximum: number
  rationale: string
  stages: string[]
}

export type CreationRouteStage = {
  stageId: string
  label: string
  artifactKind: string
  workbenchKind: string
  providerTaskKind: string | null
  upstreamStageIds: string[]
  unitization: "aggregate" | "bounded_units" | "sequential_units" | "deterministic"
  decisionPolicyRef: string
  contextPolicyRef: string
  collaborationEnabled: boolean
}

export type CreationWorkflowCatalogItem = {
  id: string
  routeId: CreationRouteId
  name: string
  source: "official" | "custom"
  revision: string
  workflowDigest: string
  summary: string
  available: boolean
  deliverableKind: "screenplay" | "short_novel" | "long_novel"
  stages: CreationRouteStage[]
  capabilities: string[]
  exportProfiles: string[]
  scalePolicy: {
    unit: "minutes" | "characters"
    minimum: number
    recommendedFloor: number
    recommended: number
    recommendedCeiling: number
    maximum: number
    rationale: string
  }
  reviewPolicy: {
    policyId: string
    revision: string
    checkpointPolicy: string
    warningPolicy: string
    contractCorrectionLimit: number
    directedRedraftLimitByStage: Record<string, number>
    autoContinueStages: string[]
    mandatoryDecisionStages: string[]
  }
}

export type WorkflowRouteMatch = {
  workflow: CreationWorkflowCatalogItem
  routeId: CreationRouteId
  source: "official" | "custom"
  matchReason: string
  recommended: boolean
}
