import { lazy, Suspense } from "react"
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
import HistoryPage from "./features/pipeline/running/history/HistoryPage"
import SettingsPage from "./features/pipeline/settings/SettingsPage"
import KnowledgePage from "./features/pipeline/brief/KnowledgePage"
import Phase32BriefStageView from "./features/pipeline/brief/Phase32BriefStageView"
import Phase32StageStatusView from "./features/pipeline/running/Phase32StageStatusView"
import CastStageView from "./features/pipeline/running/CastStageView"
import { templateIdFromLocation } from "./features/pipeline/lib/routes"
import {
  BookLoader,
  BookLoaderLayer,
} from "./features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "./features/pipeline/layout/useLoadingPresence"
import { BookSettingsPanel } from "./features/pipeline/settings/BookSettingsPanel"

const StoryMapStageView = lazy(
  () => import("./features/pipeline/running/StoryMapStageView"),
)
const BookArchitectureStageView = lazy(
  () => import("./features/pipeline/running/BookArchitectureStageView"),
)
const VolumeArchitectureStageView = lazy(
  () => import("./features/pipeline/running/VolumeArchitectureStageView"),
)
const RollingDetailStageView = lazy(
  () => import("./features/pipeline/running/RollingDetailStageView"),
)
const SectionPlanStageView = lazy(
  () => import("./features/pipeline/running/SectionPlanStageView"),
)
const BeatBoardStageView = lazy(
  () => import("./features/pipeline/running/BeatBoardStageView"),
)
const SceneDeckStageView = lazy(
  () => import("./features/pipeline/running/SceneDeckStageView"),
)
const ScreenplayStageView = lazy(
  () => import("./features/pipeline/running/ScreenplayStageView"),
)
const ShortProseStageView = lazy(
  () => import("./features/pipeline/running/ShortProseStageView"),
)
const LongChapterStageView = lazy(
  () => import("./features/pipeline/running/LongChapterStageView"),
)
const ScriptDeliveryStageView = lazy(
  () => import("./features/pipeline/running/ScriptDeliveryStageView"),
)
const Phase32CoverStageView = lazy(
  () => import("./features/pipeline/running/Phase32CoverStageView"),
)
const BookDeliveryStageView = lazy(
  () => import("./features/pipeline/running/BookDeliveryStageView"),
)
const Phase32RunMonitorPage = lazy(
  () => import("./features/pipeline/running/monitor/Phase32RunMonitorPage"),
)
const StoryBiblePage = lazy(
  () => import("./features/pipeline/running/story-bible/StoryBiblePage"),
)

function AppInner() {
  const {
    activeProject,
    activeRun,
    cmdOpen,
    projectLoading,
    projectOpen,
    route,
    runError,
    runLoading,
    selectedTemplateId,
    setCreationWizardDraft,
    setRoute,
    setSelectedTemplateId,
  } = useApp()
  const templateDetailId = templateIdFromLocation(window.location)
  const waitingForRun =
    Boolean(activeProject?.latestRunId) && !activeRun && !runError
  const workspaceLoading =
    projectOpen && (projectLoading || runLoading || waitingForRun)
  const workspaceLoader = useLoadingPresence(workspaceLoading)

  const handleTemplateDetail = (id: string) => {
    setSelectedTemplateId(id)
    setRoute("workflow-template-detail")
  }
  const handleUseTemplate = (id: string) => {
    if (route === "workflow-templates") setCreationWizardDraft(null)
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
            onCreateProject={() => {
              setCreationWizardDraft(null)
              setSelectedTemplateId(null)
              setRoute("planning")
            }}
          />
        )
      case "workflow-template-detail":
        return (
          <WorkflowTemplateDetailPage
            templateId={
              templateDetailId ?? selectedTemplateId ?? "official.short_novel"
            }
            onBack={handleDetailBack}
            onUse={handleUseTemplate}
          />
        )
      case "planning":
        return <PlanningPage />
      case "brief":
        return <Phase32BriefStageView />
      case "beat_board":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开屏幕决策节拍"
                detail="装载可见压力、角色决定、结果与铺垫覆盖"
              />
            }
          >
            <BeatBoardStageView />
          </Suspense>
        )
      case "scene_deck":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开场景调度台"
                detail="装载场景顺序、人物组合、可见目标、对抗与结果"
              />
            }
          >
            <SceneDeckStageView />
          </Suspense>
        )
      case "script":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开剧本正文"
                detail="装载逐场版本、规范剧本块与连续交接"
              />
            }
          >
            <ScreenplayStageView />
          </Suspense>
        )
      case "section_plan":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开章节与段落计划"
                detail="装载正文单元、POV、场景负载与状态交接"
              />
            }
          >
            <SectionPlanStageView />
          </Suspense>
        )
      case "story_map":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开故事地图"
                detail="装载锚点编辑器与阶段检查器"
              />
            }
          >
            <StoryMapStageView />
          </Suspense>
        )
      case "book_architecture":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开全书架构"
                detail="装载 Book root、Part 契约与生命周期检查器"
              />
            }
          >
            <BookArchitectureStageView />
          </Suspense>
        )
      case "cast":
        return <CastStageView />
      case "volumes":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开卷册架构"
                detail="装载 Volume 合同、Part 归属与人物范围检查器"
              />
            }
          >
            <VolumeArchitectureStageView />
          </Suspense>
        )
      case "rolling_detail":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开滚动细纲"
                detail="装载 Window、章节施工账本与场景蓝图"
              />
            }
          >
            <RollingDetailStageView />
          </Suspense>
        )
      case "text":
        return activeProject?.creationRouteId === "short_novel" ? (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开正文写作台"
                detail="装载逐单元正文、作者草稿与连续性交接"
              />
            }
          >
            <ShortProseStageView />
          </Suspense>
        ) : activeProject?.creationRouteId === "long_novel" ? (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开逐章正文"
                detail="装载冻结章节、历史接受版本与有限连续性交接"
              />
            }
          >
            <LongChapterStageView />
          </Suspense>
        ) : (
          <Phase32StageStatusView />
        )
      case "cover":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开封面审阅台"
                detail="装载视觉 Brief 与图片延期边界"
              />
            }
          >
            <Phase32CoverStageView />
          </Suspense>
        )
      case "export":
        return activeProject?.creationRouteId === "screenplay_sample" ? (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开剧本交付"
                detail="核验格式文件、Scene Manifest 与不可变回执"
              />
            }
          >
            <ScriptDeliveryStageView />
          </Suspense>
        ) : (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开成书交付"
                detail="核验正文 Manifest 与图片延期边界"
              />
            }
          >
            <BookDeliveryStageView />
          </Suspense>
        )
      case "story-bible":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开故事圣经"
                detail="装载已提交版本与顺序接受内容"
              />
            }
          >
            <StoryBiblePage />
          </Suspense>
        )
      case "run-monitor":
        return (
          <Suspense
            fallback={
              <BookLoader
                variant="panel"
                label="正在打开运行监控"
                detail="接入阶段、创作内容与正式运行日志"
              />
            }
          >
            <Phase32RunMonitorPage />
          </Suspense>
        )
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
