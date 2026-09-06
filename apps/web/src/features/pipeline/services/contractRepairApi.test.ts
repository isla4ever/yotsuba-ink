// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest"
import {
  getCurrentContractQuarantine,
  repairContractCandidate,
} from "./contractRepairApi"

describe("contract repair API", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("discovers server-selected quarantine and submits every source authority field", async () => {
    const quarantine = quarantineFixture()
    const run = runFixture()
    const decision = run.read_model.pending_decisions[0]
    const repair = {
      architecture_version: "phase32-routes-v1",
      repair_ref: `p32-contract-repair-${"8".repeat(64)}`,
      repair_id: "phase32-ui:contract-repair:test",
      run_id: run.definition.run_id,
      definition_digest: quarantine.definition_digest,
      domain_revision: quarantine.domain_revision,
      stage_id: "rolling_detail",
      provider_receipt_ref: quarantine.provider_receipt_ref,
      provider_request_signature: quarantine.provider_request_signature,
      source_payload_digest: quarantine.source_payload_digest,
      repaired_payload_digest: "9".repeat(64),
      candidate_ref: decision.artifact_ref,
      status: "succeeded",
      decision_id: decision.decision_id,
      result: { status: "awaiting_decision" },
      created_at: "2026-09-06T00:00:00Z",
      updated_at: "2026-09-06T00:00:01Z",
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ quarantine }))
      .mockResolvedValueOnce(
        jsonResponse({ reused: false, repair, run, decision }),
      )
    vi.stubGlobal("fetch", fetchMock)

    await expect(getCurrentContractQuarantine("run/one")).resolves.toEqual(
      quarantine,
    )
    const repairedPayload = { windows: [{ repaired: true }] }
    await expect(
      repairContractCandidate(run.definition.run_id, {
        repairId: repair.repair_id,
        quarantine,
        payload: repairedPayload,
      }),
    ).resolves.toMatchObject({ repair, run, decision })

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/runs/run%2Fone/contract-quarantine",
    )
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      repair_id: repair.repair_id,
      provider_receipt_ref: quarantine.provider_receipt_ref,
      provider_request_signature: quarantine.provider_request_signature,
      definition_digest: quarantine.definition_digest,
      domain_revision: quarantine.domain_revision,
      source_payload_digest: quarantine.source_payload_digest,
      payload: repairedPayload,
    })
  })

  it("rejects a success response that does not restore the repair candidate decision", async () => {
    const quarantine = quarantineFixture()
    const run = runFixture()
    const decision = run.read_model.pending_decisions[0]
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
        jsonResponse({
          reused: false,
          repair: {
            architecture_version: "phase32-routes-v1",
            repair_ref: "repair-ref",
            repair_id: "repair-id",
            run_id: run.definition.run_id,
            definition_digest: quarantine.definition_digest,
            domain_revision: quarantine.domain_revision,
            stage_id: "rolling_detail",
            provider_receipt_ref: quarantine.provider_receipt_ref,
            provider_request_signature: quarantine.provider_request_signature,
            source_payload_digest: quarantine.source_payload_digest,
            repaired_payload_digest: "9".repeat(64),
            candidate_ref: "another-candidate",
            status: "succeeded",
            decision_id: decision.decision_id,
            result: {},
            created_at: "now",
            updated_at: "now",
          },
          run,
          decision,
        }),
      ))

    await expect(
      repairContractCandidate(run.definition.run_id, {
        repairId: "repair-id",
        quarantine,
        payload: quarantine.source_payload,
      }),
    ).rejects.toThrow("无法识别")
  })

  it("restores an idempotent replay decision from the authoritative Run projection", async () => {
    const quarantine = quarantineFixture()
    const run = runFixture()
    const decision = run.read_model.pending_decisions[0]
    const repair = {
      architecture_version: "phase32-routes-v1",
      repair_ref: "repair-ref",
      repair_id: "repair-id",
      run_id: run.definition.run_id,
      definition_digest: quarantine.definition_digest,
      domain_revision: quarantine.domain_revision,
      stage_id: "rolling_detail",
      provider_receipt_ref: quarantine.provider_receipt_ref,
      provider_request_signature: quarantine.provider_request_signature,
      source_payload_digest: quarantine.source_payload_digest,
      repaired_payload_digest: "9".repeat(64),
      candidate_ref: decision.artifact_ref,
      status: "succeeded",
      decision_id: decision.decision_id,
      result: {},
      created_at: "now",
      updated_at: "now",
    }
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          jsonResponse({ reused: true, repair, run, decision: null }),
        ),
    )

    await expect(
      repairContractCandidate(run.definition.run_id, {
        repairId: "repair-id",
        quarantine,
        payload: quarantine.source_payload,
      }),
    ).resolves.toMatchObject({ reused: true, decision })
  })
})

