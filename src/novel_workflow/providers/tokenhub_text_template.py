from __future__ import annotations

from novel_workflow.providers.template_contract import (
    ModelCapabilityProfile,
    ProviderTemplate,
)


_STRUCTURED_STAGE_THINKING = {
    "info": {"thinking": {"type": "enabled"}},
    "summary": {"thinking": {"type": "disabled"}},
    "outline": {"thinking": {"type": "enabled"}},
    "detail": {"thinking": {"type": "enabled"}},
    "text": {"thinking": {"type": "disabled"}},
    "text.evidence": {"thinking": {"type": "disabled"}},
    "text.review": {"thinking": {"type": "enabled"}},
}


def _tokenhub_deepseek_profile(model_pattern: str) -> ModelCapabilityProfile:
    return ModelCapabilityProfile(
        model_pattern=model_pattern,
        capability_docs=["https://cloud.tencent.com/document/product/1823/132248"],
        structured_output_mode="json_object",
        supports_json_schema=False,
        sampling_parameter_mode="temperature",
        requires_json_keyword=True,
        requires_json_example=True,
        extra_body_parameters={"thinking": {"type": "disabled"}},
    )


def _tokenhub_glm_profile(
    model_pattern: str,
    *,
    supports_reasoning_effort: bool,
) -> ModelCapabilityProfile:
    stage_parameters = {
        key: dict(value)
        for key, value in _STRUCTURED_STAGE_THINKING.items()
    }
    if supports_reasoning_effort:
        stage_parameters["info"]["reasoning_effort"] = "high"
        stage_parameters["outline"]["reasoning_effort"] = "high"
        stage_parameters["detail"]["reasoning_effort"] = "max"
        stage_parameters["text.review"]["reasoning_effort"] = "max"
    return ModelCapabilityProfile(
        model_pattern=model_pattern,
        capability_docs=["https://cloud.tencent.com/document/product/1823/132061"],
        sampling_parameter_mode="temperature",
        extra_body_parameters={"thinking": {"type": "disabled"}},
        stage_extra_body_parameters=stage_parameters,
    )


TOKENHUB_TEXT_PROVIDER_TEMPLATE = ProviderTemplate(
    id="tokenhub-text",
    label="腾讯 TokenHub 文本",
    kind="openai-compatible",
    base_url="https://tokenhub.tencentmaas.com/v1",
    default_model="deepseek-v4-pro",
    model_options=[
        "deepseek-v4-pro",
        "deepseek-v4-flash",
        "deepseek-v3.2",
        "hy3",
        "hy3-preview",
        "glm-5.2",
        "glm-5.1",
        "kimi-k3",
        "kimi-k2.6",
        "minimax-m3",
        "minimax-m2.7",
        "minimax-m2.5",
        "qwen3.5-plus",
        "qwen3.5-flash",
    ],
    api_key_env="NOVEL_LLM_API_KEY",
    docs_url="https://cloud.tencent.com/document/product/1823/130079",
    capability_docs=[
        "https://cloud.tencent.com/document/product/1823/132248",
        "https://cloud.tencent.com/document/product/1823/132061",
        "https://cloud.tencent.com/document/product/1823/132232",
        "https://cloud.tencent.com/document/product/1823/132246",
    ],
    integration_tier="gateway",
    description="腾讯 TokenHub 按量计费入口；按模型族应用网关官方参数合同。",
    structured_output_mode="json_schema",
    supports_json_schema=True,
    schema_transform="openai_subset",
    requires_json_keyword=True,
    requires_json_example=True,
    omit_sampling_when_thinking=True,
    model_capabilities=[
        _tokenhub_deepseek_profile("deepseek-v4-*"),
        _tokenhub_deepseek_profile("deepseek-v3.2*"),
        _tokenhub_glm_profile("glm-5.2*", supports_reasoning_effort=True),
        _tokenhub_glm_profile("glm-5.1*", supports_reasoning_effort=False),
        ModelCapabilityProfile(
            model_pattern="kimi-k3*",
            capability_docs=["https://cloud.tencent.com/document/product/1823/132232"],
            json_schema_strict=True,
            max_tokens_field="max_completion_tokens",
            sampling_parameter_mode="none",
            request_parameters={"reasoning_effort": "max"},
        ),
        ModelCapabilityProfile(
            model_pattern="kimi-k2.6*",
            capability_docs=["https://cloud.tencent.com/document/product/1823/132232"],
            max_tokens_field="max_tokens",
            sampling_parameter_mode="temperature",
            extra_body_parameters={"thinking": {"type": "disabled"}},
        ),
        ModelCapabilityProfile(
            model_pattern="minimax-m3*",
            capability_docs=["https://cloud.tencent.com/document/product/1823/132246"],
            structured_output_mode="json_object",
            supports_json_schema=False,
            sampling_parameter_mode="temperature",
            requires_json_keyword=True,
            requires_json_example=True,
            extra_body_parameters={"thinking": {"type": "disabled"}},
        ),
        ModelCapabilityProfile(
            model_pattern="minimax-m2.*",
            capability_docs=["https://cloud.tencent.com/document/product/1823/132246"],
            structured_output_mode="prompt_only",
            supports_json_schema=False,
            sampling_parameter_mode="temperature",
            requires_json_keyword=True,
            requires_json_example=True,
            extra_body_parameters={"reasoning_split": True},
        ),
    ],
    structured_output_notes=(
        "公共 Chat 接口支持 json_schema，但 DeepSeek/MiniMax 按模型专页降为 JSON Object 或 "
        "Prompt-only；Kimi/GLM 使用各自 Token、思考与采样合同。"
    ),
)
