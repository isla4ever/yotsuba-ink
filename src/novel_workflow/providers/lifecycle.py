from __future__ import annotations

from novel_workflow.workflows.schemas import ProviderKind, ProviderProfile, WorkflowDefinition


def assign_global_default(
    profiles: list[ProviderProfile],
    *,
    provider_id: str,
    kind: ProviderKind,
) -> list[ProviderProfile]:
    target = next((profile for profile in profiles if profile.id == provider_id), None)
    if target is None:
        raise LookupError(provider_id)
    if target.kind != kind:
        raise ValueError("Provider type does not match the requested global default type")
    if not target.enabled:
        raise ValueError("Disabled Provider cannot be selected as a global default")
    return [
        profile.model_copy(update={"is_global_default": profile.id == provider_id})
        if profile.kind == kind
        else profile
        for profile in profiles
    ]


def provider_deletion_references(
    provider: ProviderProfile,
    workflows: list[WorkflowDefinition],
) -> list[str]:
    references: list[str] = []
    if provider.is_global_default:
        references.append("全局默认接口")
    for workflow in workflows:
        for node in workflow.nodes:
            _append_node_references(references, workflow, node, provider.id)
    return references


def _append_node_references(references: list[str], workflow: WorkflowDefinition, node, provider_id: str) -> None:
    _append_reference(
        references,
        node.provider_profile_id == provider_id,
        f"{workflow.name} / {node.label} 文本生成",
    )
    _append_reference(
        references,
        node.image_provider_profile_id == provider_id,
        f"{workflow.name} / {node.label} 图片生成",
    )


def _append_reference(references: list[str], condition: bool, label: str) -> None:
    if condition and label not in references:
        references.append(label)
