// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { StageDecision } from "../lib/stageDecision"
import { StageCandidateActions } from "./StageCandidateActions"

const resolveDecision = vi.hoisted(() => vi.fn())

vi.mock("../services/runApi", () => ({
  resolveRunDecision: resolveDecision,
}));

(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("StageCandidateActions", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    resolveDecision.mockResolvedValue(undefined)
  })

  it("submits the edited Version 20 artifact when the author confirms it", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const onResolved = vi.fn().mockResolvedValue(undefined)
    const artifact = { subjects: [], relations: [] }
    await act(async () => {
      root.render(
        <StageCandidateActions
          acceptLabel="确认人物编排"
          artifact={artifact}
          decision={decision()}
          draftStatus="saved"
          onResolved={onResolved}
          regenerateDescription="只调整文学字段。"
          regeneratePlaceholder="请输入方向"
          regenerateTitle="定向重做人物编排"
          runId="run-1"
        />,
      )
    })

    const accept = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("确认人物编排"),
    )
    await act(async () => {
      accept?.click()
      await Promise.resolve()
    })

    expect(resolveDecision).toHaveBeenCalledWith(
      "run-1",
      "decision-1",
      "accept",
      3,
      artifact,
      undefined,
    )
    expect(onResolved).toHaveBeenCalledOnce()
    act(() => root.unmount())
  })

  it("requires an explicit direction before a regeneration request", async () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    await act(async () => {
      root.render(
        <StageCandidateActions
          acceptLabel="确认分卷架构"
          artifact={{ volumes: [] }}
          decision={decision()}
          draftStatus="clean"
          onResolved={vi.fn()}
          regenerateDescription="只调整卷合同。"
          regeneratePlaceholder="请输入方向"
          regenerateTitle="定向重做分卷架构"
          runId="run-1"
        />,
      )
    })
    const regenerate = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("定向换稿"),
    )
    act(() => regenerate?.click())

    const confirm = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("开始换稿"),
    )
    expect(confirm?.disabled).toBe(true)
    expect(resolveDecision).not.toHaveBeenCalled()

    act(() => root.unmount())
  })
})

function decision(): StageDecision {
  return {
    allowedActions: ["accept", "regenerate", "cancel"],
    artifactRef: "cast-candidate-1",
    decisionId: "decision-1",
    domainRevision: 3,
    regenerationLimit: 1,
    regenerationUsed: 0,
    stageId: "cast",
  }
}
