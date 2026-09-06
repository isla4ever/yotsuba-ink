// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { describe, expect, it, vi } from "vitest"
import type { Phase32RunEnvelope, Phase32RunEvent } from "../../contracts/run"
import { Phase32RunMonitorInspector } from "./Phase32RunMonitorInspector"
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("Phase32RunMonitorInspector", () => {
  it("keeps the complete bounded formal event log behind an explicit view", () => {
    const container = document.createElement("div")
    const root = createRoot(container)
    const returnFocusRef = { current: document.createElement("button") }

    act(() => {
      root.render(
        <Phase32RunMonitorInspector
          connection="closed"
          events={Array.from({ length: 8 }, (_, index) => runEvent(index + 1))}
          onClose={vi.fn()}
          open={false}
          returnFocusRef={returnFocusRef}
          run={runEnvelope()}
        />,
      )
    })

    expect(container.textContent).toContain("运行状态")
    expect(container.textContent).toContain("完整日志")
    const logsButton = Array.from(container.querySelectorAll("button")).find(
      (button) => button.textContent?.includes("完整日志"),
    )
    act(() => logsButton?.click())

    expect(container.textContent).toContain("最近 8/8 条")
    expect(container.textContent).toContain("artifact-8")
    expect(container.textContent).toContain("artifact-1")
    expect(container.textContent?.indexOf("artifact-8")).toBeLessThan(
      container.textContent?.indexOf("artifact-1") ?? 0,
    )

    act(() => root.unmount())
  })

  it("returns focus before a drawer close can pan the viewport", () => {
    const container = document.createElement("div")
    const trigger = document.createElement("button")
    const root = createRoot(container)
    const onClose = vi.fn()
    document.body.append(trigger, container)

    act(() => {
      root.render(
        <Phase32RunMonitorInspector
          connection="closed"
          events={[]}
          onClose={onClose}
          open
          returnFocusRef={{ current: trigger }}
          run={runEnvelope()}
        />,
      )
    })

    const closeButton = container.querySelector<HTMLButtonElement>(
      ".phase32-monitor-inspector-close",
    )
    expect(document.activeElement).toBe(closeButton)

    act(() => closeButton?.click())

    expect(onClose).toHaveBeenCalledOnce()
    expect(document.activeElement).toBe(trigger)

    act(() => root.unmount())
    container.remove()
    trigger.remove()
  })
})

function runEnvelope() {
  return {
    read_model: {
      status: "awaiting_decision",
      updated_at: "2026-08-23T12:00:00+08:00",
      checkpoint_id: "checkpoint-1",
      definition_digest: "a".repeat(64),
      pending_decisions: [],
      stage_manifest: [
        {
          stage_id: "story_map",
          label: "故事地图",
        },
      ],
      failure: null,
      provider_usage: {
        provider_operations: 0,
        returned_operations: 0,
        succeeded_operations: 0,
        contract_rejected_operations: 0,
        failed_operations: 0,
        pending_operations: 0,
        prompt_tokens: 0,
        completion_tokens: 0,
        total_tokens: 0,
        reasoning_tokens: 0,
        estimated_cost_usd: null,
        cost_status: "unknown",
        balance_status: "unknown",
        by_provider: [],
      },
    },
    summary: {
      route_revision: "r2",
      route_label: "短中篇小说",
    },
  } as unknown as Phase32RunEnvelope
}

function runEvent(sequence: number) {
  return {
    event_id: `event-${sequence}`,
    sequence,
    occurred_at: `2026-08-23T12:00:0${sequence}+08:00`,
    run_id: "run-1",
    thread_id: "run-1",
    creation_route_id: "short_novel",
    route_revision: "r2",
    route_manifest_digest: "b".repeat(64),
    definition_digest: "a".repeat(64),
    type: "candidate.created",
    stage_id: "story_map",
    unit_ref: "",
    artifact_kind: "story_map",
    node_id: "story_map.generate",
    status: "running",
    payload: { artifact_ref: `artifact-${sequence}` },
    payload_ref: "",
    checkpoint_id: "checkpoint-1",
  } as Phase32RunEvent
}
