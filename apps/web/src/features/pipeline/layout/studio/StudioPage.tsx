import { useState, useCallback, useEffect } from "react"
import { Plus, BookOpen, TrendingUp, Clock, Zap, RefreshCw } from "lucide-react"
import { useApp } from "../../state/PipelineAppProvider"
import type { Project } from "../../contracts/app"
import { useStudioProjects } from "../../state/useStudioProjects"
import { BookLoader } from "../BookLoader"
import { useLoadingPresence } from "../useLoadingPresence"

const STAGE_LABELS: Record<string, string> = {
  brief: "简报",
  spine: "脊柱",
  cast: "角色",
  volumes: "卷册",
  detail: "细纲",
  text: "正文",
  cover: "封面",
  export: "导出",
}
const STAGE_NUM: Record<string, number> = {
  brief: 1,
  spine: 2,
  cast: 3,
  volumes: 4,
  detail: 5,
  text: 6,
  cover: 7,
  export: 8,
}

/* ─── Uniform book dimensions — slim tall spines (ratio ~0.175 desktop) ─── */
const DESK_W = 56 // px — desktop spine width  (56/320 ≈ 0.175)
const DESK_H = 320 // px — desktop spine height
const MOB_W = 42 // px — mobile spine width   (42/220 ≈ 0.19)
const MOB_H = 220 // px — mobile spine height

/* ─── Shelf layout constants ─────────────────────────────────────────────── */
const PLANK_H = 20
const PLINTH_D = 52 // desktop plinth height
const PLINTH_M = 36 // mobile  plinth height
const TOP_RAIL = 12
const LIFT = 6
const LIFT_CLR = 16 // headroom above books for the lift

/* ─── Inline sparklines ──────────────────────────────────────────────────── */
function LineSpark({
  data,
  color,
  w = 44,
  h = 14,
}: {
  data: number[]
  color: string
  w?: number
  h?: number
}) {
  const max = Math.max(...data),
    min = Math.min(...data)
  const range = max - min || 1
  const pts = data
    .map(
      (v, i) =>
        `${(i / (data.length - 1)) * w},${h - 1 - ((v - min) / range) * (h - 3)}`,
    )
    .join(" ")
  const lastX = w
  const lastY = h - 1 - ((data[data.length - 1] - min) / range) * (h - 3)
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      style={{ display: "block", overflow: "visible" }}
    >
      <polyline
        points={pts}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.5"
      />
      <circle cx={lastX} cy={lastY} r="2" fill={color} opacity="0.75" />
    </svg>
  )
}

function BarSpark({
  data,
  color,
  w = 36,
  h = 14,
}: {
  data: number[]
  color: string
  w?: number
  h?: number
}) {
  const gap = 2
  const maxBars = Math.max(1, Math.floor((w + gap) / (gap + 2)))
  const visible = data.slice(-maxBars)
  const max = Math.max(1, ...visible)
  const n = visible.length
  const bw = (w - gap * (n - 1)) / n
  return (
    <svg
      width={w}
      height={h}
      viewBox={`0 0 ${w} ${h}`}
      style={{ display: "block" }}
    >
      {visible.map((v, i) => {
        const bh = Math.max(2, (v / max) * h)
        return (
          <rect
            key={i}
            x={i * (bw + gap)}
            y={h - bh}
            width={bw}
            height={bh}
            rx="1"
            fill={color}
            opacity={i === n - 1 ? 0.8 : 0.3}
          />
        )
      })}
    </svg>
  )
}

