from __future__ import annotations

from typing import Literal

from novel_workflow.providers.template_contract import ModelCapabilityProfile, ProviderTemplate


def _qwen_hybrid_profile(
    model_pattern: str,
    *,
    info_budget: int,
    outline_budget: int,
    detail_budget: int,
    review_budget: int,
    structured_output_mode: Literal["json_schema", "json_object", "prompt_only"] | None = None,
    omit_max_tokens_in_structured: bool | None = None,
) -> ModelCapabilityProfile:
    return ModelCapabilityProfile(
        model_pattern=model_pattern,
        capability_docs=[
            "https://help.aliyun.com/zh/model-studio/qwen-structured-output",
            "https://help.aliyun.com/zh/model-studio/deep-thinking",
            "https://help.aliyun.com/zh/model-studio/text-generation-model",
        ],
        evidence_status="verified",
        evidence_note="结构化输出专题已明确列出当前模型系列；输出仍经过本地合同校验。",
        structured_output_mode=structured_output_mode,
        supports_json_schema=False if structured_output_mode == "prompt_only" else None,
        omit_max_tokens_in_structured=omit_max_tokens_in_structured,
        stage_request_parameters={
            "info": {"stream": True},
            "outline": {"stream": True},
            "detail": {"stream": True},
            "text.review": {"stream": True},
        },
        stage_extra_body_parameters={
            "info": {"enable_thinking": True, "thinking_budget": info_budget},
            "summary": {"enable_thinking": False},
            "outline": {"enable_thinking": True, "thinking_budget": outline_budget},
            "detail": {"enable_thinking": True, "thinking_budget": detail_budget},
            "text": {"enable_thinking": False},
            "text.evidence": {"enable_thinking": False},
            "text.review": {"enable_thinking": True, "thinking_budget": review_budget},
        },
    )


DASHSCOPE_TEXT_PROVIDER_TEMPLATE = ProviderTemplate(
    id="dashscope-text",
    label="阿里云百炼文本",
    kind="openai-compatible",
    base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
    default_model="qwen3.7-plus",
    model_options=["qwen3.7-max", "qwen3.7-plus", "qwen3.7-flash", "qwen3.6-flash"],
    api_key_env="DASHSCOPE_API_KEY",
    docs_url="https://help.aliyun.com/zh/model-studio/qwen-structured-output",
    capability_docs=[
        "https://help.aliyun.com/zh/model-studio/deep-thinking",
        "https://help.aliyun.com/zh/model-studio/text-generation-model",
    ],
    description="阿里云百炼 OpenAI 兼容模式；Plus 负责稳定结构创作，Max 负责质量优先正文，Flash 负责轻量节点。",
    structured_output_mode="json_object",
    requires_json_keyword=True,
    requires_json_example=True,
    omit_max_tokens_in_structured=True,
    sampling_parameter_mode="temperature",
    extra_body_parameters={"enable_thinking": False},
    thinking_parameter="extra_body.enable_thinking",
    structured_output_notes="Qwen3.7 Max/Plus/Flash 与 Qwen3.6 Flash 使用官方 JSON Mode；输出继续经过本地合同校验。",
    model_capabilities=[
        _qwen_hybrid_profile(
            "qwen3.7-max*",
            info_budget=6144,
            outline_budget=12288,
            detail_budget=16384,
            review_budget=12288,
            structured_output_mode="json_object",
            omit_max_tokens_in_structured=True,
        ),
        _qwen_hybrid_profile(
            "qwen3.7-plus*",
            info_budget=4096,
            outline_budget=8192,
            detail_budget=12288,
            review_budget=8192,
        ),
        _qwen_hybrid_profile(
            "qwen3.7-flash*",
            info_budget=3072,
            outline_budget=6144,
            detail_budget=8192,
            review_budget=6144,
        ),
        _qwen_hybrid_profile(
            "qwen3.6-flash*",
            info_budget=3072,
            outline_budget=6144,
            detail_budget=8192,
            review_budget=6144,
        ),
    ],
)
