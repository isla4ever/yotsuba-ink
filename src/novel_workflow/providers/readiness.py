from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from novel_workflow.workflows.schemas import ProviderKind, ProviderProfile, WorkflowDefinition, WorkflowNode
from novel_workflow.providers.template_contract import ProviderTemplate
from novel_workflow.providers.templates import require_provider_template


class ProviderReadinessError(ValueError):
    def __init__(self, report: "ProviderReadinessReport") -> None:
        super().__init__(report.message)
        self.report = report


class ProviderReadinessCheck(BaseModel):
    provider_id: str
    provider_name: str
    expected_kind: ProviderKind
    model: str = ""
    used_by: list[str] = Field(default_factory=list)
    ready: bool
    issue_codes: list[str] = Field(default_factory=list)
    message: str


class ProviderReadinessReport(BaseModel):
    ok: bool
    scope: Literal["configuration_only"] = "configuration_only"
    checked_provider_count: int
    checks: list[ProviderReadinessCheck] = Field(default_factory=list)
    message: str


@dataclass(frozen=True)
class _ProviderUsage:
    provider_id: str
    label: str
    expected_kind: ProviderKind
    model: str = ""


def live_provider_readiness_report(
    workflow: WorkflowDefinition,
    *,
    secret_resolver: Callable[[str], str | None] | None = None,
) -> ProviderReadinessReport:
    profiles = {profile.id: profile for profile in workflow.provider_profiles}
    usages = _provider_usages(workflow)
    grouped_usages = _group_provider_usages(usages)
    grouped_models = _group_provider_models(usages)
    checks = [
        _provider_check(
            provider_id,
            profiles.get(provider_id),
            expected_kind=expected_kind,
            secret_resolver=secret_resolver,
            used_by=used_by,
            model=", ".join(grouped_models.get((provider_id, expected_kind), [])),
            models=grouped_models.get((provider_id, expected_kind), []),
        )
        for (provider_id, expected_kind), used_by in grouped_usages.items()
    ]
    blocked = [check for check in checks if not check.ready]
    message = ""
    if blocked:
        message = "真实运行 Provider 配置不完整：" + "；".join(check.message for check in blocked[:3])
    return ProviderReadinessReport(
        ok=not blocked,
        checked_provider_count=len(checks),
        checks=checks,
        message=message,
    )


def ensure_live_provider_readiness(
    workflow: WorkflowDefinition,
    *,
    secret_resolver: Callable[[str], str | None] | None = None,
) -> None:
    report = live_provider_readiness_report(workflow, secret_resolver=secret_resolver)
    if not report.ok:
        raise ProviderReadinessError(report)


def _provider_usages(workflow: WorkflowDefinition) -> list[_ProviderUsage]:
    usages: list[_ProviderUsage] = []
    for node in workflow.nodes:
        if node.type == "export":
            continue
        usages.append(_ProviderUsage(
            provider_id=node.provider_profile_id,
            label=node.label,
            expected_kind="openai-compatible",
            model=str(node.model_settings.model),
        ))
        if node.type == "cover":
            usages.append(_ProviderUsage(
                provider_id=node.image_provider_profile_id or "",
                label=f"{node.label}图片生成",
                expected_kind="openai-compatible-image",
                model="",
            ))
    return usages


def _group_provider_usages(usages: list[_ProviderUsage]) -> dict[tuple[str, ProviderKind], list[str]]:
    grouped: dict[tuple[str, ProviderKind], list[str]] = {}
    for usage in usages:
        labels = grouped.setdefault((usage.provider_id, usage.expected_kind), [])
        if usage.label not in labels:
            labels.append(usage.label)
    return grouped


def _group_provider_models(usages: list[_ProviderUsage]) -> dict[tuple[str, ProviderKind], list[str]]:
    grouped: dict[tuple[str, ProviderKind], list[str]] = {}
    for usage in usages:
        if usage.model:
            grouped.setdefault((usage.provider_id, usage.expected_kind), []).append(usage.model)
    return {key: list(dict.fromkeys(values)) for key, values in grouped.items()}


