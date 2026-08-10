from novel_workflow.providers.compatible_text_templates import (
    COMPATIBLE_TEXT_PROVIDER_TEMPLATES,
)
from novel_workflow.providers.official_text_templates import (
    OFFICIAL_TEXT_PROVIDER_TEMPLATES,
)

_TEXT_PROVIDER_TEMPLATE_ORDER = (
    "openai-compatible-text",
    "openai-chat",
    "tokenhub-text",
    "xiaomi-mimo-text",
    "xiaomi-mimo-api-text",
    "deepseek-text",
    "dashscope-text",
    "siliconflow-text",
    "moonshot-text",
    "zhipu-text",
    "zhipu-coding-plan",
    "openrouter-text",
    "volcengine-ark-text",
    "gemini-text",
    "groq-text",
    "together-text",
    "xai-text",
    "mistral-text",
    "fireworks-text",
    "cerebras-text",
    "anthropic-openai-text",
    "litellm-proxy-text",
    "portkey-gateway-text",
)

_TEXT_PROVIDER_TEMPLATES_BY_ID = {
    template.id: template
    for template in (*OFFICIAL_TEXT_PROVIDER_TEMPLATES, *COMPATIBLE_TEXT_PROVIDER_TEMPLATES)
}

TEXT_PROVIDER_TEMPLATES = tuple(
    _TEXT_PROVIDER_TEMPLATES_BY_ID[template_id]
    for template_id in _TEXT_PROVIDER_TEMPLATE_ORDER
)
