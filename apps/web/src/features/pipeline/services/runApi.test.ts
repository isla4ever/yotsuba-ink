// @vitest-environment happy-dom

import { afterEach, describe, expect, it, vi } from "vitest"
import {
  getPhase32ArtifactDraft,
  getPhase32CurrentArtifact,
  parseRunEnvelope,
  resolvePhase32RunDecision,
  RunApiError,
  savePhase32ArtifactDraft,
  startRun,
} from "./runApi"

describe("Phase 32 run API", () => {
  afterEach(() => vi.unstubAllGlobals())

  it("accepts only a route-native Phase 32 envelope", () => {
    const envelope = runEnvelope()
    expect(parseRunEnvelope(envelope, "/api/runs/run-1")).toEqual(envelope)

    expect(() =>
      parseRunEnvelope(
        {
          definition: {
            architecture_version: "phase27-vnext",
            run_id: "run-1",
          },
          read_model: {},
          summary: {},
        },
        "/api/runs/run-1",
      ),
    ).toThrow(RunApiError)
  })

  it("accepts one authoritative amendment stale projection", () => {
    const envelope = runEnvelope()
    Object.assign(envelope.read_model, {
      status: "needs_action",
      active_amendment_id: `p32-amendment-${"a".repeat(32)}`,
      stale_stage_ids: ["brief"],
      historical_frozen_stage_ids: ["brief"],
    })
    envelope.read_model.stage_status.brief = "stale"
    envelope.summary.status = "needs_action"

    expect(parseRunEnvelope(envelope, "/api/runs/run-1")).toEqual(envelope)

    Object.assign(envelope.read_model, {
      historical_frozen_stage_ids: ["unknown"],
    })
    expect(() => parseRunEnvelope(envelope, "/api/runs/run-1")).toThrow(
      RunApiError,
    )
  })

  it("accepts only the dedicated writeback recovery decision contract", () => {
    const envelope = runEnvelope()
    const readModel = envelope.read_model as unknown as {
      pending_decisions: Array<Record<string, unknown>>
      stage_status: Record<string, string>
      status: string
    }
    readModel.status = "awaiting_decision"
    readModel.stage_status.brief = "awaiting_decision"
    readModel.pending_decisions = [writebackRecoveryDecision()]
    envelope.summary.status = "awaiting_decision"

    expect(parseRunEnvelope(envelope, "/api/runs/run-1")).toEqual(envelope)

    for (const invalid of [
      { redraft_limit: 0 },
      { redraft_used: 0 },
      { domain_revision: null },
      { allowed_actions: ["retry_writeback", "cancel", "accept"] },
      { allowed_actions: ["retry_writeback", "retry_writeback", "cancel"] },
    ]) {
      readModel.pending_decisions = [
        { ...writebackRecoveryDecision(), ...invalid },
      ]
      expect(() => parseRunEnvelope(envelope, "/api/runs/run-1")).toThrow(
        RunApiError,
      )
    }
  })

  it("uses the authoritative start and decision routes", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ run: runEnvelope() }))
      .mockResolvedValueOnce(jsonResponse({ run: runEnvelope() }))
    vi.stubGlobal("fetch", fetchMock)

    await startRun("run-1")
    await resolvePhase32RunDecision("run-1", {
      decisionId: "decision-1",
      action: "regenerate",
      domainRevision: 4,
      direction: "收紧第二场的可见冲突",
    })

    expect(fetchMock).toHaveBeenNthCalledWith(1, "/api/runs/run-1/start", {
      method: "POST",
    })
    expect(fetchMock.mock.calls[1][0]).toBe("/api/runs/run-1/decisions")
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({
      action: "regenerate",
      decision_id: "decision-1",
      direction: "收紧第二场的可见冲突",
      domain_revision: 4,
    })
  })

  it("sends the canonical retry writeback decision command", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse({ run: runEnvelope() }))
    vi.stubGlobal("fetch", fetchMock)

    await resolvePhase32RunDecision("run-1", {
      decisionId: "decision-writeback-1",
      action: "retry_writeback",
      domainRevision: 8,
    })

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      action: "retry_writeback",
      decision_id: "decision-writeback-1",
      direction: "",
      domain_revision: 8,
    })
  })

  it("reads and writes source-bound Phase 32 Artifact drafts", async () => {
    const current = currentArtifact()
    const draft = artifactDraft()
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(current))
      .mockResolvedValueOnce(jsonResponse({ draft: null }))
      .mockResolvedValueOnce(jsonResponse({ draft }))
      .mockResolvedValueOnce(jsonResponse({ run: runEnvelope() }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(getPhase32CurrentArtifact("run-1", "brief")).resolves.toEqual(
      current,
    )
    await expect(
      getPhase32ArtifactDraft("run-1", "decision-1"),
    ).resolves.toBeNull()
    await expect(
      savePhase32ArtifactDraft(
        "run-1",
        "decision-1",
        4,
        current.artifact_ref,
        current.payload,
      ),
    ).resolves.toEqual(draft)
    await resolvePhase32RunDecision("run-1", {
      decisionId: "decision-1",
      action: "accept",
      domainRevision: 4,
      draftRef: draft.draft_ref,
    })

    expect(fetchMock.mock.calls[0][0]).toBe(
      "/api/runs/run-1/stages/brief/artifacts/current",
    )
    expect(JSON.parse(fetchMock.mock.calls[2][1].body)).toEqual({
      domain_revision: 4,
      payload: current.payload,
      source_artifact_ref: current.artifact_ref,
    })
    expect(JSON.parse(fetchMock.mock.calls[3][1].body).draft_ref).toBe(
      draft.draft_ref,
    )
  })

  it("reads writeback recovery only from a committed readonly Artifact", async () => {
    const current = {
      ...currentArtifact(),
      status: "committed" as const,
      editable: false,
      pending_decision: writebackRecoveryDecision(),
    }
    const fetchMock = vi
      .fn()
      .mockResolvedValueOnce(jsonResponse(current))
      .mockResolvedValueOnce(jsonResponse({ ...current, editable: true }))
    vi.stubGlobal("fetch", fetchMock)

    await expect(getPhase32CurrentArtifact("run-1", "brief")).resolves.toEqual(
      current,
    )
    await expect(getPhase32CurrentArtifact("run-1", "brief")).rejects.toThrow(
      "Artifact 接口返回了无法识别的数据",
    )
  })
})

