from __future__ import annotations

from typing import Any

from novel_workflow.orchestration.cover_assets import CoverAssetGenerationError, generate_cover_assets
from novel_workflow.workflows.schemas import NovelRunState


class CoverAssetRetryError(RuntimeError):
    pass


async def retry_cover_asset_candidate(
    runner: Any,
    workflow: Any,
    *,
    run_id: str,
    candidate_id: str,
    request_id: str,
) -> dict[str, Any]:
    try:
        stored = runner.run_store.read(run_id)
    except FileNotFoundError as exc:
        raise CoverAssetRetryError("运行不存在") from exc
    state_data = stored.get("state")
    if not isinstance(state_data, dict):
        raise CoverAssetRetryError("运行尚未形成可恢复状态")
    state = NovelRunState.model_validate(state_data)
    node = next((item for item in workflow.nodes if item.type == "cover_image"), None)
    if node is None:
        raise CoverAssetRetryError("工作流没有封面阶段")
    output_key = node.output_key or node.id
    artifact = state.artifacts.get(output_key)
    if not isinstance(artifact, dict):
        raise CoverAssetRetryError("封面 Artifact 尚未生成")
    confirmation = state.stage_confirmation_state.get(node.id, {})
    if confirmation.get("status") == "confirmed" or output_key in state.approved_artifacts:
        raise CoverAssetRetryError("封面已经定稿，不能改写冻结资产")
    if not runner.run_store.approval_pending(run_id, node_id=node.id):
        raise CoverAssetRetryError("仅可在封面等待定稿时重试失败候选")
    candidate = next((item for item in artifact.get("candidates") or [] if isinstance(item, dict) and item.get("id") == candidate_id), None)
    if candidate is None:
        raise CoverAssetRetryError("封面候选不存在")
    if candidate.get("asset_status") == "ready":
        return {"artifact": artifact, "events": [], "reused": True}
    if int(candidate.get("attempt") or 0) >= 3:
        raise CoverAssetRetryError("该候选连续失败已达到熔断上限")
    try:
        claim = runner.run_store.claim_cover_asset_retry(run_id, request_id=request_id, candidate_id=candidate_id)
    except ValueError as exc:
        raise CoverAssetRetryError(str(exc)) from exc
    if claim.get("status") == "completed":
        latest = runner.run_store.read(run_id).get("state") or {}
        return {"artifact": (latest.get("artifacts") or {}).get(output_key, artifact), "events": [], "reused": True}
    if claim.get("status") == "failed":
        raise CoverAssetRetryError(str(claim.get("error") or "该重试请求此前已失败"))
    if claim.get("existing"):
        raise CoverAssetRetryError("该重试请求正在执行，请勿重复提交")
    events: list[dict[str, Any]] = []
    try:
        async for event in generate_cover_assets(
            runner,
            node,
            state,
            workflow,
            run_id,
            candidate_ids={candidate_id},
            explicit_retry=True,
        ):
            events.append(event)
    except (CoverAssetGenerationError, ValueError, RuntimeError) as exc:
        runner.run_store.finish_cover_asset_retry(run_id, request_id=request_id, status="failed", error=str(exc))
        raise CoverAssetRetryError(str(exc)) from exc
    artifact = state.artifacts[output_key]
    runner.run_store.request_approval(run_id, node_id=node.id, output_key=output_key, artifact=artifact)
    event_seq = max((int(event.get("event_seq") or 0) for event in events), default=0)
    runner.run_store.finish_cover_asset_retry(run_id, request_id=request_id, status="completed", event_seq=event_seq)
    return {"artifact": artifact, "events": events, "reused": False}
