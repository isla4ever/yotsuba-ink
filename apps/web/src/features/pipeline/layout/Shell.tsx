import {
  lazy,
  Suspense,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react"
import {
  ArrowLeft,
  BookMarked,
  ChevronLeft,
  ChevronRight,
  Command,
  Database,
  Menu,
  Moon,
  Settings,
  Sparkles,
  Sun,
  X,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import type { Route, StageStatus } from "../contracts/app"
import { runStageStatuses } from "../lib/runPresentation"
import { RouteLockBadge, RunConnectionStatus, StatusDot } from "./ShellStatus"
import {
  projectStageNavigation,
  runStageNavigation,
  StageProgressTrace,
} from "./StageProgressTrace"
import { StudioShell } from "./StudioShell"
import { isCollaborationStageId } from "../lib/authorCollaborationProjection"

const AuthorCollaborationDock = lazy(() =>
  import("../running/collaboration/AuthorCollaborationDock").then((module) => ({
    default: module.AuthorCollaborationDock,
  })),
)

/* Project navigation */
const PROJECT_TOOLS: Array<{
  id: Route
  label: string
  icon: ReactNode
}> = [
  { id: "story-bible", label: "故事圣经", icon: <BookMarked size={14} /> },
  { id: "knowledge", label: "本书知识库", icon: <Database size={14} /> },
  { id: "book-settings", label: "本书设置", icon: <Settings size={14} /> },
]

/* ─── Project shell ────────────────────────────────────────────────────────── */
function ProjectShell({ children }: { children: ReactNode }) {
  const {
    route,
    setRoute,
    theme,
    toggleTheme,
    setCmdOpen,
    activeRun,
    sidebarCollapsed,
    toggleSidebar,
    mobileDrawerOpen,
    setMobileDrawerOpen,
    closeProject,
    activeProject,
  } = useApp()
  const isMonitoring = route === "run-monitor"
  const workbenchRef = useRef<HTMLElement | null>(null)
  const [collaborationOpen, setCollaborationOpen] = useState(false)
  const collaborationStage = isCollaborationStageId(route)
    ? activeRun?.read_model.stage_manifest.find(
        (stage) => stage.stage_id === route,
      )
    : undefined
  const collaborationAvailable = Boolean(
    activeRun &&
      collaborationStage?.collaboration_enabled &&
      activeRun.read_model.stage_status[route] !== "locked",
  )
  const isLive = activeRun?.read_model.status === "running"
  const stages = activeRun
    ? runStageNavigation(activeRun)
    : activeProject
      ? projectStageNavigation(activeProject)
      : []
  const statuses = runStageStatuses(
    activeRun,
    activeProject?.stageStatuses ?? {},
  )

  useEffect(() => {
    setCollaborationOpen(false)
  }, [activeRun?.definition.run_id, route, collaborationAvailable])

  const currentLabel =
    stages.find((s) => s.id === route)?.label ??
    PROJECT_TOOLS.find((s) => s.id === route)?.label ??
    (route === "run-monitor" ? "实时监控" : route)

  function StageLink({
    id,
    label,
    num,
    icon,
  }: {
    id: Route
    label: string
    num: number
    icon: ReactNode
  }) {
    const isActive = route === id
    const st = statuses[id] as StageStatus | undefined
    const disabled = st === "pending"
    return (
      <button
        onClick={() => {
          setRoute(id)
          setMobileDrawerOpen(false)
        }}
        className={`nav-item w-full text-left ${isActive ? "active" : ""}`}
        disabled={disabled}
        aria-disabled={disabled}
      >
        {sidebarCollapsed ? (
          <span
            className={`font-mono text-[10px] w-full text-center ${
              isActive ? "text-action" : "text-fog"
            }`}
          >
            {num}
          </span>
        ) : (
          <>
            <span className={`shrink-0 ${isActive ? "nav-icon" : "text-fog"}`}>
              {icon}
            </span>
            <span className="flex-1 text-left">{label}</span>
            {st && <StatusDot status={st} />}
          </>
        )}
      </button>
    )
  }

  function ToolLink({
    id,
    label,
    icon,
  }: {
    id: Route
    label: string
    icon: ReactNode
  }) {
    const isActive = route === id
    return (
      <button
        onClick={() => {
          setRoute(id)
          setMobileDrawerOpen(false)
        }}
        className={`nav-item w-full text-left ${isActive ? "active" : ""}`}
      >
        <span className={`shrink-0 ${isActive ? "nav-icon" : "text-fog"}`}>
          {icon}
        </span>
        {!sidebarCollapsed && <span className="flex-1 text-left">{label}</span>}
      </button>
    )
  }

  const sidebarBody = (
    <div className="flex flex-col h-full bg-surface overflow-hidden">
      {/* Back */}
      <div className="flex items-center gap-2 px-3 h-12 border-b border-hairline shrink-0">
        <button
          onClick={closeProject}
          className="flex items-center gap-2 text-fog hover:text-ink transition-colors"
          title="返回创作台"
        >
          <ArrowLeft size={14} className="shrink-0" />
          {!sidebarCollapsed && <span className="text-xs">返回创作台</span>}
        </button>
      </div>

      {/* Book identity */}
      {!sidebarCollapsed && (
        <div className="px-3 pt-3 pb-2.5 border-b border-hairline shrink-0">
          <div className="text-[10px] text-fog uppercase tracking-wider mb-1">
            当前作品
          </div>
          <div className="text-sm font-semibold text-ink truncate mb-0.5">
            《{activeProject?.title || "读取作品中"}》
          </div>
          <div className="text-[10px] text-fog mb-2.5 truncate">
            {activeProject?.subtitle || "正在同步真实项目数据"}
          </div>
          <RouteLockBadge label={activeProject?.routeLabel ?? "路线读取中"} />
        </div>
      )}

      {/* Project navigation remains stable across every stage. */}
      <nav className="flex-1 overflow-y-auto py-2 px-2 flex flex-col">
        <div className="flex-1 overflow-y-auto min-h-0">
          {!sidebarCollapsed && (
            <div className="text-[10px] text-fog uppercase tracking-wider px-2 pb-1 pt-1">
              制作流程
            </div>
          )}
          <div className="space-y-0.5">
            {stages.map((s) => (
              <StageLink key={s.id} {...s} />
            ))}
          </div>
          {!sidebarCollapsed && (
            <div className="text-[10px] text-fog uppercase tracking-wider px-2 pt-3 pb-1">
              项目工具
            </div>
          )}
          {sidebarCollapsed && <div className="h-2" />}
          <div className="space-y-0.5">
            {PROJECT_TOOLS.map((t) => (
              <ToolLink key={t.id} {...t} />
            ))}
          </div>
        </div>
      </nav>

      <div className="px-2 pb-2 border-t border-hairline pt-2 shrink-0">
        <button onClick={toggleSidebar} className="nav-item w-full">
          <span className="text-fog">
            {sidebarCollapsed ? (
              <ChevronRight size={15} />
            ) : (
              <ChevronLeft size={15} />
            )}
          </span>
          {!sidebarCollapsed && <span className="text-xs">收起侧栏</span>}
        </button>
      </div>
    </div>
  )

  return (
    <div className="flex flex-col h-screen overflow-hidden bg-base">
      {/* Project header with ECG trace */}
      <header
        className="flex items-center gap-2 px-3 border-b border-hairline bg-surface shrink-0 z-30"
        style={{ minHeight: 50 }}
      >
        <button
          className="header-mobile-menu btn-ghost btn p-1.5 shrink-0"
          onClick={() => setMobileDrawerOpen(!mobileDrawerOpen)}
          aria-controls="project-mobile-navigation"
          aria-expanded={mobileDrawerOpen}
          aria-label={mobileDrawerOpen ? "关闭导航" : "打开导航"}
        >
          {mobileDrawerOpen ? <X size={17} /> : <Menu size={17} />}
        </button>

        {/* ECG progress trace — centered, max-width 720px, desktop only */}
        <div className="hidden md:flex flex-1 justify-center items-center min-w-0 overflow-hidden">
          <StageProgressTrace route={route} setRoute={setRoute} />
        </div>

        {/* Mobile: current page label */}
        <div className="md:hidden flex-1">
          <span className="text-sm font-medium text-ink">{currentLabel}</span>
        </div>

        <button
          onClick={() => setRoute("run-monitor")}
          className={`hidden md:flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md font-medium shrink-0 transition-all duration-160 ${
            isMonitoring
              ? "bg-action text-white shadow-sm"
              : "bg-action-bg border border-action/35 text-action hover:bg-action hover:text-white"
          }`}
          aria-current={isMonitoring ? "page" : undefined}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full shrink-0 ${
              isLive
                ? isMonitoring
                  ? "bg-white status-quiet"
                  : "bg-action status-quiet"
                : isMonitoring
                  ? "bg-white/50"
                  : "bg-action/45"
            }`}
          />
          实时监控
        </button>

        {collaborationAvailable && (
          <button
            aria-expanded={collaborationOpen}
            aria-label={collaborationOpen ? "关闭作者协作" : "打开作者协作"}
            className={`author-collaboration-trigger hidden md:inline-flex ${
              collaborationOpen ? "active" : ""
            }`}
            onClick={() => {
              setMobileDrawerOpen(false)
              setCollaborationOpen((open) => !open)
            }}
            type="button"
          >
            <Sparkles size={14} />
            作者协作
          </button>
        )}

        {/* Right controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          <div className="hidden md:block">
            <RunConnectionStatus />
          </div>
          <div className="hidden lg:block">
            <RouteLockBadge label={activeProject?.routeLabel ?? "路线读取中"} />
          </div>
          <button
            onClick={toggleTheme}
            className="btn-ghost btn p-1.5"
            aria-label="切换主题"
          >
            {theme === "dark" ? <Sun size={14} /> : <Moon size={14} />}
          </button>
          <button
            onClick={() => setCmdOpen(true)}
            className="hidden md:flex btn-ghost btn p-1.5 gap-1.5 text-xs text-fog"
          >
            <Command size={13} />K
          </button>
          {activeRun?.read_model.updated_at && (
            <span className="hidden xl:block text-[10px] font-mono text-fog">
              同步 {formatClock(activeRun.read_model.updated_at)}
            </span>
          )}
        </div>
      </header>

      <div
        className={`project-workbench-row flex flex-1 overflow-hidden ${
          collaborationOpen ? "collaboration-open" : ""
        }`}
      >
        {/* Project sidebar — hidden while monitoring to give monitor full width */}
        {!isMonitoring && !collaborationOpen && (
          <aside
            className={`hidden md:flex flex-col border-r border-hairline transition-all duration-200 shrink-0 ${
              sidebarCollapsed ? "w-14" : "w-52"
            }`}
          >
            {sidebarBody}
          </aside>
        )}

        {/* Mobile drawer — always available */}
        {mobileDrawerOpen && (
          <div
            className="md:hidden fixed inset-0 z-50 flex"
            id="project-mobile-navigation"
          >
            <div className="w-64 h-full overflow-hidden animate-slide-left border-r border-hairline shadow-xl">
              {sidebarBody}
            </div>
            <div
              className="flex-1 bg-black/40"
              onClick={() => setMobileDrawerOpen(false)}
            />
          </div>
        )}

        <main
          className="flex-1 overflow-hidden flex flex-col min-h-0"
          ref={workbenchRef}
        >
          <div
            key={route}
            className="route-content-enter flex flex-1 min-h-0 flex-col"
          >
            {children}
          </div>
        </main>
        {collaborationOpen && (
          <Suspense
            fallback={
              <aside className="author-collaboration-dock" role="status">
                正在打开作者协作…
              </aside>
            }
          >
            <AuthorCollaborationDock
              onClose={() => setCollaborationOpen(false)}
              workbenchRef={workbenchRef}
            />
          </Suspense>
        )}
      </div>

      {/* Mobile bottom bar */}
      <div className="md:hidden flex items-center gap-3 px-4 py-2.5 border-t border-hairline bg-surface shrink-0 z-20">
        <div className="flex-1">
          <RunConnectionStatus />
        </div>
        <button
          onClick={() => setRoute("run-monitor")}
          className={`flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md font-medium border transition-all ${
            isMonitoring
              ? "bg-action border-action text-white"
              : "bg-action-bg border-action/30 text-action"
          }`}
          aria-current={isMonitoring ? "page" : undefined}
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isLive ? "bg-action status-quiet" : "bg-action/45"
            }`}
          />
          监控
        </button>
        <RouteLockBadge label={activeProject?.routeLabel ?? "路线读取中"} />
        {collaborationAvailable && (
          <button
            aria-expanded={collaborationOpen}
            aria-label={collaborationOpen ? "关闭作者协作" : "打开作者协作"}
            className={`author-collaboration-trigger ${
              collaborationOpen ? "active" : ""
            }`}
            onClick={() => setCollaborationOpen((open) => !open)}
            type="button"
          >
            <Sparkles size={14} />
            协作
          </button>
        )}
        <button
          onClick={() => setCmdOpen(true)}
          className="btn btn-secondary px-3 py-2 text-xs"
          aria-label="打开命令面板"
          title="打开命令面板"
        >
          <Command size={13} />
        </button>
      </div>
    </div>
  )
}

export default function Shell({ children }: { children: ReactNode }) {
  const { projectOpen } = useApp()
  return projectOpen ? (
    <ProjectShell>{children}</ProjectShell>
  ) : (
    <StudioShell>{children}</StudioShell>
  )
}

function formatClock(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? ""
    : date.toLocaleTimeString("zh-CN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
}
