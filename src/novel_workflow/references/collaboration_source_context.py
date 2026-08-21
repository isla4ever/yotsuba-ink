from __future__ import annotations

from typing import Any

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationThread,
    SelectionAnchor,
)
from novel_workflow.references.collaboration_context_errors import (
    CollaborationFieldNotEditable,
    CollaborationSourceStale,
)
from novel_workflow.references.collaboration_field_policy import (
    collaboration_field_is_editable,
)
from novel_workflow.references.collaboration_context_material import digest


def source_snapshot(
    stores: Any,
    thread: CollaborationThread,
) -> tuple[str, str, dict[str, Any]]:
    if thread.stage_id == "text":
        records = stores.chapters.list(thread.run_id)
        record = next(
            (
                item
                for item in records
                if item.version_id == thread.scope.source_ref
                and (
                    thread.scope.unit_ref == "artifact"
                    or item.chapter_id == thread.scope.unit_ref
                )
            ),
            None,
        )
        if record is None:
            raise CollaborationSourceStale("The bound chapter version is unavailable")
        latest = stores.chapters.latest(thread.run_id, record.chapter_id)
        if latest.version_id != record.version_id:
            raise CollaborationSourceStale(
                "The chapter has a newer version; fork or rebase the conversation"
            )
        payload = _current_stage_draft_payload(
            stores,
            run_id=thread.run_id,
            stage_id=thread.stage_id,
            source_ref=record.version_id,
            fallback=record.artifact.model_dump(mode="json"),
        )
        return record.version_id, record.signature, payload
    try:
        record = stores.artifacts.read(thread.run_id, thread.scope.source_ref)
    except FileNotFoundError as exc:
        raise CollaborationSourceStale("The bound stage Artifact is unavailable") from exc
    if record.stage_id != thread.stage_id:
        raise CollaborationSourceStale("The bound Artifact belongs to another stage")
    latest = stores.artifacts.latest(
        thread.run_id,
        thread.stage_id,
        status=record.status,
    )
    if latest.artifact_id != record.artifact_id:
        raise CollaborationSourceStale(
            "The stage has a newer Artifact; fork or rebase the conversation"
        )
    payload = _current_stage_draft_payload(
        stores,
        run_id=thread.run_id,
        stage_id=thread.stage_id,
        source_ref=record.artifact_id,
        fallback=record.payload,
    )
    return record.artifact_id, record.signature, payload


def scoped_source_payload(thread: CollaborationThread, payload: dict[str, Any]) -> Any:
    scoped: Any = payload
    if thread.scope.unit_ref != "artifact":
        found = find_unit(payload, thread.scope.unit_ref)
        if found is None:
            raise CollaborationSourceStale("The bound unit no longer exists")
        scoped = found
    if thread.scope.field_path:
        scoped = resolve_path(payload, thread.scope.field_path)
    return scoped


def validate_selection(
    thread: CollaborationThread,
    selection: SelectionAnchor | None,
    source_payload: dict[str, Any],
) -> None:
    if selection is None:
        return
    if not collaboration_field_is_editable(thread.stage_id, selection.field_path):
        raise CollaborationFieldNotEditable(
            f"{selection.field_path} is not an editable {thread.stage_id} collaboration field"
        )
    if (
        selection.stage_id != thread.stage_id
        or selection.source_ref != thread.scope.source_ref
        or selection.unit_ref != thread.scope.unit_ref
    ):
        raise CollaborationSourceStale("Selection belongs to another source scope")
    field_value = resolve_path(source_payload, selection.field_path)
    if not isinstance(field_value, str):
        raise CollaborationSourceStale("Selection does not target a text field")
    if digest(field_value) != selection.field_hash:
        raise CollaborationSourceStale("Selection field changed after it was captured")
    selected = field_value[selection.selection_start : selection.selection_end]
    if selected != selection.selected_text or digest(selected) != selection.selected_text_hash:
        raise CollaborationSourceStale("Selection offsets no longer match the source")


def scope_bindings(
    stores: Any,
    thread: CollaborationThread,
    scoped_payload: Any,
) -> dict[str, Any]:
    structural_scope = scoped_payload if isinstance(scoped_payload, dict) else {}
    if thread.stage_id == "text":
        try:
            detail = stores.artifacts.latest(
                thread.run_id,
                "detail",
                status="committed",
            )
            chapter = find_unit(detail.payload, thread.scope.unit_ref)
            if isinstance(chapter, dict):
                structural_scope = chapter
        except FileNotFoundError:
            pass
    subject_ids = _string_set(structural_scope.get("cast_ids"))
    pov = str(structural_scope.get("pov") or "")
    if pov:
        subject_ids.add(pov)
    own_subject = str(structural_scope.get("id") or "")
    if own_subject.startswith("subject-"):
        subject_ids.add(own_subject)
    return {
        "subject_ids": subject_ids,
        "turn_refs": _string_set(structural_scope.get("turn_refs")),
        "volume_ref": str(structural_scope.get("volume_ref") or ""),
        "chapter_number": _chapter_number(
            str(
                structural_scope.get("ref")
                or structural_scope.get("chapter_id")
                or thread.scope.unit_ref
            )
        ),
    }


