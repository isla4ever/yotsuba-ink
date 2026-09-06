import { useEffect, useRef, useState } from "react"
import {
  Activity,
  BarChart3,
  BookMarked,
  BookOpen,
  Clock,
  Database,
  Download,
  FileText,
  GitBranch,
  Home,
  Image,
  Moon,
  Pencil,
  Search,
  Settings,
  Sun,
  Users,
} from "lucide-react"
import type { Route } from "../contracts/app"
import { useApp } from "../state/PipelineAppProvider"

interface Cmd {
  id: string
  label: string
  sublabel?: string
  icon: React.ReactNode
  action: () => void
  group: string
  keywords: string
}

export default function CommandPalette() {
  const { activeProject, setCmdOpen, setRoute, toggleTheme, theme } = useApp()
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const goto = (route: Route) => {
    setRoute(route)
    setCmdOpen(false)
  }

  const stageCommands: Cmd[] = (activeProject?.stageManifest ?? []).map(
    (stage) => ({
      id: `stage-${stage.id}`,
      label: stage.label,
      sublabel: `${activeProject?.routeLabel ?? "当前路线"} · 第 ${stage.ordinal + 1} 阶段`,
      icon: stageIcon(stage.id),
      action: () => goto(stage.id as Route),
      group: "制作流程",
      keywords: `${stage.id} ${stage.label}`,
    }),
  )

  const commands: Cmd[] = [
    {
      id: "studio",
      label: "创作台",
      sublabel: "项目库",
      icon: <Home size={15} />,
      action: () => goto("studio"),
      group: "导航",
      keywords: "创作台 项目库 studio",
    },
    ...stageCommands,
    {
      id: "story-bible",
      label: "故事圣经",
      sublabel: "人物・世界规则・伏笔・事实",
      icon: <BookMarked size={15} />,
      action: () => goto("story-bible"),
      group: "工具",
      keywords: "圣经 bible 世界 伏笔",
    },
    {
      id: "run-monitor",
      label: "运行监控",
      sublabel: "生成进度、调用与日志",
      icon: <Activity size={15} />,
      action: () => goto("run-monitor"),
      group: "工具",
      keywords: "运行 监控 monitor 日志",
    },
    {
      id: "knowledge",
      label: "知识库",
      sublabel: "项目参考资料",
      icon: <Database size={15} />,
      action: () => goto("knowledge"),
      group: "工具",
      keywords: "知识库 knowledge 资料 参考",
    },
    {
      id: "history",
      label: "历史",
      sublabel: "创作记录",
      icon: <Clock size={15} />,
      action: () => goto("history"),
      group: "工具",
      keywords: "历史 history 记录",
    },
    {
      id: "settings",
      label: "设置",
      sublabel: "AI 提供商与全局偏好",
      icon: <Settings size={15} />,
      action: () => goto("settings"),
      group: "工具",
      keywords: "设置 settings AI 提供商",
    },
    {
      id: "theme",
      label: `切换到${theme === "dark" ? "浅色" : "深色"}主题`,
      icon: theme === "dark" ? <Sun size={15} /> : <Moon size={15} />,
      action: () => {
        toggleTheme()
        setCmdOpen(false)
      },
      group: "界面",
      keywords: "主题 theme 深色 浅色",
    },
  ]

  const normalizedQuery = query.trim().toLowerCase()
  const filtered = normalizedQuery
    ? commands.filter(
        (command) =>
          command.label.toLowerCase().includes(normalizedQuery) ||
          command.sublabel?.toLowerCase().includes(normalizedQuery) ||
          command.keywords.toLowerCase().includes(normalizedQuery),
      )
    : commands
  const groups = [...new Set(filtered.map((command) => command.group))]

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-20 md:pt-32">
      <button
        type="button"
        aria-label="关闭命令面板"
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setCmdOpen(false)}
      />
      <div className="relative w-full max-w-xl overflow-hidden rounded-lg border border-hairline bg-elev shadow-2xl animate-fade-in">
        <div className="flex h-12 items-center gap-3 border-b border-hairline px-4">
          <Search size={16} className="shrink-0 text-fog" />
          <input
            ref={inputRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="搜索命令、路线或阶段…"
            className="flex-1 bg-transparent text-sm text-ink outline-none placeholder:text-fog"
          />
          <kbd className="rounded bg-hover px-1.5 py-0.5 font-mono text-[10px] text-fog">
            Esc
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto py-1">
          {filtered.length === 0 && (
            <div className="px-4 py-8 text-center text-sm text-fog">
              无匹配结果
            </div>
          )}
          {groups.map((group) => (
            <div key={group}>
              <div className="px-4 py-1.5 text-[10px] uppercase tracking-wider text-fog">
                {group}
              </div>
              {filtered
                .filter((command) => command.group === group)
                .map((command) => (
                  <button
                    key={command.id}
                    onClick={command.action}
                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-hover"
                  >
                    <span className="shrink-0 text-fog">{command.icon}</span>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm text-ink">{command.label}</div>
                      {command.sublabel && (
                        <div className="truncate text-xs text-fog">
                          {command.sublabel}
                        </div>
                      )}
                    </div>
                  </button>
                ))}
            </div>
          ))}
        </div>

        <div className="flex items-center gap-4 border-t border-hairline px-4 py-2 text-[10px] text-fog">
          <span>
            <kbd className="rounded bg-hover px-1 font-mono">Esc</kbd> 关闭
          </span>
        </div>
      </div>
    </div>
  )
}

function stageIcon(stageId: string) {
  if (stageId === "brief") return <Pencil size={15} />
  if (stageId === "cast") return <Users size={15} />
  if (stageId === "volumes") return <BarChart3 size={15} />
  if (stageId === "text" || stageId === "script") return <FileText size={15} />
  if (stageId === "cover") return <Image size={15} />
  if (stageId === "export") return <Download size={15} />
  if (stageId.includes("architecture") || stageId.includes("map")) {
    return <GitBranch size={15} />
  }
  return <BookOpen size={15} />
}
