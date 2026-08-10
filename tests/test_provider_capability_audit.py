from __future__ import annotations

from fnmatch import fnmatchcase

from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.providers.openai_request import build_chat_request
from novel_workflow.providers.templates import list_provider_templates, provider_template


TEXT_TASKS = (
    "info",
    "characters",
    "summary",
    "outline",
    "detail",
    "text",
    "cover",
    "text.review",
    "text.evidence",
)


def test_provider_templates_keep_official_evidence_with_model_overrides() -> None:
    templates = list_provider_templates()

    assert len({template.id for template in templates}) == len(templates)
    for template in templates:
        assert template.docs_url.startswith("https://"), template.id
        assert template.docs_url in template.capability_docs, template.id
        assert all(url.startswith("https://") for url in template.capability_docs), template.id
        for profile in template.model_capabilities:
            assert profile.capability_docs, f"{template.id}:{profile.model_pattern}"
            assert all(url.startswith("https://") for url in profile.capability_docs)
            if profile.evidence_status != "verified":
                assert profile.evidence_note


def test_every_static_text_model_builds_a_non_conflicting_request() -> None:
    schema = {"type": "object", "properties": {"ok": {"type": "boolean"}}}
    for template in list_provider_templates():
        if template.kind != "openai-compatible" or not template.execution_allowed:
            continue
        for model in _audit_models(template):
            for task_name in TEXT_TASKS:
                request = build_chat_request(
                    template=template,
                    model=model,
                    system="Return JSON.",
                    user='Use this JSON example: {"ok":true}',
                    task_name=task_name,
                    temperature=0.7,
                    top_p=0.9,
                    max_tokens=1024,
                    structured_schema=schema,
                )
                policy = resolve_request_policy(template, model=model, task_name=task_name)
                token_fields = {"max_tokens", "max_completion_tokens"} & request.keys()
                assert len(token_fields) <= 1, (template.id, model, task_name)
                if policy.sampling_parameter_mode == "none":
                    assert "temperature" not in request and "top_p" not in request
                if policy.structured_output_mode == "prompt_only" or not template.supports_response_format:
                    assert "response_format" not in request
                elif policy.structured_output_mode == "json_object":
                    assert request["response_format"] == {"type": "json_object"}
                elif policy.supports_json_schema:
                    assert request["response_format"]["type"] == "json_schema"
                extra_body = request.get("extra_body", {})
                assert not (
                    "thinking_budget" in extra_body and "reasoning_effort" in request
                ), (template.id, model, task_name)
                assert not (
                    "thinking_level" in extra_body and "thinking_budget" in extra_body
                ), (template.id, model, task_name)


def test_nested_model_policy_is_isolated_between_requests() -> None:
    template = provider_template("tokenhub-text", "openai-compatible")

    first = resolve_request_policy(template, model="glm-5.2", task_name="detail")
    thinking = first.extra_body_parameters["thinking"]
    assert isinstance(thinking, dict)
    thinking["type"] = "tampered"

    second = resolve_request_policy(template, model="glm-5.2", task_name="detail")
    assert second.extra_body_parameters["thinking"] == {"type": "enabled"}


def _audit_models(template) -> list[str]:
    models = list(template.model_options)
    if template.default_model and template.default_model not in models:
        models.insert(0, template.default_model)
    for profile in template.model_capabilities:
        if any(fnmatchcase(model.casefold(), profile.model_pattern.casefold()) for model in models):
            continue
        candidate = profile.model_pattern.replace("*", "audit")
        if candidate:
            models.append(candidate)
    return models or ["audit-model"]