function jsonResponse(value: unknown) {
  return new Response(JSON.stringify(value), {
    headers: { "Content-Type": "application/json" },
    status: 200,
  })
}

function runEnvelope() {
  const digest = "a".repeat(64)
  const manifestDigest = "b".repeat(64)
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
      run_id: "run-1",
      project_id: "project-1",
      workflow_id: "workflow-short",
      workflow_revision: "r1",
      workflow_digest: "c".repeat(64),
      route_contract: {
        architecture_version: "phase32-routes-v1",
        creation_route_id: "short_novel",
        route_revision: "r1",
        route_manifest: {
          route_id: "short_novel",
          route_revision: "r1",
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
      created_at: "2026-08-23T12:00:00+08:00",
      definition_digest: digest,
    },
    read_model: {
      run_id: "run-1",
      project_id: "project-1",
      thread_id: "run-1",
      creation_route_id: "short_novel",
      route_revision: "r1",
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
      updated_at: "2026-08-23T12:00:00+08:00",
    },
    summary: {
      run_id: "run-1",
      project_id: "project-1",
      creation_route_id: "short_novel",
      route_revision: "r1",
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
      created_at: "2026-08-23T12:00:00+08:00",
      updated_at: "2026-08-23T12:00:00+08:00",
    },
  }
}

function contract(id: string) {
  return {
    contract_id: id,
    contract_revision: "r1",
    payload: {},
    payload_digest: "d".repeat(64),
  }
}

function currentArtifact() {
  return {
    run_id: "run-1",
    creation_route_id: "short_novel" as const,
    stage_id: "brief",
    artifact_kind: "novel_brief",
    artifact_ref: `p32-brief-candidate-${"a".repeat(32)}-12345678`,
    unit_ref: "",
    status: "candidate" as const,
    payload: {
      premise: "一份被删除的证词改变了调查方向。",
      audience_promise: "读者会追问证词为何被删除。",
      theme_question: "真相是否值得承担公开代价？",
      world_rules: ["所有档案修改都有签名链。"],
      ending_direction: "主角公开证词并失去职位。",
      narrative_voice: "克制的限知视角",
      target_characters: 20_000,
    },
    payload_digest: "e".repeat(64),
    editable: true,
    pending_decision: {
      decision_id: "decision-1",
      stage_id: "brief",
      unit_ref: "",
      artifact_ref: `p32-brief-candidate-${"a".repeat(32)}-12345678`,
      kind: "route_stage_decision",
      domain_revision: 4,
      allowed_actions: ["accept", "regenerate", "cancel"] as const,
      redraft_limit: 2,
      redraft_used: 0,
    },
  }
}

function artifactDraft() {
  const current = currentArtifact()
  return {
    architecture_version: "phase32-routes-v1" as const,
    draft_ref: `p32-draft-${"f".repeat(64)}`,
    run_id: "run-1",
    decision_id: "decision-1",
    domain_revision: 4,
    creation_route_id: "short_novel" as const,
    stage_id: "brief",
    source_artifact_ref: current.artifact_ref,
    payload: current.payload,
    payload_digest: "f".repeat(64),
    created_at: "2026-08-23T12:00:00+08:00",
  }
}

function writebackRecoveryDecision() {
  return {
    decision_id: "decision-writeback-1",
    stage_id: "brief",
    unit_ref: "",
    artifact_ref: `p32-brief-committed-${"a".repeat(64)}`,
    kind: "writeback_recovery",
    domain_revision: 8,
    allowed_actions: ["retry_writeback", "cancel"],
    redraft_limit: null,
    redraft_used: null,
  }
}
