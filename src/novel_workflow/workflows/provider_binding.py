from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from novel_workflow.providers.readiness import provider_connection_ready
from novel_workflow.workflows.definition_schemas import ProviderKind, ProviderProfile


def bind_stages_to_connected_providers(
    workflow: dict[str, Any],
    profiles: Iterable[ProviderProfile],
    *,
    secret_resolver: Callable[[str], str | None] | None = None,
) -> dict[str, Any]:
    """Repoint stages whose provider is not connected at one that is.

    A per-project workflow is copied from a template, and the template's stage
    bindings name whichever service the template author connected. A reader who
    then connects a different service would otherwise start a book bound to a
    provider that has no Base URL or key, which only surfaces as a setup error.
    Stages that already point at a connected provider are never touched, so
    deliberate per-stage exceptions survive the copy.
    """
    catalog = {profile.id: profile for profile in profiles}
    text_fallback = _connected_default(catalog.values(), "openai-compatible", secret_resolver)
    image_fallback = _connected_default(catalog.values(), "openai-compatible-image", secret_resolver)
    if text_fallback is None and image_fallback is None:
        return workflow
    nodes = [
        _bind_node(dict(node), catalog, text_fallback, image_fallback, secret_resolver)
        for node in workflow.get("nodes", [])
    ]
    return {**workflow, "nodes": nodes}


def _bind_node(
    node: dict[str, Any],
    catalog: dict[str, ProviderProfile],
    text_fallback: ProviderProfile | None,
    image_fallback: ProviderProfile | None,
    secret_resolver: Callable[[str], str | None] | None,
) -> dict[str, Any]:
    if text_fallback is not None and not _ready(catalog.get(str(node.get("provider_profile_id") or "")), "openai-compatible", secret_resolver):
        node["provider_profile_id"] = text_fallback.id
        node["model_settings"] = {**dict(node.get("model_settings") or {}), "model": text_fallback.default_model}
    if node.get("type") == "cover" and image_fallback is not None:
        current = catalog.get(str(node.get("image_provider_profile_id") or ""))
        if not _ready(current, "openai-compatible-image", secret_resolver):
            node["image_provider_profile_id"] = image_fallback.id
    return node


def _ready(
    profile: ProviderProfile | None,
    kind: ProviderKind,
    secret_resolver: Callable[[str], str | None] | None,
) -> bool:
    return provider_connection_ready(profile, expected_kind=kind, secret_resolver=secret_resolver)


def _connected_default(
    profiles: Iterable[ProviderProfile],
    kind: ProviderKind,
    secret_resolver: Callable[[str], str | None] | None,
) -> ProviderProfile | None:
    candidates = [profile for profile in profiles if _ready(profile, kind, secret_resolver)]
    if not candidates:
        return None
    return next((profile for profile in candidates if profile.is_global_default), candidates[0])
