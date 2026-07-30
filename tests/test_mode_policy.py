"""Phase 12 Wave 3A (S2): quality_policy is derived from quality_mode.

The stage UI no longer exposes editable quality controls; the backend
derivation in `node_with_mode_policy` is the single writable truth. These
tests lock the derivation and prove min_score stays consumable by the
quality engine surface (prompt rubric).
"""

from __future__ import annotations

from novel_workflow.orchestration.helpers import node_with_mode_policy
from novel_workflow.workflows.templates import default_workflow


def _node(workflow, node_id):
    return next(node for node in workflow.nodes if node.id == node_id)


def test_fast_mode_disables_quality_retry_without_touching_min_score():
    workflow = default_workflow()
    workflow.quality_mode = "fast"
    text = _node(workflow, "text")
    derived = node_with_mode_policy(text, workflow)

    assert derived.quality_policy.retry_on_fail is False
    assert derived.quality_policy.min_score == text.quality_policy.min_score
    assert derived.variant_policy.enabled is False
    # Derivation never mutates the configured node in place.
    assert text.quality_policy.retry_on_fail is True


def test_deep_mode_raises_text_stage_floor_and_forces_retry():
    workflow = default_workflow()
    workflow.quality_mode = "deep"
    for node_id in ("summary", "outline", "detail", "text"):
        derived = node_with_mode_policy(_node(workflow, node_id), workflow)
        assert derived.quality_policy.retry_on_fail is True
        assert derived.quality_policy.min_score >= 0.84


def test_balanced_mode_keeps_template_quality_policy_and_checks():
    workflow = default_workflow()
    workflow.quality_mode = "balanced"
    text = _node(workflow, "text")
    derived = node_with_mode_policy(text, workflow)

    assert derived.quality_policy.min_score == 0.84
    assert derived.quality_policy.checks == ["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"]


def test_derived_min_score_reaches_prompt_rubric():
    from novel_workflow.stages.prompt_plan import PromptPlanBuilder

    workflow = default_workflow()
    workflow.quality_mode = "deep"
    derived = node_with_mode_policy(_node(workflow, "summary"), workflow)
    rubric = PromptPlanBuilder()._rubric(derived)

    assert f"{derived.quality_policy.min_score:.2f}" in rubric
    assert "最低分" in rubric
