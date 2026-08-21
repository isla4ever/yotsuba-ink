import { useState, useEffect, useRef } from "react"
import {
  Search,
  BookOpen,
  Layers,
  Users,
  BarChart3,
  FileText,
  Image,
  Download,
  BookMarked,
  Activity,
  Database,
  Settings,
  Clock,
  Sun,
  Moon,
  Home,
  Pencil,
} from "lucide-react"
import { useApp } from "../state/PipelineAppProvider"
import type { Route } from "../contracts/app"

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
  const { setCmdOpen, setRoute, toggleTheme, theme } = useApp()
  const [query, setQuery] = useState("")
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const goto = (r: Route) => {
    setRoute(r)
    setCmdOpen(false)
  }

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
    {
      id: "brief",
      label: "简报",
      sublabel: "冻结前提・承诺・规则・语气・篇幅",
      icon: <Pencil size={15} />,
      action: () => goto("brief"),
      group: "制作流程",
      keywords: "简报 brief 前提 承诺",
    },
    {
      id: "spine",
      label: "脊柱",
      sublabel: "因果转折链与结局",
      icon: <Layers size={15} />,
      action: () => goto("spine"),
      group: "制作流程",
      keywords: "脊柱 spine 因果 转折",
    },
    {
      id: "cast",
      label: "角色",
      sublabel: "命名角色权威来源",
      icon: <Users size={15} />,
      action: () => goto("cast"),
      group: "制作流程",
      keywords: "角色 cast 人物 人设",
    },
    {
      id: "volumes",
      label: "卷册",
      sublabel: "卷合同与边界",
      icon: <BarChart3 size={15} />,
      action: () => goto("volumes"),
      group: "制作流程",
      keywords: "卷册 volumes 分卷 卷合同",
    },
    {
      id: "detail",
      label: "细纲",
      sublabel: "章节场景建构台账",
      icon: <BookOpen size={15} />,
      action: () => goto("detail"),
      group: "制作流程",
      keywords: "细纲 detail 章节 场景",
    },
    {
      id: "text",
      label: "正文",
      sublabel: "稿件阅读器与编辑器",
      icon: <FileText size={15} />,
      action: () => goto("text"),
      group: "制作流程",
      keywords: "正文 text 稿件 编辑",
    },
    {
      id: "cover",
      label: "封面",
      sublabel: "封面视觉简报与候选",
      icon: <Image size={15} />,
      action: () => goto("cover"),
      group: "制作流程",
      keywords: "封面 cover 图片",
    },
    {
      id: "export",
      label: "导出",
      sublabel: "清单验证与下载",
      icon: <Download size={15} />,
      action: () => goto("export"),
      group: "制作流程",
      keywords: "导出 export 下载",
    },
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
      sublabel: "生成进度与日志",
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
      sublabel: "AI提供商与全局偏好",
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

  const filtered =
    query.trim() === ""
      ? commands
      : commands.filter(
          (c) =>
            c.label.includes(query) ||
            c.sublabel?.includes(query) ||
            c.keywords.includes(query.toLowerCase()),
        )

  const groups = [...new Set(filtered.map((c) => c.group))]

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-20 md:pt-32 px-4">
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={() => setCmdOpen(false)}
      />
      <div className="relative w-full max-w-xl bg-elev border border-hairline rounded-lg shadow-2xl overflow-hidden animate-fade-in">
        <div className="flex items-center gap-3 px-4 h-12 border-b border-hairline">
          <Search size={16} className="text-fog shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="搜索命令、路由、模式…"
            className="flex-1 bg-transparent text-ink text-sm outline-none placeholder:text-fog"
          />
          <kbd className="text-[10px] text-fog font-mono bg-hover px-1.5 py-0.5 rounded">
            Esc
          </kbd>
        </div>

        <div className="max-h-80 overflow-y-auto py-1">
          {filtered.length === 0 && (
            <div className="px-4 py-8 text-center text-fog text-sm">
              无匹配结果
            </div>
          )}
          {groups.map((group) => (
            <div key={group}>
              <div className="px-4 py-1.5 text-[10px] text-fog uppercase tracking-wider">
                {group}
              </div>
              {filtered
                .filter((c) => c.group === group)
                .map((cmd) => (
                  <button
                    key={cmd.id}
                    onClick={cmd.action}
                    className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-hover transition-colors text-left"
                  >
                    <span className="text-fog shrink-0">{cmd.icon}</span>
                    <div className="flex-1 min-w-0">
                      <div className="text-sm text-ink">{cmd.label}</div>
                      {cmd.sublabel && (
                        <div className="text-xs text-fog truncate">
                          {cmd.sublabel}
                        </div>
                      )}
                    </div>
                  </button>
                ))}
            </div>
          ))}
        </div>

        <div className="px-4 py-2 border-t border-hairline flex items-center gap-4 text-[10px] text-fog">
          <span>
            <kbd className="font-mono bg-hover px-1 rounded">↑↓</kbd> 选择
          </span>
          <span>
            <kbd className="font-mono bg-hover px-1 rounded">↵</kbd> 执行
          </span>
          <span>
            <kbd className="font-mono bg-hover px-1 rounded">Esc</kbd> 关闭
          </span>
        </div>
      </div>
    </div>
  )
}
