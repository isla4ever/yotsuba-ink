// @vitest-environment happy-dom

import { act, useEffect } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import type {
  Phase32ArtifactDraft,
  Phase32CurrentArtifact,
} from "../contracts/run"
import { usePhase32ArtifactDraft } from "./usePhase32ArtifactDraft"

const mocks = vi.hoisted(() => ({
  getCurrent: vi.fn(),
  getDraft: vi.fn(),
  saveDraft: vi.fn(),
}))

type ArtifactDraftHookState = ReturnType<typeof usePhase32ArtifactDraft>

vi.mock("../services/runApi", () => ({
  getPhase32CurrentArtifact: mocks.getCurrent,
  getPhase32ArtifactDraft: mocks.getDraft,
  savePhase32ArtifactDraft: mocks.saveDraft,
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

describe("usePhase32ArtifactDraft", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getCurrent.mockResolvedValue(currentArtifact())
    mocks.getDraft.mockResolvedValue(null)
    mocks.saveDraft.mockResolvedValue(artifactDraft())
  })

  it("loads the exact decision source and flushes edits before accept", async () => {
    let latest: ArtifactDraftHookState | null = null
    const container = document.createElement("div")
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <Probe
          onValue={(value) => {
            latest = value
          }}
        />,
      )
    })
    await vi.waitFor(() => expect(requireValue(latest).status).toBe("clean"))

    const changed = {
      ...currentArtifact().payload,
      premise: "作者修改后的故事前提。",
    }
    act(() => requireValue(latest).change(changed))
    expect(requireValue(latest).status).toBe("dirty")

    let draftRef = ""
    await act(async () => {
      draftRef = await requireValue(latest).flush()
    })

    expect(draftRef).toBe(artifactDraft().draft_ref)
    expect(mocks.saveDraft).toHaveBeenCalledWith(
      "run-1",
      "decision-1",
      4,
      currentArtifact().artifact_ref,
      changed,
    )
    expect(requireValue(latest).status).toBe("saved")
    act(() => root.unmount())
  })

  it("restores an existing source-bound draft without resaving it", async () => {
    mocks.getDraft.mockResolvedValue(artifactDraft())
    let latest: ArtifactDraftHookState | null = null
    const container = document.createElement("div")
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <Probe
          onValue={(value) => {
            latest = value
          }}
        />,
      )
    })
    await vi.waitFor(() => expect(requireValue(latest).status).toBe("saved"))

    let draftRef = ""
    await act(async () => {
      draftRef = await requireValue(latest).flush()
    })
    expect(draftRef).toBe(artifactDraft().draft_ref)
    expect(mocks.saveDraft).not.toHaveBeenCalled()
    act(() => root.unmount())
  })

  it("does not request an Artifact before the read model exposes one", async () => {
    let latest: ArtifactDraftHookState | null = null
    const container = document.createElement("div")
    const root = createRoot(container)

    await act(async () => {
      root.render(
        <Probe
          enabled={false}
          onValue={(value) => {
            latest = value
          }}
        />,
      )
    })

    expect(requireValue(latest).status).toBe("empty")
    expect(mocks.getCurrent).not.toHaveBeenCalled()
    expect(mocks.getDraft).not.toHaveBeenCalled()
    act(() => root.unmount())
  })
})

function requireValue(
  value: ArtifactDraftHookState | null,
): ArtifactDraftHookState {
  if (value === null) throw new Error("Probe did not publish its hook state")
  return value
}

function Probe({
  enabled = true,
  onValue,
}: {
  enabled?: boolean
  onValue: (value: ReturnType<typeof usePhase32ArtifactDraft>) => void
}) {
  const value = usePhase32ArtifactDraft("run-1", "brief", "revision-1", enabled)
  useEffect(() => {
    onValue(value)
  }, [onValue, value])
  return null
}

function currentArtifact(): Phase32CurrentArtifact {
  return {
    run_id: "run-1",
    creation_route_id: "short_novel",
    stage_id: "brief",
    artifact_kind: "novel_brief",
    artifact_ref: `p32-brief-candidate-${"a".repeat(32)}-12345678`,
    unit_ref: "",
    status: "candidate",
    payload: { premise: "候选故事前提。" },
    payload_digest: "a".repeat(64),
    editable: true,
    pending_decision: {
      decision_id: "decision-1",
      stage_id: "brief",
      unit_ref: "",
      artifact_ref: `p32-brief-candidate-${"a".repeat(32)}-12345678`,
      kind: "route_stage_decision",
      domain_revision: 4,
      allowed_actions: ["accept", "regenerate", "cancel"],
      redraft_limit: 2,
      redraft_used: 0,
    },
  }
}

function artifactDraft(): Phase32ArtifactDraft {
  return {
    architecture_version: "phase32-routes-v1",
    draft_ref: `p32-draft-${"f".repeat(64)}`,
    run_id: "run-1",
    decision_id: "decision-1",
    domain_revision: 4,
    creation_route_id: "short_novel",
    stage_id: "brief",
    source_artifact_ref: currentArtifact().artifact_ref,
    payload: { premise: "作者修改后的故事前提。" },
    payload_digest: "f".repeat(64),
    created_at: "2026-08-23T12:00:00+08:00",
  }
}
