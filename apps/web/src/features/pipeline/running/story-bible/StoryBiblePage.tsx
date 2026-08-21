import { useEffect, useMemo, useState, type CSSProperties } from "react"
import {
  Archive,
  BookMarked,
  CircleDotDashed,
  Globe2,
  Link2,
  ShieldCheck,
  Users,
} from "lucide-react"
import { useApp } from "../../state/PipelineAppProvider"
import {
  parseCharacterBibleArtifact,
  parseStoryBriefArtifact,
  type CharacterSubject,
} from "@/features/pipeline/contracts/artifacts"
import { BookLoader } from "@/features/pipeline/layout/BookLoader"
import { useLoadingPresence } from "@/features/pipeline/layout/useLoadingPresence"
import { CHARACTER_KIND_META } from "@/features/pipeline/lib/characterGraph"
import {
  StoryFactLedger,
  StoryForeshadowLedger,
} from "@/features/pipeline/running/StoryBibleLedgers"
import { useStoryBible } from "@/features/pipeline/state/useStoryBible"

type BibleTab = "cast" | "world" | "foreshadow" | "facts"

const TABS: Array<{ id: BibleTab; label: string; icon: typeof Users }> = [
  { id: "cast", label: "人物", icon: Users },
  { id: "world", label: "世界规则", icon: Globe2 },
  { id: "foreshadow", label: "伏笔台账", icon: CircleDotDashed },
  { id: "facts", label: "事实档案", icon: Archive },
]

export default function StoryBiblePage() {
  const {
    activeProject,
    activeProjectId,
    activeRun,
    runArtifactError,
    runArtifactLoading,
    runArtifacts,
    runLoading,
  } = useApp()
  const [tab, setTab] = useState<BibleTab>(() =>
    tabFromPath(window.location.pathname),
  )
  const cast = useMemo(
    () => parseCharacterBibleArtifact(runArtifacts.cast?.payload),
    [runArtifacts.cast],
  )
  const brief = useMemo(
    () => parseStoryBriefArtifact(runArtifacts.brief?.payload),
    [runArtifacts.brief],
  )
  const storyBible = useStoryBible(
    activeRun?.definition.run_id ?? "",
    activeRun?.read_model.updated_at ?? "",
  )
  const subjectNames = useMemo(
    () =>
      new Map(
        (cast.artifact?.subjects ?? []).map((subject) => [
          subject.id,
          subject.name,
        ]),
      ),
    [cast.artifact?.subjects],
  )
  const loading =
    runLoading ||
    (runArtifactLoading && !runArtifacts.cast && !runArtifacts.brief)
  const initialLoad = useLoadingPresence(loading)
  const foreshadowLoad = useLoadingPresence(
    tab === "foreshadow" && storyBible.foreshadows.status === "loading",
  )
  const factLoad = useLoadingPresence(
    tab === "facts" && storyBible.facts.status === "loading",
  )

  useEffect(() => {
    const syncTab = () => setTab(tabFromPath(window.location.pathname))
    window.addEventListener("popstate", syncTab)
    return () => window.removeEventListener("popstate", syncTab)
  }, [])

  const selectTab = (next: BibleTab) => {
    setTab(next)
    const query = activeProjectId
      ? `?project=${encodeURIComponent(activeProjectId)}`
      : ""
    window.history.pushState(null, "", `/bible/${next}${query}`)
  }

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在整理故事圣经"
        detail="同步人物、世界规则与正文事实投影"
      />
    )
  }

  if (!activeRun) {
    return (
      <BibleEmpty
        icon={BookMarked}
        title="故事圣经尚未建立"
        detail="作品启动 Run 并确认 Brief 后，这里才会出现正式投影。"
      />
    )
  }

  const castError = !cast.artifact ? cast.error : ""
  const briefError = !brief.artifact ? brief.error : ""

  return (
    <div className="story-bible-screen page-in">
      <header className="story-bible-header stage-aura">
        <div className="story-bible-identity">
          <BookMarked size={15} />
          <div>
            <strong>故事圣经</strong>
            <span>
              《{activeProject?.title || brief.artifact?.title || "当前作品"}》
              · 全书只读投影
            </span>
          </div>
        </div>
        <div className="story-bible-authority">
          <ShieldCheck size={12} />
          正式 Artifact / Evidence / Canon
        </div>
      </header>

      <nav className="story-bible-tabs" aria-label="故事圣经分类">
        {TABS.map((item) => {
          const Icon = item.icon
          return (
            <button
              key={item.id}
              type="button"
              className={tab === item.id ? "active" : ""}
              aria-current={tab === item.id ? "page" : undefined}
              onClick={() => selectTab(item.id)}
            >
              <Icon size={13} />
              {item.label}
            </button>
          )
        })}
      </nav>

      <main className="story-bible-content">
        {runArtifactError && (
          <div className="banner-warning" role="alert">
            {runArtifactError}
          </div>
        )}
        {storyBible.error && (
          <div className="banner-warning" role="alert">
            {storyBible.error}
          </div>
        )}

        {tab === "cast" &&
          (cast.artifact ? (
            <CharacterLedger
              subjects={cast.artifact.subjects}
              relationCounts={relationCountBySubject(cast.artifact.relations)}
            />
          ) : (
            <BibleEmpty
              icon={Users}
              title="人物投影尚未就绪"
              detail={castError || "确认角色阶段后会显示正式人物档案。"}
            />
          ))}

        {tab === "world" &&
          (brief.artifact ? (
            <WorldRuleLedger rules={brief.artifact.world_rules} />
          ) : (
            <BibleEmpty
              icon={Globe2}
              title="世界规则尚未就绪"
              detail={briefError || "确认 Brief 后会显示冻结的世界规则。"}
            />
          ))}

        {tab === "foreshadow" &&
          (foreshadowLoad.visible ? (
            <BookLoader
              phase={foreshadowLoad.exiting ? "exit" : "enter"}
              variant="panel"
              label="正在整理伏笔台账"
              detail="按正文 Evidence 生命周期读取"
            />
          ) : storyBible.foreshadows.items.length ||
            (storyBible.foreshadows.status !== "error" &&
              storyBible.summary) ? (
            <StoryForeshadowLedger
              error={storyBible.foreshadows.error}
              hasMore={Boolean(storyBible.foreshadows.nextCursor)}
              items={storyBible.foreshadows.items}
              loadingMore={storyBible.foreshadows.status === "loading-more"}
              onLoadMore={storyBible.loadMoreForeshadows}
              resolvedCount={storyBible.summary?.foreshadow_resolved_count ?? 0}
              total={storyBible.foreshadows.total}
              trackingCount={storyBible.summary?.foreshadow_tracking_count ?? 0}
            />
          ) : (
            <BibleEmpty
              icon={CircleDotDashed}
              title="伏笔台账暂时不可用"
              detail={
                storyBible.foreshadows.error || "正在等待正文 Evidence 投影。"
              }
            />
          ))}

        {tab === "facts" &&
          (factLoad.visible ? (
            <BookLoader
              phase={factLoad.exiting ? "exit" : "enter"}
              variant="panel"
              label="正在整理事实档案"
              detail="按章节来源读取 Canon 与 Wiki 投影"
            />
          ) : storyBible.facts.items.length ||
            (storyBible.facts.status !== "error" && storyBible.summary) ? (
            <StoryFactLedger
              conflicts={storyBible.summary?.conflicts ?? []}
              currentCount={storyBible.summary?.current_fact_count ?? 0}
              error={storyBible.facts.error}
              facts={storyBible.facts.items}
              hasMore={Boolean(storyBible.facts.nextCursor)}
              loadingMore={storyBible.facts.status === "loading-more"}
              onLoadMore={storyBible.loadMoreFacts}
              subjectNames={subjectNames}
              total={storyBible.facts.total}
              wikiProjectedCount={
                storyBible.summary?.wiki_projected_fact_count ?? 0
              }
            />
          ) : (
            <BibleEmpty
              icon={Archive}
              title="事实档案暂时不可用"
              detail={storyBible.facts.error || "正在等待 Canon 与 Wiki 投影。"}
            />
          ))}
      </main>
    </div>
  )
}

