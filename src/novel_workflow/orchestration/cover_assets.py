from __future__ import annotations

import copy
from collections.abc import AsyncIterator
from typing import Any

from novel_workflow.orchestration.control import pause_if_requested
from novel_workflow.orchestration.cover_asset_model import (
    CoverGenerationConfig,
    apply_asset_metadata,
    candidate_generation_key,
    candidate_image_prompt,
    cover_generation_config,
    prepare_cover_artifact,
    refresh_cover_generation,
)
from novel_workflow.orchestration.cover_provider_execution import (
    CoverProviderBudgetError,
    generate_cover_with_fallback,
)
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.usage import (
    BudgetExceededError,
    drain_budget_events,
    image_budget_snapshot,
    record_image_stage_usage,
)


class CoverAssetGenerationError(RuntimeError):
    pass


async def generate_cover_assets(
    runner: Any,
    node: Any,
    state: Any,
    workflow: Any,
    run_id: str,
    *,
    plan: Any | None = None,
    candidate_ids: set[str] | None = None,
    explicit_retry: bool = False,
) -> AsyncIterator[dict[str, Any]]:
    config = cover_generation_config(node, state, workflow)
    output_key = node.output_key or node.id
    artifact = prepare_cover_artifact(plan, config) if plan is not None else copy.deepcopy(state.artifacts.get(output_key) or {})
    if not artifact.get("candidates"):
        raise CoverAssetGenerationError("封面规划中没有可生成的候选")
    state.artifacts[output_key] = artifact
    budget_blocked = False

    for index, candidate in enumerate(artifact["candidates"], start=1):
        if candidate_ids is not None and candidate.get("id") not in candidate_ids:
            continue
        if _ready_asset_is_reusable(runner, run_id, candidate):
            continue
        if candidate.get("asset_status") == "blocked" and not explicit_retry:
            continue
        async for event in pause_if_requested(runner, run_id, state, node_id=node.id):
            yield event
        retry = explicit_retry or candidate.get("asset_status") == "failed"
        attempt = max(1, int(candidate.get("attempt") or 0) + (1 if retry else 0))
        generation_key = str(candidate.get("generation_key") or "")
        if not generation_key or retry:
            generation_key = candidate_generation_key(run_id, node.id, artifact, candidate, config, attempt)
        candidate.update({
            "asset_status": "generating",
            "generation_key": generation_key,
            "provider_profile_id": config.provider_profile_id,
            "model": config.model,
            "attempt": attempt,
            "error_code": "",
            "error_message": "",
        })
        cached = runner.run_store.find_cover_asset(run_id, generation_key)
        if cached:
            apply_asset_metadata(candidate, cached)
            event = _progress_event(run_id, node, artifact, candidate, index, config, "ready", "已复用落盘封面资产")
            _commit_progress(runner, run_id, state, output_key, artifact, event, config)
            yield event
            continue
        started = _progress_event(run_id, node, artifact, candidate, index, config, "generating", "正在生成真实封面资产")
        _commit_progress(runner, run_id, state, output_key, artifact, started, config)
        yield started
        prompt = candidate_image_prompt(artifact, candidate)
        try:
            provider_result = await generate_cover_with_fallback(
                runner,
                node,
                state,
                workflow,
                run_id=run_id,
                candidate_id=str(candidate["id"]),
                prompt=prompt,
                base_generation_key=generation_key,
                primary_model=config.model,
                size=config.size,
                quality=config.quality,
                candidate_count=config.candidate_count,
                explicit_retry=retry,
            )
            generation_key = provider_result.generation_key
            candidate.update({
                "generation_key": generation_key,
                "provider_profile_id": provider_result.target.provider_profile_id,
                "model": provider_result.target.model,
            })
            async for audit_event in _emit_budget_events(runner, run_id, state):
                yield audit_event
            metadata = runner.run_store.save_cover_asset(
                run_id,
                candidate_id=str(candidate["id"]),
                generation_key=generation_key,
                image=provider_result.image,
                expected_ratio=_expected_ratio(config.size),
            )
            apply_asset_metadata(candidate, metadata)
            status = "ready"
            message = "真实图片已校验并落盘"
        except CoverProviderBudgetError as exc:
            decision = exc.decision
            candidate.update({
                "asset_status": "blocked",
                "error_code": str(decision.get("code") or "budget_blocked"),
                "error_message": str(decision.get("message") or "图片预算已阻断"),
            })
            async for audit_event in _emit_budget_events(runner, run_id, state):
                yield audit_event
            status = "blocked"
            message = candidate["error_message"]
            budget_blocked = True
        except Exception as exc:
            async for audit_event in _emit_budget_events(runner, run_id, state):
                yield audit_event
            candidate.update({
                "image_url": "",
                "asset_status": "failed",
                "asset_id": "",
                "error_code": _error_code(exc),
                "error_message": _safe_error(exc),
            })
            status = "failed"
            message = candidate["error_message"]
        event = _progress_event(run_id, node, artifact, candidate, index, config, status, message)
        _commit_progress(runner, run_id, state, output_key, artifact, event, config)
        yield event
        if budget_blocked:
            break

    counts = refresh_cover_generation(artifact, config)
    state.artifacts[output_key] = artifact
    state.cover_asset_state[node.id] = {"status": artifact["asset_generation"]["status"], **counts}
    budget = image_budget_snapshot(state, node.id)
    consumed = float(budget.get("scope", {}).get("consumed_cost_usd") or 0)
    summary = record_image_stage_usage(
        state,
        node=node,
        provider_profile_id=str(artifact.get("asset_generation", {}).get("provider_profile_id") or config.provider_profile_id),
        model=str(artifact.get("asset_generation", {}).get("model") or config.model),
        image_count=counts["ready_count"],
        failed_image_count=counts["failed_count"],
        estimated_cost_usd=consumed if _cost_tracking_available(workflow, node) else None,
    )
    usage_events = [
        {"type": "stage_usage_updated", "run_id": run_id, "node_id": node.id, "node_type": node.type, "usage": summary.model_dump()},
        {"type": "stage_usage_finalized", "run_id": run_id, "node_id": node.id, "node_type": node.type, "usage": summary.model_dump()},
    ]
    runner.run_store.commit_state_events(run_id, state, usage_events)
    for event in usage_events:
        yield event
    if counts["ready_count"] == 0:
        if budget_blocked:
            raise BudgetExceededError("封面图片预算已阻断，尚无可用资产", scope_key=node.id)
        raise CoverAssetGenerationError("所有封面候选均生成失败，已保留失败状态供恢复")