/* ─── Data strip ─────────────────────────────────────────────────────────── */
function StatsStrip({ books }: { books: Project[] }) {
  const active = books.filter((book) => book.status === "active").length
  const totalWords = books.reduce((sum, book) => sum + book.wordCount, 0)
  const trend = books.length
    ? [0, ...books.map((book) => book.wordCount / 10_000)]
    : [0, 0]
  const bars = books.length ? books.map((book) => book.wordCount / 10_000) : [0]
  const latest = books
    .map((book) => Date.parse(book.updatedAt))
    .filter(Number.isFinite)
    .sort((a, b) => b - a)[0]
  return (
    <div className="border-b border-hairline bg-surface shrink-0 px-6 py-2 flex items-center gap-6 flex-wrap">
      {/* 活跃项目 */}
      <div className="flex items-center gap-2">
        <BookOpen size={11} className="text-mint shrink-0" />
        <span className="text-[10px] text-fog">活跃项目</span>
        <span className="text-[11px] font-mono font-semibold text-ink">
          {active}
        </span>
      </div>

      {/* 总字数 with line sparkline */}
      <div className="flex items-center gap-2">
        <TrendingUp size={11} className="text-blue shrink-0" />
        <span className="text-[10px] text-fog">总字数</span>
        <LineSpark data={trend} color="var(--color-mint)" />
        <span className="text-[11px] font-mono font-semibold text-ink">
          {formatWords(totalWords)}
        </span>
      </div>

      {/* 本月生成 with bar sparkline */}
      <div className="flex items-center gap-2">
        <Zap size={11} className="text-mint shrink-0" />
        <span className="text-[10px] text-fog">本月生成</span>
        <BarSpark data={bars} color="var(--action-primary)" />
        <span className="text-[11px] font-mono font-semibold text-ink">
          {formatWords(totalWords)}
        </span>
      </div>

      {/* 最近活跃 */}
      <div className="flex items-center gap-2">
        <Clock size={11} className="text-ash shrink-0" />
        <span className="text-[10px] text-fog">最近活跃</span>
        <span className="text-[11px] font-medium text-ink">
          {latest ? formatRecent(latest) : "暂无"}
        </span>
      </div>
    </div>
  )
}

/* ─── Collision-aware tooltip ────────────────────────────────────────────── */
interface TipData {
  book: Project
  anchorX: number
  anchorY: number
}

const TIP_W = 208
const TIP_H = 128
const HDR_H = 50
const ARROW_SZ = 6

function BookTooltip({ data }: { data: TipData }) {
  const { book, anchorX, anchorY } = data
  const hue = book.coverHue
  const pct = Math.min(
    100,
    Math.round((book.wordCount / book.targetWordCount) * 100),
  )
  const stN = STAGE_NUM[book.currentStage] ?? 1
  const wc =
    book.wordCount >= 10000
      ? `${(book.wordCount / 10000).toFixed(1)}万字`
      : `${book.wordCount.toLocaleString()}字`

  const vw = typeof window !== "undefined" ? window.innerWidth : 1280

  let left = anchorX - TIP_W / 2
  let top = anchorY - TIP_H - ARROW_SZ - 4

  left = Math.max(8, Math.min(left, vw - TIP_W - 8))
  top = Math.max(HDR_H + 8, top)

  const arrowX = Math.max(12, Math.min(anchorX - left, TIP_W - 12))

  return (
    <div
      className="fixed z-[9999] pointer-events-none animate-fade-in"
      style={{ left, top, width: TIP_W }}
    >
      <div className="bg-elev border border-hairline rounded-lg shadow-2xl p-3">
        <div className="text-sm font-semibold text-ink mb-0.5 font-serif">
          《{book.title}》
        </div>
        <div className="text-[10px] text-fog mb-2">
          {book.genre} · {book.subtitle}
        </div>
        <div className="flex items-center justify-between mb-1.5">
          <span className="text-[10px] text-ash">{wc}</span>
          <span className="text-[10px] font-mono text-fog">{pct}%</span>
        </div>
        <div className="h-1 bg-ghost rounded-full overflow-hidden mb-2">
          <div
            className="h-full rounded-full"
            style={{ width: `${pct}%`, background: `hsl(${hue} 55% 55%)` }}
          />
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-ash">
            阶段 {stN}·{STAGE_LABELS[book.currentStage]}
          </span>
          <span className="text-[10px] text-fog">{book.updatedAt}</span>
        </div>
      </div>
      <div
        style={{
          position: "absolute",
          top: "100%",
          left: arrowX,
          width: 0,
          height: 0,
          borderLeft: `${ARROW_SZ}px solid transparent`,
          borderRight: `${ARROW_SZ}px solid transparent`,
          borderTop: `${ARROW_SZ}px solid var(--bg-elev)`,
          transform: "translateX(-50%)",
        }}
      />
    </div>
  )
}

