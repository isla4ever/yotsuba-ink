from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from novel_workflow.workflows.schemas import ProviderKind, ProviderProfile, WorkflowDefinition, WorkflowNode
from novel_workflow.providers.templates import require_provider_template


class ProviderReadinessError(ValueError):
    def __init__(self, report: "ProviderReadinessReport") -> None:
        super().__init__(report.message)
        self.report = report


class ProviderReadinessCheck(BaseModel):
    provider_id: str
    provider_name: str
    expected_kind: ProviderKind
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


def live_provider_readiness_report(
    workflow: WorkflowDefinition,
    *,
    secret_resolver: Callable[[str], str | None] | None = None,
) -> ProviderReadinessReport:
    profiles = {profile.id: profile for profile in workflow.provider_profiles}
    grouped_usages = _group_provider_usages(_provider_usages(workflow))
    checks = [
        _provider_check(
            provider_id,
            profiles.get(provider_id),
            expected_kind=expected_kind,
            secret_resolver=secret_resolver,
            used_by=used_by,
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
        if node.type == "export_artifact":
            continue
        usages.append(_ProviderUsage(
            provider_id=node.provider_profile_id,
            label=node.label,
            expected_kind="openai-compatible",
        ))
        for target in sorted(node.fallback_targets, key=lambda item: item.priority):
            if target.enabled:
                usages.append(_ProviderUsage(
                    provider_id=target.provider_profile_id,
                    label=f"{node.label}文本备用 {target.priority}",
                    expected_kind="openai-compatible",
                ))
        if node.type == "cover_image":
            usages.append(_ProviderUsage(
                provider_id=node.image_provider_profile_id or "",
                label=f"{node.label}图片生成",
                expected_kind="openai-compatible-image",
            ))
            for target in sorted(node.image_fallback_targets, key=lambda item: item.priority):
                if target.enabled:
                    usages.append(_ProviderUsage(
                        provider_id=target.provider_profile_id,
                        label=f"{node.label}图片备用 {target.priority}",
                        expected_kind="openai-compatible-image",
                    ))
        judge_provider_id = _explicit_judge_provider_id(node)
        if judge_provider_id:
            usages.append(_ProviderUsage(
                provider_id=judge_provider_id,
                label=f"{node.label}评审",
                expected_kind="openai-compatible",
            ))
    return usages


def _group_provider_usages(usages: list[_ProviderUsage]) -> dict[tuple[str, ProviderKind], list[str]]:
    grouped: dict[tuple[str, ProviderKind], list[str]] = {}
    for usage in usages:
        labels = grouped.setdefault((usage.provider_id, usage.expected_kind), [])
        if usage.label not in labels:
            labels.append(usage.label)
    return grouped


def _explicit_judge_provider_id(node: WorkflowNode) -> str:
    if not node.variant_policy.enabled:
        return ""
    provider_id = node.variant_policy.judge_provider_profile_id
    return provider_id if provider_id and provider_id != "inherit" else ""


def _provider_check(
    provider_id: str,
    profile: ProviderProfile | None,
    *,
    expected_kind: ProviderKind,
    secret_resolver: Callable[[str], str | None] | None,
    used_by: list[str],
) -> ProviderReadinessCheck:
    issue_codes: list[str] = []
    if profile is None:
        issue_codes.append("provider_not_found")
    else:
        if not profile.enabled:
            issue_codes.append("provider_disabled")
        if profile.kind != expected_kind:
            issue_codes.append("provider_kind_mismatch")
        try:
            require_provider_template(profile.template_id, profile.kind)
        except ValueError:
            issue_codes.append("provider_template_invalid")
        if not profile.base_url.strip():
            issue_codes.append("base_url_missing")
        if not profile.default_model.strip():
            issue_codes.append("model_missing")
        if not _has_secret(profile, secret_resolver=secret_resolver):
            issue_codes.append("secret_missing")
    provider_name = profile.name if profile is not None else provider_id or "未指定 Provider"
    return ProviderReadinessCheck(
        provider_id=provider_id,
        provider_name=provider_name,
        expected_kind=expected_kind,
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
        "secret_missing": "缺少 API Key",
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
