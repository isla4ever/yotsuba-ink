export type ProviderKind = "openai-compatible" | "openai-compatible-image"

export type ProviderProfile = {
  id: string
  name: string
  kind: ProviderKind
  template_id: string
  base_url: string
  api_key_env: string
  default_model: string
  model_options: string[]
  model_supported_parameters: Record<string, string[]>
  estimated_cost_per_output_usd: number | null
  is_global_default: boolean
  has_saved_secret: boolean
  has_env_secret: boolean
  enabled: boolean
}

export type ProviderTemplate = {
  id: string
  label: string
  kind: ProviderKind
  base_url: string
  default_model: string
  model_options: string[]
  api_key_env: string
  docs_url: string
  integration_tier: "official" | "compatibility" | "gateway" | "custom"
  description: string
  execution_allowed: boolean
  execution_policy_note: string
  workflow_execution_allowed: boolean
  workflow_execution_policy_note: string
}

export type ProviderTestResult = {
  ok: boolean
  provider_id: string
  kind: ProviderKind
  model: string
  error_code: string
  message: string
  response_preview: string
}

export type ProviderModelDiscoveryResult = {
  ok: boolean
  provider_id: string
  kind: ProviderKind
  models: string[]
  added_models: string[]
  model_supported_parameters: Record<string, string[]>
  error_code: string
  message: string
}