/* ─── Book spine ─────────────────────────────────────────────────────────── */
interface SpineProps {
  project: Project
  bw: number
  bh: number
  dragging: boolean
  dropTarget: boolean
  onClick: () => void
  onDragStart: () => void
  onDragOver: (e: React.DragEvent) => void
  onDrop: () => void
  onDragEnd: () => void
  onHoverEnter: (e: React.MouseEvent) => void
  onHoverLeave: () => void
}

function BookSpine(props: SpineProps) {
  const {
    project,
    bw,
    bh,
    dragging,
    dropTarget,
    onClick,
    onDragStart,
    onDragOver,
    onDrop,
    onDragEnd,
    onHoverEnter,
    onHoverLeave,
  } = props
  const [hovered, setHovered] = useState(false)
  const hue = project.coverHue
  const pct = Math.min(
    100,
    Math.round((project.wordCount / project.targetWordCount) * 100),
  )
  const stN = STAGE_NUM[project.currentStage] ?? 1

  return (
    <div
      className="relative flex-shrink-0 select-none focus-visible:outline-2 focus-visible:outline-offset-2"
      style={{ width: bw, zIndex: hovered ? 20 : 1 }}
      onMouseEnter={(e) => {
        setHovered(true)
        onHoverEnter(e)
      }}
      onMouseLeave={() => {
        setHovered(false)
        onHoverLeave()
      }}
      onClick={onClick}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDrop={onDrop}
      onDragEnd={onDragEnd}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick()
      }}
    >
      {/* Drag insertion indicator */}
      {dropTarget && !dragging && (
        <div
          className="absolute left-0 top-0 bottom-0 w-0.5 z-30 rounded-full"
          style={{
            background: "var(--action-primary)",
            boxShadow: "0 0 8px var(--action-primary)",
          }}
        />
      )}

      {/* Spine body */}
      <div
        className="relative rounded-t-sm cursor-pointer overflow-hidden"
        style={{
          height: bh,
          opacity: dragging ? 0.25 : 1,
          willChange: "transform",
          transform: hovered ? `translateY(-${LIFT}px)` : "translateY(0)",
          transition:
            "transform 200ms cubic-bezier(0.25,0.46,0.45,0.94), box-shadow 220ms ease, opacity 160ms ease, background 200ms ease",
          background: hovered
            ? `linear-gradient(to right, hsl(${hue} 42% 30%), hsl(${hue} 32% 23%))`
            : `linear-gradient(to right, hsl(${hue} 30% 21%), hsl(${hue} 22% 15%))`,
          boxShadow: hovered
            ? `0 ${LIFT + 6}px 22px rgba(0,0,0,0.65), inset 1px 0 0 hsl(${hue} 65% 60% / 0.28), inset -1px 0 0 rgba(255,255,255,0.05), 0 0 0 1px hsl(${hue} 40% 28% / 0.18)`
            : `2px 0 8px rgba(0,0,0,0.45), inset -1px 0 0 rgba(255,255,255,0.04)`,
        }}
      >
        {/* Genre color cap */}
        <div
          className="absolute top-0 left-0 right-0"
          style={{
            height: 3,
            background:
              project.status === "active"
                ? `hsl(${hue} 72% 56%)`
                : `hsl(${hue} 32% 38%)`,
          }}
        />

        {/* Stage badge */}
        <div className="absolute top-3 left-0 right-0 flex justify-center">
          <div
            className="w-5 h-5 rounded-full flex items-center justify-center font-mono text-[10.5px] font-bold"
            style={{
              background: `hsl(${hue} 46% ${hovered ? "34%" : "26%"})`,
              color: `hsl(${hue} 80% 84%)`,
              boxShadow: hovered ? `0 0 7px hsl(${hue} 50% 34%)` : "none",
              transition: "box-shadow 220ms ease, background 200ms ease",
            }}
          >
            {stN}
          </div>
        </div>

        {/* Vertical title — no clipping, text fits uniform height */}
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ paddingTop: 36, paddingBottom: 18 }}
        >
          <span
            className="font-serif leading-tight"
            style={{
              writingMode: "vertical-rl",
              textOrientation: "mixed",
              fontSize: bw >= 64 ? 13 : 11,
              letterSpacing: "0.12em",
              maxHeight: bh - 58,
              overflow: "hidden",
              color: hovered
                ? "rgba(255,255,255,0.92)"
                : "rgba(255,255,255,0.60)",
              transition: "color 200ms ease",
              userSelect: "none",
            }}
          >
            {project.title}
          </span>
        </div>

        {/* Edge depth gradient */}
        <div
          className="absolute inset-0 pointer-events-none"
          style={{
            background:
              "linear-gradient(to right, rgba(0,0,0,0.18) 0%, transparent 22%, transparent 78%, rgba(0,0,0,0.10) 100%)",
          }}
        />

        {/* Progress strip */}
        <div
          className="absolute bottom-0 left-0 right-0 overflow-hidden"
          style={{ height: 4 }}
        >
          <div className="absolute inset-0 bg-black/30" />
          <div
            className="absolute inset-y-0 left-0 transition-all duration-700"
            style={{ width: `${pct}%`, background: `hsl(${hue} 68% 52%)` }}
          />
        </div>
      </div>
    </div>
  )
}

