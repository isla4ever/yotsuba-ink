import {
  AlertTriangle,
  Check,
  Database,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
} from "lucide-react"
import { useEffect, useMemo, useRef, useState } from "react"
import type {
  CollaborationMode,
  CollaborationSettings,
  CollaborationSettingsEnvelope,
} from "../contracts/authorCollaboration"
import type { GraphRunEnvelope } from "../contracts/run"
import { collaborationModeLabels } from "../lib/authorCollaborationProjection"
import {
  getCollaborationSettings,
  saveCollaborationSettings,
} from "../services/authorCollaborationApi"

export function AuthorCollaborationSettings() {
  const [envelope, setEnvelope] =
    useState<CollaborationSettingsEnvelope | null>(null)
  const [draft, setDraft] = useState<CollaborationSettings | null>(null)
  const [status, setStatus] =
    useState<"loading" | "ready" | "saving" | "saved" | "failed">(
      "loading",
    )
  const [error, setError] = useState("")
  const savedStatusTimerRef = useRef(0)

  const load = () => {
    setStatus("loading")
    setError("")
    void getCollaborationSettings()
      .then((record) => {
        setEnvelope(record)
        setDraft(record.settings)
        setStatus("ready")
      })
      .catch((reason: unknown) => {
        setError(errorMessage(reason, "作者协作设置加载失败"))
        setStatus("failed")
      })
  }

  useEffect(() => {
    load()
    return () => window.clearTimeout(savedStatusTimerRef.current)
  }, [])

  const readyCapabilities = useMemo(
    () =>
      envelope?.capabilities.filter(
        (item) => item.ready && item.supports_multi_turn,
      ) ?? [],
    [envelope],
  )

  if (!draft || !envelope) {
    return (
      <section className="collaboration-settings-state" role="status">
        <Sparkles size={18} />
        <strong>
          {status === "failed"
            ? "无法读取作者协作设置"
            : "正在读取作者协作设置"}
        </strong>
        {error && <span>{error}</span>}
        {status === "failed" && (
          <button className="btn btn-secondary" onClick={load} type="button">
            <RefreshCw size={13} /> 重试
          </button>
        )}
      </section>
    )
  }

  const selectedCapabilityKey = capabilityKey({
    provider_profile_id: draft.default_provider_profile_id,
    model: draft.default_model,
  })
  const selectedCapabilityReady = readyCapabilities.some(
    (item) => capabilityKey(item) === selectedCapabilityKey,
  )
  const unavailableBinding = Boolean(
    draft.default_provider_profile_id &&
      draft.default_model &&
      !selectedCapabilityReady,
  )
  const patchPolicy = (
    patch: Partial<CollaborationSettings["context_policy"]>,
  ) =>
    setDraft((current) =>
      current
        ? {
            ...current,
            context_policy: { ...current.context_policy, ...patch },
          }
        : current,
    )

  const save = () => {
    setStatus("saving")
    setError("")
    void saveCollaborationSettings(draft)
      .then((record) => {
        setEnvelope(record)
        setDraft(record.settings)
        setStatus("saved")
        window.clearTimeout(savedStatusTimerRef.current)
        savedStatusTimerRef.current = window.setTimeout(
          () => setStatus("ready"),
          1800,
        )
      })
      .catch((reason: unknown) => {
        setError(errorMessage(reason, "作者协作设置保存失败"))
        setStatus("failed")
      })
  }

  return (
    <div className="collaboration-settings-panel">
      <header className="collaboration-settings-intro">
        <div>
          <span>DEEP MODE · AUTHOR COLLABORATION</span>
          <h1>作者协作</h1>
          <p>
            为新建对话配置冻结模型、上下文预算与写作偏好。改稿始终先生成可审阅候选，不直接覆盖作品事实。
          </p>
        </div>
        <div className="collaboration-settings-seal">
          <Sparkles size={19} />
          <span>五阶段</span>
          <strong>讨论 · 方案 · 改稿</strong>
        </div>
      </header>

      <section className="collaboration-settings-block">
        <header>
          <div>
            <span>默认模型</span>
            <strong>只影响新建协作线程</strong>
          </div>
          <ShieldCheck size={16} />
        </header>
        <div className="collaboration-settings-grid">
          <label>
            <span>Provider / Model</span>
            <select
              aria-invalid={unavailableBinding}
              className="input"
              onChange={(event) => {
                const selected = readyCapabilities.find(
                  (item) => capabilityKey(item) === event.target.value,
                )
                if (selected)
                  setDraft({
                    ...draft,
                    default_provider_profile_id: selected.provider_profile_id,
                    default_model: selected.model,
                  })
              }}
              value={selectedCapabilityKey}
            >
              {unavailableBinding && (
                <option value={selectedCapabilityKey}>
                  当前绑定不可用 · {draft.default_provider_profile_id} · {draft.default_model}
                </option>
              )}
              {!readyCapabilities.length && !unavailableBinding && (
                <option value={selectedCapabilityKey}>
                  没有通过多轮对话就绪检查的文本服务
                </option>
              )}
              {readyCapabilities.map((item) => (
                <option key={capabilityKey(item)} value={capabilityKey(item)}>
                  {item.provider_name} · {item.model}
                </option>
              ))}
            </select>
            {unavailableBinding && (
              <small className="collaboration-provider-warning" role="alert">
                当前保存的服务已失效。既有线程仍保持冻结绑定；请选择已就绪服务后保存新的默认配置。
              </small>
            )}
          </label>
          <div className="collaboration-settings-field">
            <span>默认协作模式</span>
            <div className="collaboration-settings-segmented" role="group">
              {(["discuss", "plan", "revise"] as CollaborationMode[]).map(
                (mode) => (
                  <button
                    aria-pressed={draft.default_mode === mode}
                    className={draft.default_mode === mode ? "active" : ""}
                    key={mode}
                    onClick={() => setDraft({ ...draft, default_mode: mode })}
                    type="button"
                  >
                    {collaborationModeLabels[mode]}
                  </button>
                ),
              )}
            </div>
          </div>
        </div>
      </section>

      <section className="collaboration-settings-block">
        <header>
          <div>
            <span>上下文策略</span>
            <strong>只注入当前范围的可追溯来源</strong>
          </div>
          <Database size={16} />
        </header>
        <div className="collaboration-policy-list">
          <PolicyToggle checked={draft.context_policy.include_author_preferences} label="作者偏好" onChange={(value) => patchPolicy({ include_author_preferences: value })} />
          <PolicyToggle checked={draft.context_policy.include_craft_mechanisms} label="写作机制包" onChange={(value) => patchPolicy({ include_craft_mechanisms: value })} />
          <PolicyToggle checked={draft.context_policy.include_canon_wiki} label="相关 Canon / Wiki" onChange={(value) => patchPolicy({ include_canon_wiki: value })} />
          <PolicyToggle checked={draft.context_policy.include_foreshadow} label="当前范围伏笔" onChange={(value) => patchPolicy({ include_foreshadow: value })} />
          <PolicyToggle checked={draft.context_policy.include_knowledge} label="知识库 Source Pack" onChange={(value) => patchPolicy({ include_knowledge: value })} />
        </div>
        <div className="collaboration-settings-grid compact">
          <label>
            <span>单轮字符预算</span>
            <input className="input" max={120000} min={4000} onChange={(event) => patchPolicy({ max_input_chars: Number(event.target.value) })} step={1000} type="number" value={draft.context_policy.max_input_chars} />
          </label>
          <label>
            <span>最多历史轮次</span>
            <input className="input" max={40} min={0} onChange={(event) => patchPolicy({ max_history_turns: Number(event.target.value) })} type="number" value={draft.context_policy.max_history_turns} />
          </label>
        </div>
      </section>

      <section className="collaboration-settings-block">
        <header>
          <div>
            <span>作者偏好与机制</span>
            <strong>进入上下文回执后才发送给模型</strong>
          </div>
          <Sparkles size={16} />
        </header>
        <div className="collaboration-settings-wide-fields">
          <label>
            <span>作者偏好</span>
            <textarea className="input" onChange={(event) => patchPolicy({ author_preferences: event.target.value })} placeholder="例如：克制叙述、动作可验证、避免总结式对白。" rows={5} value={draft.context_policy.author_preferences} />
          </label>
          <label>
            <span>写作机制包（每行一项）</span>
            <textarea className="input" onChange={(event) => patchPolicy({ craft_mechanisms: splitLines(event.target.value).slice(0, 12) })} placeholder={"场景-续篇\n因果压力测试\n人物语言护栏"} rows={5} value={draft.context_policy.craft_mechanisms.join("\n")} />
          </label>
        </div>
        <label className="collaboration-retention-field">
          <span>历史保留天数</span>
          <input className="input" max={3650} min={7} onChange={(event) => setDraft({ ...draft, history_retention_days: Number(event.target.value) })} type="number" value={draft.history_retention_days} />
        </label>
      </section>

      <section className="collaboration-capability-block">
        <header>
          <span>Provider 能力矩阵</span>
          <strong>{envelope.capabilities.length} 个文本服务</strong>
        </header>
        <div>
          {envelope.capabilities.map((item) => (
            <article data-ready={item.ready} key={capabilityKey(item)}>
              <div>
                <strong>{item.provider_name}</strong>
                <span>{item.model}</span>
              </div>
              <Capability label="多轮" value={item.supports_multi_turn} />
              <Capability label="流式" value={item.supports_streaming} />
              <Capability label="结构化改稿" value={item.supports_structured_patch} />
              <small>
                {item.capability_source === "tested"
                  ? "实测"
                  : item.capability_source === "discovered"
                    ? "发现"
                    : "手动"}
                · {item.issue_codes.length ? item.issue_codes.join(" / ") : "就绪"}
              </small>
            </article>
          ))}
        </div>
      </section>

      {error && (
        <div className="collaboration-settings-error" role="alert">
          <AlertTriangle size={14} /> {error}
        </div>
      )}
      <footer className="collaboration-settings-savebar">
        <span>
          固定安全规则：改稿需确认、source binding、无静默 Provider fallback、对话无 Canon/Wiki 直接写权。
        </span>
        <button
          className="btn btn-primary"
          disabled={status === "saving" || !selectedCapabilityReady}
          onClick={save}
          type="button"
        >
          <Save size={13} />
          {status === "saving"
            ? "保存中"
            : status === "saved"
              ? "已保存"
              : "保存作者协作设置"}
        </button>
      </footer>
    </div>
  )
}

