// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest"
import {
  applyArtifactAmendment,
  createArtifactAmendment,
  createArtifactAmendmentBranch,
  getArtifactAmendmentBranch,
  getArtifactAmendmentImpact,
} from "./artifactAmendmentApi"

describe("artifact amendment API", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("uses the five source-bound amendment endpoints and restores apply authority", async () => {
    const amendment = amendmentFixture()
    const impact = impactFixture()
    const applyReceipt = applyReceiptFixture()
    const branchReceipt = branchReceiptFixture()
    const sourceRun = runEnvelope("run-source")
    const targetRun = runEnvelope("run-target")
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ reused: false, amendment, impact }))
      .mockResolvedValueOnce(jsonResponse({ impact }))
      .mockResolvedValueOnce(
        jsonResponse({ reused: false, receipt: applyReceipt, run: sourceRun }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          apply_receipt: applyReceipt,
          receipt: null,
          target_run: null,
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({
          reused: false,
          receipt: branchReceipt,
          source_run: sourceRun,
          target_run: targetRun,
        }),
      )
    vi.stubGlobal("fetch", fetchMock)

    await createArtifactAmendment("run-source", "brief", {
      sourceArtifactRef: amendment.source_artifact_ref,
      proposedPayload: amendment.proposed_payload,
      idempotencyKey: "create-key",
      authorNote: "  收紧承诺  ",
    })
    await getArtifactAmendmentImpact("run-source", amendment.amendment_id)
    await applyArtifactAmendment("run-source", amendment.amendment_id, {
      scope: "affected_only",
      idempotencyKey: "apply-key",
    })
    await expect(
      getArtifactAmendmentBranch("run-source", amendment.amendment_id),
    ).resolves.toEqual({
      apply_receipt: applyReceipt,
      receipt: null,
      target_run: null,
    })
    await createArtifactAmendmentBranch("run-source", amendment.amendment_id, {
      applyReceiptId: applyReceipt.receipt_id,
      sourceDomainRevision: 4,
      idempotencyKey: "branch-key",
    })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      source_artifact_ref: amendment.source_artifact_ref,
      proposed_payload: amendment.proposed_payload,
      idempotency_key: "create-key",
      author_note: "收紧承诺",
    })
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      scope: "affected_only",
      idempotency_key: "apply-key",
    })
    expect(JSON.parse(fetchMock.mock.calls[4][1].body)).toEqual({
      apply_receipt_id: applyReceipt.receipt_id,
      source_domain_revision: 4,
      idempotency_key: "branch-key",
    })
    expect(JSON.parse(fetchMock.mock.calls[4][1].body)).not.toHaveProperty(
      "target_run_id",
    )
  })

  it("rejects a branch status that loses its apply receipt identity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
        jsonResponse({
          apply_receipt: applyReceiptFixture(),
          receipt: { ...branchReceiptFixture(), apply_receipt_id: "other" },
          target_run: runEnvelope("run-target"),
        }),
      ))

    await expect(
      getArtifactAmendmentBranch("run-source", amendmentFixture().amendment_id),
    ).rejects.toThrow("无法识别")
  })
})

function amendmentFixture() {
  return {
    architecture_version: "phase32-routes-v1" as const,
    amendment_id: `p32-amendment-${"a".repeat(32)}`,
    command_digest: "a".repeat(64),
    idempotency_key_digest: "b".repeat(64),
    run_id: "run-source",
    creation_route_id: "short_novel" as const,
    route_revision: "r3",
    definition_digest: "c".repeat(64),
    source_stage_id: "brief",
    artifact_kind: "novel_brief",
    source_artifact_ref: `p32-brief-committed-${"d".repeat(64)}`,
    source_payload_digest: "d".repeat(64),
    source_domain_revision: 3,
    proposed_payload: { premise: "新的故事承诺" },
    proposed_payload_digest: "e".repeat(64),
    impact_id: `p32-impact-${"f".repeat(32)}`,
    author_note: "收紧承诺",
    created_at: "2026-08-25T12:00:00+08:00",
  }
}

function impactFixture() {
  const amendment = amendmentFixture()
  return {
    architecture_version: "phase32-routes-v1" as const,
    impact_id: amendment.impact_id,
    amendment_id: amendment.amendment_id,
    run_id: amendment.run_id,
    creation_route_id: amendment.creation_route_id,
    route_revision: amendment.route_revision,
    definition_digest: amendment.definition_digest,
    source_stage_id: "brief",
    source_artifact_ref: amendment.source_artifact_ref,
    source_payload_digest: amendment.source_payload_digest,
    proposed_payload_digest: amendment.proposed_payload_digest,
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
    impact_digest: "1".repeat(64),
  }
}

