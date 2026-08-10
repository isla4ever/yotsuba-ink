from novel_workflow.providers.official_cn_text_templates import (
    OFFICIAL_CN_TEXT_PROVIDER_TEMPLATES,
)
from novel_workflow.providers.official_global_text_templates import (
    OFFICIAL_GLOBAL_TEXT_PROVIDER_TEMPLATES,
)
from novel_workflow.providers.policy_text_templates import (
    POLICY_TEXT_PROVIDER_TEMPLATES,
)

OFFICIAL_TEXT_PROVIDER_TEMPLATES = (
    *OFFICIAL_GLOBAL_TEXT_PROVIDER_TEMPLATES,
    *POLICY_TEXT_PROVIDER_TEMPLATES,
    *OFFICIAL_CN_TEXT_PROVIDER_TEMPLATES,
)
