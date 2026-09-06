// @vitest-environment happy-dom

import { act } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type {
  Phase32CurrentArtifact,
  Phase32RunEnvelope,
} from "../contracts/run"
import {
  type ArtifactAmendmentController,
  useArtifactAmendment,
} from "./useArtifactAmendment"

const api = vi.hoisted(() => ({
  apply: vi.fn(),
  branch: vi.fn(),
  create: vi.fn(),
  getBranch: vi.fn(),
  getImpact: vi.fn(),
}))

vi.mock("../services/artifactAmendmentApi", () => ({
  applyArtifactAmendment: api.apply,
  createArtifactAmendment: api.create,
  createArtifactAmendmentBranch: api.branch,
  getArtifactAmendmentBranch: api.getBranch,
  getArtifactAmendmentImpact: api.getImpact,
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("useArtifactAmendment", () => {
  beforeEach(() => vi.clearAllMocks())

  it("runs one committed Artifact through impact, apply and successor", async () => {
    const fixture = flowFixture()
    api.create.mockResolvedValue({
      reused: false,
      amendment: fixture.amendment,
      impact: fixture.impact,
    })
    api.apply.mockResolvedValue({
      reused: false,
      receipt: fixture.applyReceipt,
      run: fixture.sourceRun,
    })
    api.branch.mockResolvedValue({
      reused: false,
      apply_receipt: null,
      receipt: fixture.branchReceipt,
      source_run: fixture.sourceRun,
      target_run: fixture.targetRun,
    })
    const refreshed = vi.fn()
    const harness = renderHook({
      run: fixture.sourceRun,
      current: fixture.current,
      onSourceRunChanged: refreshed,
    })

    expect(harness.value.canStart).toBe(true)
    act(() => harness.value.begin())
    expect(harness.value.phase).toBe("editing")
    act(() =>
      harness.value.change({
        premise: "修订后的故事承诺",
        target_characters: 20_000,
      }),
    )
    expect(harness.value.hasChanges).toBe(true)
    act(() => harness.value.openReview())
    await act(async () => {
      await harness.value.preview()
    })
    expect(harness.value.phase).toBe("impact")
    expect(harness.value.impact?.stale[0].stage_id).toBe("story_map")

    await act(async () => {
      await harness.value.apply()
    })
    expect(harness.value.phase).toBe("applied")
    expect(refreshed).toHaveBeenCalledOnce()

    await act(async () => {
      await harness.value.branch()
    })
    expect(harness.value.phase).toBe("successor")
    expect(harness.value.targetRun?.definition.run_id).toBe("run-target")
    expect(api.branch.mock.calls[0][2]).toMatchObject({
      applyReceiptId: fixture.applyReceipt.receipt_id,
      sourceDomainRevision: 4,
    })

    harness.unmount()
  })

  it("restores an applied or completed successor from server authority", async () => {
    const fixture = flowFixture()
    const staleRun = {
      ...fixture.sourceRun,
      read_model: {
        ...fixture.sourceRun.read_model,
        status: "needs_action",
        active_amendment_id: fixture.amendment.amendment_id,
        stale_stage_ids: ["story_map"],
        historical_frozen_stage_ids: [],
        stage_status: { brief: "completed", story_map: "stale" },
      },
    } as Phase32RunEnvelope
    api.getImpact.mockResolvedValue(fixture.impact)
    api.getBranch.mockResolvedValue({
      apply_receipt: fixture.applyReceipt,
      receipt: fixture.branchReceipt,
      target_run: fixture.targetRun,
    })
    const harness = renderHook({ run: staleRun, current: fixture.current })

    await eventually(() => harness.value.phase === "successor")
    expect(api.getImpact).toHaveBeenCalledWith(
      "run-source",
      fixture.amendment.amendment_id,
      expect.any(AbortSignal),
    )
    expect(harness.value.branchReceipt?.frontier_stage_id).toBe("story_map")

    harness.unmount()
  })
})

function renderHook(options: {
  run: Phase32RunEnvelope
  current: Phase32CurrentArtifact
  onSourceRunChanged?: () => unknown
}) {
  const container = document.createElement("div")
  const root = createRoot(container)
  let value: ArtifactAmendmentController = null as never

  function Probe() {
    value = useArtifactAmendment({
      ...options,
      stageId: "brief",
    })
    return null
  }

  act(() => root.render(<Probe />))
  return {
    get value() {
      return value
    },
    unmount() {
      act(() => root.unmount())
    },
  }
}

async function eventually(predicate: () => boolean) {
  for (let attempt = 0; attempt < 20; attempt += 1) {
    await act(async () => Promise.resolve())
    if (predicate()) return
  }
  throw new Error("condition did not settle")
}

function flowFixture() {
  const sourceRun = runEnvelope("run-source")
  const targetRun = runEnvelope("run-target")
  const amendmentId = `p32-amendment-${"a".repeat(32)}`
  const impactId = `p32-impact-${"b".repeat(32)}`
  const sourceRef = `p32-brief-committed-${"c".repeat(64)}`
  const amendment = {
    architecture_version: "phase32-routes-v1" as const,
    amendment_id: amendmentId,
    command_digest: "d".repeat(64),
    idempotency_key_digest: "e".repeat(64),
    run_id: "run-source",
    creation_route_id: "short_novel" as const,
    route_revision: "r3",
    definition_digest: "f".repeat(64),
    source_stage_id: "brief",
    artifact_kind: "novel_brief",
    source_artifact_ref: sourceRef,
    source_payload_digest: "1".repeat(64),
    source_domain_revision: 3,
    proposed_payload: {
      premise: "修订后的故事承诺",
      target_characters: 20_000,
    },
    proposed_payload_digest: "2".repeat(64),
    impact_id: impactId,
    author_note: "",
    created_at: "2026-08-25T12:00:00+08:00",
  }
  const impact = {
    architecture_version: "phase32-routes-v1" as const,
    impact_id: impactId,
    amendment_id: amendmentId,
    run_id: "run-source",
    creation_route_id: "short_novel" as const,
    route_revision: "r3",
    definition_digest: "f".repeat(64),
    source_stage_id: "brief",
    source_artifact_ref: sourceRef,
    source_payload_digest: "1".repeat(64),
    proposed_payload_digest: "2".repeat(64),
    source_domain_revision: 3,
    preserved: [],
    stale: [
      {
        stage_id: "story_map",
        artifact_kind: "story_map",
        artifact_ref: "artifact-story-map",
        unit_ref: "",
        reason: "depends_on_source_stage",
      },
    ],
    historical_frozen: [],
    blocked_references: [],
    affected_only_scope: ["story_map"],
    restart_from_stage_scope: ["story_map"],
    impact_digest: "3".repeat(64),
  }
  const applyReceipt = {
    architecture_version: "phase32-routes-v1" as const,
    receipt_id: `p32-amendment-receipt-${"4".repeat(32)}`,
    plan_id: `p32-amendment-plan-${"5".repeat(32)}`,
    run_id: "run-source",
    amendment_id: amendmentId,
    scope: "affected_only" as const,
    previous_artifact_ref: sourceRef,
    committed_artifact_ref: `p32-brief-committed-${"6".repeat(64)}`,
    domain_revision_before: 3,
    domain_revision_after: 4,
    event_id: "amendment:applied",
    applied_at: "2026-08-25T12:01:00+08:00",
  }
  const branchReceipt = {
    architecture_version: "phase32-routes-v1" as const,
    receipt_id: `p32-amendment-branch-receipt-${"7".repeat(32)}`,
    plan_id: `p32-amendment-branch-plan-${"8".repeat(32)}`,
    source_run_id: "run-source",
    target_run_id: "run-target",
    project_id: "project-1",
    amendment_id: amendmentId,
    apply_receipt_id: applyReceipt.receipt_id,
    source_domain_revision: 4,
    target_definition_digest: "9".repeat(64),
    frontier_stage_id: "story_map",
    imported_artifact_refs: { brief: sourceRef },
    source_event_id: "source-event",
    target_event_id: "target-event",
    branched_at: "2026-08-25T12:02:00+08:00",
  }
  const current = {
    run_id: "run-source",
    creation_route_id: "short_novel" as const,
    stage_id: "brief",
    artifact_kind: "novel_brief",
    artifact_ref: sourceRef,
    unit_ref: "",
    status: "committed" as const,
    payload: { premise: "原始故事承诺", target_characters: 20_000 },
    payload_digest: "1".repeat(64),
    editable: false,
    pending_decision: null,
  }
  return {
    amendment,
    applyReceipt,
    branchReceipt,
    current,
    impact,
    sourceRun,
    targetRun,
  }
}

function runEnvelope(runId: string) {
  return {
    definition: { run_id: runId },
    read_model: {
      status: "completed",
      active_amendment_id: "",
      pending_decisions: [],
      updated_at: "2026-08-25T12:00:00+08:00",
    },
  } as unknown as Phase32RunEnvelope
}
