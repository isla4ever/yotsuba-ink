// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest"
import { listRunHistory } from "./runHistoryApi"

describe("Phase 32 run history API", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("lists dynamic route summaries from the formal run collection", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        new Response(
          JSON.stringify({ items: [historyItem()], next_cursor: "" }),
          { status: 200 },
        ),
      )
    vi.stubGlobal("fetch", fetchMock)

    const response = await listRunHistory({ limit: 20, status: "running" })

    expect(fetchMock.mock.calls[0][0]).toBe("/api/runs?limit=20&status=running")
    expect(response.items[0].route_label).toBe("短中篇小说")
    expect(response.items[0].provider_usage.total_tokens).toBe(300)
    expect(response.items[0]).not.toHaveProperty("quality_mode")
  })
})

function historyItem() {
  const usage = {
    provider_operations: 2,
    returned_operations: 2,
    succeeded_operations: 2,
    contract_rejected_operations: 0,
    failed_operations: 0,
    pending_operations: 0,
    prompt_tokens: 200,
    completion_tokens: 100,
    total_tokens: 300,
    reasoning_tokens: 0,
    estimated_cost_usd: 0.001,
    cost_status: "known",
    balance_status: "unknown",
    by_provider: [],
  }
  return {
    run_id: "run-1",
    project_id: "project-1",
    creation_route_id: "short_novel",
    route_revision: "r1",
    route_label: "短中篇小说",
    deliverable_kind: "book",
    status: "running",
    active_stage: {
      stage_id: "story_map",
      label: "故事地图",
      ordinal: 1,
      total: 7,
    },
    completed_stage_ids: ["brief"],
    progress: { completed: 1, total: 7, ratio: 1 / 7 },
    active_unit_ref: "",
    pending_decisions: [],
    provider_usage: usage,
    failure: null,
    checkpoint_id: "checkpoint-1",
    can_branch: false,
    export_ready: false,
    created_at: "2026-08-23T12:00:00+08:00",
    updated_at: "2026-08-23T12:05:00+08:00",
  }
}
