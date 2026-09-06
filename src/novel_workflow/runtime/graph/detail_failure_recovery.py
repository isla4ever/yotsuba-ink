from __future__ import annotations

import re
from collections.abc import Callable, Iterable
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    DetailArtifact,
    DetailLayoutProposalBatch,
    DetailLayoutVolumeProposal,
    DetailSegmentArtifact,
    DetailSegmentChapter,
    StoryBriefArtifact,
    StorySpineArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.output_contracts.provider_tasks import DetailRecoveryPatch
from novel_workflow.output_contracts.prompt_materials import (
    DetailCustodyRecoveryContract,
    DetailPreflightFeedback,
    DetailPreflightFeedbackItem,
    DetailRecoverySource,
)
from novel_workflow.quality.custody_contracts import (
    project_custody_safe_dramatic_task,
    text_assumes_custody,
    text_executes_custody_entry,
)
from novel_workflow.quality.narrative_contracts import (
    dramatic_endpoints_for_chapter,
    dramatic_endpoints_for_text,
)
from novel_workflow.runtime.graph.detail_preflight import build_detail_preflight
from novel_workflow.runtime.graph.context_compiler import NarrativeContextCompiler
from novel_workflow.runtime.graph.detail_planning import (
    detail_layout_turn_windows,
    validate_detail_layout_proposal,
    validate_detail_layout_turn_window_proposal,
)
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.artifact_store import ArtifactStore
from novel_workflow.storage.operation_store import OperationStore
from novel_workflow.storage.provider_input_store import ProviderInputPayload
from novel_workflow.workflows.narrative_scale import NarrativeScaleProfile


_MAX_PREFLIGHT_FEEDBACK_ITEMS = 24
_PREFLIGHT_FEEDBACK_PRIORITY = {
    "premature_main_resolution": 0,
    "historical_status_overreach": 1,
    "detail_duplicate_job": 2,
    "missing_state_delta": 3,
    "unauthorized_repetition": 4,
    "evidence_provenance_conflict": 5,
    "clue_source_missing": 6,
    "clue_lifecycle_incomplete": 7,
    "central_mystery_missing": 8,
    "reader_promise_missing": 9,
}


