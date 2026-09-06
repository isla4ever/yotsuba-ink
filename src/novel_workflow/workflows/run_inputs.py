"""Freeze project-owned workflow inputs into one immutable Run intent."""

from __future__ import annotations

import copy
from typing import Any

from novel_workflow.workflows.definition_schemas import WorkflowDefinition
from novel_workflow.workflows.executable_contract import WorkflowContractError


_KNOWLEDGE_KEYS = frozenset(
    {
        "reference_mode",
        "reference_keywords",
        "reference_query_intent",
        "reference_urls",
        "knowledge_base_doc_ids",
        "enable_web_search",
        "reference_summary",
    }
)
_SCALE_KEYS = frozenset({"word_target_soft"})


def freeze_project_run_inputs(
    workflow: WorkflowDefinition,
    requested_inputs: dict[str, Any],
) -> dict[str, Any]:
    """Bind the project idea from its owned workflow before Run persistence.

    The project workflow is the sole authority for ``core_concept``. The API may
    still carry narrow Run-specific hints and a length target, but it cannot
    replace the idea accepted by the creation wizard.
    """

    frozen = copy.deepcopy(requested_inputs)
    requested_brief = frozen.get("project_brief")
    if requested_brief is None:
        project_brief: dict[str, Any] = {}
    elif isinstance(requested_brief, dict):
        project_brief = dict(requested_brief)
    else:
        raise WorkflowContractError(
            "run_inputs_invalid",
            "Run project_brief must be an object",
        )

    brief = next((node for node in workflow.nodes if node.type == "brief"), None)
    if brief is None:
        raise WorkflowContractError(
            "workflow_graph_invalid",
            "Workflow is missing the Brief stage",
        )
    defaults = {field.key: copy.deepcopy(field.default) for field in brief.input_schema}
    core_concept = str(defaults.get("core_concept") or "").strip()
    if not core_concept:
        raise WorkflowContractError(
            "project_idea_missing",
            "The project-owned workflow does not contain a frozen creation idea",
        )
    requested_concept = str(project_brief.get("core_concept") or "").strip()
    if requested_concept and requested_concept != core_concept:
        raise WorkflowContractError(
            "project_idea_mismatch",
            "Run input cannot replace the idea frozen by the project creation wizard",
        )

    project_brief["core_concept"] = core_concept
    for key, value in defaults.items():
        if key in _SCALE_KEYS or key in _KNOWLEDGE_KEYS or key == "core_concept":
            continue
        if key not in project_brief and _has_value(value):
            project_brief[key] = value
    frozen["project_brief"] = project_brief

    knowledge = frozen.get("knowledge_strategy")
    if knowledge is None:
        knowledge_strategy: dict[str, Any] = {}
    elif isinstance(knowledge, dict):
        knowledge_strategy = dict(knowledge)
    else:
        raise WorkflowContractError(
            "run_inputs_invalid",
            "Run knowledge_strategy must be an object",
        )
    for key in _KNOWLEDGE_KEYS:
        if key not in knowledge_strategy and _has_value(defaults.get(key)):
            knowledge_strategy[key] = copy.deepcopy(defaults[key])
    if knowledge_strategy:
        frozen["knowledge_strategy"] = knowledge_strategy
    return frozen


def _has_value(value: Any) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return bool(value)
    return value is not None


__all__ = ["freeze_project_run_inputs"]
