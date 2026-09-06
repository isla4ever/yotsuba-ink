import type { ComponentType } from "react"
import {
  ArrowUpRight,
  BookOpenText,
  CheckCircle2,
  CircleDotDashed,
  FileCheck2,
  GitBranch,
  Link2,
  LoaderCircle,
  Orbit,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react"
import type { CreationRouteId } from "../contracts/run"
import type {
  StoryBibleEntry,
  StoryBibleEntryStatus,
  StoryBibleSection,
  StoryBibleSummary,
} from "../contracts/storyBible"

export function StoryBibleMetrics({ summary }: { summary: StoryBibleSummary }) {
  const items = [
    {
      icon: ShieldCheck,
      label: "正式来源",
      value: summary.source_artifact_count,
    },
    { icon: Users, label: "人物", value: summary.character_count },
    { icon: GitBranch, label: "结构单元", value: summary.structure_count },
    {
      icon: FileCheck2,
      label: "已接受内容",
      value: summary.accepted_unit_count,
    },
  ]
  return (
    <section className="story-bible-metrics" aria-label="故事圣经摘要">
      {items.map(({ icon: Icon, label, value }) => (
        <div key={label}>
          <Icon size={13} />
          <span>{label}</span>
          <strong>{String(value).padStart(2, "0")}</strong>
        </div>
      ))}
    </section>
  )
}

export function StoryBibleLedger({
  hasMore,
  items,
  loadingMore,
  onLoadMore,
  onOpenSource,
  routeId,
  section,
  total,
}: {
  hasMore: boolean
  items: StoryBibleEntry[]
  loadingMore: boolean
  onLoadMore: () => void
  onOpenSource: (stageId: string) => void
  routeId: CreationRouteId
  section: StoryBibleSection
  total: number
}) {
  if (!items.length) {
    return (
      <StoryBibleEmpty
        icon={sectionIcon(section)}
        title={emptyCopy(section, routeId).title}
        detail={emptyCopy(section, routeId).detail}
      />
    )
  }
  return (
    <section className={`story-bible-ledger section-${section}`}>
      <header>
        <div>
          <span>{sectionEyebrow(section, routeId)}</span>
          <strong>{sectionTitle(section, routeId)}</strong>
        </div>
        <em>{total} 项可追溯记录</em>
      </header>

      {section === "overview" ? (
        <OverviewEntries items={items} onOpenSource={onOpenSource} />
      ) : section === "cast" ? (
        <CastEntries items={items} onOpenSource={onOpenSource} />
      ) : section === "units" ? (
        <AcceptedUnitEntries items={items} onOpenSource={onOpenSource} />
      ) : (
        <TrackEntries
          items={items}
          onOpenSource={onOpenSource}
          section={section}
        />
      )}

      {(hasMore || loadingMore) && (
        <footer className="story-bible-pagination">
          <span>
            已显示 {items.length} / {total}
          </span>
          <button type="button" disabled={loadingMore} onClick={onLoadMore}>
            {loadingMore && <LoaderCircle size={12} />}
            {loadingMore ? "正在读取" : "继续读取"}
          </button>
        </footer>
      )}
    </section>
  )
}

function OverviewEntries({ items, onOpenSource }: LedgerProps) {
  const fields = items.filter((item) => item.kind === "brief_field")
  const rules = items.filter((item) => item.kind === "world_rule")
  return (
    <div className="story-bible-overview-grid">
      <dl className="story-bible-definition-list">
        {fields.map((item) => (
          <div key={item.entry_ref}>
            <dt>{item.title}</dt>
            <dd>{item.body}</dd>
            <SourceButton item={item} onOpenSource={onOpenSource} />
          </div>
        ))}
      </dl>
      {rules.length > 0 && (
        <section className="story-bible-rules">
          <header>
            <Orbit size={13} />
            <strong>冻结世界规则</strong>
            <span>{rules.length}</span>
          </header>
          <ol>
            {rules.map((item, index) => (
              <li key={item.entry_ref}>
                <em>{String(index + 1).padStart(2, "0")}</em>
                <p>{item.body}</p>
              </li>
            ))}
          </ol>
        </section>
      )}
    </div>
  )
}

function CastEntries({ items, onOpenSource }: LedgerProps) {
  const characters = items.filter((item) => item.kind === "character")
  const relations = items.filter((item) => item.kind === "relationship")
  const names = new Map(
    characters.map((item) => [item.entry_ref, item.title] as const),
  )
  return (
    <div className="story-bible-cast-layout">
      <div className="story-bible-character-list">
        {characters.map((item, index) => (
          <article className="story-bible-character" key={item.entry_ref}>
            <div className={`story-bible-avatar tone-${index % 6}`}>
              {item.title.slice(0, 1)}
            </div>
            <div>
              <header>
                <strong>{item.title}</strong>
                <span>{item.entry_ref}</span>
                <StatusBadge status={item.status} />
              </header>
              <p>{item.body}</p>
              <dl>
                <div>
                  <dt>行动驱力</dt>
                  <dd>{item.detail}</dd>
                </div>
                <div>
                  <dt>变化范围</dt>
                  <dd>{item.tags.at(-1)}</dd>
                </div>
              </dl>
            </div>
            <SourceButton item={item} onOpenSource={onOpenSource} />
          </article>
        ))}
      </div>
      {relations.length > 0 && (
        <aside className="story-bible-relations">
          <header>
            <Link2 size={13} />
            <strong>关系压力</strong>
            <span>{relations.length}</span>
          </header>
          {relations.map((item) => (
            <article key={item.entry_ref}>
              <div>
                <strong>{nameFor(item.subject_refs[0], names)}</strong>
                <i />
                <strong>{nameFor(item.subject_refs[1], names)}</strong>
              </div>
              <p>{item.body}</p>
              <span>{item.detail}</span>
            </article>
          ))}
        </aside>
      )}
    </div>
  )
}

function TrackEntries({
  items,
  onOpenSource,
  section,
}: LedgerProps & {
  section: "structure" | "continuity"
}) {
  return (
    <div className={`story-bible-track track-${section}`}>
      {items.map((item, index) => (
        <article key={`${item.kind}:${item.entry_ref}`}>
          <div className="story-bible-track-mark" aria-hidden="true">
            <span>{String(item.ordinal ?? index + 1).padStart(2, "0")}</span>
            <i />
          </div>
          <div className="story-bible-track-copy">
            <header>
              <KindBadge item={item} />
              <StatusBadge status={item.status} />
              {item.parent_ref && <em>{item.parent_ref}</em>}
            </header>
            <h3>{item.title}</h3>
            {item.body && <p>{item.body}</p>}
            {item.detail && <blockquote>{item.detail}</blockquote>}
            <TagList item={item} />
          </div>
          <SourceButton item={item} onOpenSource={onOpenSource} />
        </article>
      ))}
    </div>
  )
}

function AcceptedUnitEntries({ items, onOpenSource }: LedgerProps) {
  return (
    <div className="story-bible-unit-list">
      {items.map((item, index) => (
        <article key={item.entry_ref}>
          <header>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <div>
              <strong>{item.title}</strong>
              <em>{item.entry_ref}</em>
            </div>
            <StatusBadge status={item.status} />
          </header>
          <p>{item.body}</p>
          <footer>
            <span>
              <BookOpenText size={11} />
              {item.detail}
            </span>
            <TagList item={item} />
            <SourceButton item={item} onOpenSource={onOpenSource} />
          </footer>
        </article>
      ))}
    </div>
  )
}

function SourceButton({
  item,
  onOpenSource,
}: {
  item: StoryBibleEntry
  onOpenSource: (stageId: string) => void
}) {
  return (
    <button
      type="button"
      className="story-bible-source"
      onClick={() => onOpenSource(item.source.stage_id)}
      title={`${item.source.source_path} · ${item.source.artifact_ref}`}
      aria-label={`查看${item.title}的来源阶段`}
    >
      <ArrowUpRight size={12} />
      <span>查看来源</span>
    </button>
  )
}

function TagList({ item }: { item: StoryBibleEntry }) {
  const tags = [...item.tags, ...item.promise_refs.map((ref) => `承诺 ${ref}`)]
  if (!tags.length) return null
  return (
    <div className="story-bible-tags">
      {tags.slice(0, 5).map((tag) => (
        <span key={tag}>{tag}</span>
      ))}
    </div>
  )
}

function KindBadge({ item }: { item: StoryBibleEntry }) {
  const tone = item.kind === "formal_fact" ? "handoff" : item.kind
  return (
    <span className={`story-bible-kind kind-${tone}`}>
      {kindLabel(item.kind)}
    </span>
  )
}

function StatusBadge({ status }: { status: StoryBibleEntryStatus }) {
  const tone = status === "verified" ? "committed" : status
  const Icon =
    status === "accepted" || status === "committed" || status === "verified"
      ? CheckCircle2
      : status === "open"
        ? CircleDotDashed
        : Sparkles
  return (
    <span className={`story-bible-status status-${tone}`}>
      <Icon size={10} />
      {statusLabel(status)}
    </span>
  )
}

type LedgerProps = {
  items: StoryBibleEntry[]
  onOpenSource: (stageId: string) => void
}

export function StoryBibleEmpty({
  detail,
  icon: Icon,
  title,
}: {
  detail: string
  icon: ComponentType<{ size?: number }>
  title: string
}) {
  return (
    <div className="story-bible-empty" role="status">
      <Icon size={22} />
      <strong>{title}</strong>
      <span>{detail}</span>
    </div>
  )
}

function sectionIcon(section: StoryBibleSection) {
  if (section === "cast") return Users
  if (section === "units") return FileCheck2
  if (section === "continuity") return Orbit
  return GitBranch
}

function sectionEyebrow(section: StoryBibleSection, routeId: CreationRouteId) {
  if (section === "overview") return "FROZEN PREMISE"
  if (section === "cast") return "SUBJECT REGISTRY"
  if (section === "units")
    return routeId === "screenplay_sample"
      ? "ACCEPTED SCENES"
      : "ACCEPTED PROSE"
  if (section === "continuity") return "TRACEABLE CONTINUITY"
  return routeId === "screenplay_sample"
    ? "BEAT / SCENE ORDER"
    : "STRUCTURE ORDER"
}

function sectionTitle(section: StoryBibleSection, routeId: CreationRouteId) {
  if (section === "overview") return "作品承诺与硬边界"
  if (section === "cast") return "人物主体与关系压力"
  if (section === "units")
    return routeId === "screenplay_sample" ? "已接受场次" : "已接受正文单元"
  if (section === "continuity") return "承诺、开放问题与交接"
  if (routeId === "screenplay_sample") return "决策节拍与可见场景"
  if (routeId === "short_novel") return "Story Map 与单元计划"
  return "Book / Part / Volume / Chapter"
}

function emptyCopy(section: StoryBibleSection, routeId: CreationRouteId) {
  if (section === "overview")
    return {
      title: "核心设定尚未提交",
      detail: "确认 Brief 后会显示作品承诺与硬边界。",
    }
  if (section === "cast")
    return {
      title: "人物注册表尚未提交",
      detail: "确认人物阶段后会显示主体与关系。",
    }
  if (section === "units")
    return {
      title:
        routeId === "screenplay_sample" ? "尚无已接受场次" : "尚无已接受正文",
      detail: "这里只读取顺序执行中已经接受的不可变版本。",
    }
  if (section === "continuity")
    return {
      title: "连续性记录尚未建立",
      detail: "规划阶段提交后才会出现可追溯交接。",
    }
  return {
    title: "结构尚未提交",
    detail: "当前路线的规划 Artifact 提交后会在这里按顺序展开。",
  }
}

function kindLabel(kind: StoryBibleEntry["kind"]) {
  const labels: Record<StoryBibleEntry["kind"], string> = {
    brief_field: "核心设定",
    world_rule: "世界规则",
    character: "人物",
    relationship: "关系",
    beat: "决策节拍",
    scene: "场景",
    story_anchor: "故事锚点",
    section_unit: "正文单元",
    part: "Book Part",
    volume: "卷",
    detail_window: "施工窗口",
    chapter_plan: "章节计划",
    accepted_unit: "已接受",
    promise: "承诺引用",
    open_question: "开放问题",
    handoff: "交接",
    ending_condition: "闭合条件",
    formal_fact: "正式事实",
  }
  return labels[kind]
}

function statusLabel(status: StoryBibleEntryStatus) {
  return {
    committed: "已提交",
    accepted: "已接受",
    tracked: "追踪中",
    open: "待闭合",
    planned: "规划中",
    verified: "已核验",
  }[status]
}

function nameFor(subjectRef: string | undefined, names: Map<string, string>) {
  return subjectRef ? names.get(subjectRef) || subjectRef : "未知主体"
}
