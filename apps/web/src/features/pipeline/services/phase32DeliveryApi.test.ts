import { afterEach, describe, expect, it, vi } from "vitest"
import { BookDeliveryApiError, getBookDelivery } from "./bookDeliveryApi"
import { getScriptDelivery, ScriptDeliveryApiError } from "./scriptDeliveryApi"

describe("phase32 delivery API errors", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("preserves deferred book dependency metadata from a 409 response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errorResponse("book_delivery")),
    )

    await expect(getBookDelivery("run-book-1")).rejects.toMatchObject({
      code: "image_deferred",
      status: 409,
      artifactType: "book_delivery",
      dependencyStatus: "deferred",
      deferredReason: "image_acceptance_not_in_current_wave",
      sourceArtifactRefs: ["p32-cover-ref"],
    } satisfies Partial<BookDeliveryApiError>)
  })

  it("preserves deferred script dependency metadata from a 409 response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(errorResponse("script_delivery")),
    )

    await expect(getScriptDelivery("run-script-1")).rejects.toMatchObject({
      code: "image_deferred",
      status: 409,
      artifactType: "script_delivery",
      dependencyStatus: "deferred",
      deferredReason: "image_acceptance_not_in_current_wave",
      sourceArtifactRefs: ["p32-cover-ref"],
    } satisfies Partial<ScriptDeliveryApiError>)
  })

  it("keeps a string detail message for a non-JSON contract error", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
        json: async () => ({ detail: "delivery backend unavailable" }),
      }))

    await expect(getBookDelivery("run-book-1")).rejects.toMatchObject({
      message: "delivery backend unavailable",
      status: 503,
      code: "",
      dependencyStatus: "",
    } satisfies Partial<BookDeliveryApiError>)
  })

  it("keeps structured code when object detail omits a display message", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
        ok: false,
        status: 409,
        json: async () => ({
          detail: {
            code: "delivery_not_materialized",
            artifact_type: "book_delivery",
            dependency_status: "blocked",
            deferred_reason: "",
            source_artifact_refs: [],
          },
        }),
      }))

    await expect(getBookDelivery("run-book-1")).rejects.toMatchObject({
      status: 409,
      code: "delivery_not_materialized",
      dependencyStatus: "blocked",
      message: expect.not.stringContaining("[object Object]"),
    } satisfies Partial<BookDeliveryApiError>)
  })
})

function errorResponse(artifactType: "book_delivery" | "script_delivery") {
  return {
    ok: false,
    status: 409,
    json: async () => ({
      detail: {
        code: "image_deferred",
        message:
          "图片验收尚未启用，当前 Run 仅完成 CoverBrief，暂不可导出成书。",
        artifact_type: artifactType,
        dependency_status: "deferred",
        deferred_reason: "image_acceptance_not_in_current_wave",
        source_artifact_refs: ["p32-cover-ref"],
      },
    }),
  }
}