def previous_detail_preflight_feedback(
    artifacts: ArtifactStore,
    state: NarrativeRunState,
) -> DetailPreflightFeedback | None:
    """Rebuild bounded feedback from the checkpoint's source-bound candidate.

    A stage-level author regeneration has its own revision direction and must not
    inherit this sidecar. A technical recovery attempt may stop before saving a
    new candidate, so the authoritative candidate can legitimately predate the
    immediately preceding attempt.
    """

    current_attempt = int((state.get("stage_attempts") or {}).get("detail") or 1)
    revision_direction = str(
        (state.get("stage_revision_directions") or {}).get("detail") or ""
    ).strip()
    if current_attempt <= 1 or revision_direction:
        return None

    run_id = state["run_id"]
    candidate_ref = str(
        (state.get("candidate_artifact_refs") or {}).get("detail") or ""
    )
    if not candidate_ref:
        return None
    try:
        candidate = artifacts.read(run_id, candidate_ref)
    except FileNotFoundError:
        return None
    source_attempt = _detail_candidate_source_attempt(
        candidate.source,
        run_id=run_id,
        current_attempt=current_attempt,
    )
    if (
        candidate.stage_id != "detail"
        or candidate.status != "candidate"
        or source_attempt is None
    ):
        return None

    refs = state.get("artifact_refs") or {}
    required_refs = {
        stage_id: str(refs.get(stage_id) or "")
        for stage_id in ("brief", "spine", "cast", "volumes")
    }
    if not all(required_refs.values()):
        raise ValueError("Detail preflight recovery requires all committed planning artifacts")

    report = build_detail_preflight(
        brief=StoryBriefArtifact.model_validate(
            artifacts.read(run_id, required_refs["brief"]).payload
        ),
        spine=StorySpineArtifact.model_validate(
            artifacts.read(run_id, required_refs["spine"]).payload
        ),
        cast=CharacterBibleArtifact.model_validate(
            artifacts.read(run_id, required_refs["cast"]).payload
        ),
        volumes=VolumeArchitectureArtifact.model_validate(
            artifacts.read(run_id, required_refs["volumes"]).payload
        ),
        detail=DetailArtifact.model_validate(candidate.payload),
    )
    if not report.blockers:
        return None

    unique: list[DetailPreflightFeedbackItem] = []
    seen: set[tuple[str, tuple[str, ...], str, str]] = set()
    for blocker in report.blockers:
        key = (
            blocker.code,
            tuple(blocker.chapter_refs),
            blocker.evidence,
            blocker.required_fix,
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(
            DetailPreflightFeedbackItem(
                code=blocker.code,
                chapter_refs=list(blocker.chapter_refs),
                evidence=blocker.evidence[:800],
                required_fix=blocker.required_fix[:800],
            )
        )

    unique.sort(
        key=lambda item: _PREFLIGHT_FEEDBACK_PRIORITY.get(item.code, 100)
    )
    visible = unique[:_MAX_PREFLIGHT_FEEDBACK_ITEMS]
    return DetailPreflightFeedback(
        source_candidate_ref=candidate.artifact_id,
        source_attempt=source_attempt,
        unique_blocker_count=len(unique),
        omitted_blocker_count=len(unique) - len(visible),
        blockers=visible,
    )


def _detail_candidate_source_attempt(
    source: str,
    *,
    run_id: str,
    current_attempt: int,
) -> int | None:
    prefix = f"provider:{run_id}:detail:generate:"
    raw_attempt = source.removeprefix(prefix) if source.startswith(prefix) else ""
    if not re.fullmatch(r"[1-9][0-9]*", raw_attempt):
        return None
    source_attempt = int(raw_attempt)
    return source_attempt if source_attempt < current_attempt else None


def failed_detail_generation_attempt(
    operations: OperationStore,
    state: NarrativeRunState,
) -> int | None:
    """Return the immediately failed Detail attempt eligible for technical recovery."""

    current_attempt = int((state.get("stage_attempts") or {}).get("detail") or 1)
    revision_direction = str(
        (state.get("stage_revision_directions") or {}).get("detail") or ""
    ).strip()
    if current_attempt <= 1 or revision_direction:
        return None

    failed_attempt = current_attempt - 1
    prefix = f"{state['run_id']}:detail:generate:{failed_attempt}:"
    receipts = [
        receipt
        for receipt in operations.list(state["run_id"])
        if receipt.kind == "stage_generation_unit"
        and receipt.operation_key.startswith(prefix)
    ]
    if sum(receipt.status == "failed" for receipt in receipts) != 1:
        return None
    if any(receipt.status not in {"succeeded", "failed"} for receipt in receipts):
        return None
    return failed_attempt


def reusable_provider_result(
    operations: OperationStore,
    *,
    run_id: str,
    operation_keys: Iterable[str],
    expected_kind: str,
    current_input: ProviderInputPayload,
    input_matcher: Callable[[ProviderInputPayload, ProviderInputPayload], bool]
    | None = None,
) -> tuple[dict[str, Any], str] | None:
    """Find a successful paid result whose complete frozen input still matches."""

    for operation_key in operation_keys:
        receipt = operations.find(run_id, operation_key)
        if (
            receipt is None
            or receipt.kind != expected_kind
            or receipt.status != "succeeded"
            or not receipt.provider_input_ref
            or not isinstance(receipt.result, dict)
        ):
            continue
        try:
            snapshot = operations.provider_inputs.read(
                run_id,
                receipt.provider_input_ref,
            )
        except (FileNotFoundError, TypeError, ValueError):
            continue
        # Attempts identify executions, not model-visible story context. Every
        # other Provider input field must stay byte-for-byte equivalent unless
        # an explicit source-bound repair matcher verifies the narrower drift.
        matches = (
            input_matcher(snapshot.input, current_input)
            if input_matcher is not None
            else snapshot.input.model_copy(update={"attempt": current_input.attempt})
            == current_input
        )
        if not matches:
            continue
        return dict(receipt.result), operation_key
    return None


def reusable_detail_layout_proposal(
    operations: OperationStore,
    artifacts: ArtifactStore,
    context_compiler: NarrativeContextCompiler,
    *,
    state: NarrativeRunState,
    profile: NarrativeScaleProfile,
    failed_attempt: int,
    current_input: Callable[[dict[str, Any], str], ProviderInputPayload],
    source_attempts: Iterable[int] | None = None,
    input_matcher: Callable[[ProviderInputPayload, ProviderInputPayload], bool]
    | None = None,
) -> tuple[DetailLayoutProposalBatch, list[str]] | None:
    """Rebuild and validate a complete previous layout before reusing any of it."""

    run_id = state["run_id"]
    architecture_ref = (state.get("artifact_refs") or {}).get("volumes")
    spine_ref = (state.get("artifact_refs") or {}).get("spine")
    if not architecture_ref or not spine_ref:
        return None
    architecture = VolumeArchitectureArtifact.model_validate(
        artifacts.read(run_id, architecture_ref).payload
    )
    spine = StorySpineArtifact.model_validate(
        artifacts.read(run_id, spine_ref).payload
    )

    allocated_chapters = 0
    volume_layouts: list[DetailLayoutVolumeProposal] = []
    source_operation_keys: list[str] = []
    attempts = tuple(source_attempts or prior_attempts(failed_attempt))
    for volume_index, volume in enumerate(architecture.volumes):
        windows = detail_layout_turn_windows(
            architecture=architecture,
            profile=profile,
            spine_turn_count=len(spine.turns),
            volume_index=volume_index,
            allocated_chapters=allocated_chapters,
        )
        volume_chapters = []
        for window in windows:
            context = context_compiler.detail_layout_turn_window(
                state,
                window,
                previous_chapters=volume_chapters,
            )
            reusable = reusable_provider_result(
                operations,
                run_id=run_id,
                operation_keys=(
                    _detail_layout_operation_key(
                        run_id,
                        source_attempt,
                        window.scope_ref,
                    )
                    for source_attempt in attempts
                ),
                expected_kind="detail_layout_proposal",
                current_input=current_input(context, window.scope_ref),
                input_matcher=input_matcher,
            )
            if reusable is None:
                return None
            result, source_operation_key = reusable
            try:
                window_batch = DetailLayoutProposalBatch.model_validate(result)
                validate_detail_layout_turn_window_proposal(
                    window_batch,
                    volume=volume,
                    spine=spine,
                    window=window,
                )
            except (TypeError, ValueError):
                return None
            source_operation_keys.append(source_operation_key)
            volume_chapters.extend(window_batch.volumes[0].chapters)
        volume_layouts.append(
            DetailLayoutVolumeProposal(
                volume_ref=volume.id,
                chapters=volume_chapters,
            )
        )
        allocated_chapters += sum(window.chapter_target for window in windows)

    batch = DetailLayoutProposalBatch(
        status="sufficient",
        diagnosis="",
        volumes=volume_layouts,
    )
    try:
        validate_detail_layout_proposal(
            batch,
            architecture=architecture,
            spine=spine,
            profile=profile,
        )
    except ValueError:
        return None
    return batch, source_operation_keys


def source_bound_detail_layout_proposal(
    operations: OperationStore,
    artifacts: ArtifactStore,
    context_compiler: NarrativeContextCompiler,
    *,
    state: NarrativeRunState,
    profile: NarrativeScaleProfile,
    source_attempt: int,
    current_input: Callable[[dict[str, Any], str], ProviderInputPayload],
) -> tuple[DetailLayoutProposalBatch, list[str]] | None:
    """Reuse the rejected candidate's exact layout under the same frozen sources."""

    return reusable_detail_layout_proposal(
        operations,
        artifacts,
        context_compiler,
        state=state,
        profile=profile,
        failed_attempt=source_attempt,
        current_input=current_input,
        source_attempts=prior_attempts(source_attempt),
        input_matcher=_source_bound_provider_input_matches,
    )


def build_detail_recovery_source(
    *,
    detail: DetailArtifact,
    feedback: DetailPreflightFeedback,
    unit_id: str,
    provider_context: dict[str, Any],
) -> tuple[DetailRecoverySource, DetailPreflightFeedback | None]:
    """Slice one immutable candidate segment and its local blocker boundary."""

    material = provider_context.get("material")
    scale = material.get("scale_projection") if isinstance(material, dict) else None
    if not isinstance(scale, dict):
        raise ValueError("Detail recovery requires a scale projection")
    start = int(scale.get("chapter_number_start") or 0)
    count = int(scale.get("chapter_target") or 0)
    if start < 1 or count < 1:
        raise ValueError("Detail recovery scale projection is invalid")
    selected = detail.chapters[start - 1 : start - 1 + count]
    if len(selected) != count:
        raise ValueError("Detail recovery source does not cover the frozen segment")
    volume_ref = unit_id.split(".segment-", maxsplit=1)[0]
    beats = scale.get("chapter_beats")
    if not isinstance(beats, list) or len(beats) != count:
        raise ValueError("Detail recovery chapter beats are invalid")
    for chapter, beat in zip(selected, beats, strict=True):
        if chapter.volume_ref != volume_ref or chapter.turn_refs != beat.get("turn_refs"):
            raise ValueError("Detail recovery source drifted from the frozen layout")

    chapter_refs = [chapter.ref for chapter in selected]
    chapter_ref_set = set(chapter_refs)
    local_items: list[DetailPreflightFeedbackItem] = []
    editable_refs: list[str] = []
    required_removed_endpoints: dict[str, list[str]] = {}
    custody_repair_contracts: dict[str, DetailCustodyRecoveryContract] = {}
    for item in feedback.blockers:
        candidates = _editable_chapter_refs(item)
        if not candidates:
            candidates = list(chapter_refs)
        endpoint_removals = _required_duplicate_endpoint_removals(
            item=item,
            detail=detail,
            selected=selected,
            beats=beats,
        )
        repeated_endpoints = _repeated_duplicate_endpoints(item, detail)
        if repeated_endpoints:
            candidates = [ref for ref in candidates if ref in endpoint_removals]
        local = [ref for ref in candidates if ref in chapter_ref_set]
        if not local:
            continue
        local_items.append(item)
        editable_refs.extend(ref for ref in local if ref not in editable_refs)
        if item.code == "custody_handoff_conflict":
            if len(item.chapter_refs) < 2:
                raise ValueError(
                    "Detail custody recovery requires an adjacent chapter handoff"
                )
            beat_by_ref = {
                chapter.ref: beat
                for chapter, beat in zip(selected, beats, strict=True)
            }
            for chapter_ref in local:
                dramatic_job = str(
                    beat_by_ref.get(chapter_ref, {}).get("dramatic_job") or ""
                )
                custody_repair_contracts[chapter_ref] = DetailCustodyRecoveryContract(
                    previous_chapter_ref=item.chapter_refs[-2],
                    target_state=(
                        "detained"
                        if text_assumes_custody(dramatic_job)
                        or text_executes_custody_entry(dramatic_job)
                        else "free_or_detained"
                    ),
                    preserved_dramatic_task=project_custody_safe_dramatic_task(
                        dramatic_job
                    ),
                )
        for chapter_ref, endpoints in endpoint_removals.items():
            existing = required_removed_endpoints.setdefault(chapter_ref, [])
            existing.extend(endpoint for endpoint in endpoints if endpoint not in existing)

    source_segment = DetailSegmentArtifact.model_validate(
        {
            "chapters": [
                chapter.model_dump(
                    mode="json",
                    exclude={"ref", "volume_ref", "target_characters", "turn_refs"},
                )
                for chapter in selected
            ]
        }
    )
    if not local_items:
        # This object stays runtime-local; no Provider sees an empty edit scope.
        return (
            DetailRecoverySource(
                source_candidate_ref=feedback.source_candidate_ref,
                source_attempt=feedback.source_attempt,
                segment_ref=unit_id,
                chapter_refs=chapter_refs,
                editable_chapter_refs=chapter_refs,
                preserved_chapter_refs=[],
                required_removed_endpoints={},
                custody_repair_contracts={},
                source_segment=source_segment,
            ),
            None,
        )

    preserved_refs = [ref for ref in chapter_refs if ref not in set(editable_refs)]
    source = DetailRecoverySource(
        source_candidate_ref=feedback.source_candidate_ref,
        source_attempt=feedback.source_attempt,
        segment_ref=unit_id,
        chapter_refs=chapter_refs,
        editable_chapter_refs=editable_refs,
        preserved_chapter_refs=preserved_refs,
        required_removed_endpoints=required_removed_endpoints,
        custody_repair_contracts=custody_repair_contracts,
        source_segment=source_segment,
    )
    local_feedback = DetailPreflightFeedback(
        source_candidate_ref=feedback.source_candidate_ref,
        source_attempt=feedback.source_attempt,
        unique_blocker_count=len(local_items),
        omitted_blocker_count=0,
        blockers=local_items,
    )
    return source, local_feedback


def merge_detail_recovery_patch(
    payload: dict[str, Any],
    source: DetailRecoverySource,
    *,
    selected_dossiers: list[dict[str, Any]],
) -> dict[str, Any]:
    """Validate a narrow editable-chapter patch and restore preserved chapters."""

    patch = DetailRecoveryPatch.model_validate(payload)
    editable_refs = source.editable_chapter_refs
    if len(patch.chapters) != len(editable_refs):
        raise ValueError(
            f"Detail recovery returned {len(patch.chapters)} editable chapters; "
            f"expected {len(editable_refs)}"
        )
    source_by_ref = dict(
        zip(source.chapter_refs, source.source_segment.chapters, strict=True)
    )
    subject_names = {
        str(item.get("id") or ""): str(item.get("name") or "").strip()
        for item in selected_dossiers
        if isinstance(item, dict)
        and str(item.get("id") or "").strip()
        and str(item.get("name") or "").strip()
    }
    patched_by_ref = {}
    for chapter_ref, changes in zip(editable_refs, patch.chapters, strict=True):
        before = source_by_ref[chapter_ref]
        after = DetailSegmentChapter(
            title=before.title,
            pov=before.pov,
            cast_ids=before.cast_ids,
            purpose=changes.purpose,
            scenes=changes.scenes,
            handoff=changes.handoff,
        )
        before_text = _detail_segment_chapter_text(before)
        after_text = _detail_segment_chapter_text(after)
        allowed_names = {
            name
            for subject_id, name in subject_names.items()
            if subject_id in before.cast_ids or name in before_text
        }
        introduced_names = sorted(
            name
            for name in subject_names.values()
            if name in after_text and name not in allowed_names
        )
        if introduced_names:
            raise ValueError(
                f"Detail recovery introduced subjects outside the frozen chapter cast for "
                f"{chapter_ref}: {introduced_names}"
            )
        if after == before:
            raise ValueError(
                f"Detail recovery returned {chapter_ref} without materially changing it"
            )
        custody_contract = source.custody_repair_contracts.get(chapter_ref)
        if custody_contract is not None:
            _validate_custody_recovery(chapter_ref, after, custody_contract)
        patched_by_ref[chapter_ref] = after
    unresolved_endpoints = {
        chapter_ref: sorted(
            set(endpoints)
            & dramatic_endpoints_for_chapter(patched_by_ref[chapter_ref])
        )
        for chapter_ref, endpoints in source.required_removed_endpoints.items()
    }
    unresolved_endpoints = {
        chapter_ref: endpoints
        for chapter_ref, endpoints in unresolved_endpoints.items()
        if endpoints
    }
    if unresolved_endpoints:
        raise ValueError(
            "Detail recovery kept dramatic endpoints outside the frozen chapter job: "
            f"{unresolved_endpoints}"
        )
    return DetailSegmentArtifact(
        chapters=[
            patched_by_ref.get(chapter_ref, source_by_ref[chapter_ref])
            for chapter_ref in source.chapter_refs
        ]
    ).model_dump(mode="json")


def _detail_segment_chapter_text(chapter: DetailSegmentChapter) -> str:
    return " ".join(
        [
            chapter.purpose,
            *(
                " ".join(
                    [
                        scene.place,
                        scene.objective,
                        scene.conflict,
                        scene.turn,
                        scene.result,
                    ]
                )
                for scene in chapter.scenes
            ),
            chapter.handoff,
        ]
    )


def _validate_custody_recovery(
    chapter_ref: str,
    chapter: DetailSegmentChapter,
    contract: DetailCustodyRecoveryContract,
) -> None:
    transition_indexes = [
        index
        for index, scene in enumerate(chapter.scenes)
        if text_executes_custody_entry(f"{scene.turn} {scene.result}")
        and not text_assumes_custody(scene.place)
    ]
    custody_scene_indexes = [
        index
        for index, scene in enumerate(chapter.scenes)
        if text_assumes_custody(
            " ".join(
                [scene.place, scene.objective, scene.conflict, scene.turn, scene.result]
            )
        )
    ]
    assumes_custody = bool(custody_scene_indexes) or text_assumes_custody(
        f"{chapter.purpose} {chapter.handoff}"
    )
    needs_transition = contract.target_state == "detained" or assumes_custody
    if needs_transition and not transition_indexes:
        raise ValueError(
            f"Detail recovery for {chapter_ref} must execute the free-to-custody "
            "transition on page"
        )
    if custody_scene_indexes and min(custody_scene_indexes) <= min(transition_indexes):
        raise ValueError(
            f"Detail recovery for {chapter_ref} must execute the arrest or surrender "
            "before entering a custody scene"
        )


def _required_duplicate_endpoint_removals(
    *,
    item: DetailPreflightFeedbackItem,
    detail: DetailArtifact,
    selected: list[Any],
    beats: list[dict[str, Any]],
) -> dict[str, list[str]]:
    repeated = _repeated_duplicate_endpoints(item, detail)
    if not repeated:
        return {}
    local_jobs = {
        chapter.ref: str(beat.get("dramatic_job") or "")
        for chapter, beat in zip(selected, beats, strict=True)
    }
    ordered_refs = [ref for ref in item.chapter_refs if ref]
    owners: dict[str, str] = {}
    for endpoint in repeated:
        explicit_owners = [
            chapter_ref
            for chapter_ref in ordered_refs
            if endpoint in _owned_endpoints_for_job(local_jobs.get(chapter_ref, ""))
        ]
        # A repeated endpoint without an explicit local owner stays in the
        # later chapter. This prevents an earlier preparatory beat from
        # consuming a macro result before its consequence can occur.
        owners[endpoint] = (explicit_owners or ordered_refs)[-1]

    removals: dict[str, list[str]] = {}
    for chapter in selected:
        if chapter.ref not in item.chapter_refs:
            continue
        forbidden = sorted(
            endpoint for endpoint in repeated if owners[endpoint] != chapter.ref
        )
        if forbidden:
            removals[chapter.ref] = forbidden
    return removals


def _repeated_duplicate_endpoints(
    item: DetailPreflightFeedbackItem,
    detail: DetailArtifact,
) -> set[str]:
    if item.code != "detail_duplicate_job" or len(item.chapter_refs) < 2:
        return set()
    chapters_by_ref = {chapter.ref: chapter for chapter in detail.chapters}
    endpoint_sets = [
        dramatic_endpoints_for_chapter(chapters_by_ref[chapter_ref])
        for chapter_ref in item.chapter_refs
        if chapter_ref in chapters_by_ref
    ]
    return set.intersection(*endpoint_sets) if len(endpoint_sets) >= 2 else set()


def _owned_endpoints_for_job(dramatic_job: str) -> set[str]:
    endpoints = dramatic_endpoints_for_text(dramatic_job)
    if "authority_refusal" in endpoints:
        endpoints.add("evidence_submission")
    return endpoints


def preserve_detail_recovery_metadata(
    payload: dict[str, Any],
    source: DetailArtifact,
) -> dict[str, Any]:
    """Keep code-owned chapter identity and prose budgets frozen during repair."""

    repaired = DetailArtifact.model_validate(payload)
    if len(repaired.chapters) != len(source.chapters):
        raise ValueError("Detail recovery changed the frozen chapter count")
    chapters = []
    for before, after in zip(source.chapters, repaired.chapters, strict=True):
        if (
            after.ref != before.ref
            or after.volume_ref != before.volume_ref
            or after.turn_refs != before.turn_refs
        ):
            raise ValueError(
                f"Detail recovery changed frozen slot ownership for {before.ref}"
            )
        chapters.append(
            after.model_copy(update={"target_characters": before.target_characters})
        )
    return DetailArtifact(chapters=chapters).model_dump(mode="json")


def _editable_chapter_refs(item: DetailPreflightFeedbackItem) -> list[str]:
    refs = [ref for ref in item.chapter_refs if re.fullmatch(r"chapter-[1-9][0-9]*", ref)]
    if item.code in {"premature_main_resolution", "historical_status_overreach"}:
        return refs[:1]
    if item.code == "custody_handoff_conflict":
        return refs[-1:]
    return refs


def _source_bound_provider_input_matches(
    source: ProviderInputPayload,
    current: ProviderInputPayload,
) -> bool:
    if (
        source.stage_id != current.stage_id
        or source.task_name != current.task_name
        or source.chapter_id != current.chapter_id
        or source.chapter_version_id != current.chapter_version_id
        or source.provider_binding != current.provider_binding
        or source.prompt_template_id != current.prompt_template_id
        or source.output_contract != current.output_contract
    ):
        return False
    return _without_detail_recovery(source.structured_context) == _without_detail_recovery(
        current.structured_context
    )


def _without_detail_recovery(context: dict[str, Any]) -> dict[str, Any]:
    material = dict(context.get("material") or {})
    material.pop("preflight_feedback", None)
    material.pop("recovery_source", None)
    return {**context, "material": material}


def reusable_detail_segment_result(
    operations: OperationStore,
    *,
    state: NarrativeRunState,
    failed_attempt: int,
    unit_id: str,
    current_input: ProviderInputPayload,
) -> tuple[dict[str, Any], str] | None:
    return reusable_provider_result(
        operations,
        run_id=state["run_id"],
        operation_keys=(
            f"{state['run_id']}:detail:generate:{source_attempt}:{unit_id}"
            for source_attempt in prior_attempts(failed_attempt)
        ),
        expected_kind="stage_generation_unit",
        current_input=current_input,
    )


def prior_attempts(start: int) -> range:
    return range(start, 0, -1)


def _detail_layout_operation_key(run_id: str, attempt: int, scope_ref: str) -> str:
    return f"{run_id}:detail_layout:proposal:{attempt}:{scope_ref}"


__all__ = [
    "failed_detail_generation_attempt",
    "previous_detail_preflight_feedback",
    "prior_attempts",
    "preserve_detail_recovery_metadata",
    "build_detail_recovery_source",
    "reusable_detail_layout_proposal",
    "reusable_detail_segment_result",
    "reusable_provider_result",
    "source_bound_detail_layout_proposal",
    "merge_detail_recovery_patch",
]
