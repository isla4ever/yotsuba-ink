// @vitest-environment happy-dom

import { act, createRef } from "react"
import { createRoot } from "react-dom/client"
import { beforeEach, describe, expect, it, vi } from "vitest"
import { AuthorCollaborationDock } from "./AuthorCollaborationDock"

const mocks = vi.hoisted(() => ({
  app: {} as Record<string, unknown>,
  source: vi.fn(),
}))

vi.mock("../../state/PipelineAppProvider", () => ({
  useApp: () => mocks.app,
}))

vi.mock("../../state/usePhase32CollaborationSource", () => ({
  usePhase32CollaborationSource: (input: Record<string, unknown>) =>
    mocks.source(input),
}))

vi.mock("../../state/useAuthorCollaboration", () => ({
  useAuthorCollaboration: () => ({ sourceRef: "p32-text-candidate-chapter-2" }),
}))

vi.mock("../../state/useProjectKnowledge", () => ({
  useProjectKnowledge: () => ({ documents: [] }),
}))

vi.mock("../../state/useStageSelectionCapture", () => ({
  useStageSelectionCapture: () => ({
    clearSelection: vi.fn(),
    selection: null,
  }),
}))

vi.mock("./AuthorCollaborationPanel", () => ({
  AuthorCollaborationPanel: ({
    canRevise,
    stageId,
  }: {
    canRevise: boolean
    stageId: string
  }) => (
    <aside aria-label="作者协作面板">
      {stageId}:{canRevise ? "editable" : "readonly"}
    </aside>
  ),
}))
;(globalThis as Record<string, unknown>).IS_REACT_ACT_ENVIRONMENT = true

describe("AuthorCollaborationDock Phase 32 source binding", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.source.mockReturnValue({
      artifact: {
        artifact_kind: "chapter",
        artifact_ref: "p32-text-candidate-chapter-2",
        creation_route_id: "long_novel",
        editable: true,
        payload: {
          chapter_ref: "chapter-2",
          content: "当前章节正文。",
          title: "异常封存",
        },
        payload_digest: "digest",
        pending_decision: null,
        run_id: "run-32",
        stage_id: "text",
        status: "candidate",
        unit_ref: "chapter-2",
      },
      error: "",
      loading: false,
    })
  })

  it("requests the active unit for a sequential stage", () => {
    Object.assign(
      mocks.app,
      appState("text", "chapter-2", "text", "awaiting_decision"),
    )
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <AuthorCollaborationDock
          onClose={vi.fn()}
          workbenchRef={createRef<HTMLElement>()}
        />,
      ),
    )

    expect(mocks.source).toHaveBeenCalledWith({
      enabled: true,
      runId: "run-32",
      stageId: "text",
      unitRef: "chapter-2",
    })
    expect(container.textContent).toContain("text:editable")

    act(() => root.unmount())
  })

  it("lets the backend resolve the last committed unit after the stage completes", () => {
    Object.assign(mocks.app, appState("text", "", "cover", "completed"))
    mocks.source.mockReturnValue({
      artifact: {
        artifact_kind: "chapter",
        artifact_ref: "p32-text-committed-chapter-2",
        creation_route_id: "long_novel",
        editable: false,
        payload: {
          chapter_ref: "chapter-2",
          content: "最后一章正文。",
          title: "公开听证",
        },
        payload_digest: "digest",
        pending_decision: null,
        run_id: "run-32",
        stage_id: "text",
        status: "committed",
        unit_ref: "chapter-2",
      },
      error: "",
      loading: false,
    })
    const container = document.createElement("div")
    const root = createRoot(container)
    act(() =>
      root.render(
        <AuthorCollaborationDock
          onClose={vi.fn()}
          workbenchRef={createRef<HTMLElement>()}
        />,
      ),
    )

    expect(mocks.source).toHaveBeenCalledWith({
      enabled: true,
      runId: "run-32",
      stageId: "text",
      unitRef: "",
    })
    expect(container.textContent).toContain("text:readonly")

    act(() => root.unmount())
  })
})

function appState(
  route: string,
  activeUnitRef: string,
  activeStageId: string,
  stageStatus: string,
) {
  return {
    activeProjectId: "project-32",
    activeRun: {
      definition: { run_id: "run-32" },
      read_model: {
        active_stage_id: activeStageId,
        active_unit_ref: activeUnitRef,
        stage_manifest: [
          {
            collaboration_enabled: true,
            stage_id: "text",
            unitization: "sequential_units",
          },
        ],
        stage_status: { text: stageStatus },
      },
    },
    route,
    setRoute: vi.fn(),
  }
}
