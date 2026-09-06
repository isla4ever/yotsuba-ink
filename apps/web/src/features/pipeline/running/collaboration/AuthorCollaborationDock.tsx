import { AlertCircle, Sparkles } from "lucide-react"
import { useMemo } from "react"
import type { ReactNode, RefObject } from "react"
import { useApp } from "@/features/pipeline/state/PipelineAppProvider"
import {
  defaultCollaborationUnit,
  isCollaborationStageId,
  type CollaborationUnitScope,
} from "../../lib/authorCollaborationProjection"
import { useAuthorCollaboration } from "../../state/useAuthorCollaboration"
import { usePhase32CollaborationSource } from "../../state/usePhase32CollaborationSource"
import { useProjectKnowledge } from "../../state/useProjectKnowledge"
import { useStageSelectionCapture } from "../../state/useStageSelectionCapture"
import { AuthorCollaborationPanel } from "./AuthorCollaborationPanel"

type Props = {
  onClose: () => void
  workbenchRef: RefObject<HTMLElement | null>
}

export function AuthorCollaborationDock({ onClose, workbenchRef }: Props) {
  const { activeProjectId, activeRun, route, setRoute } = useApp()
  const stageId = isCollaborationStageId(route) ? route : null
  const stage = activeRun?.read_model.stage_manifest.find(
    (item) => item.stage_id === stageId,
  )
  const enabled = Boolean(
    activeRun &&
      stageId &&
      stage?.collaboration_enabled &&
      activeRun.read_model.stage_status[stageId] !== "locked",
  )
  const activeUnitRef =
    stage?.unitization === "sequential_units" &&
    activeRun?.read_model.active_stage_id === stageId
      ? activeRun.read_model.active_unit_ref
      : ""
  const source = usePhase32CollaborationSource({
    enabled,
    runId: activeRun?.definition.run_id ?? "",
    stageId: stageId ?? "",
    unitRef: activeUnitRef,
  })
  const artifactText = useMemo(
    () => (source.artifact ? JSON.stringify(source.artifact.payload) : ""),
    [source.artifact],
  )
  const activeUnit = useMemo<CollaborationUnitScope | undefined>(() => {
    if (!source.artifact || !stageId) return undefined
    if (!source.artifact.unit_ref)
      return defaultCollaborationUnit(stageId, artifactText)
    return {
      label: artifactLabel(source.artifact.payload, source.artifact.unit_ref),
      unitRef: source.artifact.unit_ref,
    }
  }, [artifactText, source.artifact, stageId])
  const knowledge = useProjectKnowledge(activeProjectId ?? "", enabled)
  const collaboration = useAuthorCollaboration({
    activeUnit,
    artifactText,
    enabled: Boolean(enabled && source.artifact),
    knowledgeDocuments: knowledge.documents,
    runId: activeRun?.definition.run_id ?? "",
    sourceRef: source.artifact?.artifact_ref ?? "",
    stageId: stageId ?? "cast",
  })
  const selection = useStageSelectionCapture({
    enabled: Boolean(enabled && source.artifact),
    rootRef: workbenchRef,
    sourceRef: collaboration.sourceRef,
    stageId: stageId ?? "cast",
  })

  if (!stageId || !enabled) {
    return (
      <DockState
        icon={<AlertCircle size={18} />}
        title="当前阶段未开放作者协作"
      >
        作者协作只在路线合同声明的文学创作阶段可用。
      </DockState>
    )
  }

  if (source.loading || !source.artifact) {
    return (
      <DockState
        icon={source.error ? <AlertCircle size={18} /> : <Sparkles size={18} />}
        title={source.error ? "当前内容读取失败" : "正在绑定当前创作内容"}
      >
        {source.error || "读取本阶段 Artifact 与单元版本，请稍候。"}
      </DockState>
    )
  }

  return (
    <AuthorCollaborationPanel
      canRevise={source.artifact.editable}
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

function DockState({
  children,
  icon,
  title,
}: {
  children: string
  icon: ReactNode
  title: string
}) {
  return (
    <aside
      aria-label="作者协作"
      className="author-collaboration-panel collaboration-panel-loading"
    >
      {icon}
      <strong>{title}</strong>
      <span>{children}</span>
    </aside>
  )
}

function artifactLabel(payload: Record<string, unknown>, fallback: string) {
  for (const key of ["title", "display_name", "scene_heading"]) {
    if (typeof payload[key] === "string" && payload[key]) return payload[key]
  }
  return fallback
}

export { isCollaborationStageId as isCollaborationStage }
