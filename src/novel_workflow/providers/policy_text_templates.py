from novel_workflow.providers.template_contract import ProviderTemplate


POLICY_TEXT_PROVIDER_TEMPLATES = (
    ProviderTemplate(
        id="xiaomi-mimo-text",
        label="小米 MiMo Token Plan 文本",
        kind="openai-compatible",
        base_url="https://token-plan-cn.xiaomimimo.com/v1",
        default_model="mimo-v2.5-pro",
        model_options=["mimo-v2.5-pro", "mimo-v2.5"],
        api_key_env="XIAOMI_MIMO_API_KEY",
        docs_url="https://token-plan-cn.xiaomimimo.com/",
        integration_tier="compatibility",
        description="小米 MiMo Token Plan 的编程工具专用入口，不用于 Yotsuba Ink 应用后端。",
        structured_output_mode="json_object",
        requires_json_keyword=True,
        requires_json_example=True,
        auth_header="api-key",
        max_tokens_field="max_completion_tokens",
        sampling_parameter_mode="temperature",
        omit_sampling_when_thinking=True,
        extra_body_parameters={"thinking": {"type": "disabled"}},
        thinking_parameter="thinking.type",
        structured_output_notes="MiMo 2.5 使用 json_object；Prompt 会补齐 JSON 字段示例，响应继续经过本地合同校验。",
        execution_allowed=False,
        execution_policy_note="Token Plan 仅限 AI 编程工具，不得用于自定义应用后端或自动化脚本。请改用按量计费 MiMo API Key。",
    ),
)
