from __future__ import annotations

from typing import Any

import pytest

from novel_workflow.orchestration.recovery import register_failure
from novel_workflow.usage.budget import authorize_provider_call, drain_budget_events, prepare_budget_recovery, settle_provider_call
from novel_workflow.usage.image_budget import authorize_image_call, settle_image_call
from novel_workflow.usage.tracker import estimate_text_tokens
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow


def _state(inputs: dict[str, Any] | None = None) -> NovelRunState:
    return NovelRunState(
        run_id="budget-test",
        project_id="budget-project",
        workflow_id="default-novel-workflow",
        inputs=inputs or {},
    )


def test_provider_call_is_denied_before_budgeted_provider_work() -> None:
    node = default_workflow().nodes[1]
    prompt = "一段会被预算拒绝的 prompt"
    state = _state({"budget_limits": {"stages": {node.id: 1}}})

    decision = authorize_provider_call(state, node, prompt_text=prompt)

    assert decision["allowed"] is False
    assert state.budget_state["status"] == "exceeded"
    assert [event["type"] for event in drain_budget_events(state)] == ["stage_budget_exceeded", "manual_intervention_required"]


def test_candidate_attempts_are_counted_and_cannot_exceed_policy() -> None:
    node = default_workflow().nodes[4]
    node.variant_policy.enabled = True
    node.variant_policy.candidate_count = 2
    state = _state()
    prompt = "candidate prompt"

    first = authorize_provider_call(state, node, prompt_text=prompt, chapter="第1章", kind="candidate")
    settle_provider_call(state, scope_key=first["scope_key"], operation_id=first["operation_id"], prompt_text=prompt, output_text="第一候选")
    second = authorize_provider_call(state, node, prompt_text=prompt, chapter="第1章", kind="candidate")
    settle_provider_call(state, scope_key=second["scope_key"], operation_id=second["operation_id"], prompt_text=prompt, output_text="第二候选")
    third = authorize_provider_call(state, node, prompt_text=prompt, chapter="第1章", kind="candidate")

    assert first["allowed"] and second["allowed"]
    assert third["allowed"] is False
    assert state.budget_state["scopes"]["text:第1章"]["attempts"]["candidate"] == 2


def test_warning_is_emitted_before_scope_is_exhausted() -> None:
    node = default_workflow().nodes[1]
    prompt = "warning prompt"
    predicted = estimate_text_tokens(prompt, node.model_settings.model) + node.model_settings.max_tokens
    state = _state({"budget_limits": {"stages": {node.id: int(predicted * 1.1)}}})

    decision = authorize_provider_call(state, node, prompt_text=prompt)

    assert decision["allowed"] is True
    events = drain_budget_events(state)
    assert any(event["type"] == "stage_budget_warning" for event in events)


def test_explicit_recovery_allows_one_bounded_retry() -> None:
    node = default_workflow().nodes[1]
    state = _state()
    prompt = "retry prompt"
    first = authorize_provider_call(state, node, prompt_text=prompt)
    settle_provider_call(state, scope_key=first["scope_key"], operation_id=first["operation_id"], prompt_text=prompt, output_text="", failed=True)

    prepare_budget_recovery(state)
    retry = authorize_provider_call(state, node, prompt_text=prompt)

    assert retry["allowed"] is True
    scope = state.budget_state["scopes"][node.id]
    assert scope["attempts"]["generation"] == 1
    assert scope["attempts"]["retry"] == 1


def test_recovery_conservatively_settles_reserved_tokens_once() -> None:
    node = default_workflow().nodes[1]
    state = _state()
    prompt = "interrupted provider prompt"
    decision = authorize_provider_call(state, node, prompt_text=prompt)
    predicted = decision["predicted_tokens"]
    register_failure(
        state,
        node_id=node.id,
        node_type=node.type,
        code="provider_error",
        message="provider connection interrupted",
    )

    prepare_budget_recovery(state)
    scope = state.budget_state["scopes"][node.id]
    assert scope["operations"][0]["status"] == "uncertain"
    assert scope["reserved_tokens"] == 0
    assert scope["consumed_tokens"] == predicted
    assert state.budget_state["run_consumed_tokens"] == predicted
    prepare_budget_recovery(state)
    assert state.budget_state["run_consumed_tokens"] == predicted


def test_image_recovery_reuses_uncertain_operation_and_idempotency_key() -> None:
    workflow = default_workflow()
    node = next(item for item in workflow.nodes if item.id == "cover")
    state = NovelRunState(
        run_id="image-budget-recovery",
        project_id="image-budget-recovery",
        workflow_id=workflow.id,
        inputs={"stage_configs": {"cover": {"candidate_count": 3, "asset_retry_limit": 2}}},
    )
    generation_key = "a" * 64
    first = authorize_image_call(
        state,
        node,
        candidate_id="cover-1",
        generation_key=generation_key,
        estimated_cost_usd=0.04,
    )
    register_failure(state, node_id="cover", node_type="cover_image", code="image_call_interrupted", message="interrupted")

    prepare_budget_recovery(state)
    resumed = authorize_image_call(
        state,
        node,
        candidate_id="cover-1",
        generation_key=generation_key,
        estimated_cost_usd=0.04,
    )
    settle_image_call(state, scope_key="cover", operation_id=resumed["operation_id"], failed=False, actual_cost_usd=0.04)

    scope = state.budget_state["image"]["scopes"]["cover"]
    assert resumed["allowed"] is True
    assert resumed["recovery"] is True
    assert resumed["operation_id"] == first["operation_id"]
    assert scope["attempts"]["calls"] == 1
    assert scope["consumed_cost_usd"] == pytest.approx(0.04)


def test_artifact_validation_failure_retries_completed_provider_scope_once() -> None:
    node = default_workflow().nodes[1]
    state = _state()
    prompt = "provider 返回后合同校验失败"
    first = authorize_provider_call(state, node, prompt_text=prompt)
    settle_provider_call(
        state,
        scope_key=first["scope_key"],
        operation_id=first["operation_id"],
        prompt_text=prompt,
        output_text={"unexpected": "shape"},
    )
    consumed_before = state.budget_state["run_consumed_tokens"]
    register_failure(
        state,
        node_id=node.id,
        node_type=node.type,
        code="artifact_validation",
        message="artifact schema mismatch",
    )

    prepare_budget_recovery(state)
    scope = state.budget_state["scopes"][node.id]
    assert scope["operations"][0]["status"] == "completed"
    assert scope["recovery_retry_ready"] is True
    assert state.budget_state["run_consumed_tokens"] == consumed_before
    retry = authorize_provider_call(state, node, prompt_text=prompt)
    assert retry["allowed"] is True
    prepare_budget_recovery(state)
    assert scope["recovery_retry_ready"] is False
    assert authorize_provider_call(state, node, prompt_text=prompt)["allowed"] is False