def resolve_thread_source(
    stores: Any,
    *,
    run_id: str,
    stage_id: str,
    source_ref: str,
    unit_ref: str,
) -> tuple[str, str]:
    if stage_id == "text":
        records = stores.chapters.list(run_id)
        record = next(
            (
                item
                for item in records
                if (not source_ref or item.version_id == source_ref)
                and (unit_ref == "artifact" or item.chapter_id == unit_ref)
            ),
            None,
        )
        if record is None:
            raise FileNotFoundError("No chapter version matches the collaboration scope")
        return record.version_id, record.signature
    if source_ref:
        record = stores.artifacts.read(run_id, source_ref)
    else:
        read_model = stores.runs.read(run_id)
        resolved = str(read_model.artifact_refs.get(stage_id) or "")
        if not resolved:
            try:
                record = stores.artifacts.latest(run_id, stage_id, status="candidate")
            except FileNotFoundError:
                record = stores.artifacts.latest(run_id, stage_id, status="committed")
        else:
            record = stores.artifacts.read(run_id, resolved)
    if record.stage_id != stage_id:
        raise ValueError("Collaboration source does not match its stage")
    return record.artifact_id, record.signature


def relevant_upstream(
    payload: dict[str, Any],
    unit_ref: str,
    *,
    subject_ids: set[str],
    turn_refs: set[str],
    volume_ref: str,
) -> Any:
    found = find_unit(payload, unit_ref)
    if found is not None:
        return found
    subjects = payload.get("subjects")
    if isinstance(subjects, list) and subject_ids:
        relations = payload.get("relations")
        selected_relations = [
            item
            for item in relations
            if isinstance(item, dict)
            and (
                str(item.get("a") or "") in subject_ids
                or str(item.get("b") or "") in subject_ids
            )
        ] if isinstance(relations, list) else []
        neighborhood = set(subject_ids)
        for relation in selected_relations:
            neighborhood.update(
                {str(relation.get("a") or ""), str(relation.get("b") or "")}
            )
        return {
            "subjects": [
                item
                for item in subjects
                if isinstance(item, dict)
                and str(item.get("id") or "") in neighborhood
            ],
            "relations": selected_relations,
        }
    turns = payload.get("turns")
    if isinstance(turns, list) and turn_refs:
        return {
            **{key: value for key, value in payload.items() if key != "turns"},
            "turns": [
                item
                for item in turns
                if isinstance(item, dict)
                and str(item.get("id") or "") in turn_refs
            ],
        }
    volumes = payload.get("volumes")
    if isinstance(volumes, list) and volume_ref:
        return {
            "volumes": [
                item
                for item in volumes
                if isinstance(item, dict)
                and str(item.get("id") or "") == volume_ref
            ]
        }
    return payload


def find_unit(value: Any, unit_ref: str) -> Any | None:
    if isinstance(value, dict):
        if str(value.get("id") or value.get("ref") or value.get("chapter_id") or "") == unit_ref:
            return value
        for item in value.values():
            found = find_unit(item, unit_ref)
            if found is not None:
                return found
    elif isinstance(value, list):
        for item in value:
            found = find_unit(item, unit_ref)
            if found is not None:
                return found
    return None


def resolve_path(value: Any, field_path: str) -> Any:
    current = value
    for part in field_path.split("."):
        if not part:
            continue
        if isinstance(current, dict):
            if part not in current:
                raise CollaborationSourceStale(f"Field path is stale at {part}")
            current = current[part]
            continue
        if isinstance(current, list) and part.isdigit():
            index = int(part)
            if index >= len(current):
                raise CollaborationSourceStale("Field path list index is stale")
            current = current[index]
            continue
        raise CollaborationSourceStale("Field path no longer resolves")
    return current


def _current_stage_draft_payload(
    stores: Any,
    *,
    run_id: str,
    stage_id: str,
    source_ref: str,
    fallback: dict[str, Any],
) -> dict[str, Any]:
    pending = next(
        (
            item
            for item in stores.runs.read(run_id).pending_decisions
            if str(item.get("node_id") or "").partition(".")[0] == stage_id
            and str(item.get("artifact_ref") or "") == source_ref
        ),
        None,
    )
    if pending is None:
        return fallback
    decision_id = str(pending.get("decision_id") or "")
    domain_revision = pending.get("domain_revision")
    if not decision_id or not isinstance(domain_revision, int):
        raise CollaborationSourceStale("The pending draft binding is incomplete")
    try:
        draft = stores.stage_drafts.latest(run_id, decision_id)
    except FileNotFoundError:
        return fallback
    if (
        draft.stage_id != stage_id
        or draft.source_artifact_id != source_ref
        or draft.domain_revision != domain_revision
    ):
        raise CollaborationSourceStale("The saved draft no longer matches the active decision")
    return draft.payload


def _string_set(value: Any) -> set[str]:
    if not isinstance(value, list):
        return set()
    return {str(item) for item in value if str(item)}


def _chapter_number(value: str) -> int | None:
    prefix, separator, raw = value.partition("-")
    if prefix != "chapter" or not separator or not raw.isdigit():
        return None
    return int(raw)


__all__ = [
    "relevant_upstream",
    "resolve_thread_source",
    "scope_bindings",
    "scoped_source_payload",
    "source_snapshot",
    "validate_selection",
]
