import "../../../../styles/phase32-story-bible.css"
import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react"
import {
  BookMarked,
  Braces,
  FileCheck2,
  GitBranch,
  Orbit,
  ShieldCheck,
  Users,
} from "lucide-react"
import type { Route } from "@/features/pipeline/contracts/app"
import type {
  StoryBibleSection,
  StoryBibleSummary,
} from "@/features/pipeline/contracts/storyBible"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { isProductionStageRoute } from "@/features/pipeline/lib/routes"
import {
  StoryBibleEmpty,
  StoryBibleLedger,
  StoryBibleMetrics,
} from "@/features/pipeline/running/StoryBibleLedgers"
import { useApp } from "@/features/pipeline/state/PipelineAppProvider"
import { useStoryBible } from "@/features/pipeline/state/useStoryBible"

const TABS: Array<{
  id: StoryBibleSection
  label: string
  icon: typeof BookMarked
}> = [
  { id: "overview", label: "核心设定", icon: Braces },
  { id: "cast", label: "人物与关系", icon: Users },
  { id: "structure", label: "故事结构", icon: GitBranch },
  { id: "units", label: "已接受内容", icon: FileCheck2 },
  { id: "continuity", label: "连续性", icon: Orbit },
]

export default function StoryBiblePage() {
  const { activeProject, activeRun, runLoading, setRoute } = useApp()
  const tabListRef = useRef<HTMLElement | null>(null)
  const [section, setSection] = useState<StoryBibleSection>(() =>
    sectionFromPath(window.location.pathname),
  )
  const runId = activeRun?.definition.run_id ?? ""
  const storyBible = useStoryBible(
    runId,
    section,
    activeRun?.read_model.updated_at ?? "",
  )
  const loadingPresence = useLoadingPresence(
    runLoading || (storyBible.status === "loading" && !storyBible.items.length),
  )
  const tabs = useMemo(
    () => routeTabs(activeRun?.definition.route_contract.creation_route_id),
    [activeRun?.definition.route_contract.creation_route_id],
  )

  useEffect(() => {
    const syncSection = () =>
      setSection(sectionFromPath(window.location.pathname))
    window.addEventListener("popstate", syncSection)
    return () => window.removeEventListener("popstate", syncSection)
  }, [])

  useLayoutEffect(() => {
    const tabList = tabListRef.current
    const activeTab = tabList?.querySelector<HTMLElement>("button.active")
    if (!tabList || !activeTab) return
    const visibleLeft = tabList.scrollLeft
    const visibleRight = visibleLeft + tabList.clientWidth
    const activeLeft = activeTab.offsetLeft
    const activeRight = activeLeft + activeTab.offsetWidth
    if (activeLeft < visibleLeft) tabList.scrollLeft = activeLeft
    else if (activeRight > visibleRight)
      tabList.scrollLeft = activeRight - tabList.clientWidth
  }, [loadingPresence.visible, section, tabs])

  const selectSection = (next: StoryBibleSection) => {
    setSection(next)
    const projectQuery = activeProject?.id
      ? `?project=${encodeURIComponent(activeProject.id)}`
      : ""
    window.history.pushState(null, "", `/bible/${next}${projectQuery}`)
  }

  const openSource = (stageId: string) => {
    if (isProductionStageRoute(stageId)) setRoute(stageId as Route)
  }

  if (loadingPresence.visible) {
    return (
      <BookLoader
        phase={loadingPresence.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在整理故事圣经"
        detail="读取当前路线的正式版本与已接受内容"
      />
    )
  }

  if (!activeRun) {
    return (
      <StoryBibleEmpty
        icon={BookMarked}
        title="故事圣经尚未建立"
        detail="作品启动 Run 后，这里会按当前创作路线建立只读投影。"
      />
    )
  }

  return (
    <div className="story-bible-screen page-in">
      <header className="story-bible-header stage-aura">
        <div className="story-bible-identity">
          <BookMarked size={16} />
          <div>
            <strong>故事圣经</strong>
            <span>
              《
              {storyBible.summary?.title || activeProject?.title || "待定标题"}
              》
              <i aria-hidden="true" />
              {storyBible.summary?.route_label || activeProject?.routeLabel}
            </span>
          </div>
        </div>
        <div className="story-bible-authority">
          <ShieldCheck size={13} />
          已提交版本 · 只读投影
        </div>
      </header>

      {storyBible.summary && <StoryBibleMetrics summary={storyBible.summary} />}

      <nav
        ref={tabListRef}
        className="story-bible-tabs"
        aria-label="故事圣经分类"
      >
        {tabs.map((item) => {
          const Icon = item.icon
          const count = sectionCount(item.id, storyBible.summary)
          return (
            <button
              key={item.id}
              type="button"
              className={section === item.id ? "active" : ""}
              aria-current={section === item.id ? "page" : undefined}
              onClick={() => selectSection(item.id)}
            >
              <Icon size={13} />
              <span>{item.label}</span>
              {count !== null && <em>{count}</em>}
            </button>
          )
        })}
      </nav>

      <main className="story-bible-content">
        {storyBible.error && (
          <div className="banner-warning" role="alert">
            {storyBible.error}
          </div>
        )}
        {section === "continuity" && storyBible.summary && (
          <div
            className={`story-bible-boundary-note ${writebackTone(storyBible.summary)}`}
          >
            <ShieldCheck size={13} />
            <div>
              <strong>{writebackCopy(storyBible.summary).title}</strong>
              <span>{writebackCopy(storyBible.summary).detail}</span>
            </div>
          </div>
        )}
        <StoryBibleLedger
          items={storyBible.items}
          section={section}
          routeId={activeRun.definition.route_contract.creation_route_id}
          hasMore={Boolean(storyBible.nextCursor)}
          loadingMore={storyBible.status === "loading-more"}
          onLoadMore={storyBible.loadMore}
          onOpenSource={openSource}
          total={storyBible.total}
        />
      </main>
    </div>
  )
}

function writebackCopy(summary: StoryBibleSummary) {
  if (summary.formal_writeback_status === "committed") {
    return {
      title: `已核验 ${summary.formal_fact_count} 条正式事实`,
      detail:
        "这些记录由已接受正文的直接证据写入 Canon，并已完成 Wiki 只读投影。",
    }
  }
  if (summary.formal_writeback_status === "recovery_required") {
    return {
      title: "正式事实写回需要恢复",
      detail:
        "已接受正文保持安全；请返回对应正文单元重试 Canon / Wiki 写回，本页不会自行补写或猜测。",
    }
  }
  if (summary.formal_writeback_status === "in_progress") {
    return {
      title: "正在提交正式事实",
      detail:
        "正文版本已经冻结，Canon 与 Wiki 正在完成幂等写回；现有记录继续保持只读。",
    }
  }
  return {
    title: "当前展示可追溯的规划与正文投影",
    detail:
      "尚无正文事实写回回执；本页只读取已提交 Artifact，不从候选稿或文本中自行猜测。",
  }
}

function writebackTone(summary: StoryBibleSummary) {
  if (summary.formal_writeback_status === "committed")
    return "!border-mint/25 !bg-mint-bg !text-mint"
  if (summary.formal_writeback_status === "in_progress")
    return "!border-action/25 !bg-action-bg !text-action"
  return ""
}

function routeTabs(
  routeId: "screenplay_sample" | "short_novel" | "long_novel" | undefined,
) {
  return TABS.map((tab) => {
    if (tab.id === "structure") {
      if (routeId === "screenplay_sample")
        return { ...tab, label: "节拍与场景" }
      if (routeId === "short_novel") return { ...tab, label: "故事地图" }
      if (routeId === "long_novel") return { ...tab, label: "全书架构" }
    }
    if (tab.id === "units") {
      return {
        ...tab,
        label: routeId === "screenplay_sample" ? "已接受剧本" : "已接受正文",
      }
    }
    if (tab.id === "continuity" && routeId === "screenplay_sample")
      return { ...tab, label: "兑现与交接" }
    return tab
  })
}

function sectionFromPath(pathname: string): StoryBibleSection {
  const value = pathname.split("/").filter(Boolean).at(-1)
  return TABS.some((item) => item.id === value)
    ? value as StoryBibleSection
    : "overview"
}

function sectionCount(
  section: StoryBibleSection,
  summary: StoryBibleSummary | null,
) {
  if (!summary) return null
  if (section === "cast") return summary.character_count
  if (section === "structure") return summary.structure_count
  if (section === "units") return summary.accepted_unit_count
  if (section === "continuity") return summary.continuity_count
  return summary.source_artifact_count
}
