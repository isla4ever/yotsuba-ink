from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class ProviderResponseError(RuntimeError):
    def __init__(self, code: str, message: str, *, http_status: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.http_status = http_status


@dataclass(frozen=True)
class ProviderPublicFailure:
    code: str
    message: str


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
    "http_error": ProviderPublicFailure(
        code="provider_request_failed",
        message="Provider 拒绝了请求，请检查服务状态、接口地址和模型配置。",
    ),
}

_GENERIC_FAILURE = ProviderPublicFailure(
    code="provider_request_failed",
    message="Provider 请求失败，请检查服务状态与配置后重试。",
)

_BALANCE_MARKERS = (
    "insufficient_balance",
    "insufficient_quota",
    "quota_exhausted",
    "quota_exceeded",
    "billing_hard_limit",
)


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
