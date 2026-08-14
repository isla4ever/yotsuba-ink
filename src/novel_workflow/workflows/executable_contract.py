from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from pydantic import ValidationError

from novel_workflow.output_contracts.artifacts_vnext import STAGE_ORDER
from novel_workflow.workflows.definition_schemas import WorkflowDefinition


PHASE27_ARCHITECTURE_VERSION = "phase27-vnext"
PHASE27_EDGES: tuple[tuple[str, str], ...] = (
    ("brief", "spine"),
    ("spine", "cast"),
    ("cast", "volumes"),
    ("volumes", "detail"),
    ("detail", "text"),
    ("detail", "cover"),
    ("text", "export"),
    ("cover", "export"),
)


class WorkflowContractError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def require_executable_workflow(raw: dict[str, Any] | WorkflowDefinition) -> WorkflowDefinition:
    try:
        workflow = (
            raw
            if isinstance(raw, WorkflowDefinition)
            else WorkflowDefinition.model_validate(raw)
        )
    except ValidationError as exc:
        raise WorkflowContractError(
            "workflow_contract_retired",
            "Workflow does not satisfy the Phase 27 production contract",
        ) from exc

    if workflow.architecture_version != PHASE27_ARCHITECTURE_VERSION:
        raise WorkflowContractError(
            "workflow_contract_retired",
            "Workflow architecture is not executable by the Phase 27 graph",
        )

    node_ids = tuple(node.id for node in workflow.nodes)
    node_types = tuple(node.type for node in workflow.nodes)
    if node_ids != STAGE_ORDER or node_types != STAGE_ORDER:
        raise WorkflowContractError(
            "workflow_graph_invalid",
            "Workflow nodes must exactly match the Phase 27 stage order",
        )

    edge_pairs = tuple((edge.source, edge.target) for edge in workflow.edges)
    if edge_pairs != PHASE27_EDGES or len({edge.id for edge in workflow.edges}) != len(
        workflow.edges
    ):
        raise WorkflowContractError(
            "workflow_graph_invalid",
            "Workflow edges must exactly match the Phase 27 production graph",
        )

    prompts = {prompt.id: prompt for prompt in workflow.prompt_templates}
    if len(prompts) != len(workflow.prompt_templates):
        raise WorkflowContractError(
            "workflow_prompt_invalid",
            "Workflow Prompt ids must be unique",
        )
    for node in workflow.nodes:
        if node.id == "export":
            if node.prompt_template_id:
                raise WorkflowContractError(
                    "workflow_prompt_invalid",
                    "Export is deterministic and cannot bind a generation Prompt",
                )
            continue
        prompt = prompts.get(node.prompt_template_id)
        if prompt is None or prompt.stage_type != node.type:
            raise WorkflowContractError(
                "workflow_prompt_invalid",
                f"Stage {node.id} must bind its matching Phase 27 Prompt",
            )
    return workflow


def executable_workflows(items: Iterable[dict[str, Any]]) -> list[WorkflowDefinition]:
    workflows: list[WorkflowDefinition] = []
    for item in items:
        try:
            workflows.append(require_executable_workflow(item))
        except WorkflowContractError:
            continue
    return workflows


def workflow_execution_digest(workflow: WorkflowDefinition) -> str:
    require_executable_workflow(workflow)
    payload = workflow.model_dump(
        mode="json",
        exclude={"provider_profiles", "prompt_templates", "canvas_layout"},
    )
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


__all__ = [
    "PHASE27_ARCHITECTURE_VERSION",
    "PHASE27_EDGES",
    "WorkflowContractError",
    "executable_workflows",
    "require_executable_workflow",
    "workflow_execution_digest",
]
