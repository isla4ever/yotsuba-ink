import { useEffect, useMemo, useState, type ReactNode } from "react"
import {
  AlertTriangle,
  CheckCircle2,
  CloudCog,
  Image as ImageIcon,
  KeyRound,
  ListRestart,
  LoaderCircle,
  Plus,
  RefreshCw,
  Save,
  Server,
  ShieldCheck,
  Trash2,
} from "lucide-react"
import type {
  ProviderKind,
  ProviderProfile,
  ProviderTemplate,
} from "../contracts/provider"
import { useProviderSettings } from "../state/useProviderSettings"
import { BookLoader } from "../layout/BookLoader"
import { useLoadingPresence } from "../layout/useLoadingPresence"

const KIND_META: Record<ProviderKind, { label: string; icon: ReactNode }> = {
  "openai-compatible": { label: "文本服务", icon: <CloudCog size={13} /> },
  "openai-compatible-image": {
    label: "图片服务",
    icon: <ImageIcon size={13} />,
  },
}

export function ProviderSettingsPanel() {
  const settings = useProviderSettings()
  const [kind, setKind] = useState<ProviderKind>("openai-compatible")
  const [selectedId, setSelectedId] = useState("")
  const [newTemplateId, setNewTemplateId] = useState("")
  const providers = settings.profiles.filter(
    (provider) => provider.kind === kind,
  )
  const compatibleTemplates = settings.templates.filter(
    (template) => template.kind === kind,
  )
  const selected =
    settings.profiles.find((provider) => provider.id === selectedId) ??
    providers[0]
  const globalText = settings.profiles.find(
    (provider) =>
      provider.kind === "openai-compatible" && provider.is_global_default,
  )
  const globalImage = settings.profiles.find(
    (provider) =>
      provider.kind === "openai-compatible-image" && provider.is_global_default,
  )

  useEffect(() => {
    if (!settings.profiles.length) return
    if (
      !settings.profiles.some(
        (provider) => provider.id === selectedId && provider.kind === kind,
      )
    ) {
      const preferred =
        settings.profiles.find(
          (provider) => provider.kind === kind && provider.is_global_default,
        ) ?? settings.profiles.find((provider) => provider.kind === kind)
      setSelectedId(preferred?.id ?? "")
    }
  }, [kind, selectedId, settings.profiles])

  useEffect(() => {
    if (
      !compatibleTemplates.some((template) => template.id === newTemplateId)
    ) {
      setNewTemplateId(
        compatibleTemplates.find((template) => template.execution_allowed)
          ?.id ??
          compatibleTemplates[0]?.id ??
          "",
      )
    }
  }, [compatibleTemplates, newTemplateId])

  const initialLoad = useLoadingPresence(settings.loading)

  if (initialLoad.visible) {
    return (
      <BookLoader
        phase={initialLoad.exiting ? "exit" : "enter"}
        variant="panel"
        label="正在读取 AI 服务"
        detail="同步服务商、模型能力与密钥状态"
      />
    )
  }

  return (
    <div className="provider-settings-panel">
      <header className="provider-settings-heading">
        <div>
          <span>AI SERVICES</span>
          <h1>服务商与密钥</h1>
          <p>默认服务用于新建配置；已经启动的 Run 继续使用冻结绑定。</p>
        </div>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => void settings.refresh()}
        >
          <RefreshCw size={13} />
          刷新
        </button>
      </header>

      {settings.loadError && (
        <div className="banner-warning" role="alert">
          <AlertTriangle size={13} />
          {settings.loadError}
        </div>
      )}

      <section className="provider-default-band" aria-label="全局默认服务">
        <DefaultProviderSelect
          label="默认文本服务"
          kind="openai-compatible"
          value={globalText?.id ?? ""}
          profiles={settings.profiles}
          busy={Boolean(settings.activeOperation)}
          onSelect={(provider) => void settings.setDefault(provider)}
        />
        <DefaultProviderSelect
          label="默认封面服务"
          kind="openai-compatible-image"
          value={globalImage?.id ?? ""}
          profiles={settings.profiles}
          busy={Boolean(settings.activeOperation)}
          onSelect={(provider) => void settings.setDefault(provider)}
        />
      </section>

      <div className="provider-workspace">
        <aside className="provider-service-sidebar">
          <div
            className="provider-kind-switch"
            role="tablist"
            aria-label="服务类型"
          >
            {(Object.keys(KIND_META) as ProviderKind[]).map((item) => (
              <button
                key={item}
                type="button"
                role="tab"
                aria-selected={kind === item}
                className={kind === item ? "active" : ""}
                onClick={() => setKind(item)}
              >
                {KIND_META[item].icon}
                <span>{KIND_META[item].label}</span>
                <small>
                  {
                    settings.profiles.filter(
                      (provider) => provider.kind === item,
                    ).length
                  }
                </small>
              </button>
            ))}
          </div>

          <nav
            className="provider-service-list"
            aria-label={KIND_META[kind].label}
          >
            {providers.map((provider) => (
              <button
                key={provider.id}
                type="button"
                className={selected?.id === provider.id ? "active" : ""}
                onClick={() => setSelectedId(provider.id)}
              >
                <span
                  className={`provider-health-dot ${
                    providerReady(provider) ? "ready" : "missing"
                  }`}
                />
                <span>
                  <strong>{provider.name}</strong>
                  <small>{provider.default_model || "未选择模型"}</small>
                </span>
                {provider.is_global_default && <em>默认</em>}
              </button>
            ))}
            {!providers.length && (
              <div className="provider-list-empty">
                暂无{KIND_META[kind].label}
              </div>
            )}
          </nav>

          <div className="provider-create-row">
            <label>
              <span>新增服务</span>
              <select
                className="input"
                value={newTemplateId}
                onChange={(event) => setNewTemplateId(event.target.value)}
              >
                {groupTemplates(compatibleTemplates).map(
                  ([tier, templates]) => (
                    <optgroup key={tier} label={tierLabel(tier)}>
                      {templates.map((template) => (
                        <option
                          key={template.id}
                          value={template.id}
                          disabled={!template.execution_allowed}
                        >
                          {template.label}
                        </option>
                      ))}
                    </optgroup>
                  ),
                )}
              </select>
            </label>
            <button
              type="button"
              className="btn btn-secondary"
              disabled={!newTemplateId || Boolean(settings.activeOperation)}
              onClick={async () => {
                const template = compatibleTemplates.find(
                  (item) => item.id === newTemplateId,
                )
                if (!template) return
                const id = await settings.createProvider(template)
                if (id) setSelectedId(id)
              }}
              aria-label="新增 AI 服务"
            >
              <Plus size={14} />
            </button>
          </div>
        </aside>

        <section className="provider-detail-pane">
          {selected ? (
            <ProviderEditor
              key={selected.id}
              provider={selected}
              templates={compatibleTemplates}
              settings={settings}
            />
          ) : (
            <div className="provider-detail-empty">
              <Server size={20} />
              <span>选择或新增一个 AI 服务</span>
            </div>
          )}
        </section>
      </div>
    </div>
  )
}

