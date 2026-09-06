import type {
  ProviderKind,
  ProviderModelDiscoveryResult,
  ProviderProfile,
  ProviderTemplate,
  ProviderTestResult,
} from "../contracts/provider"

export async function listProviderProfiles(
  signal?: AbortSignal,
): Promise<ProviderProfile[]> {
  const response = await fetch("/api/providers", { signal })
  if (!response.ok) throw await providerApiError(response, "/api/providers")
  const payload: unknown = await response.json()
  if (!Array.isArray(payload))
    throw new Error("AI 服务接口返回了无法识别的数据")
  return payload as ProviderProfile[]
}

export async function listProviderTemplates(
  signal?: AbortSignal,
): Promise<ProviderTemplate[]> {
  const response = await fetch("/api/providers/templates", { signal })
  if (!response.ok)
    throw await providerApiError(response, "/api/providers/templates")
  const payload: unknown = await response.json()
  if (!Array.isArray(payload))
    throw new Error("服务商模板接口返回了无法识别的数据")
  return payload as ProviderTemplate[]
}

export async function saveProviderProfile(
  provider: ProviderProfile,
): Promise<ProviderProfile> {
  const response = await postJson("/api/providers", profilePayload(provider))
  return response.json() as Promise<ProviderProfile>
}

export async function setDefaultProviderProfile(
  providerId: string,
  kind: ProviderKind,
): Promise<ProviderProfile[]> {
  const response = await postJson("/api/providers/default", {
    provider_id: providerId,
    kind,
  })
  return response.json() as Promise<ProviderProfile[]>
}

export async function saveProviderSecret(providerId: string, apiKey: string) {
  const response = await postJson(
    `/api/providers/${encodeURIComponent(providerId)}/secret`,
    { api_key: apiKey },
  )
  return response.json() as Promise<{
    ok: boolean
    provider_id: string
    has_saved_secret: boolean
  }>
}

export async function deleteProviderSecret(providerId: string) {
  const url = `/api/providers/${encodeURIComponent(providerId)}/secret`
  const response = await fetch(url, { method: "DELETE" })
  if (!response.ok) throw await providerApiError(response, url)
  return response.json() as Promise<{
    ok: boolean
    provider_id: string
    has_saved_secret: boolean
  }>
}

export async function testProviderConnection(
  provider: ProviderProfile,
  apiKey = "",
): Promise<ProviderTestResult> {
  const response = await postJson("/api/providers/test", {
    provider: profilePayload(provider),
    api_key: apiKey,
    prompt: "你好，请用一句话确认连接正常。",
  })
  return response.json() as Promise<ProviderTestResult>
}

export async function discoverProviderModels(
  providerId: string,
  apiKey = "",
): Promise<ProviderModelDiscoveryResult> {
  const url = `/api/providers/${encodeURIComponent(providerId)}/models/discover`
  const response = await postJson(url, { api_key: apiKey })
  return response.json() as Promise<ProviderModelDiscoveryResult>
}

export async function deleteProviderProfile(providerId: string) {
  const url = `/api/providers/${encodeURIComponent(providerId)}`
  const response = await fetch(url, { method: "DELETE" })
  if (!response.ok) throw await providerApiError(response, url)
  return response.json() as Promise<{
    ok: boolean
    provider_id: string
  }>
}

function profilePayload(provider: ProviderProfile) {
  return {
    id: provider.id,
    name: provider.name,
    kind: provider.kind,
    template_id: provider.template_id,
    base_url: provider.base_url,
    api_key_env: provider.api_key_env,
    default_model: provider.default_model,
    model_options: provider.model_options,
    model_supported_parameters: provider.model_supported_parameters,
    estimated_cost_per_output_usd: provider.estimated_cost_per_output_usd,
    estimated_input_cost_per_million_tokens_usd:
      provider.estimated_input_cost_per_million_tokens_usd,
    estimated_output_cost_per_million_tokens_usd:
      provider.estimated_output_cost_per_million_tokens_usd,
    model_pricing: provider.model_pricing,
    is_global_default: provider.is_global_default,
    enabled: provider.enabled,
  }
}

async function postJson(url: string, body: unknown) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await providerApiError(response, url)
  return response
}

async function providerApiError(response: Response, url: string) {
  let detail = ""
  try {
    const payload = (await response.json()) as { detail?: unknown }
    if (typeof payload.detail === "string") detail = payload.detail
  } catch {
    detail = ""
  }
  return new Error(detail || `请求失败：${url} (${response.status})`)
}