function quarantineFixture() {
  return {
    run_id: "contract-run",
    creation_route_id: "long_novel" as const,
    stage_id: "rolling_detail",
    definition_digest: "a".repeat(64),
    domain_revision: 7,
    provider_receipt_ref: `p32-provider-operation-${"b".repeat(64)}`,
    provider_request_signature: "c".repeat(64),
    source_payload_digest: "d".repeat(64),
    source_payload: { windows: [{ repaired: false }] },
    eligible: true,
    findings: [
      {
        code: "stage_reference_contract_invalid",
        message: "chapter-01 人物范围无效",
      },
    ],
  }
}

function runFixture() {
  const runId = "contract-run"
  const definitionDigest = "a".repeat(64)
  const manifestDigest = "e".repeat(64)
  const stage = {
    ordinal: 0,
    stage_id: "rolling_detail",
    label: "滚动细纲",
    artifact_kind: "detail_plan_index",
    workbench_kind: "rolling_detail",
    provider_task_kind: "rolling_detail",
    upstream_stage_ids: [],
    downstream_stage_ids: [],
    unitization: "bounded_units",
    decision_policy_ref: "decision.long.rolling-detail.v1",
    context_policy_ref: "context.long.rolling-detail.v1",
    collaboration_enabled: true,
  }
  const decision = {
    decision_id: "decision-repaired",
    stage_id: "rolling_detail",
    unit_ref: "",
    artifact_ref: `p32-rolling-detail-candidate-${"f".repeat(64)}`,
    kind: "artifact_candidate",
    domain_revision: 8,
    allowed_actions: ["accept", "cancel"],
    redraft_limit: 1,
    redraft_used: 1,
  }
  const usage = {
    provider_operations: 9,
    returned_operations: 9,
    succeeded_operations: 7,
    contract_rejected_operations: 2,
    failed_operations: 0,
    pending_operations: 0,
    prompt_tokens: 100,
    completion_tokens: 200,
    total_tokens: 300,
    reasoning_tokens: 0,
  }
  return {
    definition: {
      architecture_version: "phase32-routes-v1",
      run_id: runId,
      project_id: "project-1",
      workflow_id: "official-long",
      workflow_revision: "r3",
      workflow_digest: "1".repeat(64),
      route_contract: {
        architecture_version: "phase32-routes-v1",
        creation_route_id: "long_novel",
        route_revision: "r3",
        route_manifest: {
          route_id: "long_novel",
          route_revision: "r3",
          deliverable_kind: "book",
          start_stage_id: "rolling_detail",
          terminal_stage_id: "rolling_detail",
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
      created_at: "2026-09-06T00:00:00Z",
      definition_digest: definitionDigest,
    },
    read_model: {
      run_id: runId,
      project_id: "project-1",
      thread_id: runId,
      creation_route_id: "long_novel",
      route_revision: "r3",
      route_manifest_digest: manifestDigest,
      definition_digest: definitionDigest,
      stage_manifest: [stage],
      review_policy_summary: {
        policy_id: "review.long",
        revision: "r1",
        checkpoint_policy: "milestone",
        warning_policy: "pause_at_milestone",
        auto_continue_stages: [],
        mandatory_decision_stages: ["rolling_detail"],
      },
      status: "awaiting_decision",
      active_stage_id: "rolling_detail",
      active_unit_ref: "",
      stage_status: { rolling_detail: "awaiting_decision" },
      artifact_refs: {},
      sequential_stage_progress: {},
      pending_decisions: [decision],
      active_amendment_id: "",
      stale_stage_ids: [],
      historical_frozen_stage_ids: [],
      provider_usage: usage,
      failure: null,
      checkpoint_id: "checkpoint-1",
      updated_at: "2026-09-06T00:00:01Z",
    },
    summary: {
      run_id: runId,
      project_id: "project-1",
      creation_route_id: "long_novel",
      route_revision: "r3",
      route_label: "长篇小说",
      deliverable_kind: "book",
      status: "awaiting_decision",
      active_stage: {
        stage_id: "rolling_detail",
        label: "滚动细纲",
        ordinal: 0,
        total: 1,
      },
      completed_stage_ids: [],
      progress: { completed: 0, total: 1, ratio: 0 },
      active_unit_ref: "",
      pending_decisions: [decision],
      provider_usage: usage,
      failure: null,
      checkpoint_id: "checkpoint-1",
      can_branch: false,
      export_ready: false,
      created_at: "2026-09-06T00:00:00Z",
      updated_at: "2026-09-06T00:00:01Z",
    },
  }
}

function contract(id: string) {
  return {
    contract_id: id,
    contract_revision: "r1",
    payload: {},
    payload_digest: "2".repeat(64),
  }
}

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  })
}
