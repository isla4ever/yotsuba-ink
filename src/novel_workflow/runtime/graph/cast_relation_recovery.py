from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterRelation,
    CharacterRelationBatch,
    ambiguous_relation_markers,
)
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.operation_store import OperationStore


def cast_relation_retry_feedback(
    operations: OperationStore,
    state: NarrativeRunState,
    *,
    requirements: dict[str, Any],
    known_subject_ids: set[str],
) -> dict[str, Any] | None:
    """Return bounded feedback for the immediately failed relation-only attempt."""

    attempt = int((state.get("stage_attempts") or {}).get("cast") or 1)
    revision_direction = str(
        (state.get("stage_revision_directions") or {}).get("cast") or ""
    ).strip()
    if attempt <= 1 or revision_direction:
        return None

    previous_key = f"{state['run_id']}:cast_relation:proposal:{attempt - 1}"
    receipt = operations.find(state["run_id"], previous_key)
    if (
        receipt is None
        or receipt.kind != "cast_relation_proposal"
    ):
        return None

    if receipt.status == "succeeded":
        try:
            relations = CharacterRelationBatch.model_validate(receipt.result).relations
        except (TypeError, ValueError):
            return None
        linked = {ref for relation in relations for ref in (relation.a, relation.b)}
        missing = sorted(set(requirements["required_subject_ids"]) - linked)
        unknown = sorted(linked - known_subject_ids)
        protagonist_subject_id = str(requirements["protagonist_subject_id"])
        protagonist_links = {
            relation.b if relation.a == protagonist_subject_id else relation.a
            for relation in relations
            if protagonist_subject_id in {relation.a, relation.b}
        }
        missing_protagonist_link = bool(
            requirements["required_subject_ids"]
            and protagonist_subject_id
            and not protagonist_links.intersection(requirements["required_subject_ids"])
        )
        if not missing and not unknown and not missing_protagonist_link:
            return None
        return {
            "missing_required_subject_ids": missing,
            "unknown_subject_ids": unknown,
            "missing_protagonist_link": missing_protagonist_link,
            "required_action": (
                "Return a fresh complete relation batch satisfying relationship_requirements "
                "without adding speculative edges."
            ),
        }

    if receipt.status != "contract_rejected" or not isinstance(
        receipt.provider_result, dict
    ):
        return None

    raw_relations = receipt.provider_result.get("relations")
    if not isinstance(raw_relations, list):
        return None

    rejected: list[dict[str, Any]] = []
    for index, raw_relation in enumerate(raw_relations, start=1):
        try:
            CharacterRelation.model_validate(raw_relation)
        except ValidationError as exc:
            rejected.append(
                {
                    "item": index,
                    "relation": raw_relation,
                    "errors": [
                        {
                            "field": ".".join(str(part) for part in error["loc"]),
                            "message": error["msg"],
                            **(
                                {"ambiguous_markers": list(markers)}
                                if (
                                    markers := ambiguous_relation_markers(
                                        str(
                                            raw_relation.get(
                                                str(error["loc"][0]),
                                                "",
                                            )
                                            if isinstance(raw_relation, dict)
                                            else ""
                                        )
                                    )
                                )
                                else {}
                            ),
                        }
                        for error in exc.errors(include_url=False, include_input=False)
                    ],
                }
            )

    if not rejected:
        return None
    return {
        "rejected_relations": rejected,
        "required_action": (
            "Return a fresh complete relation batch. Omit or rewrite every rejected "
            "edge as a completed two-subject action and present consequence. Remove "
            "every ambiguous_markers term reported above instead of paraphrasing it."
        ),
    }


def reusable_cast_relation_result(
    operations: OperationStore,
    state: NarrativeRunState,
) -> tuple[dict[str, Any], str] | None:
    """Revalidate the immediately rejected immutable relation payload."""

    attempt = int((state.get("stage_attempts") or {}).get("cast") or 1)
    revision_direction = str(
        (state.get("stage_revision_directions") or {}).get("cast") or ""
    ).strip()
    if attempt <= 1 or revision_direction:
        return None
    operation_key = f"{state['run_id']}:cast_relation:proposal:{attempt - 1}"
    receipt = operations.find(state["run_id"], operation_key)
    if (
        receipt is None
        or receipt.kind != "cast_relation_proposal"
        or receipt.status != "contract_rejected"
        or not isinstance(receipt.provider_result, dict)
    ):
        return None
    try:
        payload = CharacterRelationBatch.model_validate(
            receipt.provider_result
        ).model_dump(mode="json")
    except (TypeError, ValueError):
        return None
    return payload, operation_key


__all__ = ["cast_relation_retry_feedback", "reusable_cast_relation_result"]
