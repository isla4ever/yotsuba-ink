import type {
  CreationRouteId,
  CreationRouteStage,
  CreationWorkflowCatalogItem,
} from "../contracts/creationWizard"

const CATALOG_URL = "/api/creation-wizard/catalog"

export class CreationCatalogApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message)
    this.name = "CreationCatalogApiError"
  }
}

export async function listCreationWorkflowCatalog(
  signal?: AbortSignal,
): Promise<CreationWorkflowCatalogItem[]> {
  const response = await fetch(CATALOG_URL, { signal })
  if (!response.ok) throw await catalogApiError(response)
  const payload: unknown = await response.json()
  if (!isRecord(payload)) throw invalidCatalog()
  const workflows = payload.workflow_catalog
  const routes = payload.routes
  if (!Array.isArray(workflows) || !Array.isArray(routes))
    throw invalidCatalog()

  const routeById = new Map<CreationRouteId, ParsedRoute>()
  for (const value of routes) {
    const route = parseRoute(value)
    if (routeById.has(route.routeId)) throw invalidCatalog()
    routeById.set(route.routeId, route)
  }

  return workflows.map((value) => {
    const workflow = parseWorkflowEntry(value)
    const route = routeById.get(workflow.routeId)
    if (!route) throw invalidCatalog()
    return { ...workflow, ...route }
  })
}

type ParsedRoute = Pick<CreationWorkflowCatalogItem, "routeId" | "deliverableKind" | "stages" | "capabilities" | "exportProfiles" | "scalePolicy" | "reviewPolicy">

function parseWorkflowEntry(
  value: unknown,
): Pick<CreationWorkflowCatalogItem, "id" | "routeId" | "name" | "source" | "revision" | "workflowDigest" | "summary" | "available"> {
  if (!isRecord(value) || !isRouteId(value.route_id)) throw invalidCatalog()
  if (
    !requiredStrings(value, [
      "workflow_id",
      "label",
      "revision",
      "workflow_digest",
      "summary",
    ]) ||
    (value.source !== "official" && value.source !== "custom") ||
    typeof value.available !== "boolean"
  )
    throw invalidCatalog()
  return {
    id: value.workflow_id,
    routeId: value.route_id,
    name: value.label,
    source: value.source,
    revision: value.revision,
    workflowDigest: value.workflow_digest,
    summary: value.summary,
    available: value.available,
  }
}

function parseRoute(value: unknown): ParsedRoute {
  if (!isRecord(value) || !isRecord(value.route)) throw invalidCatalog()
  const route = value.route
  const scale = value.scale_policy
  const review = value.review_policy
  if (
    !isRecord(scale) ||
    !isRecord(review) ||
    !isRouteId(route.route_id) ||
    !isDeliverableKind(route.deliverable_kind) ||
    !Array.isArray(route.stages) ||
    !Array.isArray(route.capabilities) ||
    !Array.isArray(route.export_profiles) ||
    !route.capabilities.every(isString) ||
    !route.export_profiles.every(isString)
  )
    throw invalidCatalog()

  const unit = scale.unit
  if (
    (unit !== "minutes" && unit !== "characters") ||
    !requiredNumbers(scale, [
      "minimum",
      "recommended_floor",
      "recommended",
      "recommended_ceiling",
      "maximum",
    ]) ||
    typeof scale.rationale !== "string" ||
    !requiredStrings(review, [
      "policy_id",
      "revision",
      "checkpoint_policy",
      "warning_policy",
    ]) ||
    typeof review.contract_correction_limit !== "number" ||
    !isNumberRecord(review.directed_redraft_limit_by_stage) ||
    !Array.isArray(review.auto_continue_stages) ||
    !review.auto_continue_stages.every(isString) ||
    !Array.isArray(review.mandatory_decision_stages) ||
    !review.mandatory_decision_stages.every(isString)
  )
    throw invalidCatalog()

  return {
    routeId: route.route_id,
    deliverableKind: route.deliverable_kind,
    stages: route.stages.map(parseStage),
    capabilities: route.capabilities,
    exportProfiles: route.export_profiles,
    scalePolicy: {
      unit,
      minimum: Number(scale.minimum),
      recommendedFloor: Number(scale.recommended_floor),
      recommended: Number(scale.recommended),
      recommendedCeiling: Number(scale.recommended_ceiling),
      maximum: Number(scale.maximum),
      rationale: scale.rationale,
    },
    reviewPolicy: {
      policyId: review.policy_id,
      revision: review.revision,
      checkpointPolicy: review.checkpoint_policy,
      warningPolicy: review.warning_policy,
      contractCorrectionLimit: review.contract_correction_limit,
      directedRedraftLimitByStage: review.directed_redraft_limit_by_stage,
      autoContinueStages: review.auto_continue_stages,
      mandatoryDecisionStages: review.mandatory_decision_stages,
    },
  }
}

function parseStage(value: unknown): CreationRouteStage {
  if (
    !isRecord(value) ||
    !requiredStrings(value, [
      "stage_id",
      "label",
      "artifact_kind",
      "workbench_kind",
      "decision_policy_ref",
      "context_policy_ref",
    ]) ||
    (value.provider_task_kind !== null &&
      typeof value.provider_task_kind !== "string") ||
    !Array.isArray(value.upstream_stage_ids) ||
    !value.upstream_stage_ids.every(isString) ||
    ![
      "aggregate",
      "bounded_units",
      "sequential_units",
      "deterministic",
    ].includes(String(value.unitization)) ||
    typeof value.collaboration_enabled !== "boolean"
  )
    throw invalidCatalog()
  return {
    stageId: value.stage_id,
    label: value.label,
    artifactKind: value.artifact_kind,
    workbenchKind: value.workbench_kind,
    providerTaskKind: value.provider_task_kind,
    upstreamStageIds: value.upstream_stage_ids,
    unitization: value.unitization as CreationRouteStage["unitization"],
    decisionPolicyRef: value.decision_policy_ref,
    contextPolicyRef: value.context_policy_ref,
    collaborationEnabled: value.collaboration_enabled,
  }
}

function isRouteId(value: unknown): value is CreationRouteId {
  return (
    value === "screenplay_sample" ||
    value === "short_novel" ||
    value === "long_novel"
  )
}

function isDeliverableKind(
  value: unknown,
): value is CreationWorkflowCatalogItem["deliverableKind"] {
  return (
    value === "screenplay" || value === "short_novel" || value === "long_novel"
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function isString(value: unknown): value is string {
  return typeof value === "string"
}

function requiredStrings(
  value: Record<string, unknown>,
  keys: string[],
): value is Record<string, string> {
  return keys.every((key) => typeof value[key] === "string" && value[key])
}

function requiredNumbers(value: Record<string, unknown>, keys: string[]) {
  return keys.every((key) => typeof value[key] === "number")
}

function isNumberRecord(value: unknown): value is Record<string, number> {
  return (
    isRecord(value) &&
    Object.values(value).every((item) => typeof item === "number")
  )
}

function invalidCatalog() {
  return new CreationCatalogApiError(
    "创建目录返回了无法识别的三路线合同。",
    502,
  )
}

async function catalogApiError(response: Response) {
  let detail = ""
  try {
    const payload = (await response.json()) as { detail?: unknown }
    detail = typeof payload.detail === "string" ? payload.detail : ""
  } catch {
    detail = ""
  }
  return new CreationCatalogApiError(
    detail || `创建目录请求失败 (${response.status})`,
    response.status,
  )
}