def provider_connection_ready(
    profile: ProviderProfile | None,
    *,
    expected_kind: ProviderKind,
    secret_resolver: Callable[[str], str | None] | None = None,
) -> bool:
    """True when the profile alone can reach the vendor, ignoring stage models.

    Stage binding decisions need the connection verdict without the per-stage
    model checks, which only make sense once a stage points at the provider.
    """
    issue_codes, _ = _connection_issue_codes(profile, expected_kind=expected_kind, secret_resolver=secret_resolver)
    return not issue_codes


def _connection_issue_codes(
    profile: ProviderProfile | None,
    *,
    expected_kind: ProviderKind,
    secret_resolver: Callable[[str], str | None] | None,
) -> tuple[list[str], ProviderTemplate | None]:
    if profile is None:
        return ["provider_not_found"], None
    issue_codes: list[str] = []
    template: ProviderTemplate | None = None
    if not profile.enabled:
        issue_codes.append("provider_disabled")
    if profile.kind != expected_kind:
        issue_codes.append("provider_kind_mismatch")
    try:
        template = require_provider_template(profile.template_id, profile.kind)
        if not template.execution_allowed:
            issue_codes.append("provider_policy_blocked")
        elif not template.workflow_execution_allowed:
            issue_codes.append("provider_workflow_blocked")
    except ValueError:
        issue_codes.append("provider_template_invalid")
    if not profile.base_url.strip():
        issue_codes.append("base_url_missing")
    if not profile.default_model.strip():
        issue_codes.append("model_missing")
    if not _has_secret(profile, secret_resolver=secret_resolver):
        issue_codes.append("secret_missing")
    return issue_codes, template


def _provider_check(
    provider_id: str,
    profile: ProviderProfile | None,
    *,
    expected_kind: ProviderKind,
    secret_resolver: Callable[[str], str | None] | None,
    used_by: list[str],
    model: str,
    models: list[str],
) -> ProviderReadinessCheck:
    issue_codes, template = _connection_issue_codes(
        profile,
        expected_kind=expected_kind,
        secret_resolver=secret_resolver,
    )
    if profile is not None:
        available_models = set(profile.model_options)
        if models and available_models and any(item not in available_models for item in models):
            issue_codes.append("model_not_discovered")
        if template is not None and _models_lack_required_parameters(profile, template, models):
            issue_codes.append("model_parameter_not_supported")
    provider_name = profile.name if profile is not None else provider_id or "未指定 Provider"
    return ProviderReadinessCheck(
        provider_id=provider_id,
        provider_name=provider_name,
        expected_kind=expected_kind,
        model=model,
        used_by=used_by,
        ready=not issue_codes,
        issue_codes=issue_codes,
        message=_check_message(provider_name, issue_codes, used_by),
    )


def _check_message(provider_name: str, issue_codes: list[str], used_by: list[str]) -> str:
    issue_labels = {
        "provider_not_found": "不存在",
        "provider_disabled": "未启用",
        "provider_kind_mismatch": "类型不匹配",
        "provider_template_invalid": "厂商模板无效",
        "base_url_missing": "缺少 Base URL",
        "model_missing": "缺少模型",
        "model_not_discovered": "阶段模型未在已发现目录中",
        "model_parameter_not_supported": "阶段模型目录未声明所需结构化输出参数",
        "secret_missing": "缺少 API Key",
        "provider_policy_blocked": "不允许用于应用后端（请改用按量计费 API）",
        "provider_workflow_blocked": "只允许连接测试或模型评估，不能进入生产工作流",
    }
    if not issue_codes:
        return f"{provider_name} 配置完整"
    usage = "、".join(used_by[:3])
    if len(used_by) > 3:
        usage += f"等 {len(used_by)} 个环节"
    return f"{provider_name} {'、'.join(issue_labels[code] for code in issue_codes)}（用于：{usage}）"


def _has_secret(
    profile: ProviderProfile,
    *,
    secret_resolver: Callable[[str], str | None] | None,
) -> bool:
    saved = secret_resolver(profile.id) if secret_resolver else None
    if saved:
        return True
    return bool(profile.api_key_env and os.environ.get(profile.api_key_env))


def _models_lack_required_parameters(
    profile: ProviderProfile,
    template: ProviderTemplate,
    models: list[str],
) -> bool:
    required = set(template.required_model_parameter_any_of)
    if not required or not profile.model_supported_parameters:
        return False
    for model in models:
        parameters = profile.model_supported_parameters.get(model)
        if parameters is not None and required.isdisjoint(parameters):
            return True
    return False
