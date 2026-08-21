import { Sparkles } from "lucide-react"
import { useEffect, useMemo, useRef } from "react"
import type { RefObject } from "react"
import { useApp } from "@/features/pipeline/state/PipelineAppProvider"
import type { CollaborationStageId } from "../../contracts/authorCollaboration"
import {
  defaultCollaborationUnit,
  type CollaborationUnitScope,
} from "../../lib/authorCollaborationProjection"
import { stageDecisionFor } from "../../lib/stageDecision"
import { announceStageDraftUpdated } from "../../state/stageDraftEvents"
import { useAuthorCollaboration } from "../../state/useAuthorCollaboration"
import { useProjectKnowledge } from "../../state/useProjectKnowledge"
import { useStageSelectionCapture } from "../../state/useStageSelectionCapture"
import { AuthorCollaborationPanel } from "./AuthorCollaborationPanel"

type Props = {
  onClose: () => void
  workbenchRef: RefObject<HTMLElement | null>
}

export function AuthorCollaborationDock({ onClose, workbenchRef }: Props) {
  const handledPatchRef = useRef("")
  const {
    activeProjectId,
    activeRun,
    refreshRun,
    route,
    runArtifacts,
    runCandidateArtifacts,
    runChapters,
    selectedChapter,
    selectedChar,
    selectedVolumeId,
    setRoute,
    spineSelectedId,
  } = useApp()
  const stageId = isCollaborationStage(route) ? route : "spine"
  const source = useMemo(() => {
    if (stageId === "text") {
      const chapter =
        runChapters.find((item) => item.chapter_id === selectedChapter) ??
        runChapters.at(-1)
      return chapter
        ? {
            artifactText: JSON.stringify(chapter.artifact),
            sourceRef: chapter.version_id,
            unit: {
              label: chapter.artifact.title || chapter.chapter_id,
              unitRef: chapter.chapter_id,
            },
          }
        : null
    }
    const record = runCandidateArtifacts[stageId] ?? runArtifacts[stageId]
    if (!record) return null
    const artifactText = JSON.stringify(record.payload)
    return {
      artifactText,
      sourceRef: record.artifact_id,
      unit: activeUnit(stageId, record.payload, {
        selectedChapter,
        selectedChar,
        selectedVolumeId,
        spineSelectedId,
      }) ?? defaultCollaborationUnit(stageId, artifactText),
    }
  }, [
    route,
    runArtifacts,
    runCandidateArtifacts,
    runChapters,
    selectedChapter,
    selectedChar,
    selectedVolumeId,
    spineSelectedId,
    stageId,
  ])
  const knowledge = useProjectKnowledge(activeProjectId ?? "", true)
  const collaboration = useAuthorCollaboration({
    activeUnit: source?.unit,
    artifactText: source?.artifactText ?? "",
    enabled: Boolean(activeRun && source),
    knowledgeDocuments: knowledge.documents,
    runId: activeRun?.definition.run_id ?? "",
    sourceRef: source?.sourceRef ?? "",
    stageId,
  })
  const selection = useStageSelectionCapture({
    enabled: Boolean(activeRun && source),
    rootRef: workbenchRef,
    sourceRef: collaboration.sourceRef,
    stageId,
  })
  const canRevise = stageId === "text"
    ? activeRun?.read_model.pending_decisions.some((item) =>
        String(item.node_id ?? "").startsWith("text."),
      ) ?? false
    : Boolean(stageDecisionFor(activeRun, stageId))

  useEffect(() => {
    if (!collaboration.acceptedPatchRef || !activeRun) return
    const patchRefreshKey = `${activeRun.definition.run_id}:${stageId}:${collaboration.acceptedPatchRef}`
    if (handledPatchRef.current === patchRefreshKey) return
    handledPatchRef.current = patchRefreshKey
    announceStageDraftUpdated({
      runId: activeRun.definition.run_id,
      stageId,
    })
    void refreshRun()
    selection.clearSelection()
  }, [
    activeRun,
    collaboration.acceptedPatchRef,
    refreshRun,
    selection.clearSelection,
    stageId,
  ])

  if (!activeRun || !source) {
    return (
      <aside aria-label="作者协作" className="author-collaboration-panel collaboration-panel-loading">
        <Sparkles size={18} />
        <strong>当前阶段还没有可绑定的正式内容</strong>
        <span>等待 Artifact 或章节版本就绪后再开始协作。</span>
      </aside>
    )
  }

  return (
    <AuthorCollaborationPanel
      canRevise={canRevise}
      collaboration={collaboration}
      knowledgeDocuments={knowledge.documents}
      onClearSelection={selection.clearSelection}
      onClose={onClose}
      onOpenKnowledgeManager={() => {
        onClose()
        setRoute("knowledge")
      }}
      selection={selection.selection}
      stageId={stageId}
    />
  )
}

function activeUnit(
  stageId: CollaborationStageId,
  payload: Record<string, unknown>,
  selection: {
    selectedChapter: string
    selectedChar: string | null
    selectedVolumeId: string
    spineSelectedId: string
  },
): CollaborationUnitScope | null {
  if (stageId === "spine" && selection.spineSelectedId) {
    const item = findUnit(payload.turns, selection.spineSelectedId)
    return item
      ? { label: text(item.title) || text(item.change) || item.id, unitRef: item.id }
      : null
  }
  if (stageId === "cast" && selection.selectedChar) {
    const item = findUnit(payload.subjects, selection.selectedChar)
    return item
      ? { label: text(item.name) || item.id, unitRef: item.id }
      : null
  }
  if (stageId === "volumes" && selection.selectedVolumeId) {
    const item = findUnit(payload.volumes, selection.selectedVolumeId)
    return item
      ? { label: text(item.title) || item.id, unitRef: item.id }
      : null
  }
  if (stageId === "detail" && selection.selectedChapter) {
    const item = findUnit(payload.chapters, selection.selectedChapter)
    return item
      ? { label: text(item.title) || item.id, unitRef: item.id }
      : null
  }
  return null
}

function findUnit(value: unknown, id: string) {
  if (!Array.isArray(value)) return null
  const item = value.find(
    (candidate) =>
      candidate &&
      typeof candidate === "object" &&
      String((candidate as Record<string, unknown>).id ?? "") === id,
  )
  return item ? (item as Record<string, unknown> & { id: string }) : null
}

function text(value: unknown) {
  return typeof value === "string" ? value : ""
}

export function isCollaborationStage(value: string): value is CollaborationStageId {
  return ["spine", "cast", "volumes", "detail", "text"].includes(value)
}
