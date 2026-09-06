// @vitest-environment happy-dom

import { act, useEffect } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type { Phase32RunEnvelope, Phase32RunEvent } from "../contracts/run"
import { useActiveRun } from "./useActiveRun"

const mocks = vi.hoisted(() => ({
  consume: vi.fn(),
  getRun: vi.fn(),
  stream: vi.fn(),
}))

vi.mock("../services/runApi", () => ({
  getRun: mocks.getRun,
  streamRunEvents: mocks.stream,
}))

vi.mock("../services/runStream", () => ({
  consumeRunEventStream: mocks.consume,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("useActiveRun", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getRun.mockResolvedValue(runEnvelope())
    mocks.stream.mockResolvedValue(new Response(null, { status: 200 }))
    mocks.consume.mockImplementation(
      async ({
        onEvents,
      }: {
        onEvents: (events: Phase32RunEvent[]) => void
      }) => {
        const event = runEvent()
        onEvents([event, event])
      },
    )
  })

  it("reads the formal run route, deduplicates cursor events, and closes at a decision frontier", async () => {
    const states: Array<ReturnType<typeof useActiveRun>> = []
    const container = document.createElement("div")
    const root = createRoot(container)

    await act(async () => {
      root.render(<Probe onValue={(value) => states.push(value)} />)
    })

    await vi.waitFor(() => {
      expect(states.at(-1)?.connection).toBe("closed")
    })

    expect(mocks.getRun).toHaveBeenCalledWith("run-1", expect.any(AbortSignal))
    expect(mocks.stream).toHaveBeenCalledWith(
      "run-1",
      expect.any(AbortSignal),
      0,
    )
    expect(states.at(-1)?.events).toHaveLength(1)
    expect(states.at(-1)?.events[0].sequence).toBe(7)

    act(() => root.unmount())
  })
})

function Probe({
  onValue,
}: {
  onValue: (value: ReturnType<typeof useActiveRun>) => void
}) {
  const value = useActiveRun("run-1")
  useEffect(() => {
    onValue(value)
  }, [onValue, value])
  return null
}

function runEnvelope() {
  return {
    read_model: {
      status: "awaiting_decision",
    },
  } as Phase32RunEnvelope
}

function runEvent() {
  return {
    event_id: "event-7",
    sequence: 7,
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
    payload: null,
    payload_ref: "",
    checkpoint_id: "checkpoint-1",
  } as Phase32RunEvent
}
