import {
  ChevronLeft,
  ChevronRight,
  Clock,
  Command,
  Globe,
  Home,
  Layout,
  Menu,
  Moon,
  Plus,
  Settings,
  Sun,
  X,
} from "lucide-react"
import type { ReactNode } from "react"
import type { Route } from "../contracts/app"
import { useApp } from "../state/PipelineAppProvider"

const STUDIO_NAV: Array<{
  id: Route
  label: string
  icon: ReactNode
}> = [
  { id: "studio", label: "创作台 · 作品库", icon: <Home size={14} /> },
  { id: "workflow-templates", label: "工作流模板", icon: <Layout size={14} /> },
  { id: "knowledge", label: "知识总览", icon: <Globe size={14} /> },
  { id: "history", label: "创作历史", icon: <Clock size={14} /> },
  { id: "settings", label: "全局 AI 与服务设置", icon: <Settings size={14} /> },
]

export function StudioShell({ children }: { children: ReactNode }) {
  const {
    route,
    setRoute,
    theme,
    toggleTheme,
    setCmdOpen,
    setCreationWizardDraft,
    setSelectedTemplateId,
    sidebarCollapsed,
    toggleSidebar,
    mobileDrawerOpen,
    setMobileDrawerOpen,
  } = useApp()

  function NavLink({
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
        {!sidebarCollapsed && (
          <span className="flex-1 text-left truncate">{label}</span>
        )}
      </button>
    )
  }

  const sidebarBody = (
    <div className="flex flex-col h-full bg-surface overflow-hidden">
      <div className="flex items-center gap-2.5 px-3 h-12 border-b border-hairline shrink-0">
        <div className="w-7 h-7 rounded-[6px] flex items-center justify-center shrink-0 bg-elev border border-hairline">
          <span className="text-ink font-bold text-sm leading-none">四</span>
        </div>
        {!sidebarCollapsed && (
          <div>
            <div className="text-sm font-semibold text-ink leading-tight">
              四叶墨
            </div>
            <div className="text-[10px] text-fog leading-tight">
              Yotsuba Ink
            </div>
          </div>
        )}
      </div>

      <nav className="flex-1 overflow-y-auto py-2 px-2 space-y-0.5">
        {STUDIO_NAV.map((item) => (
          <NavLink key={item.id} {...item} />
        ))}
      </nav>

      <div className="px-2 py-3 border-t border-hairline shrink-0">
        {sidebarCollapsed ? (
          <button
            onClick={() => {
              setSelectedTemplateId(null)
              setCreationWizardDraft(null)
              setRoute("planning")
              setMobileDrawerOpen(false)
            }}
            className="nav-item w-full justify-center"
            title="新建作品"
          >
            <Plus size={15} className="text-action" />
          </button>
        ) : (
          <button
            onClick={() => {
              setSelectedTemplateId(null)
              setCreationWizardDraft(null)
              setRoute("planning")
              setMobileDrawerOpen(false)
            }}
            className="btn btn-action w-full text-xs"
          >
            <Plus size={13} /> 新建作品
          </button>
        )}
      </div>

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
      <header className="flex items-center gap-3 h-11 px-4 border-b border-hairline bg-surface shrink-0 z-30">
        <button
          className="header-mobile-menu btn-ghost btn p-1.5"
          onClick={() => setMobileDrawerOpen(!mobileDrawerOpen)}
          aria-controls="studio-mobile-navigation"
          aria-expanded={mobileDrawerOpen}
          aria-label={mobileDrawerOpen ? "关闭导航" : "打开导航"}
        >
          {mobileDrawerOpen ? <X size={17} /> : <Menu size={17} />}
        </button>
        {sidebarCollapsed && (
          <div className="hidden md:flex items-center gap-2">
            <div className="w-6 h-6 rounded flex items-center justify-center bg-elev border border-hairline">
              <span className="text-ink font-bold text-xs leading-none">
                四
              </span>
            </div>
            <span className="text-sm font-semibold text-ink">四叶墨</span>
          </div>
        )}
        <div className="flex-1" />
        <div className="flex items-center gap-2">
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
        </div>
      </header>

      <div className="flex flex-1 overflow-hidden">
        <aside
          className={`hidden md:flex flex-col border-r border-hairline transition-all duration-200 shrink-0 ${
            sidebarCollapsed ? "w-14" : "w-56"
          }`}
        >
          {sidebarBody}
        </aside>
        {mobileDrawerOpen && (
          <div
            className="md:hidden fixed inset-0 z-50 flex"
            id="studio-mobile-navigation"
          >
            <div className="w-64 h-full overflow-hidden animate-slide-left border-r border-hairline shadow-xl">
              {sidebarBody}
            </div>
            <button
              type="button"
              aria-label="关闭导航"
              className="flex-1 bg-black/40"
              onClick={() => setMobileDrawerOpen(false)}
            />
          </div>
        )}
        <main className="flex-1 overflow-hidden flex flex-col min-h-0">
          <div
            key={route}
            className="route-content-enter flex flex-1 min-h-0 flex-col"
          >
            {children}
          </div>
        </main>
      </div>

      <div className="md:hidden flex items-center gap-3 px-4 py-2.5 border-t border-hairline bg-surface shrink-0 z-20">
        <button
          onClick={() => {
            setSelectedTemplateId(null)
            setCreationWizardDraft(null)
            setRoute("planning")
            setMobileDrawerOpen(false)
          }}
          className="btn btn-action text-xs flex-1"
        >
          <Plus size={12} /> 新建作品
        </button>
        <button
          onClick={() => setCmdOpen(true)}
          className="btn btn-secondary px-3 py-2 text-xs"
          aria-label="打开命令面板"
        >
          <Command size={13} />
        </button>
      </div>
    </div>
  )
}
