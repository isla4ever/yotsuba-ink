// @vitest-environment happy-dom

import { act, useState } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { Phase32CurrentArtifact } from "../contracts/run"
import { usePhase32MonitorArtifact } from "./usePhase32MonitorArtifact"

const mocks = vi.hoisted(() => ({ getCurrent: vi.fn() }))

vi.mock("../services/runApi", () => ({
  getPhase32CurrentArtifact: mocks.getCurrent,
  RunApiError: class RunApiError extends Error {
    constructor(
      message: string,
      readonly status: number,
    ) {
      super(message)
    }
  },
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("usePhase32MonitorArtifact", () => {
  it("keeps the last successful artifact visible during a silent refresh", async () => {
    mocks.getCurrent.mockResolvedValueOnce(
      currentArtifact("旧内容", "artifact-1"),
    )
    const container = document.createElement("div")
    const root = createRoot(container)
    let setRevision: ((value: string) => void) | null = null

    function Harness() {
      const [revision, updateRevision] = useState("r1")
      setRevision = updateRevision
      const state = usePhase32MonitorArtifact({
        authorityRevision: revision,
        runId: "run-1",
        stageId: "text",
        unitRef: "chapter-1",
      })
      return (
        <div>
          <span>{String(state.artifact?.payload.content ?? "empty")}</span>
          <i>{state.refreshing ? "refreshing" : "settled"}</i>
        </div>
      )
    }

    await act(async () => root.render(<Harness />))
    expect(container.textContent).toContain("旧内容settled")

    let resolveRefresh: ((value: Phase32CurrentArtifact) => void) | undefined
    mocks.getCurrent.mockReturnValueOnce(
      new Promise<Phase32CurrentArtifact>((resolve) => {
        resolveRefresh = resolve
      }),
    )
    act(() => setRevision?.("r2"))
    expect(container.textContent).toContain("旧内容refreshing")

    await act(async () => {
      resolveRefresh?.(currentArtifact("新内容", "artifact-2"))
    })
    expect(container.textContent).toContain("新内容settled")

    act(() => root.unmount())
  })
})

function currentArtifact(
  content: string,
  artifactRef: string,
): Phase32CurrentArtifact {
  return {
    artifact_kind: "chapter",
    artifact_ref: artifactRef,
    creation_route_id: "long_novel",
    editable: false,
    payload: { content, title: "第一章" },
    payload_digest: "a".repeat(64),
    pending_decision: null,
    run_id: "run-1",
    stage_id: "text",
    status: "committed",
    unit_ref: "chapter-1",
  }
}