function CharacterLedger({
  subjects,
  relationCounts,
}: {
  subjects: CharacterSubject[]
  relationCounts: Map<string, number>
}) {
  return (
    <section className="story-ledger" aria-label="人物档案">
      <header>
        <span>正式主体</span>
        <strong>{subjects.length} 人</strong>
      </header>
      <div className="story-character-list">
        {subjects.map((subject, index) => {
          const kind = CHARACTER_KIND_META[subject.kind]
          return (
            <article className="story-character-row" key={subject.id}>
              <div
                className={`story-character-avatar story-avatar-${index % 6}`}
                aria-hidden="true"
              >
                {subject.name.slice(0, 1)}
              </div>
              <div className="story-character-copy">
                <div className="story-character-title">
                  <strong>{subject.name}</strong>
                  <span>{subject.id}</span>
                  <em
                    style={{ "--subject-color": kind.color } as CSSProperties}
                  >
                    {kind.label}
                  </em>
                </div>
                <p>{subject.function}</p>
                <dl>
                  <div>
                    <dt>首次登场</dt>
                    <dd>{formatDebut(subject.debut)}</dd>
                  </div>
                  <div>
                    <dt>行动驱力</dt>
                    <dd>{subject.drive}</dd>
                  </div>
                  <div>
                    <dt>
                      <Link2 size={10} />
                      关系
                    </dt>
                    <dd>{relationCounts.get(subject.id) ?? 0} 条</dd>
                  </div>
                </dl>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}

function WorldRuleLedger({ rules }: { rules: string[] }) {
  return (
    <section className="story-ledger" aria-label="冻结世界规则">
      <header>
        <span>Brief 冻结规则</span>
        <strong>{rules.length} 条</strong>
      </header>
      <ol className="story-world-list">
        {rules.map((rule, index) => (
          <li key={`${index}-${rule}`}>
            <span>{String(index + 1).padStart(2, "0")}</span>
            <p>{rule}</p>
            <em>BRIEF</em>
          </li>
        ))}
      </ol>
    </section>
  )
}

function BibleEmpty({
  detail,
  icon: Icon,
  title,
}: {
  detail: string
  icon: typeof BookMarked
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

function relationCountBySubject(relations: Array<{ a: string; b: string }>) {
  const counts = new Map<string, number>()
  relations.forEach((relation) => {
    counts.set(relation.a, (counts.get(relation.a) ?? 0) + 1)
    counts.set(relation.b, (counts.get(relation.b) ?? 0) + 1)
  })
  return counts
}

function tabFromPath(pathname: string): BibleTab {
  const value = pathname.split("/").filter(Boolean).at(-1)
  return TABS.some((item) => item.id === value) ? value as BibleTab : "cast"
}

function formatDebut(value: string) {
  return `第 ${value.replace("chapter:", "").replace("-", "–")} 章`
}