def cover_has_inflight_asset(state: Any) -> bool:
    artifact = state.artifacts.get("cover") if isinstance(state.artifacts, dict) else None
    return bool(isinstance(artifact, dict) and any(
        isinstance(item, dict) and item.get("asset_status") == "generating"
        for item in artifact.get("candidates") or []
    ))


def _ready_asset_is_reusable(runner: Any, run_id: str, candidate: dict[str, Any]) -> bool:
    if candidate.get("asset_status") != "ready" or not candidate.get("generation_key"):
        return False
    metadata = runner.run_store.find_cover_asset(run_id, str(candidate["generation_key"]))
    if not metadata:
        candidate.update({"asset_status": "failed", "image_url": "", "error_code": "asset_missing", "error_message": "已记录资产文件缺失或校验失败"})
        return False
    apply_asset_metadata(candidate, metadata)
    return True


def _commit_progress(runner: Any, run_id: str, state: Any, output_key: str, artifact: dict[str, Any], event: dict[str, Any], config: CoverGenerationConfig) -> None:
    counts = refresh_cover_generation(artifact, config)
    state.artifacts[output_key] = artifact
    state.progress[event["node_id"]] = {"status": "running", **counts}
    state.cover_asset_state[event["node_id"]] = {"status": artifact["asset_generation"]["status"], **counts}
    event.update(counts)
    event["artifact"] = copy.deepcopy(artifact)
    runner.run_store.commit_state_event(run_id, state, event)


async def _emit_budget_events(runner: Any, run_id: str, state: Any) -> AsyncIterator[dict[str, Any]]:
    for event in drain_budget_events(state):
        event = {"run_id": run_id, **event}
        runner.run_store.commit_state_event(run_id, state, event)
        yield event


def _progress_event(run_id: str, node: Any, artifact: dict[str, Any], candidate: dict[str, Any], index: int, config: CoverGenerationConfig, status: str, message: str) -> dict[str, Any]:
    return {
        "type": "asset_progress_updated",
        "run_id": run_id,
        "node_id": node.id,
        "node_type": node.type,
        "candidate_id": candidate["id"],
        "candidate_index": index,
        "asset_status": status,
        "generation_key": candidate.get("generation_key", ""),
        "provider_profile_id": candidate.get("provider_profile_id") or config.provider_profile_id,
        "model": candidate.get("model") or config.model,
        "message": message,
        "error_code": candidate.get("error_code", ""),
        "artifact_source": "live",
    }


def _expected_ratio(size: str) -> float | None:
    try:
        width, height = (int(value) for value in size.lower().split("x", 1))
        return width / height
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _cost_tracking_available(workflow: Any, node: Any) -> bool:
    provider_ids = {node.image_provider_profile_id}
    provider_ids.update(target.provider_profile_id for target in node.image_fallback_targets if target.enabled)
    return any(
        profile.id in provider_ids and profile.estimated_cost_per_output_usd is not None
        for profile in workflow.provider_profiles
    )


def _error_code(exc: Exception) -> str:
    return exc.code if isinstance(exc, ProviderResponseError) else "asset_validation_failed" if isinstance(exc, ValueError) else "image_provider_failed"


def _safe_error(exc: Exception) -> str:
    if isinstance(exc, ProviderResponseError):
        return str(exc)
    if isinstance(exc, ValueError):
        return str(exc)
    return f"图片生成失败：{exc.__class__.__name__}"