/* ─── New book slot ──────────────────────────────────────────────────────── */
function NewBookSlot({
  onClick,
  bw,
  bh,
}: {
  onClick: () => void
  bw: number
  bh: number
}) {
  const [hovered, setHovered] = useState(false)
  return (
    <div
      className="relative flex-shrink-0 cursor-pointer select-none"
      style={{ width: bw }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      onClick={onClick}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") onClick()
      }}
    >
      <div
        className="rounded-t-sm border border-dashed flex items-center justify-center"
        style={{
          height: bh,
          borderColor: hovered ? "var(--action-primary)" : "var(--border-hl)",
          background: hovered ? "var(--action-primary-bg)" : "rgba(0,0,0,0.12)",
          transform: hovered ? `translateY(-${LIFT}px)` : "none",
          transition:
            "transform 200ms cubic-bezier(0.25,0.46,0.45,0.94), background 200ms ease, border-color 200ms ease",
        }}
      >
        <Plus
          size={bw >= 64 ? 16 : 13}
          style={{
            color: hovered ? "var(--action-primary)" : "var(--text-fog)",
            transition: "color 200ms ease",
          }}
        />
      </div>
    </div>
  )
}

/* ─── Dimensional bookshelf ──────────────────────────────────────────────── */
interface ShelfProps {
  books: Project[]
  setBooks: (b: Project[]) => void
  onOpen: (p: Project) => void
  onNewBook: () => void
  mobile: boolean
}

