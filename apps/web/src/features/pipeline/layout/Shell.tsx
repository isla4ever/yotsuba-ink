import { lazy, Suspense, useEffect, useRef, useState, type ReactNode } from "react"
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
import {
  activeRunModel,
  runStageStatuses,
} from "../lib/runPresentation"
import { isCollaborationStageId } from "../lib/authorCollaborationProjection"
import { ModeLockBadge, RunConnectionStatus, StatusDot } from "./ShellStatus"
import { STAGES, StageProgressTrace } from "./StageProgressTrace"
import { StudioShell } from "./StudioShell"

const AuthorCollaborationDock = lazy(async () => {
  const module = await import(
    "../running/collaboration/AuthorCollaborationDock"
  )
  return { default: module.AuthorCollaborationDock }
})

/* Project navigation */
const PROJECT_TOOLS: Array<{ id: Route; label: string; icon: ReactNode }> = [
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
    mode,
    setCmdOpen,
    activeRun,
    sidebarCollapsed,
    toggleSidebar,
    mobileDrawerOpen,
    setMobileDrawerOpen,
    closeProject,
    activeProject,
  } = useApp()
  const [collaborationOpen, setCollaborationOpen] = useState(false)
  const collaborationTriggerRef = useRef<HTMLButtonElement>(null)
  const collaborationWasOpenRef = useRef(false)
  const workbenchRef = useRef<HTMLElement>(null)

  const isMonitoring = route === "run-monitor"
  const collaborationEligible =
    activeRun?.definition.quality_mode === "deep" &&
    isCollaborationStageId(route)
  const isLive = activeRun?.read_model.status === "running"
  const model = activeRunModel(activeRun)
  const statuses = runStageStatuses(
    activeRun,
    activeProject?.stageStatuses ?? {},
  )

  useEffect(() => {
    if (!collaborationEligible) setCollaborationOpen(false)
  }, [collaborationEligible])

  useEffect(() => {
    if (!collaborationOpen && collaborationWasOpenRef.current)
      window.requestAnimationFrame(() => collaborationTriggerRef.current?.focus())
    collaborationWasOpenRef.current = collaborationOpen
  }, [collaborationOpen])

  const currentLabel =
    STAGES.find((s) => s.id === route)?.label ??
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
    return (
      <button
        onClick={() => {
          setRoute(id)
          setMobileDrawerOpen(false)
        }}
        className={`nav-item w-full text-left ${isActive ? "active" : ""}`}
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
          <ModeLockBadge mode={mode} />
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
            {STAGES.map((s) => (
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

        {/* Live Monitor tab — always action-colored, always visible */}
        {collaborationEligible && (
          <button
            ref={collaborationTriggerRef}
            type="button"
            aria-expanded={collaborationOpen}
            aria-label={collaborationOpen ? "关闭作者协作" : "打开作者协作"}
            className={`author-collaboration-trigger ${collaborationOpen ? "active" : ""}`}
            onClick={() => {
              setMobileDrawerOpen(false)
              setCollaborationOpen((open) => !open)
            }}
            title="作者协作"
          >
            <Sparkles size={14} />
            <span className="hidden xl:inline">作者协作</span>
          </button>
        )}

        {/* Live Monitor tab — always action-colored, always visible */}
        <button
          onClick={() => setRoute("run-monitor")}
          className={`hidden md:flex items-center gap-1.5 text-xs px-2.5 py-1.5 rounded-md font-medium shrink-0 transition-all duration-160 ${
            isMonitoring
              ? "bg-action text-white shadow-sm"
              : "bg-action-bg border border-action/35 text-action hover:bg-action hover:text-white"
          }`}
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

        {/* Right controls */}
        <div className="flex items-center gap-1.5 shrink-0">
          <div className="hidden md:block">
            <RunConnectionStatus />
          </div>
          <div className="hidden lg:block">
            <ModeLockBadge mode={mode} model={model} />
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

      <div className={`project-workbench-row flex flex-1 overflow-hidden ${collaborationOpen ? "collaboration-open" : ""}`}>
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

        <main ref={workbenchRef} className="flex-1 overflow-hidden flex flex-col min-h-0">
          <div
            key={route}
            className="route-content-enter flex flex-1 min-h-0 flex-col"
          >
            {children}
          </div>
        </main>
        {collaborationOpen && collaborationEligible && (
          <Suspense
            fallback={
              <aside aria-label="作者协作" className="author-collaboration-panel collaboration-panel-loading">
                <Sparkles size={18} />
                <span>正在恢复协作现场...</span>
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
        >
          <span
            className={`w-1.5 h-1.5 rounded-full ${
              isLive ? "bg-action status-quiet" : "bg-action/45"
            }`}
          />
          监控
        </button>
        <ModeLockBadge mode={mode} model={model} />
        <button
          onClick={() => setCmdOpen(true)}
          className="btn btn-secondary px-3 py-2 text-xs"
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
