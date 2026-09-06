// @vitest-environment happy-dom

import { describe, expect, it, vi } from "vitest"
import { consumeRunEventStream } from "./runStream"

describe("Phase 32 run SSE", () => {
  it("parses route-aware events and preserves sequence order", async () => {
    const onEvents = vi.fn()
    const event = runEvent()
    const response = new Response(`id: 1\ndata: ${JSON.stringify(event)}\n\n`, {
      status: 200,
    })

    await consumeRunEventStream({ onEvents, response })

    expect(onEvents).toHaveBeenCalledOnce()
    expect(onEvents.mock.calls[0][0]).toEqual([event])
  })

  it("rejects a legacy event without route identity", async () => {
    const response = new Response(
      `data: ${JSON.stringify({ event_id: "old", sequence: 1 })}\n\n`,
      { status: 200 },
    )

    await expect(
      consumeRunEventStream({ onEvents: vi.fn(), response }),
    ).rejects.toThrow("Phase 32")
  })
})

function runEvent() {
  return {
    event_id: "event-1",
    sequence: 1,
    occurred_at: "2026-08-23T12:00:00+08:00",
    run_id: "run-1",
    thread_id: "run-1",
    creation_route_id: "short_novel",
    route_revision: "r1",
    route_manifest_digest: "a".repeat(64),
    definition_digest: "b".repeat(64),
    type: "decision.required",
    stage_id: "brief",
    unit_ref: "",
    artifact_kind: null,
    node_id: "",
    status: "running",
    payload: { decision_id: "decision-1" },
    payload_ref: "",
    checkpoint_id: "checkpoint-1",
  }
}
