export type StageType = "brief" | "spine" | "cast" | "volumes" | "detail" | "text" | "cover" | "export"

export type QualityMode = "fast" | "balanced" | "deep"

export type InputField = {
  key: string
  label: string
  type: "text" | "textarea" | "number" | "select" | "tags" | "boolean"
  required?: boolean
  default?: unknown
  help?: string
  hint?: string
  placeholder?: string
  options?: string[]
}

export type ModelSettings = {
  model: string
  temperature: number
  max_tokens: number
  top_p: number
  timeout_seconds: number
}

export type ProviderProfile = {
  id: string
  name: string
  kind: "openai-compatible" | "openai-compatible-image"
  default_model: string
  model_options?: string[]
  enabled: boolean
}

export type WorkflowStage = {
  id: string
  type: StageType
  label: string
  provider_profile_id: string
  image_provider_profile_id?: string
  model_settings: ModelSettings
  prompt_template_id: string
  input_schema: InputField[]
  generation_budget?: { max_tokens: number; description?: string } | null
}

export type WorkflowDefinition = {
  architecture_version: "phase27-vnext"
  id: string
  name: string
  version: string
  is_template: boolean
  global_inputs: InputField[]
  provider_profiles: ProviderProfile[]
  prompt_templates: unknown[]
  quality_mode: QualityMode
  canvas_layout?: unknown
  nodes: WorkflowStage[]
  edges: Array<{ id: string; source: string; target: string }>
}
