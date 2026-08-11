from __future__ import annotations

from novel_workflow.providers.template_contract import (
    ModelCapabilityProfile,
    ProviderTemplate,
)
from novel_workflow.providers.qwen_text_template import DASHSCOPE_TEXT_PROVIDER_TEMPLATE
from novel_workflow.providers.zhipu_coding_plan_template import (
    ZHIPU_CODING_PLAN_PROVIDER_TEMPLATE,
)


OFFICIAL_CN_TEXT_PROVIDER_TEMPLATES = (
    ProviderTemplate(
        id="xiaomi-mimo-api-text",
        label="小米 MiMo API 文本",
        kind="openai-compatible",
        base_url="https://api.xiaomimimo.com/v1",
        default_model="mimo-v2.5-pro",
        model_options=["mimo-v2.5-pro", "mimo-v2.5"],
        api_key_env="MIMO_API_KEY",
        docs_url="https://mimo.mi.com/docs/zh-CN/api/chat/openai-api",
        capability_docs=[
            "https://mimo.mi.com/docs/zh-CN/quick-start/usage-guide/text-generation/structured-output",
            "https://mimo.mi.com/docs/quick-start/summary/model",
        ],
        description="小米 MiMo 按量计费 API；api-key 鉴权，适合应用后端小说链路。",
        structured_output_mode="json_object",
        requires_json_keyword=True,
        requires_json_example=True,
        auth_header="api-key",
        max_tokens_field="max_completion_tokens",
        sampling_parameter_mode="temperature",
        omit_sampling_when_thinking=True,
        extra_body_parameters={"thinking": {"type": "disabled"}},
        thinking_parameter="thinking.type",
        structured_output_notes="MiMo 2.5 使用 json_object；max_completion_tokens 同时覆盖思考与正文，默认关闭思考以保护结构化输出预算。",
        model_capabilities=[
            ModelCapabilityProfile(
                model_pattern="mimo-v2.5-pro*",
                capability_docs=["https://mimo.mi.com/docs/zh-CN/api/chat/openai-api"],
                stage_extra_body_parameters={
                    "info": {"thinking": {"type": "enabled"}},
                    "summary": {"thinking": {"type": "disabled"}},
                    "outline": {"thinking": {"type": "enabled"}},
                    "detail": {"thinking": {"type": "enabled"}},
                    "text": {"thinking": {"type": "disabled"}},
                    "text.evidence": {"thinking": {"type": "disabled"}},
                    "text.review": {"thinking": {"type": "enabled"}},
                },
            ),
        ],
    ),
    ProviderTemplate(
        id="deepseek-text",
        label="DeepSeek 官方文本",
        kind="openai-compatible",
        base_url="https://api.deepseek.com",
        default_model="deepseek-v4-pro",
        model_options=["deepseek-v4-pro", "deepseek-v4-flash"],
        api_key_env="DEEPSEEK_API_KEY",
        docs_url="https://api-docs.deepseek.com/zh-cn/guides/json_mode",
        capability_docs=[
            "https://api-docs.deepseek.com/zh-cn/guides/chat_prefix_completion",
            "https://api-docs.deepseek.com/zh-cn/guides/thinking_mode",
            "https://api-docs.deepseek.com/zh-cn/guides/kv_cache/",
            "https://api-docs.deepseek.com/zh-cn/quick_start/pricing",
        ],
        description="DeepSeek V4 官方接口；Pro 负责复杂创作，Flash 适合高频结构化节点。",
        structured_output_mode="json_object",
        requires_json_keyword=True,
        requires_json_example=True,
        empty_content_policy="documented_structured_empty",
        assistant_prefill_mode="deepseek_prefix_beta",
        assistant_prefill_base_url="https://api.deepseek.com/beta",
        assistant_prefill_tasks=["text"],
        sampling_parameter_mode="temperature",
        omit_sampling_when_thinking=True,
        extra_body_parameters={"thinking": {"type": "disabled"}},
        thinking_parameter="thinking.type + reasoning_effort",
        structured_output_notes=(
            "结构化节点和语义审校使用 JSON Output；独立冷读使用 JSON Prompt + 本地 Schema 校验。"
            "官方已知的空 content 会显式失败且不会隐藏重试；Prefix Completion 仅用于显式 Beta 实验。"
        ),
        model_capabilities=[
            ModelCapabilityProfile(
                model_pattern="deepseek-v4-pro*",
                capability_docs=["https://api-docs.deepseek.com/zh-cn/guides/thinking_mode"],
                stage_request_parameters={
                    "info": {"reasoning_effort": "high"},
                },
                stage_extra_body_parameters={
                    "info": {"thinking": {"type": "enabled"}},
                    # Summary is a compact structured compression node. Keeping
                    # its output budget for JSON avoids reasoning consuming the
                    # response envelope before the artifact is complete.
                    "summary": {"thinking": {"type": "disabled"}},
                    # Outline and detail are bounded structured artifacts. Their
                    # response budget must remain available for the JSON object.
                    "outline": {"thinking": {"type": "disabled"}},
                    "detail": {"thinking": {"type": "disabled"}},
                    "text": {"thinking": {"type": "disabled"}},
                    "text.evidence": {"thinking": {"type": "disabled"}},
                    # Review lanes return a compact strict JSON decision. A live
                    # DeepSeek call consumed its entire response budget in
                    # reasoning and returned no JSON, so reserve this envelope
                    # for the review artifact itself.
                    "text.review": {"thinking": {"type": "disabled"}},
                },
            ),
            ModelCapabilityProfile(
                model_pattern="deepseek-v4-flash*",
                capability_docs=["https://api-docs.deepseek.com/zh-cn/guides/thinking_mode"],
                stage_request_parameters={
                    "info": {"reasoning_effort": "high"},
                },
                stage_extra_body_parameters={
                    "info": {"thinking": {"type": "enabled"}},
                    "summary": {"thinking": {"type": "disabled"}},
                    "outline": {"thinking": {"type": "disabled"}},
                    "detail": {"thinking": {"type": "disabled"}},
                    "text": {"thinking": {"type": "disabled"}},
                    "text.evidence": {"thinking": {"type": "disabled"}},
                    "text.review": {"thinking": {"type": "disabled"}},
                },
            ),
        ],
    ),
    DASHSCOPE_TEXT_PROVIDER_TEMPLATE,
    ProviderTemplate(
        id="moonshot-text",
        label="Kimi / Moonshot 文本",
        kind="openai-compatible",
        base_url="https://api.moonshot.cn/v1",
        default_model="kimi-k3",
        model_options=["kimi-k3", "kimi-k2.6"],
        api_key_env="MOONSHOT_API_KEY",
        docs_url="https://platform.kimi.com/docs/api/chat",
        capability_docs=[
            "https://platform.kimi.com/docs/guide/response_format",
            "https://platform.kimi.com/docs/api/models-overview",
            "https://platform.kimi.com/docs/api/partial",
        ],
        description="官方 Chat 模型目录以 K3 为默认；K2.6 作为轻量结构化与成本回退。",
        structured_output_mode="json_schema",
        supports_json_schema=True,
        schema_transform="openai_subset",
        requires_json_keyword=True,
        requires_json_example=True,
        assistant_prefill_mode="kimi_partial",
        assistant_prefill_tasks=["text"],
        assistant_prefill_model_patterns=["kimi-k3*", "kimi-k2.6*"],
        supports_prompt_cache_key=True,
        max_tokens_field="max_completion_tokens",
        sampling_parameter_mode="none",
        thinking_parameter="reasoning_effort (K3) / thinking.type (K2.6)",
        structured_output_notes="优先 JSON Schema；Partial 不与 response_format 混用；同一 Run/阶段使用散列 prompt_cache_key 提高共享前缀命中。",
        model_capabilities=[
            ModelCapabilityProfile(
                model_pattern="kimi-k3*",
                capability_docs=[
                    "https://platform.kimi.com/docs/guide/response_format",
                    "https://platform.kimi.com/docs/api/models-overview",
                ],
                json_schema_strict=True,
                stage_request_parameters={
                    "info": {"reasoning_effort": "high"},
                    "summary": {"reasoning_effort": "low"},
                    "outline": {"reasoning_effort": "high"},
                    "detail": {"reasoning_effort": "max"},
                    "text": {"reasoning_effort": "low"},
                    "text.evidence": {"reasoning_effort": "low"},
                    "text.review": {"reasoning_effort": "max"},
                },
            ),
            ModelCapabilityProfile(
                model_pattern="kimi-k2.6*",
                capability_docs=[
                    "https://platform.kimi.com/docs/api/chat",
                    "https://platform.kimi.com/docs/api/partial",
                ],
                extra_body_parameters={"thinking": {"type": "disabled"}},
            ),
        ],
    ),
    ProviderTemplate(
        id="zhipu-text",
        label="智谱 GLM 文本",
        kind="openai-compatible",
        base_url="https://open.bigmodel.cn/api/paas/v4",
        default_model="glm-5.2",
        model_options=["glm-5.2", "glm-5.1", "glm-4.7"],
        api_key_env="ZHIPUAI_API_KEY",
        docs_url="https://docs.bigmodel.cn/cn/guide/capabilities/struct-output",
        capability_docs=[
            "https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2",
            "https://docs.bigmodel.cn/cn/guide/capabilities/thinking",
        ],
        description="GLM-5.2 负责复杂创作与评审，5.1/4.7 作为兼容和轻量选项。",
        structured_output_mode="json_object",
        requires_json_keyword=True,
        requires_json_example=True,
        sampling_parameter_mode="temperature",
        omit_sampling_when_thinking=True,
        extra_body_parameters={"thinking": {"type": "disabled"}},
        thinking_parameter="thinking.type + reasoning_effort (GLM-5.2)",
        structured_output_notes="对话接口使用 json_object；思考参数按具体模型匹配，结果始终经过本地合同校验。",
        model_capabilities=[
            ModelCapabilityProfile(
                model_pattern="glm-5.2*",
                capability_docs=["https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2"],
                stage_request_parameters={
                    "info": {"reasoning_effort": "high"},
                    "outline": {"reasoning_effort": "high"},
                    "detail": {"reasoning_effort": "high", "stream": True},
                    "text.review": {"reasoning_effort": "high"},
                },
                stage_extra_body_parameters={
                    "info": {"thinking": {"type": "enabled"}},
                    "summary": {"thinking": {"type": "disabled"}},
                    "outline": {"thinking": {"type": "enabled"}},
                    "detail": {"thinking": {"type": "enabled"}},
                    "text": {"thinking": {"type": "disabled"}},
                    "text.evidence": {"thinking": {"type": "disabled"}},
                    "text.review": {"thinking": {"type": "enabled"}},
                },
            ),
            ModelCapabilityProfile(
                model_pattern="glm-5.1*",
                capability_docs=["https://docs.bigmodel.cn/cn/guide/capabilities/thinking"],
                stage_extra_body_parameters={
                    "detail": {"thinking": {"type": "enabled"}},
                    "text.review": {"thinking": {"type": "enabled"}},
                    "text": {"thinking": {"type": "disabled"}},
                },
            ),
            ModelCapabilityProfile(
                model_pattern="glm-4.7*",
                capability_docs=["https://docs.bigmodel.cn/cn/guide/capabilities/thinking"],
                extra_body_parameters={"thinking": {"type": "disabled"}},
            ),
        ],
    ),
    ZHIPU_CODING_PLAN_PROVIDER_TEMPLATE,
)
