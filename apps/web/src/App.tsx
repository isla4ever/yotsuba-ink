import {
  AppProvider,
  useApp,
} from "./features/pipeline/state/PipelineAppProvider"
import Shell from "./features/pipeline/layout/Shell"
import CommandPalette from "./features/pipeline/layout/CommandPalette"
import StudioPage from "./features/pipeline/layout/studio/StudioPage"
import PlanningPage from "./features/pipeline/planning/PlanningPage"
import WorkflowTemplatesPage from "./features/pipeline/planning/WorkflowTemplatesPage"
import WorkflowTemplateDetailPage from "./features/pipeline/planning/WorkflowTemplateDetailPage"
import StoryBiblePage from "./features/pipeline/running/story-bible/StoryBiblePage"
import RunMonitorPage from "./features/pipeline/running/monitor/RunMonitorPage"
import HistoryPage from "./features/pipeline/running/history/HistoryPage"
import SettingsPage from "./features/pipeline/settings/SettingsPage"
import KnowledgePage from "./features/pipeline/brief/KnowledgePage"
import BriefStageView from "./features/pipeline/brief/BriefStageView"
import SpineStageView from "./features/pipeline/running/SpineStageView"
import CastStageView from "./features/pipeline/running/CastStageView"
import VolumesStageView from "./features/pipeline/running/VolumesStageView"
import DetailStageView from "./features/pipeline/running/DetailStageView"
import TextStageView from "./features/pipeline/running/TextStageView"
import CoverStageView from "./features/pipeline/running/CoverStageView"
import ExportStageView from "./features/pipeline/running/ExportStageView"
import { templateIdFromLocation } from "./features/pipeline/lib/routes"
import {
  BookLoader,
  BookLoaderLayer,
} from "./features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "./features/pipeline/layout/useLoadingPresence"
import { BookSettingsPanel } from "./features/pipeline/settings/BookSettingsPanel"

function AppInner() {
  const {
    activeProject,
    activeRun,
    cmdOpen,
    projectLoading,
    projectOpen,
    route,
    runArtifactLoading,
    runArtifacts,
    runError,
    runLoading,
    selectedTemplateId,
    setRoute,
    setSelectedTemplateId,
  } = useApp()
  const templateDetailId = templateIdFromLocation(window.location)
  const waitingForRun =
    Boolean(activeProject?.latestRunId) && !activeRun && !runError
  const waitingForArtifacts =
    Boolean(activeRun) &&
    runArtifactLoading &&
    Object.keys(runArtifacts).length === 0
  const workspaceLoading =
    projectOpen &&
    (projectLoading || runLoading || waitingForRun || waitingForArtifacts)
  const workspaceLoader = useLoadingPresence(workspaceLoading)

  const handleTemplateDetail = (id: string) => {
    setSelectedTemplateId(id)
    setRoute("workflow-template-detail")
  }
  const handleUseTemplate = (id: string) => {
    setSelectedTemplateId(id)
    setRoute("planning")
  }
  const handleDetailBack = () => {
    setRoute("workflow-templates")
  }

  const view = () => {
    switch (route) {
      case "studio":
        return <StudioPage />
      case "workflow-templates":
        return (
          <WorkflowTemplatesPage
            onDetail={handleTemplateDetail}
            onUseTemplate={handleUseTemplate}
          />
        )
      case "workflow-template-detail":
        return (
          <WorkflowTemplateDetailPage
            templateId={
              templateDetailId ??
              selectedTemplateId ??
              "official-deepseek-balanced"
            }
            onBack={handleDetailBack}
            onOpen={handleTemplateDetail}
            onUse={handleUseTemplate}
          />
        )
      case "planning":
        return <PlanningPage />
      case "brief":
        return <BriefStageView />
      case "spine":
        return <SpineStageView />
      case "cast":
        return <CastStageView />
      case "volumes":
        return <VolumesStageView />
      case "detail":
        return <DetailStageView />
      case "text":
        return <TextStageView />
      case "cover":
        return <CoverStageView />
      case "export":
        return <ExportStageView />
      case "story-bible":
        return <StoryBiblePage />
      case "run-monitor":
        return <RunMonitorPage />
      case "knowledge":
        return <KnowledgePage />
      case "book-settings":
        return <BookSettingsPanel />
      case "history":
        return <HistoryPage />
      case "settings":
        return <SettingsPage />
      default:
        return <StudioPage />
    }
  }

  return (
    <BookLoaderLayer overlayVisible={workspaceLoader.visible}>
      <div className="h-screen">
        <Shell>{view()}</Shell>
        {cmdOpen && <CommandPalette />}
        {workspaceLoader.visible && (
          <BookLoader
            phase={workspaceLoader.exiting ? "exit" : "enter"}
            variant="overlay"
            label={projectLoading ? "正在进入创作工作台" : "正在恢复创作现场"}
            detail="同步项目、Run 状态与正式 Artifact"
          />
        )}
      </div>
    </BookLoaderLayer>
  )
}

export default function App() {
  return (
    <AppProvider>
      <AppInner />
    </AppProvider>
  )
}
