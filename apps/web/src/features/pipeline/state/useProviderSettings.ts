import { useCallback, useEffect, useRef, useState } from "react"
import type { ProviderProfile, ProviderTemplate } from "../contracts/provider"
import {
  deleteProviderProfile,
  deleteProviderSecret,
  discoverProviderModels,
  listProviderProfiles,
  listProviderTemplates,
  saveProviderProfile,
  saveProviderSecret,
  setDefaultProviderProfile,
  testProviderConnection,
} from "../services/providerApi"

export type ProviderOperation = "saving" | "testing" | "discovering" | "defaulting" | "deleting" | "secret"
export type ProviderOperationStatus = {
  tone: "success" | "error"
  message: string
}

export function useProviderSettings() {
  const [profiles, setProfiles] = useState<ProviderProfile[]>([])
  const [templates, setTemplates] = useState<ProviderTemplate[]>([])
  const [secretInputs, setSecretInputs] = useState<Record<string, string>>({})
  const [statuses, setStatuses] =
    useState<Record<string, ProviderOperationStatus>>({})
  const [activeOperation, setActiveOperation] = useState<{
    providerId: string
    type: ProviderOperation
  } | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState("")
  const activeRef = useRef(new Set<string>())

  const refresh = useCallback(async (signal?: AbortSignal) => {
    setLoading(true)
    setLoadError("")
    try {
      const [nextProfiles, nextTemplates] = await Promise.all([
        listProviderProfiles(signal),
        listProviderTemplates(signal),
      ])
      setProfiles(nextProfiles)
      setTemplates(nextTemplates)
    } catch (reason) {
      if (signal?.aborted) return
      setLoadError(errorMessage(reason))
    } finally {
      if (!signal?.aborted) setLoading(false)
    }
  }, [])

  useEffect(() => {
    const controller = new AbortController()
    void refresh(controller.signal)
    return () => controller.abort()
  }, [refresh])

  const perform = useCallback(
    async (
      providerId: string,
      type: ProviderOperation,
      task: () => Promise<string>,
    ) => {
      if (activeRef.current.has(providerId)) return false
      activeRef.current.add(providerId)
      setActiveOperation({ providerId, type })
      setStatuses((current) => {
        const next = { ...current }
        delete next[providerId]
        return next
      })
      try {
        const message = await task()
        setStatuses((current) => ({
          ...current,
          [providerId]: { tone: "success", message },
        }))
        return true
      } catch (reason) {
        setStatuses((current) => ({
          ...current,
          [providerId]: { tone: "error", message: errorMessage(reason) },
        }))
        return false
      } finally {
        activeRef.current.delete(providerId)
        setActiveOperation((current) =>
          current?.providerId === providerId ? null : current,
        )
      }
    },
    [],
  )

  const updateProvider = useCallback(
    (providerId: string, patch: Partial<ProviderProfile>) => {
      setProfiles((current) =>
        current.map((provider) =>
          provider.id === providerId ? { ...provider, ...patch } : provider,
        ),
      )
    },
    [],
  )

  const setSecretInput = useCallback((providerId: string, value: string) => {
    setSecretInputs((current) => ({ ...current, [providerId]: value }))
  }, [])

  const saveProvider = useCallback(
    async (provider: ProviderProfile, testAfterSave = false) => {
      const apiKey = secretInputs[provider.id]?.trim() ?? ""
      return perform(
        provider.id,
        testAfterSave ? "testing" : "saving",
        async () => {
          const saved = await saveProviderProfile(provider)
          let hasSavedSecret = provider.has_saved_secret
          if (apiKey) {
            await saveProviderSecret(provider.id, apiKey)
            hasSavedSecret = true
            setSecretInputs((current) => ({ ...current, [provider.id]: "" }))
          }
          const hydrated = hydrateProfile(saved, provider, hasSavedSecret)
          setProfiles((current) =>
            current.map((item) => (item.id === provider.id ? hydrated : item)),
          )
          if (!testAfterSave)
            return apiKey
              ? "服务配置与新密钥已保存到本机后端。"
              : "服务配置已保存。"
          const result = await testProviderConnection(hydrated, apiKey)
          if (!result.ok) throw new Error(result.message)
          return result.response_preview
            ? `${result.message} ${result.response_preview}`
            : result.message
        },
      )
    },
    [perform, secretInputs],
  )

  const setDefault = useCallback(
    async (provider: ProviderProfile) =>
      perform(provider.id, "defaulting", async () => {
        const updated = await setDefaultProviderProfile(
          provider.id,
          provider.kind,
        )
        setProfiles((current) =>
          updated.map((item) =>
            hydrateProfile(
              item,
              current.find((candidate) => candidate.id === item.id),
            ),
          ),
        )
        return provider.kind === "openai-compatible"
          ? "默认文本服务已切换。"
          : "默认封面服务已切换。"
      }),
    [perform],
  )

  const discoverModels = useCallback(
    async (provider: ProviderProfile) =>
      perform(provider.id, "discovering", async () => {
        const result = await discoverProviderModels(
          provider.id,
          secretInputs[provider.id]?.trim() ?? "",
        )
        if (!result.ok) throw new Error(result.message)
        setProfiles((current) =>
          current.map((item) =>
            item.id === provider.id
              ? {
                  ...item,
                  model_options: Array.from(
                    new Set(
                      [
                        item.default_model,
                        ...item.model_options,
                        ...result.models,
                      ].filter(Boolean),
                    ),
                  ),
                  model_supported_parameters: result.model_supported_parameters,
                }
              : item,
          ),
        )
        return result.message
      }),
    [perform, secretInputs],
  )

  const clearSecret = useCallback(
    async (provider: ProviderProfile) =>
      perform(provider.id, "secret", async () => {
        await deleteProviderSecret(provider.id)
        setProfiles((current) =>
          current.map((item) =>
            item.id === provider.id
              ? { ...item, has_saved_secret: false }
              : item,
          ),
        )
        setSecretInputs((current) => ({ ...current, [provider.id]: "" }))
        return "本机保存的 API Key 已清除。"
      }),
    [perform],
  )

  const removeProvider = useCallback(
    async (provider: ProviderProfile) =>
      perform(provider.id, "deleting", async () => {
        await deleteProviderProfile(provider.id)
        setProfiles((current) =>
          current.filter((item) => item.id !== provider.id),
        )
        return "AI 服务已删除。"
      }),
    [perform],
  )

  const createProvider = useCallback(
    async (template: ProviderTemplate) => {
      const providerId = `provider-${template.id}-${crypto.randomUUID().slice(0, 8)}`
      const provider = providerFromTemplate(providerId, template)
      const ok = await perform(providerId, "saving", async () => {
        const saved = await saveProviderProfile(provider)
        setProfiles((current) => [...current, hydrateProfile(saved, provider)])
        return "AI 服务已创建，请继续填写密钥并检查连接。"
      })
      return ok ? providerId : null
    },
    [perform],
  )

  return {
    activeOperation,
    clearSecret,
    createProvider,
    discoverModels,
    loadError,
    loading,
    profiles,
    refresh,
    removeProvider,
    saveProvider,
    secretInputs,
    setDefault,
    setSecretInput,
    statuses,
    templates,
    updateProvider,
  }
}

function providerFromTemplate(
  id: string,
  template: ProviderTemplate,
): ProviderProfile {
  return {
    id,
    name: template.label,
    kind: template.kind,
    template_id: template.id,
    base_url: template.base_url,
    api_key_env: template.api_key_env,
    default_model: template.default_model,
    model_options: template.model_options,
    model_supported_parameters: {},
    estimated_cost_per_output_usd: null,
    estimated_input_cost_per_million_tokens_usd: null,
    estimated_output_cost_per_million_tokens_usd: null,
    model_pricing: {},
    is_global_default: false,
    has_saved_secret: false,
    has_env_secret: false,
    enabled: true,
  }
}

function hydrateProfile(
  profile: ProviderProfile,
  previous?: ProviderProfile,
  hasSavedSecret?: boolean,
): ProviderProfile {
  return {
    ...profile,
    has_saved_secret: hasSavedSecret ?? previous?.has_saved_secret ?? false,
    has_env_secret: previous?.has_env_secret ?? false,
  }
}

function errorMessage(reason: unknown) {
  return reason instanceof Error ? reason.message : "请求失败，请稍后重试。"
}