function applyReceiptFixture() {
  return {
    architecture_version: "phase32-routes-v1" as const,
    receipt_id: `p32-amendment-receipt-${"2".repeat(32)}`,
    plan_id: `p32-amendment-plan-${"3".repeat(32)}`,
    run_id: "run-source",
    amendment_id: amendmentFixture().amendment_id,
    scope: "affected_only" as const,
    previous_artifact_ref: amendmentFixture().source_artifact_ref,
    committed_artifact_ref: `p32-brief-committed-${"4".repeat(64)}`,
    domain_revision_before: 3,
    domain_revision_after: 4,
    event_id: "amendment:applied",
    applied_at: "2026-08-25T12:01:00+08:00",
  }
}

function branchReceiptFixture() {
  return {
    architecture_version: "phase32-routes-v1" as const,
    receipt_id: `p32-amendment-branch-receipt-${"5".repeat(32)}`,
    plan_id: `p32-amendment-branch-plan-${"6".repeat(32)}`,
    source_run_id: "run-source",
    target_run_id: "run-target",
    project_id: "project-1",
    amendment_id: amendmentFixture().amendment_id,
    apply_receipt_id: applyReceiptFixture().receipt_id,
    source_domain_revision: 4,
    target_definition_digest: "7".repeat(64),
    frontier_stage_id: "story_map",
    imported_artifact_refs: { brief: "artifact-brief" },
    source_event_id: "source-event",
    target_event_id: "target-event",
    branched_at: "2026-08-25T12:02:00+08:00",
  }
}

function runEnvelope(runId: string) {
  const digest = "8".repeat(64)
  const manifestDigest = "9".repeat(64)
  const stage = {
    ordinal: 0,
    stage_id: "brief",
    label: "小说立项",
    artifact_kind: "novel_brief",
    workbench_kind: "novel_brief",
    provider_task_kind: "novel_brief",
    upstream_stage_ids: [],
    downstream_stage_ids: [],
    unitization: "aggregate",
    decision_policy_ref: "decision.short.brief.v1",
    context_policy_ref: "context.short.brief.v1",
    collaboration_enabled: false,
  }
  const usage = {
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
  }
  return {
    definition: {
      architecture_version: "phase32-routes-v1",
      run_id: runId,
      project_id: "project-1",
      workflow_id: "workflow-short",
      workflow_revision: "r3",
      workflow_digest: "a".repeat(64),
      route_contract: {
        architecture_version: "phase32-routes-v1",
        creation_route_id: "short_novel",
        route_revision: "r3",
        route_manifest: {
          route_id: "short_novel",
          route_revision: "r3",
          deliverable_kind: "book",
          start_stage_id: "brief",
          terminal_stage_id: "export",
          stages: [stage],
          capabilities: [],
          export_profiles: ["book"],
        },
        route_manifest_digest: manifestDigest,
      },
      scale_profile: contract("scale"),
      inputs: contract("inputs"),
      provider_bindings_by_stage: [],
      export_profile: "book",
      created_at: "2026-08-25T12:00:00+08:00",
      definition_digest: digest,
    },
    read_model: {
      run_id: runId,
      project_id: "project-1",
      thread_id: runId,
      creation_route_id: "short_novel",
      route_revision: "r3",
      route_manifest_digest: manifestDigest,
      definition_digest: digest,
      stage_manifest: [stage],
      review_policy_summary: {
        policy_id: "review.short.default",
        revision: "r1",
        checkpoint_policy: "milestone",
        warning_policy: "pause_at_milestone",
        auto_continue_stages: [],
        mandatory_decision_stages: ["brief"],
      },
      status: "created",
      active_stage_id: "brief",
      active_unit_ref: "",
      stage_status: { brief: "available" },
      artifact_refs: {},
      sequential_stage_progress: {},
      pending_decisions: [],
      active_amendment_id: "",
      stale_stage_ids: [],
      historical_frozen_stage_ids: [],
      provider_usage: usage,
      failure: null,
      checkpoint_id: "",
      updated_at: "2026-08-25T12:00:00+08:00",
    },
    summary: {
      run_id: runId,
      project_id: "project-1",
      creation_route_id: "short_novel",
      route_revision: "r3",
      route_label: "短中篇小说",
      deliverable_kind: "book",
      status: "created",
      active_stage: {
        stage_id: "brief",
        label: "小说立项",
        ordinal: 0,
        total: 1,
      },
      completed_stage_ids: [],
      progress: { completed: 0, total: 1, ratio: 0 },
      active_unit_ref: "",
      pending_decisions: [],
      provider_usage: usage,
      failure: null,
      checkpoint_id: "",
      can_branch: false,
      export_ready: false,
      created_at: "2026-08-25T12:00:00+08:00",
      updated_at: "2026-08-25T12:00:00+08:00",
    },
  }
}

function contract(id: string) {
  return {
    contract_id: id,
    contract_revision: "r1",
    payload: {},
    payload_digest: "b".repeat(64),
  }
}

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  })
}
