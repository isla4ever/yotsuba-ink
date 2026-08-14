from novel_workflow.providers.template_contract import (
    ModelCapabilityProfile,
    ProviderTemplate,
)


ZHIPU_CODING_PLAN_PROVIDER_TEMPLATE = ProviderTemplate(
    id="zhipu-coding-plan",
    label="智谱 GLM Coding Plan",
    kind="openai-compatible",
    base_url="https://open.bigmodel.cn/api/coding/paas/v4",
    default_model="glm-5.2",
    model_options=["glm-5.2", "glm-5-turbo", "glm-4.7"],
    api_key_env="ZHIPUAI_API_KEY",
    docs_url="https://docs.bigmodel.cn/cn/coding-plan/tool/others",
    capability_docs=[
        "https://docs.bigmodel.cn/cn/coding-plan/tool/others",
        "https://docs.bigmodel.cn/cn/coding-plan/latest-model",
        "https://docs.bigmodel.cn/cn/guide/capabilities/struct-output",
        "https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2",
    ],
    description=(
        "智谱 Coding Plan 专属 OpenAI 兼容入口；用于开发和验收，"
        "不与标准按量接口余额混用。"
    ),
    structured_output_mode="json_object",
    requires_json_keyword=True,
    requires_json_example=True,
    sampling_parameter_mode="temperature",
    omit_sampling_when_thinking=True,
    extra_body_parameters={"thinking": {"type": "disabled"}},
    thinking_parameter="thinking.type + reasoning_effort (GLM-5.2)",
    structured_output_notes="Coding Plan 使用专属 endpoint；结构化结果仍经过本地合同校验。",
    model_capabilities=[
        ModelCapabilityProfile(
            model_pattern="glm-5.2*",
            capability_docs=["https://docs.bigmodel.cn/cn/guide/models/text/glm-5.2"],
            stage_request_parameters={
                "brief": {"reasoning_effort": "high"},
                "cast": {"reasoning_effort": "high"},
                "volumes": {"reasoning_effort": "high"},
                "detail": {"reasoning_effort": "high", "stream": True},
                "text.review": {"reasoning_effort": "high"},
            },
            stage_extra_body_parameters={
                "brief": {"thinking": {"type": "enabled"}},
                "spine": {"thinking": {"type": "disabled"}},
                "cast": {"thinking": {"type": "enabled"}},
                "volumes": {"thinking": {"type": "enabled"}},
                "detail": {"thinking": {"type": "enabled"}},
                "text": {"thinking": {"type": "disabled"}},
                "text.evidence": {"thinking": {"type": "disabled"}},
                "text.review": {"thinking": {"type": "enabled"}},
            },
        ),
        ModelCapabilityProfile(
            model_pattern="glm-5-turbo*",
            capability_docs=["https://docs.bigmodel.cn/cn/coding-plan/latest-model"],
            extra_body_parameters={"thinking": {"type": "disabled"}},
        ),
        ModelCapabilityProfile(
            model_pattern="glm-4.7*",
            capability_docs=["https://docs.bigmodel.cn/cn/coding-plan/latest-model"],
            extra_body_parameters={"thinking": {"type": "disabled"}},
        ),
    ],
)
