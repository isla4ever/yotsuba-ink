import {
  ArrowRight,
  Clapperboard,
  FileText,
  Ruler,
  Sparkles,
} from "lucide-react"
import type { CreationIntentDraft } from "../contracts/creationWizard"
import {
  CREATION_ROUTE_META,
  intentError,
  routeMetaForIntent,
  formatTarget,
} from "../lib/creationWizard"

export function CreationIntentStep({
  intent,
  onChange,
  onNext,
}: {
  intent: CreationIntentDraft
  onChange: (next: CreationIntentDraft) => void
  onNext: () => void
}) {
  const route = routeMetaForIntent(intent)
  const error = intentError(intent)

  const setKind = (creationKind: CreationIntentDraft["creationKind"]) => {
    const nextLength =
      creationKind === "novel"
        ? (intent.novelLengthClass ?? "short_novel")
        : null
    const nextRoute =
      creationKind === "novel" ? nextLength : "screenplay_sample"
    onChange({
      ...intent,
      creationKind,
      novelLengthClass: nextLength,
      requestedTarget: nextRoute
        ? CREATION_ROUTE_META[nextRoute].recommended
        : null,
    })
  }

  const setNovelLength = (novelLengthClass: "short_novel" | "long_novel") => {
    onChange({
      ...intent,
      novelLengthClass,
      requestedTarget: CREATION_ROUTE_META[novelLengthClass].recommended,
    })
  }

  return (
    <section
      className="animate-fade-in"
      aria-labelledby="creation-intent-title"
    >
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <p className="mb-2 flex items-center gap-2 text-[10px] uppercase tracking-[0.16em] text-action">
            <Sparkles size={12} /> STEP 01 · 创作意图
          </p>
          <h2
            id="creation-intent-title"
            className="text-xl font-semibold text-ink"
          >
            先确定这次要交付什么
          </h2>
          <p className="mt-1.5 max-w-xl text-sm leading-relaxed text-ash">
            作品类型和目标规模会决定后续阶段链路。创建后路线冻结，运行中不会再被模式开关打断。
          </p>
        </div>
        <div className="hidden rounded-full border border-action/25 bg-action-bg p-2.5 text-action sm:block">
          <Ruler size={15} />
        </div>
      </div>

      <div className="space-y-6">
        <fieldset>
          <legend className="mb-2.5 text-xs font-medium text-ink">
            交付类型
          </legend>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <button
              type="button"
              aria-pressed={intent.creationKind === "screenplay"}
              onClick={() => setKind("screenplay")}
              className={`flex items-start gap-3 rounded-lg border p-3.5 text-left transition-[border-color,background-color,transform] duration-200 hover:-translate-y-0.5 ${
                intent.creationKind === "screenplay"
                  ? "border-action/55 bg-action-bg"
                  : "border-hairline bg-elev hover:border-action/30"
              }`}
            >
              <span className="mt-0.5 rounded-md bg-base p-2 text-action">
                <Clapperboard size={16} />
              </span>
              <span>
                <strong className="block text-sm font-medium text-ink">
                  剧本样片
                </strong>
                <span className="mt-0.5 block text-[11px] leading-relaxed text-ash">
                  以场景、动作和对白为核心，直接产出可讨论的样片。
                </span>
              </span>
            </button>
            <button
              type="button"
              aria-pressed={intent.creationKind === "novel"}
              onClick={() => setKind("novel")}
              className={`flex items-start gap-3 rounded-lg border p-3.5 text-left transition-[border-color,background-color,transform] duration-200 hover:-translate-y-0.5 ${
                intent.creationKind === "novel"
                  ? "border-action/55 bg-action-bg"
                  : "border-hairline bg-elev hover:border-action/30"
              }`}
            >
              <span className="mt-0.5 rounded-md bg-base p-2 text-action">
                <FileText size={16} />
              </span>
              <span>
                <strong className="block text-sm font-medium text-ink">
                  小说
                </strong>
                <span className="mt-0.5 block text-[11px] leading-relaxed text-ash">
                  先搭建故事地图，再按篇幅逐步推进正文和连续性校验。
                </span>
              </span>
            </button>
          </div>
        </fieldset>

        {intent.creationKind === "novel" && (
          <fieldset className="animate-fade-in">
            <legend className="mb-2.5 text-xs font-medium text-ink">
              小说篇幅
            </legend>
            <div className="flex flex-wrap gap-2">
              {(["short_novel", "long_novel"] as const).map((lengthClass) => {
                const meta = CREATION_ROUTE_META[lengthClass]
                const active = intent.novelLengthClass === lengthClass
                return (
                  <button
                    key={lengthClass}
                    type="button"
                    aria-pressed={active}
                    onClick={() => setNovelLength(lengthClass)}
                    className={`rounded-md border px-3.5 py-2 text-xs transition-colors ${
                      active
                        ? "border-action/55 bg-action-bg text-action"
                        : "border-hairline bg-elev text-ash hover:border-action/30 hover:text-ink"
                    }`}
                  >
                    <span className="font-medium">{meta.shortLabel}</span>
                    <span className="ml-2 text-[10px] text-fog">
                      {formatTarget(meta.recommended, meta.unit)}起
                    </span>
                  </button>
                )
              })}
            </div>
          </fieldset>
        )}

        {route && (
          <div className="grid gap-4 rounded-lg border border-hairline bg-elev/70 p-4 sm:grid-cols-[minmax(0,1fr)_220px]">
            <div>
              <div className="mb-1 flex items-center gap-2">
                <span className="badge badge-action">
                  将匹配 · {route.label}
                </span>
                <span className="font-mono text-[10px] text-fog">
                  {route.unitLabel}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-ash">
                {route.rationale}
              </p>
              <div
                className="mt-3 flex flex-wrap gap-1.5"
                aria-label={`${route.label}阶段预览`}
              >
                {route.stages.map((stage, index) => (
                  <span
                    key={stage}
                    className="inline-flex items-center gap-1 text-[10px] text-fog"
                  >
                    <span className="grid size-4 place-items-center rounded-full border border-hairline bg-base font-mono text-[9px] text-action">
                      {index + 1}
                    </span>
                    {stage}
                    {index < route.stages.length - 1 && (
                      <span className="mx-0.5 text-fog/50">→</span>
                    )}
                  </span>
                ))}
              </div>
            </div>
            <label className="block">
              <span className="mb-1.5 flex items-center justify-between text-xs text-ink">
                <span>{route.targetLabel}</span>
                <span className="font-mono text-[10px] text-fog">
                  建议 {formatTarget(route.recommended, route.unit)}
                </span>
              </span>
              <div className="relative">
                <input
                  className="input pr-12 text-right font-mono"
                  type="number"
                  min={route.minimum}
                  max={route.maximum}
                  step={route.unit === "minutes" ? 1 : 1000}
                  value={intent.requestedTarget ?? ""}
                  onChange={(event) => {
                    const nextValue =
                      event.target.value === ""
                        ? null
                        : Number(event.target.value)
                    onChange({
                      ...intent,
                      requestedTarget: Number.isFinite(nextValue)
                        ? nextValue
                        : null,
                    })
                  }}
                  aria-describedby="creation-target-help"
                />
                <span className="pointer-events-none absolute inset-y-0 right-3 flex items-center text-[10px] text-fog">
                  {route.unitLabel}
                </span>
              </div>
              <span
                id="creation-target-help"
                className="mt-1.5 block text-[10px] leading-relaxed text-fog"
              >
                范围 {formatTarget(route.minimum, route.unit)}–
                {formatTarget(route.maximum, route.unit)}，创建后写入冻结 Run
                配置。
              </span>
            </label>
          </div>
        )}

        <label className="block">
          <span className="mb-1.5 flex items-center justify-between text-xs font-medium text-ink">
            <span>创作意图</span>
            <span className="font-mono text-[10px] text-fog">
              {intent.creativeIntent.trim().length}/4000
            </span>
          </span>
          <textarea
            className="input min-h-36 resize-y leading-relaxed"
            value={intent.creativeIntent}
            onChange={(event) =>
              onChange({ ...intent, creativeIntent: event.target.value })
            }
            placeholder="写下题材、核心冲突、想保留的气质、禁忌或参考作品。这里不需要先写完整大纲，系统会把这段意图交给匹配到的流水线。"
            aria-describedby="creation-intent-help"
          />
          <span
            id="creation-intent-help"
            className="mt-1.5 block text-[10px] text-fog"
          >
            至少 20 个字符；越具体越利于后续简报阶段建立稳定的创作合同。
          </span>
        </label>

        {error && (
          <p className="text-xs text-risk" role="alert">
            {error}
          </p>
        )}
      </div>

      <div className="mt-7 flex justify-end border-t border-hairline pt-5">
        <button
          type="button"
          className="btn btn-primary"
          onClick={onNext}
          disabled={Boolean(error)}
        >
          匹配流水线 <ArrowRight size={14} />
        </button>
      </div>
    </section>
  )
}
