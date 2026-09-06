import { describe, expect, it } from "vitest"
import {
  parsePhase32DeliveryEnvelopeMetadata,
  readPhase32DeliveryErrorDetails,
} from "./phase32Delivery"

describe("phase32Delivery", () => {
  it("normalizes ready delivery metadata for a route-specific envelope", () => {
    expect(
      parsePhase32DeliveryEnvelopeMetadata(
        {
          artifact_type: "book_delivery",
          dependency_status: "ready",
          deferred_reason: "",
          source_artifact_refs: ["p32-export-committed-ref", "p32-text-ref"],
        },
        "book_delivery",
      ),
    ).toEqual({
      artifactType: "book_delivery",
      dependencyStatus: "ready",
      deferredReason: "",
      sourceArtifactRefs: ["p32-export-committed-ref", "p32-text-ref"],
    })
  })

  it("rejects a ready envelope without provenance refs", () => {
    expect(() =>
      parsePhase32DeliveryEnvelopeMetadata(
        {
          artifact_type: "book_delivery",
          dependency_status: "ready",
          deferred_reason: "",
          source_artifact_refs: [],
        },
        "book_delivery",
      ),
    ).toThrow("交付依赖元数据与当前交付类型不一致")
  })

  it("keeps structured dependency details from a deferred response", () => {
    expect(
      readPhase32DeliveryErrorDetails({
        code: "image_deferred",
        artifact_type: "book_delivery",
        dependency_status: "deferred",
        deferred_reason: "image_acceptance_not_in_current_wave",
        source_artifact_refs: ["p32-cover-ref", "", 42],
      }),
    ).toEqual({
      code: "image_deferred",
      artifactType: "book_delivery",
      dependencyStatus: "deferred",
      deferredReason: "image_acceptance_not_in_current_wave",
      sourceArtifactRefs: ["p32-cover-ref"],
    })
  })

  it("rejects an unknown dependency status", () => {
    expect(() =>
      parsePhase32DeliveryEnvelopeMetadata(
        {
          artifact_type: "book_delivery",
          dependency_status: "pending",
          deferred_reason: "",
          source_artifact_refs: ["p32-export-committed-ref"],
        },
        "book_delivery",
      ),
    ).toThrow("交付依赖元数据与当前交付类型不一致")
  })
})
