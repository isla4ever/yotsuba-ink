from __future__ import annotations

import json
from dataclasses import dataclass
from fnmatch import fnmatchcase
from typing import Any

from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.model_capabilities import (
    EffectiveRequestPolicy,
    resolve_request_policy,
)
from novel_workflow.providers.template_contract import ProviderTemplate
from novel_workflow.providers.structured_schema import (
    StructuredFormatDecision,
    schema_example,
    structured_format_decision,
)


@dataclass(frozen=True)
class ChatRequestPlan:
    request: dict[str, Any]
    structured_decision: StructuredFormatDecision | None = None
    request_headers: dict[str, str] | None = None


def ensure_structured_prompt(
    prompt: str,
    *,
    task_name: str,
    schema: dict[str, Any] | None,
    policy: EffectiveRequestPolicy,
) -> str:
    lower = prompt.lower()
    has_json_keyword = "json" in lower
    has_json_example = "{" in prompt and "}" in prompt
    has_schema_definition = "json schema：" in lower or "json schema:" in lower
    has_structured_contract = any(
        marker in lower
        for marker in (
            "## 输出结构",
            "## 输出合同",
            "## json 输出协议",
            "## json 输出示例",
            "## json 示例",
        )
    )
    decision = structured_format_decision(
        policy,
        task_name=task_name,
        schema=schema or {"type": "object"},
    )
    requires_json_keyword = policy.requires_json_keyword or decision.effective_mode == "json_object"
    requires_json_example = policy.requires_json_example or decision.effective_mode == "json_object"
    needs_contract = (
        (requires_json_keyword and not has_json_keyword)
        or (requires_json_example and not has_json_example)
        or (policy.requires_schema_definition and schema is not None and not has_schema_definition)
        or (
            schema is not None
            and (requires_json_keyword or requires_json_example)
            and not has_structured_contract
        )
    )
    if not needs_contract:
        return prompt
    example = json.dumps(schema_example(schema), ensure_ascii=False, separators=(",", ":"))
    lines = [
        prompt,
        "",
        "## JSON 输出协议",
        "请只返回 JSON 对象（合法 JSON object），不要 Markdown、代码块或解释文字。",
    ]
    if policy.requires_schema_definition and schema is not None:
        definition = json.dumps(schema, ensure_ascii=False, separators=(",", ":"))
        lines.append(f"JSON Schema：{definition}")
    lines.append(f"JSON 格式示例：{example}")
    return "\n".join(lines)


def build_chat_request(
    *,
    template: ProviderTemplate,
    model: str,
    system: str,
    user: str,
    task_name: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    structured_schema: dict[str, Any] | None,
    assistant_prefill: str = "",
    prompt_cache_key: str = "",
) -> dict[str, Any]:
    return build_chat_request_plan(
        template=template,
        model=model,
        system=system,
        user=user,
        task_name=task_name,
        temperature=temperature,
        top_p=top_p,
        max_tokens=max_tokens,
        structured_schema=structured_schema,
        assistant_prefill=assistant_prefill,
        prompt_cache_key=prompt_cache_key,
    ).request


def build_chat_request_plan(
    *,
    template: ProviderTemplate,
    model: str,
    system: str,
    user: str,
    task_name: str,
    temperature: float,
    top_p: float,
    max_tokens: int,
    structured_schema: dict[str, Any] | None,
    assistant_prefill: str = "",
    prompt_cache_key: str = "",
    disable_thinking: bool = False,
) -> ChatRequestPlan:
    structured = structured_schema is not None
    if assistant_prefill and structured:
        raise ProviderResponseError(
            "provider_feature_conflict",
            "Assistant prefill cannot be combined with structured output",
        )
    if assistant_prefill and task_name not in template.assistant_prefill_tasks:
        raise ProviderResponseError(
            "unsupported_assistant_prefill",
            "Assistant prefill is not enabled for this task",
        )
    if assistant_prefill and not _supports_assistant_prefill(template, model):
        raise ProviderResponseError(
            "unsupported_assistant_prefill",
            "Assistant prefill is not enabled for this model",
        )
    policy = resolve_request_policy(template, model=model, task_name=task_name)
    request_parameters = dict(policy.request_parameters)
    extra_body_parameters = dict(policy.extra_body_parameters)
    if disable_thinking:
        request_parameters.pop("reasoning_effort", None)
        if "thinking" in extra_body_parameters:
            extra_body_parameters["thinking"] = {"type": "disabled"}
        if "enable_thinking" in extra_body_parameters:
            extra_body_parameters["enable_thinking"] = False
            extra_body_parameters.pop("thinking_budget", None)
    request: dict[str, Any] = {
        "model": model,
        "stream": False,
        "messages": _messages(template, system=system, user=user, assistant_prefill=assistant_prefill),
    }
    request_headers: dict[str, str] = {}
    if prompt_cache_key and template.supports_prompt_cache_key:
        if template.prompt_cache_key_header:
            request_headers[template.prompt_cache_key_header] = prompt_cache_key
        else:
            request["prompt_cache_key"] = prompt_cache_key
    if not (structured and policy.omit_max_tokens_in_structured):
        request[policy.max_tokens_field] = max_tokens
    if not (
        template.omit_sampling_when_thinking
        and _thinking_is_enabled(extra_body_parameters)
    ):
        _apply_sampling(request, policy, temperature=temperature, top_p=top_p)
    request.update(request_parameters)
    if extra_body_parameters:
        request["extra_body"] = extra_body_parameters
    decision = None
    if structured:
        if not template.supports_response_format:
            decision = StructuredFormatDecision(None, "prompt_only")
        else:
            decision = structured_format_decision(policy, task_name=task_name, schema=structured_schema)
        if decision.response_format is not None:
            request["response_format"] = decision.response_format
    return ChatRequestPlan(
        request=request,
        structured_decision=decision,
        request_headers=request_headers or None,
    )


def _messages(
    template: ProviderTemplate,
    *,
    system: str,
    user: str,
    assistant_prefill: str,
) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]
    if not assistant_prefill:
        return messages
    if template.assistant_prefill_mode in {"assistant_prefix", "deepseek_prefix_beta"}:
        messages.append({"role": "assistant", "content": assistant_prefill, "prefix": True})
    elif template.assistant_prefill_mode == "kimi_partial":
        messages.append({"role": "assistant", "content": assistant_prefill, "partial": True})
    else:
        raise ProviderResponseError(
            "unsupported_assistant_prefill",
            "Selected provider template does not support assistant prefill",
        )
    return messages


def _supports_assistant_prefill(template: ProviderTemplate, model: str) -> bool:
    patterns = template.assistant_prefill_model_patterns
    return not patterns or any(
        fnmatchcase(model.casefold(), pattern.casefold()) for pattern in patterns
    )


def _apply_sampling(
    request: dict[str, Any],
    policy: EffectiveRequestPolicy,
    *,
    temperature: float,
    top_p: float,
) -> None:
    if policy.sampling_parameter_mode in {"both", "temperature"}:
        request["temperature"] = temperature
    if policy.sampling_parameter_mode in {"both", "top_p"}:
        request["top_p"] = top_p


def _thinking_is_enabled(extra_body: dict[str, object]) -> bool:
    thinking = extra_body.get("thinking")
    return isinstance(thinking, dict) and thinking.get("type") == "enabled"
