from novel_workflow.providers.template_contract import ProviderTemplate


GATEWAY_TEXT_PROVIDER_TEMPLATES = (
    ProviderTemplate(
        id="litellm-proxy-text",
        label="LiteLLM Proxy",
        kind="openai-compatible",
        base_url="",
        default_model="",
        api_key_env="LITELLM_API_KEY",
        docs_url="https://docs.litellm.ai/docs/simple_proxy",
        capability_docs=["https://docs.litellm.ai/docs/completion/json_mode"],
        integration_tier="gateway",
        description="连接自建 LiteLLM Proxy；Yotsuba Ink 仍负责阶段、预算、恢复与写回。",
        supports_response_format=False,
        structured_output_mode="prompt_only",
        requires_json_keyword=True,
        requires_json_example=True,
        structured_output_notes="网关不继承任一上游能力承诺；默认只做 Prompt 约束与本地校验。",
    ),
    ProviderTemplate(
        id="portkey-gateway-text",
        label="Portkey AI Gateway",
        kind="openai-compatible",
        base_url="https://api.portkey.ai/v1",
        default_model="",
        api_key_env="PORTKEY_API_KEY",
        docs_url="https://portkey.ai/docs/api-reference/inference-api/models/models",
        capability_docs=[
            "https://portkey.ai/docs/product/ai-gateway/universal-api",
            "https://portkey.ai/docs/product/ai-gateway/responses-api",
        ],
        integration_tier="gateway",
        description="Portkey 网关入口；模型路由和附加 Header 需与网关配置保持一致。",
        supports_response_format=False,
        structured_output_mode="prompt_only",
        requires_json_keyword=True,
        requires_json_example=True,
        models_auth_header="x-portkey-api-key",
        structured_output_notes="网关路由能力未知；默认不发送 response_format，避免上游静默忽略。",
    ),
)
