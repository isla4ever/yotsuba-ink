import {
  AlertTriangle,
  Archive,
  BookOpenText,
  CheckCircle2,
  CircleDotDashed,
  Database,
  FileCheck2,
  GitBranch,
  LoaderCircle,
  Quote,
} from "lucide-react"
import type {
  ResolvedStoryConflict,
  StoryBibleFactEntry,
  StoryBibleForeshadowEntry,
  StoryEpistemicStatus,
  StoryFactLifecycle,
} from "../contracts/storyBible"

export function StoryFactLedger({
  conflicts,
  currentCount,
  error,
  facts,
  hasMore,
  loadingMore,
  onLoadMore,
  subjectNames,
  total,
  wikiProjectedCount,
}: {
  conflicts: ResolvedStoryConflict[]
  currentCount: number
  error: string
  facts: StoryBibleFactEntry[]
  hasMore: boolean
  loadingMore: boolean
  onLoadMore: () => void
  subjectNames: Map<string, string>
  total: number
  wikiProjectedCount: number
}) {
  if (!facts.length) {
    return (
      <LedgerEmpty
        icon={Archive}
        title="暂无可读取的 Canon 事实"
        detail="事实必须先有正文 Evidence 并完成批准与写回，界面不会从章节文本自行猜测。"
      />
    )
  }
  return (
    <section className="story-ledger" aria-label="Canon 事实档案">
      <header>
        <span>Evidence → Canon → Wiki</span>
        <strong>
          {currentCount} 条当前事实 · {conflicts.length} 组冲突
        </strong>
      </header>

      <div className="story-ledger-metrics" aria-label="事实账本状态">
        <div>
          <Database size={14} />
          <span>Canon 事实</span>
          <strong>{total}</strong>
        </div>
        <div>
          <FileCheck2 size={14} />
          <span>Wiki 已投影</span>
          <strong>
            {wikiProjectedCount}
          </strong>
        </div>
        <div className={conflicts.length ? "warning" : "healthy"}>
          {conflicts.length ? (
            <AlertTriangle size={14} />
          ) : (
            <CheckCircle2 size={14} />
          )}
          <span>未解决冲突</span>
          <strong>{conflicts.length}</strong>
        </div>
      </div>

      {conflicts.length > 0 && (
        <div className="story-conflict-list" role="alert">
          <div className="story-conflict-heading">
            <AlertTriangle size={13} />
            <strong>需要人工判断的事实冲突</strong>
            <span>投影保留全部来源，不自动选择答案</span>
          </div>
          {conflicts.map((conflict) => (
            <article
              key={`${conflict.subject_id}:${conflict.property_key}`}
            >
              <div>
                <strong>{subjectLabel(conflict.subject_id, subjectNames)}</strong>
                <span>{propertyLabel(conflict.property_key)}</span>
              </div>
              <ul>
                {conflict.values.map((value) => (
                  <li key={value}>{value}</li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      )}

      <div className="story-fact-list">
        {facts.map((fact) => {
          const source = fact.evidence_sources[0]
          const excerpt = source?.quotes[0]
          return (
            <article
              className={`story-fact-row ${fact.is_current ? "current" : "historical"}`}
              key={fact.fact_id}
            >
              <div className="story-fact-status" aria-hidden="true">
                <span />
              </div>
              <div className="story-fact-copy">
                <div className="story-fact-kickers">
                  <em className={fact.is_current ? "current" : "historical"}>
                    {fact.is_current ? "当前" : "历史"}
                  </em>
                  <em>{EPISTEMIC_LABELS[fact.epistemic_status]}</em>
                  <em>{LIFECYCLE_LABELS[fact.lifecycle]}</em>
                  <span>
                    {subjectLabel(fact.subject_id, subjectNames)} ·{" "}
                    {propertyLabel(fact.property_key)}
                  </span>
                </div>
                <p>{fact.claim}</p>
                {fact.value && fact.value !== fact.claim && (
                  <div className="story-fact-value">当前值：{fact.value}</div>
                )}
                {excerpt && (
                  <blockquote className="story-evidence-excerpt">
                    <Quote size={11} />
                    <span>{excerpt}</span>
                  </blockquote>
                )}
                <footer>
                  <span>
                    <BookOpenText size={11} />
                    {chapterLabel(
                      fact.effective_from_chapter,
                      source?.chapter_id,
                    )}
                  </span>
                  <span>
                    <FileCheck2 size={11} />
                    Evidence {fact.evidence_sources.length} 条
                  </span>
                  <span
                    className={
                      fact.wiki_transaction_ids.length ? "projected" : "pending"
                    }
                  >
                    <Database size={11} />
                    {fact.wiki_transaction_ids.length
                      ? "Wiki 已投影"
                      : "Wiki 待投影"}
                  </span>
                  {fact.missing_evidence_refs.length > 0 && (
                    <span className="missing">
                      <AlertTriangle size={11} />
                      缺少 {fact.missing_evidence_refs.length} 条来源
                    </span>
                  )}
                </footer>
              </div>
            </article>
          )
        })}
      </div>
      <LedgerPagination
        error={error}
        hasMore={hasMore}
        loaded={facts.length}
        loading={loadingMore}
        onLoadMore={onLoadMore}
        total={total}
      />
    </section>
  )
}

export function StoryForeshadowLedger({
  error,
  hasMore,
  items,
  loadingMore,
  onLoadMore,
  resolvedCount,
  total,
  trackingCount,
}: {
  error: string
  hasMore: boolean
  items: StoryBibleForeshadowEntry[]
  loadingMore: boolean
  onLoadMore: () => void
  resolvedCount: number
  total: number
  trackingCount: number
}) {
  if (!items.length) {
    return (
      <LedgerEmpty
        icon={CircleDotDashed}
        title="暂无可读取的伏笔台账"
        detail="此区只接收正文 Evidence 驱动的提案；没有证据时不会从细纲或正文自行推断伏笔。"
      />
    )
  }
  return (
    <section className="story-ledger" aria-label="伏笔 Evidence 台账">
      <header>
        <span>正文 Evidence 生命周期</span>
        <strong>
          {trackingCount} 条跟踪中 · {resolvedCount} 条已回收
        </strong>
      </header>
      <div className="story-foreshadow-list">
        {items.map((item, index) => {
          const excerpt = item.quotes[0]
          const status = WRITEBACK_LABELS[item.writeback_status]
          return (
            <article
              className={`story-foreshadow-row lifecycle-${item.lifecycle}`}
              key={item.evidence_id}
            >
              <div className="story-foreshadow-track" aria-hidden="true">
                <span>{String(index + 1).padStart(2, "0")}</span>
                <i />
              </div>
              <div className="story-foreshadow-copy">
                <div className="story-fact-kickers">
                  <em>{LIFECYCLE_LABELS[item.lifecycle]}</em>
                  <em>{EPISTEMIC_LABELS[item.epistemic_status]}</em>
                  <span>{chapterLabel(item.effective_from_chapter, item.chapter_id)}</span>
                </div>
                <p>{item.claim}</p>
                {excerpt && (
                  <blockquote className="story-evidence-excerpt">
                    <Quote size={11} />
                    <span>{excerpt}</span>
                  </blockquote>
                )}
                <footer>
                  <span className={item.writeback_status}>
                    {item.writeback_status === "wiki_projected" ? (
                      <CheckCircle2 size={11} />
                    ) : item.writeback_status === "canon_committed" ? (
                      <Database size={11} />
                    ) : (
                      <FileCheck2 size={11} />
                    )}
                    {status}
                  </span>
                  {item.resolves_fact_ids.length > 0 && (
                    <span>
                      <GitBranch size={11} />
                      回收 {item.resolves_fact_ids.length} 条前置事实
                    </span>
                  )}
                  {item.supersedes_fact_ids.length > 0 && (
                    <span>
                      <GitBranch size={11} />
                      更新 {item.supersedes_fact_ids.length} 条前置事实
                    </span>
                  )}
                </footer>
              </div>
            </article>
          )
        })}
      </div>
      <LedgerPagination
        error={error}
        hasMore={hasMore}
        loaded={items.length}
        loading={loadingMore}
        onLoadMore={onLoadMore}
        total={total}
      />
    </section>
  )
}

function LedgerPagination({
  error,
  hasMore,
  loaded,
  loading,
  onLoadMore,
  total,
}: {
  error: string
  hasMore: boolean
  loaded: number
  loading: boolean
  onLoadMore: () => void
  total: number
}) {
  if (!hasMore && !error) return null
  return (
    <footer className="story-ledger-pagination">
      <span>
        已显示 {loaded} / {total}
      </span>
      {error && <em role="alert">{error}</em>}
      {hasMore && (
        <button type="button" disabled={loading} onClick={onLoadMore}>
          {loading && <LoaderCircle size={12} aria-hidden="true" />}
          {loading ? "正在读取" : error ? "重试加载" : "加载更多"}
        </button>
      )}
    </footer>
  )
}

function LedgerEmpty({
  detail,
  icon: Icon,
  title,
}: {
  detail: string
  icon: typeof Archive
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

const EPISTEMIC_LABELS: Record<StoryEpistemicStatus, string> = {
  fact: "确定事实",
  rumour: "传闻",
  belief: "人物认知",
  reveal: "揭示",
  refutation: "证伪",
}

const LIFECYCLE_LABELS: Record<StoryFactLifecycle, string> = {
  active: "跟踪中",
  supersedes: "已更新",
  resolves: "已回收",
  contradicted: "已否定",
}

const WRITEBACK_LABELS: Record<
  StoryBibleForeshadowEntry["writeback_status"],
  string
> = {
  evidence_only: "Evidence 待写回",
  canon_committed: "Canon 已提交",
  wiki_projected: "Wiki 已投影",
}

function subjectLabel(subjectId: string, subjectNames: Map<string, string>) {
  if (!subjectId || subjectId === "story") return "全书事实"
  return subjectNames.get(subjectId) ?? "未识别主体"
}

function propertyLabel(propertyKey: string) {
  if (!propertyKey || propertyKey.startsWith("claim:")) return "叙事声明"
  const known: Record<string, string> = {
    identity: "身份",
    life_status: "生存状态",
    location: "位置",
    relationship: "关系",
    possession: "持有物",
    knowledge: "已知信息",
  }
  return known[propertyKey] ?? propertyKey.split("_").join(" · ")
}

function chapterLabel(chapter: number | null, sourceId = "") {
  const sourceNumber = sourceId.match(/(?:chapter|ch)[-:]?(\d+)/i)?.[1]
  const number = chapter ?? (sourceNumber ? Number(sourceNumber) : 0)
  return number > 0 ? `第 ${number} 章` : "章节来源已记录"
}
