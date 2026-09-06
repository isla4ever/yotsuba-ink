import type {
  Phase32DeliveryArtifactType,
  Phase32DeliveryDependencyStatus,
  Phase32DeliveryEnvelopeMetadata,
  Phase32DeliveryErrorDetails,
} from "../contracts/phase32Delivery"

const ARTIFACT_TYPES = new Set<Phase32DeliveryArtifactType>([
  "script_delivery",
  "book_delivery",
])
const DEPENDENCY_STATUSES = new Set<Phase32DeliveryDependencyStatus>([
  "ready",
  "deferred",
  "blocked",
])

export function parsePhase32DeliveryEnvelopeMetadata(
  value: Record<string, unknown>,
  expectedArtifactType: Phase32DeliveryArtifactType,
): Phase32DeliveryEnvelopeMetadata {
  const artifactType = value.artifact_type
  const dependencyStatus = value.dependency_status
  const deferredReason = value.deferred_reason
  const sourceArtifactRefs = value.source_artifact_refs
  if (
    artifactType !== expectedArtifactType ||
    !isArtifactType(artifactType) ||
    dependencyStatus !== "ready" ||
    !isDependencyStatus(dependencyStatus) ||
    deferredReason !== "" ||
    !Array.isArray(sourceArtifactRefs) ||
    sourceArtifactRefs.length === 0 ||
    sourceArtifactRefs.some(
      (ref) => typeof ref !== "string" || ref.trim().length === 0,
    )
  )
    throw new Error("交付依赖元数据与当前交付类型不一致")
  return {
    artifactType,
    dependencyStatus,
    deferredReason,
    sourceArtifactRefs: sourceArtifactRefs.map((ref) => String(ref)),
  }
}

export function readPhase32DeliveryErrorDetails(
  detail: unknown,
): Phase32DeliveryErrorDetails {
  if (!isRecord(detail))
    return {
      code: "",
      artifactType: "",
      dependencyStatus: "",
      deferredReason: "",
      sourceArtifactRefs: [],
    }
  const artifactType = isArtifactType(detail.artifact_type)
    ? detail.artifact_type
    : ""
  const dependencyStatus = isDependencyStatus(detail.dependency_status)
    ? detail.dependency_status
    : ""
  const sourceArtifactRefs = Array.isArray(detail.source_artifact_refs)
    ? detail.source_artifact_refs.filter(
        (ref): ref is string =>
          typeof ref === "string" && ref.trim().length > 0,
      )
    : []
  return {
    code: stringValue(detail.code),
    artifactType,
    dependencyStatus,
    deferredReason: stringValue(detail.deferred_reason),
    sourceArtifactRefs,
  }
}

function isArtifactType(value: unknown): value is Phase32DeliveryArtifactType {
  return (
    typeof value === "string" &&
    ARTIFACT_TYPES.has(value as Phase32DeliveryArtifactType)
  )
}

function isDependencyStatus(
  value: unknown,
): value is Phase32DeliveryDependencyStatus {
  return (
    typeof value === "string" &&
    DEPENDENCY_STATUSES.has(value as Phase32DeliveryDependencyStatus)
  )
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value)
}

function stringValue(value: unknown) {
  return typeof value === "string" ? value : ""
}
