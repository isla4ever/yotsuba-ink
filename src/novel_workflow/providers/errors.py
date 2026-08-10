from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ProviderResponseError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        diagnostic_code: str = "",
        diagnostic_details: dict[str, Any] | None = None,
        partial_content: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status
        self.diagnostic_code = diagnostic_code
        self.diagnostic_details = dict(diagnostic_details or {})
        self.partial_content = partial_content


@dataclass(frozen=True)
class ProviderPublicFailure:
    code: str
    message: str


def public_provider_response_diagnostic(error: Exception) -> dict[str, Any]:
    """Return the only Provider response metadata allowed in run events."""

    if not isinstance(error, ProviderResponseError):
        return {}
    source = error.diagnostic_details
    result: dict[str, Any] = {}
    finish_reason = source.get("finish_reason")
    if isinstance(finish_reason, str) and finish_reason:
        result["finish_reason"] = finish_reason[:80]
    for key in ("response_chars", "reasoning_chars"):
        value = _nonnegative_int(source.get(key))
        if value is not None:
            result[key] = value
    structured = source.get("structured_parse")
    if isinstance(structured, dict):
        parsed = _public_structured_parse_diagnostic(structured)
        if parsed:
            result["structured_parse"] = parsed
    return result


def _public_structured_parse_diagnostic(source: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in (
        "response_chars",
        "candidate_count",
        "balanced_object_count",
        "parsed_object_count",
        "schema_match_count",
        "repairs_applied",
        "parse_error_codes",
    ):
        value = _nonnegative_int(source.get(key))
        if value is not None:
            result[key] = value
    digest = source.get("response_sha256")
    if (
        isinstance(digest, str)
        and len(digest) == 64
        and all(character in "0123456789abcdef" for character in digest.lower())
    ):
        result["response_sha256"] = digest.lower()
    selection = source.get("selection")
    if isinstance(selection, str) and selection:
        result["selection"] = selection[:80]
    for key in ("repairs_applied", "parse_error_codes"):
        values = source.get(key)
        if isinstance(values, list):
            result[key] = [str(value)[:80] for value in values[:8]]
    types = source.get("top_level_types")
    if isinstance(types, list):
        result["top_level_types"] = [
            str(value)[:40] for value in types[:8]
        ]
    object_keys = source.get("object_keys")
    if isinstance(object_keys, list):
        result["object_keys"] = [
            [str(key)[:80] for key in keys[:32]]
            for keys in object_keys[:8]
            if isinstance(keys, list)
        ]
    return result


def _nonnegative_int(value: Any) -> int | None:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


_PUBLIC_FAILURES = {
    "authentication_failed": ProviderPublicFailure(
        code="authentication_failed",
        message="鉴权失败，请检查 API Key 是否有效且有权访问当前模型。",
    ),
    "insufficient_balance": ProviderPublicFailure(
        code="insufficient_balance",
        message="Provider 余额或调用额度不足，请充值或切换到有可用额度的账号后重试。",
    ),
    "endpoint_or_model_unavailable": ProviderPublicFailure(
        code="endpoint_or_model_unavailable",
        message="接口地址或模型不可用，请检查 Base URL 和模型名称。",
    ),
    "rate_limited": ProviderPublicFailure(
        code="rate_limited",
        message="请求过于频繁或已达到并发限制，请稍后重试并检查账户配额。",
    ),
    "timeout": ProviderPublicFailure(
        code="provider_timeout",
        message="Provider 连接超时，请检查网络和服务状态后重试。",
    ),
    "network_error": ProviderPublicFailure(
        code="provider_unreachable",
        message="无法连接 Provider，请检查网络和服务地址后重试。",
    ),
    "service_unavailable": ProviderPublicFailure(
        code="provider_unavailable",
        message="Provider 服务暂时不可用，请稍后重试或切换服务。",
    ),
    "response_json_error": ProviderPublicFailure(
        code="incompatible_response",
        message="接口响应与 OpenAI-compatible 协议不兼容，请检查兼容模式和服务版本。",
    ),
    "response_shape_error": ProviderPublicFailure(
        code="incompatible_response",
        message="接口响应与 OpenAI-compatible 协议不兼容，请检查兼容模式和服务版本。",
    ),
    "json_parse_failed": ProviderPublicFailure(
        code="incompatible_response",
        message="模型未返回当前阶段要求的结构化内容，请检查模型兼容性后重试。",
    ),
    "output_truncated": ProviderPublicFailure(
        code="output_truncated",
        message="模型输出被长度上限截断，请提高 Token 上限或缩短输入后重试。",
    ),
    "empty_content": ProviderPublicFailure(
        code="empty_response",
        message="模型返回了空内容，请检查模型状态或切换模型后重试。",
    ),
    "structured_empty_content": ProviderPublicFailure(
        code="structured_empty_response",
        message="模型在结构化输出模式下返回空内容；已停止且未进行隐藏重试，请调整 Prompt 或切换模型后显式继续。",
    ),
    "provider_feature_conflict": ProviderPublicFailure(
        code="provider_feature_conflict",
        message="当前厂商能力组合不兼容，请关闭预填或结构化输出中的一项。",
    ),
    "unsupported_assistant_prefill": ProviderPublicFailure(
        code="provider_feature_unsupported",
        message="当前厂商模板不支持 assistant 预填，请关闭该实验能力。",
    ),
    "http_error": ProviderPublicFailure(
        code="provider_request_failed",
        message="Provider 拒绝了请求，请检查服务状态、接口地址和模型配置。",
    ),
    "provider_policy_blocked": ProviderPublicFailure(
        code="provider_policy_blocked",
        message="当前 Token Plan 仅限 AI 编程工具，不能用于自定义应用后端；请改用普通 MiMo API Key。",
    ),
    "provider_workflow_blocked": ProviderPublicFailure(
        code="provider_workflow_blocked",
        message="当前厂商入口仅用于连接测试或模型评估，不能执行小说生产工作流。",
    ),
}

_GENERIC_FAILURE = ProviderPublicFailure(
    code="provider_request_failed",
    message="Provider 请求失败，请检查服务状态与配置后重试。",
)

_BALANCE_MARKERS = (
    "1113",
    "insufficient_balance",
    "insufficient_quota",
    "quota_exhausted",
    "quota_exceeded",
    "billing_hard_limit",
)

_PRE_INFERENCE_REJECTION_CODES = {
    "authentication_failed",
    "endpoint_or_model_unavailable",
    "insufficient_balance",
    "rate_limited",
}


def provider_http_error(response: Any) -> ProviderResponseError:
    status = _status_code(response)
    markers = _structured_error_markers(response)
    if status in {401, 403}:
        code = "authentication_failed"
    elif status == 402 or any(token in marker for marker in markers for token in _BALANCE_MARKERS):
        code = "insufficient_balance"
    elif status == 404:
        code = "endpoint_or_model_unavailable"
    elif status == 429:
        code = "rate_limited"
    elif status in {408, 504}:
        code = "timeout"
    elif status is not None and status >= 500:
        code = "service_unavailable"
    else:
        code = "http_error"
    failure = public_provider_failure(ProviderResponseError(code, "", http_status=status))
    return ProviderResponseError(code, failure.message, http_status=status)


def public_provider_failure(error: Exception) -> ProviderPublicFailure:
    if not isinstance(error, ProviderResponseError):
        return _GENERIC_FAILURE
    return _PUBLIC_FAILURES.get(error.code, _GENERIC_FAILURE)


def provider_rejected_before_inference(error: Exception) -> bool:
    return (
        isinstance(error, ProviderResponseError)
        and error.code in _PRE_INFERENCE_REJECTION_CODES
    )


def _status_code(response: Any) -> int | None:
    value = getattr(response, "status_code", None)
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _structured_error_markers(response: Any) -> tuple[str, ...]:
    try:
        payload = response.json()
    except Exception:
        return ()
    values: list[str] = []
    _collect_error_markers(payload, values, depth=0)
    return tuple(_normalize_marker(value) for value in values)


def _collect_error_markers(value: Any, values: list[str], *, depth: int) -> None:
    if depth > 3:
        return
    if isinstance(value, dict):
        for key, item in value.items():
            normalized_key = str(key).lower()
            if normalized_key in {"code", "error_code", "reason", "status", "type", "message"} and isinstance(item, (str, int)):
                values.append(str(item))
            elif isinstance(item, (dict, list)):
                _collect_error_markers(item, values, depth=depth + 1)
    elif isinstance(value, list):
        for item in value[:8]:
            _collect_error_markers(item, values, depth=depth + 1)


def _normalize_marker(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")