type ProviderSettings = ReturnType<typeof useProviderSettings>

function ProviderEditor({
  provider,
  templates,
  settings,
}: {
  provider: ProviderProfile
  templates: ProviderTemplate[]
  settings: ProviderSettings
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const active =
    settings.activeOperation?.providerId === provider.id
      ? settings.activeOperation.type
      : null
  const status = settings.statuses[provider.id]
  const template = templates.find((item) => item.id === provider.template_id)
  const modelOptions = useMemo(
    () =>
      Array.from(
        new Set(
          [provider.default_model, ...provider.model_options].filter(Boolean),
        ),
      ),
    [provider.default_model, provider.model_options],
  )

  const applyTemplate = (templateId: string) => {
    const next = templates.find((item) => item.id === templateId)
    if (!next) return
    settings.updateProvider(provider.id, {
      template_id: next.id,
      base_url: next.base_url,
      api_key_env: next.api_key_env,
      default_model: next.default_model,
      model_options: next.model_options,
      model_supported_parameters: {},
    })
  }

  return (
    <div className="provider-editor-v20" aria-busy={Boolean(active)}>
      <header>
        <div>
          <span>
            {KIND_META[provider.kind].label} ·{" "}
            {template?.integration_tier
              ? tierLabel(template.integration_tier)
              : "自定义"}
          </span>
          <h2>{provider.name}</h2>
        </div>
        <label className="provider-enable-toggle">
          <input
            type="checkbox"
            checked={provider.enabled}
            disabled={Boolean(active)}
            onChange={(event) =>
              settings.updateProvider(provider.id, {
                enabled: event.target.checked,
              })
            }
          />
          <span>启用</span>
        </label>
      </header>

      <div className="provider-connection-state">
        {providerReady(provider) ? (
          <CheckCircle2 size={13} />
        ) : (
          <AlertTriangle size={13} />
        )}
        <span>{secretLabel(provider)}</span>
        <small>{provider.base_url || "Base URL 未配置"}</small>
      </div>

      <div className="provider-editor-fields">
        <label>
          <span>服务名称</span>
          <input
            className="input"
            value={provider.name}
            disabled={Boolean(active)}
            onChange={(event) =>
              settings.updateProvider(provider.id, { name: event.target.value })
            }
          />
        </label>
        <label>
          <span>服务商模板</span>
          <select
            className="input"
            value={provider.template_id}
            disabled={Boolean(active)}
            onChange={(event) => applyTemplate(event.target.value)}
          >
            {templates.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="provider-wide-field">
          <span>Base URL</span>
          <input
            className="input font-mono"
            value={provider.base_url}
            disabled={Boolean(active)}
            placeholder="https://api.example.com/v1"
            onChange={(event) =>
              settings.updateProvider(provider.id, {
                base_url: event.target.value,
              })
            }
          />
        </label>
        <label>
          <span>默认模型</span>
          <input
            className="input font-mono"
            list={`models-${provider.id}`}
            value={provider.default_model}
            disabled={Boolean(active)}
            onChange={(event) =>
              settings.updateProvider(provider.id, {
                default_model: event.target.value,
              })
            }
          />
          <datalist id={`models-${provider.id}`}>
            {modelOptions.map((model) => (
              <option key={model} value={model} />
            ))}
          </datalist>
        </label>
        <label>
          <span>API Key 环境变量</span>
          <input
            className="input font-mono"
            value={provider.api_key_env}
            disabled={Boolean(active)}
            onChange={(event) =>
              settings.updateProvider(provider.id, {
                api_key_env: event.target.value,
              })
            }
          />
        </label>
        <label className="provider-wide-field">
          <span>{provider.has_saved_secret ? "更换 API Key" : "API Key"}</span>
          <input
            className="input font-mono"
            type="password"
            autoComplete="off"
            value={settings.secretInputs[provider.id] ?? ""}
            disabled={Boolean(active)}
            placeholder={
              provider.has_saved_secret
                ? "输入新密钥后保存，现有密钥不会显示"
                : "仅发送到本机后端，不在浏览器保存"
            }
            onChange={(event) =>
              settings.setSecretInput(provider.id, event.target.value)
            }
          />
        </label>
      </div>

      {template?.description && (
        <p className="provider-template-note">{template.description}</p>
      )}
      {status && (
        <div
          className={`provider-operation-status ${status.tone}`}
          role={status.tone === "error" ? "alert" : "status"}
        >
          {status.tone === "success" ? (
            <ShieldCheck size={12} />
          ) : (
            <AlertTriangle size={12} />
          )}
          {status.message}
        </div>
      )}

      <div className="provider-primary-actions">
        <button
          type="button"
          className="btn btn-secondary"
          disabled={Boolean(active)}
          onClick={() => void settings.discoverModels(provider)}
        >
          {active === "discovering" ? (
            <LoaderCircle size={13} className="animate-spin" />
          ) : (
            <ListRestart size={13} />
          )}
          同步模型
        </button>
        <div />
        <button
          type="button"
          className="btn btn-secondary"
          disabled={Boolean(active)}
          onClick={() => void settings.saveProvider(provider, false)}
        >
          {active === "saving" ? (
            <LoaderCircle size={13} className="animate-spin" />
          ) : (
            <Save size={13} />
          )}
          保存配置
        </button>
        <button
          type="button"
          className="btn btn-primary"
          disabled={Boolean(active)}
          onClick={() => void settings.saveProvider(provider, true)}
        >
          {active === "testing" ? (
            <LoaderCircle size={13} className="animate-spin" />
          ) : (
            <KeyRound size={13} />
          )}
          保存并检查
        </button>
      </div>

      <div className="provider-danger-actions">
        {provider.has_saved_secret && (
          <button
            type="button"
            disabled={Boolean(active)}
            onClick={() => void settings.clearSecret(provider)}
          >
            清除本机密钥
          </button>
        )}
        {!confirmDelete ? (
          <button
            type="button"
            disabled={Boolean(active) || provider.is_global_default}
            title={provider.is_global_default ? "请先切换默认服务" : "删除服务"}
            onClick={() => setConfirmDelete(true)}
          >
            <Trash2 size={12} />
            删除服务
          </button>
        ) : (
          <span>
            <button type="button" onClick={() => setConfirmDelete(false)}>
              取消
            </button>
            <button
              type="button"
              className="danger"
              disabled={Boolean(active)}
              onClick={() => void settings.removeProvider(provider)}
            >
              确认删除
            </button>
          </span>
        )}
      </div>
    </div>
  )
}

function DefaultProviderSelect({
  label,
  kind,
  value,
  profiles,
  busy,
  onSelect,
}: {
  label: string
  kind: ProviderKind
  value: string
  profiles: ProviderProfile[]
  busy: boolean
  onSelect: (provider: ProviderProfile) => void
}) {
  const options = profiles.filter(
    (provider) => provider.kind === kind && provider.enabled,
  )
  return (
    <label>
      <span>{label}</span>
      <select
        className="input"
        value={value}
        disabled={busy || !options.length}
        onChange={(event) => {
          const provider = options.find(
            (item) => item.id === event.target.value,
          )
          if (provider) onSelect(provider)
        }}
      >
        {!value && <option value="">未指定</option>}
        {options.map((provider) => (
          <option key={provider.id} value={provider.id}>
            {provider.name} · {provider.default_model || "未选模型"}
          </option>
        ))}
      </select>
    </label>
  )
}

function providerReady(provider: ProviderProfile) {
  return (
    provider.enabled &&
    Boolean(
      provider.base_url &&
        provider.default_model &&
        (provider.has_saved_secret || provider.has_env_secret),
    )
  )
}

function secretLabel(provider: ProviderProfile) {
  if (provider.has_saved_secret) return "已保存本机密钥"
  if (provider.has_env_secret) return "已检测环境密钥"
  return "尚未配置密钥"
}

function groupTemplates(templates: ProviderTemplate[]) {
  const tiers: ProviderTemplate["integration_tier"][] = [
    "official",
    "gateway",
    "compatibility",
    "custom",
  ]
  return tiers
    .map(
      (tier) =>
        [
          tier,
          templates.filter((template) => template.integration_tier === tier),
        ] as const,
    )
    .filter(([, items]) => items.length)
}

function tierLabel(tier: ProviderTemplate["integration_tier"]) {
  return ({
    official: "官方接入",
    gateway: "聚合网关",
    compatibility: "兼容接入",
    custom: "自定义接口",
  } as const)[tier]
}
