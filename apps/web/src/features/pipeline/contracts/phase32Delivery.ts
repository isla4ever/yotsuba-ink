export type Phase32DeliveryArtifactType = "script_delivery" | "book_delivery"

export type Phase32DeliveryDependencyStatus = "ready" | "deferred" | "blocked"

export type Phase32DeliveryEnvelopeMetadata = {
  artifactType: Phase32DeliveryArtifactType
  dependencyStatus: Phase32DeliveryDependencyStatus
  deferredReason: string
  sourceArtifactRefs: string[]
}

export type Phase32DeliveryErrorDetails = {
  code: string
  artifactType: Phase32DeliveryArtifactType | ""
  dependencyStatus: Phase32DeliveryDependencyStatus | ""
  deferredReason: string
  sourceArtifactRefs: string[]
}