function Bookshelf({ books, setBooks, onOpen, onNewBook, mobile }: ShelfProps) {
  const [dragIdx, setDragIdx] = useState<number | null>(null)
  const [dropIdx, setDropIdx] = useState<number | null>(null)
  const [tooltip, setTooltip] = useState<TipData | null>(null)

  const BW = mobile ? MOB_W : DESK_W
  const BH = mobile ? MOB_H : DESK_H
  const PLINTH = mobile ? PLINTH_M : PLINTH_D

  // Row height: book height + headroom for lift — books stay within this, no clipping
  const rowH = BH + LIFT_CLR

  const handleHoverEnter = useCallback(
    (p: Project) => (e: React.MouseEvent) => {
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
      setTooltip({
        book: p,
        anchorX: rect.left + rect.width / 2,
        anchorY: rect.top,
      })
    },
    [],
  )

  const handleHoverLeave = useCallback(() => setTooltip(null), [])

  const handleDrop = (targetIdx: number) => {
    if (dragIdx === null || dragIdx === targetIdx) {
      setDragIdx(null)
      setDropIdx(null)
      return
    }
    const next = [...books]
    const [item] = next.splice(dragIdx, 1)
    next.splice(targetIdx, 0, item)
    setBooks(next)
    setDragIdx(null)
    setDropIdx(null)
    setTooltip(null)
  }

  return (
    <div
      className="flex-1 relative min-h-0 rounded-xl"
      style={{ border: "1px solid var(--border-ghost)" }}
    >
      {/* Collision-safe fixed tooltip */}
      {tooltip && dragIdx === null && <BookTooltip data={tooltip} />}

      {/* Chamber wall */}
      <div
        className="absolute inset-0 rounded-xl pointer-events-none"
        style={{
          background:
            "linear-gradient(168deg, hsl(25 12% 11%) 0%, hsl(24 8% 8%) 100%)",
        }}
      />

      {/* Wood grain overlay */}
      <div
        className="absolute inset-0 rounded-xl pointer-events-none"
        style={{
          backgroundImage:
            "repeating-linear-gradient(90deg, transparent 0px, transparent 54px, rgba(0,0,0,0.015) 54px, rgba(0,0,0,0.015) 55px)",
        }}
      />

      {/* Top rail */}
      <div
        className="absolute top-0 left-0 right-0 rounded-t-xl pointer-events-none"
        style={{
          height: TOP_RAIL,
          background:
            "linear-gradient(to bottom, hsl(30 18% 24%), hsl(30 12% 16%))",
          borderBottom: "1px solid rgba(0,0,0,0.35)",
        }}
      />

      {/* Books row — absolute, bottom-anchored above plank
          Books all share uniform BH, so lift stays within rowH = BH + LIFT_CLR */}
      <div
        style={{
          position: "absolute",
          bottom: PLANK_H + PLINTH,
          left: 0,
          right: 0,
          height: rowH,
          overflowX: "auto",
          overflowY: "auto", // forced by browser when overflow-x != visible
          display: "flex",
          alignItems: "flex-end",
          gap: 4,
          paddingLeft: 20,
          paddingRight: 20,
          paddingTop: LIFT_CLR,
          scrollbarWidth: "thin",
          // @ts-ignore
          scrollbarColor: "rgba(255,255,255,0.06) transparent",
        }}
        onDragOver={(e) => e.preventDefault()}
      >
        {/* Left bookend */}
        <div
          className="flex-shrink-0 self-end"
          style={{
            width: 8,
            height: BH - 10,
            background:
              "linear-gradient(to right, hsl(30 20% 20%), hsl(30 16% 27%))",
            borderRadius: "2px 0 0 2px",
            boxShadow: "2px 0 6px rgba(0,0,0,0.55)",
          }}
        />

        {books.map((p, i) => (
          <BookSpine
            key={p.id}
            project={p}
            bw={BW}
            bh={BH}
            dragging={dragIdx === i}
            dropTarget={dropIdx === i}
            onClick={() => {
              if (dragIdx === null) onOpen(p)
            }}
            onDragStart={() => {
              setDragIdx(i)
              setTooltip(null)
            }}
            onDragOver={(e) => {
              e.preventDefault()
              setDropIdx(i)
            }}
            onDrop={() => handleDrop(i)}
            onDragEnd={() => {
              setDragIdx(null)
              setDropIdx(null)
            }}
            onHoverEnter={handleHoverEnter(p)}
            onHoverLeave={handleHoverLeave}
          />
        ))}

        <NewBookSlot onClick={onNewBook} bw={BW} bh={BH} />

        {/* Right bookend — slight lean */}
        <div
          className="flex-shrink-0 self-end"
          style={{
            width: 7,
            height: BH - 32,
            background:
              "linear-gradient(to left, hsl(30 20% 22%), hsl(30 16% 27%))",
            borderRadius: "0 2px 2px 0",
            boxShadow: "-2px 0 5px rgba(0,0,0,0.45)",
            transform: "skewY(-2.5deg)",
            transformOrigin: "bottom",
          }}
        />

        {dragIdx === null && (
          <div className="absolute bottom-1 right-5 text-[10px] text-white/12 pointer-events-none select-none">
            拖拽排序
          </div>
        )}
      </div>

      {/* Shelf plank */}
      <div
        style={{
          position: "absolute",
          bottom: PLINTH,
          left: 0,
          right: 0,
          height: PLANK_H,
          background:
            "linear-gradient(to bottom, hsl(30 22% 26%), hsl(30 15% 16%))",
          boxShadow:
            "0 6px 24px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.07), inset 0 -1px 0 rgba(0,0,0,0.5)",
        }}
      />

      {/* Compact plinth base */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          right: 0,
          height: PLINTH,
          borderRadius: "0 0 10px 10px",
          background:
            "linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.28) 100%)",
          borderTop: "1px solid rgba(0,0,0,0.4)",
        }}
      />
    </div>
  )
}