export function CollaborationRunBinding({ run }: { run: GraphRunEnvelope | null }) {
  const eligible = run?.definition.quality_mode === "deep"
  return (
    <section className="collaboration-run-binding">
      <header>
        <div>
          <span>作者协作</span>
          <strong>{eligible ? "精细模式已启用" : "仅精细模式开放"}</strong>
        </div>
        <ShieldCheck size={16} />
      </header>
      <p>
        新线程采用全局作者协作默认并在创建时冻结 Provider；已经存在的线程不会随设置变化而静默换模。
      </p>
      <div>
        {(["spine", "cast", "volumes", "detail", "text"] as const).map(
          (stageId) => {
            const binding = run?.definition.provider_bindings[stageId]
            return (
              <article key={stageId}>
                <span>{stageLabel(stageId)}</span>
                <strong>
                  {binding
                    ? `${binding.provider_profile_id} · ${binding.model}`
                    : "开始运行后冻结"}
                </strong>
              </article>
            )
          },
        )}
      </div>
    </section>
  )
}

function PolicyToggle({ checked, label, onChange }: { checked: boolean; label: string; onChange: (value: boolean) => void }) {
  return (
    <label>
      <input checked={checked} onChange={(event) => onChange(event.target.checked)} type="checkbox" />
      <span>{label}</span>
    </label>
  )
}

function Capability({ label, value }: { label: string; value: boolean }) {
  return <span className={value ? "ready" : ""}>{value && <Check size={11} />}{label}</span>
}

function capabilityKey(item: { provider_profile_id: string; model: string }) {
  return JSON.stringify([item.provider_profile_id, item.model])
}

function splitLines(value: string) {
  return value.split("\n").map((item) => item.trim()).filter(Boolean)
}

function stageLabel(stageId: string) {
  return ({ spine: "故事脊柱", cast: "人物编排", volumes: "分卷架构", detail: "章节细纲", text: "章节正文" } as Record<string, string>)[stageId] ?? stageId
}

function errorMessage(reason: unknown, fallback: string) {
  return reason instanceof Error ? reason.message : fallback
}