/* ─── Main Studio view ───────────────────────────────────────────────────── */
export default function StudioPage() {
  const {
    setCreationWizardDraft,
    setRoute,
    setSelectedTemplateId,
    openProject,
  } = useApp()
  const { error, loading, projects, refresh, reorder } = useStudioProjects()
  const [books, setBooks] = useState<Project[]>([])
  const shelfLoad = useLoadingPresence(loading && books.length === 0)

  useEffect(() => setBooks(projects), [projects])

  const openBook = useCallback(
    (p: Project) => openProject(p, p.currentStage),
    [openProject],
  )
  const newBook = useCallback(() => {
    setSelectedTemplateId(null)
    setCreationWizardDraft(null)
    setRoute("planning")
  }, [setCreationWizardDraft, setRoute, setSelectedTemplateId])
  const orderBooks = useCallback(
    (next: Project[]) => {
      setBooks(next)
      void reorder(next)
    },
    [reorder],
  )

  return (
    <div className="flex-1 overflow-hidden flex flex-col bg-base page-in">
      {/* Page heading + action */}
      <div className="border-b border-hairline bg-surface px-6 py-3 shrink-0 flex items-center justify-between gap-4">
        <div>
          <h1 className="text-sm font-semibold text-ink leading-tight">
            创作台 · 作品库
          </h1>
          <p className="text-[11px] text-fog">
            管理剧本样片、短中篇与长篇创作项目
          </p>
        </div>
        <button className="btn btn-action text-xs shrink-0" onClick={newBook}>
          <Plus size={13} /> 新建作品
        </button>
      </div>

      {/* Data strip — always visible, above bookshelf, with sparklines */}
      <StatsStrip books={books} />

      {error && (
        <div className="mx-5 mt-3 banner-warning justify-between" role="alert">
          <span>{error}</span>
          <button
            className="btn btn-ghost text-xs py-1"
            onClick={() => void refresh()}
            type="button"
          >
            <RefreshCw size={12} /> 重试
          </button>
        </div>
      )}

      {/* Bookshelf content area */}
      <div className="flex-1 overflow-hidden flex flex-col px-5 py-4 min-h-0">
        {/* Label row */}
        <div className="flex items-center gap-2 mb-3 shrink-0">
          <h2 className="text-xs font-semibold text-ink">书架</h2>
          <span className="badge badge-ash">
            {loading ? "读取中" : `${books.length} 部`}
          </span>
          <span className="text-[10.5px] text-fog">· 点击开启 · 拖拽排序</span>
        </div>

        {shelfLoad.visible ? (
          <BookLoader
            phase={shelfLoad.exiting ? "exit" : "enter"}
            variant="compact"
            label="正在整理作品书架"
            detail="同步作品、Run 摘要与书架顺序"
          />
        ) : (
          <>
            {/* Desktop shelf */}
            <div className="hidden md:flex flex-col flex-1 min-h-0">
              <Bookshelf
                books={books}
                setBooks={orderBooks}
                onOpen={openBook}
                onNewBook={newBook}
                mobile={false}
              />
            </div>

            {/* Mobile shelf — horizontal scroll, uniform smaller spines */}
            <div className="md:hidden flex flex-col flex-1 min-h-0">
              <Bookshelf
                books={books}
                setBooks={orderBooks}
                onOpen={openBook}
                onNewBook={newBook}
                mobile={true}
              />
            </div>
          </>
        )}
      </div>
    </div>
  )
}

function formatWords(words: number) {
  return words >= 10_000
    ? `${(words / 10_000).toFixed(1)}万`
    : words.toLocaleString("zh-CN")
}

function formatRecent(timestamp: number) {
  const date = new Date(timestamp)
  const today = new Date()
  if (date.toDateString() === today.toDateString()) return "今天"
  return date.toLocaleDateString("zh-CN", { month: "2-digit", day: "2-digit" })
}
