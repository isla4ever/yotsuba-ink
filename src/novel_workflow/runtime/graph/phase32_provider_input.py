"""Compile the exact secret-free input sent by the Phase 32 gateway."""

from __future__ import annotations

import json
from typing import Any

from novel_workflow.providers.base import PROMPT_SYSTEM_SPLIT
from novel_workflow.providers.frozen_contract import prompt_digest
from novel_workflow.providers.model_capabilities import resolve_request_policy
from novel_workflow.providers.openai_request import ensure_structured_prompt
from novel_workflow.providers.phase32_contract import (
    Phase32ProviderRequest,
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    BookArchitectureArtifact,
    CharacterBibleArtifact,
    ChapterArtifact,
    DetailPlanIndexArtifact,
    SceneDeckArtifact,
    ScreenplayDraftArtifact,
    SectionPlanArtifact,
    ShortProseUnitArtifact,
    StoryMapArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.runtime.graph.route_run_state import RouteRunStateSnapshot
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.workflows.phase32_epistemic_context import (
    compile_phase32_cast_epistemic_context,
)
from novel_workflow.workflows.graph_run_definition import GraphRunDefinition
from novel_workflow.workflows.phase32_short_prose import short_prose_unit_kind
from novel_workflow.workflows.route_compiler import CompiledRouteStage


class Phase32ProviderContextError(ValueError):
    """A committed upstream Artifact cannot produce the frozen stage context."""


def compile_phase32_provider_request(
    *,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    stage: CompiledRouteStage,
    binding: Phase32StageProviderBindingSnapshot,
    binding_digest: str,
    operation_key: str,
    context: dict[str, object],
    direction: str,
) -> Phase32ProviderRequest:
    """Return the final Prompt/Schema snapshot before any network operation."""

    if (
        binding.creation_route_id != definition.creation_route_id
        or binding.stage_id != stage.stage_id
        or binding.workflow_id != definition.workflow_id
        or binding.task.provider_task_kind != stage.provider_task_kind
        or binding.task.artifact_kind != stage.artifact_kind
    ):
        raise ValueError("Phase 32 Provider binding does not match its Run stage")
    user_payload = {
        "route": {
            "creation_route_id": definition.creation_route_id,
            "route_revision": definition.route_revision,
            "stage_id": stage.stage_id,
            "artifact_kind": stage.artifact_kind,
            "context_policy_ref": stage.context_policy_ref,
        },
        "frozen_context": context,
        "author_direction": direction.strip(),
        "output_rules": {
            "format": "single_json_object",
            "schema_digest": binding.task.output_schema_digest,
            "no_markdown": True,
            "no_runtime_metadata": True,
        },
    }
    base_prompt = (
        binding.task.prompt_template
        + PROMPT_SYSTEM_SPLIT
        + "请根据以下冻结输入生成当前阶段 Artifact：\n"
        + json.dumps(user_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    policy = resolve_request_policy(
        binding.execution.provider_template,
        model=binding.execution.model_id,
        task_name=binding.task.transport_task_name,
    )
    rendered_prompt = ensure_structured_prompt(
        base_prompt,
        task_name=binding.task.transport_task_name,
        schema=binding.task.output_schema,
        policy=policy,
    )
    return Phase32ProviderRequest(
        operation_key=operation_key,
        run_id=definition.run_id,
        creation_route_id=definition.creation_route_id,
        route_revision=definition.route_revision,
        stage_id=stage.stage_id,
        provider_task_kind=binding.task.provider_task_kind,
        artifact_kind=binding.task.artifact_kind,
        provider_profile_id=binding.execution.provider_profile_id,
        provider_template_id=binding.execution.provider_template_id,
        model_id=binding.execution.model_id,
        provider_binding_digest=binding_digest,
        transport_task_name=binding.task.transport_task_name,
        rendered_prompt=rendered_prompt,
        rendered_prompt_digest=prompt_digest(rendered_prompt),
        output_schema=binding.task.output_schema,
        output_schema_digest=binding.task.output_schema_digest,
        context=context,
        direction=direction.strip(),
    )


def compile_phase32_stage_context(
    *,
    artifact_store: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    stage: CompiledRouteStage,
) -> dict[str, Any]:
    """Load committed ancestors and compile the exact stage context."""

    upstream_artifacts: dict[str, Any] = {}
    for upstream_stage_id in _ancestor_stage_ids(definition, stage):
        artifact_ref = state.artifact_refs.get(upstream_stage_id, "")
        if not artifact_ref:
            continue
        try:
            record = artifact_store.read(definition.run_id, artifact_ref)
        except Exception as exc:
            raise Phase32ProviderContextError(
                f"Cannot compile Provider context from {upstream_stage_id}"
            ) from exc
        if (
            record.status != "committed"
            or record.creation_route_id != definition.creation_route_id
            or record.stage_id != upstream_stage_id
        ):
            raise Phase32ProviderContextError(
                f"Provider context source is not a committed {upstream_stage_id} Artifact"
            )
        upstream_artifacts[upstream_stage_id] = {
            "artifact_ref": record.artifact_ref,
            "artifact_kind": record.artifact_kind,
            "payload": record.payload,
            "payload_digest": record.payload_digest,
        }
    context = {
        "inputs": definition.inputs.payload,
        "scale_profile": definition.scale_profile.payload,
        "upstream_artifacts": upstream_artifacts,
        "active_unit_ref": state.active_unit_ref,
        "stage_attempt": (
            state.stage_attempts.get(stage.stage_id, 0)
            + state.pending_decision_redraft_count
            + 1
        ),
        "route_stage_ordinal": stage.ordinal,
    }
    if (
        definition.creation_route_id == "screenplay_sample"
        and stage.stage_id == "script"
    ):
        context.update(
            _compile_screenplay_unit_context(
                artifact_store=artifact_store,
                definition=definition,
                state=state,
                upstream_artifacts=upstream_artifacts,
            )
        )
    if definition.creation_route_id == "short_novel" and stage.stage_id == "text":
        context.update(
            _compile_short_prose_unit_context(
                artifact_store=artifact_store,
                definition=definition,
                state=state,
                upstream_artifacts=upstream_artifacts,
            )
        )
    if definition.creation_route_id == "long_novel" and stage.stage_id == "text":
        context.update(
            _compile_long_novel_chapter_context(
                artifact_store=artifact_store,
                definition=definition,
                state=state,
                upstream_artifacts=upstream_artifacts,
            )
        )
    if stage.stage_id == "cast":
        epistemic_context = compile_phase32_cast_epistemic_context(
            creation_route_id=definition.creation_route_id,
            context_policy_ref=stage.context_policy_ref,
            inputs=definition.inputs.payload,
            inputs_digest=definition.inputs.payload_digest,
            upstream_artifacts=upstream_artifacts,
        )
        if epistemic_context is not None:
            context["epistemic_custody"] = epistemic_context.model_dump(mode="json")
    return context


def _compile_screenplay_unit_context(
    *,
    artifact_store: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    upstream_artifacts: dict[str, Any],
) -> dict[str, Any]:
    active_scene_ref = state.active_unit_ref
    progress = state.sequential_progress("script")
    if (
        not active_scene_ref
        or progress is None
        or progress.next_unit_ref != active_scene_ref
    ):
        raise Phase32ProviderContextError(
            "Script context requires the next frozen Scene cursor"
        )
    try:
        scene_deck = SceneDeckArtifact.model_validate(
            upstream_artifacts["scene_deck"]["payload"]
        )
        cast = CharacterBibleArtifact.model_validate(
            upstream_artifacts["cast"]["payload"]
        )
    except Exception as exc:
        raise Phase32ProviderContextError(
            "Script context requires committed Scene Deck and Cast Artifacts"
        ) from exc
    scenes = tuple(scene_deck.scenes)
    scene_index = next(
        (index for index, scene in enumerate(scenes) if scene.scene_ref == active_scene_ref),
        -1,
    )
    if scene_index < 0 or progress.ordered_unit_refs != tuple(
        scene.scene_ref for scene in scenes
    ):
        raise Phase32ProviderContextError(
            "Script cursor does not match the committed Scene Deck order"
        )
    current_scene = scenes[scene_index]
    related_subjects = set(current_scene.cast_subject_refs)
    related_cast = cast.model_copy(
        update={
            "characters": tuple(
                character
                for character in cast.characters
                if character.subject_ref in related_subjects
            ),
            "relationships": tuple(
                relationship
                for relationship in cast.relationships
                if relationship.from_subject_ref in related_subjects
                and relationship.to_subject_ref in related_subjects
            ),
        }
    )
    accepted_prefix: list[dict[str, str]] = []
    previous_blocks: list[dict[str, Any]] = []
    for scene_ref, artifact_ref in progress.committed_artifact_refs.items():
        record = artifact_store.read(definition.run_id, artifact_ref)
        script = ScreenplayDraftArtifact.model_validate(record.payload)
        if (
            record.status != "committed"
            or record.stage_id != "script"
            or script.scene_ref != scene_ref
        ):
            raise Phase32ProviderContextError(
                "Script accepted prefix contains an invalid Scene version"
            )
        accepted_prefix.append(
            {
                "scene_ref": scene_ref,
                "scene_version_ref": artifact_ref,
                "payload_digest": record.payload_digest,
            }
        )
        previous_blocks = [
            block.model_dump(mode="json") for block in script.blocks[-4:]
        ]
    projected_upstream = dict(upstream_artifacts)
    projected_upstream["cast"] = {
        "artifact_ref": upstream_artifacts["cast"]["artifact_ref"],
        "artifact_kind": upstream_artifacts["cast"]["artifact_kind"],
        "source_payload_digest": upstream_artifacts["cast"]["payload_digest"],
        "payload": related_cast.model_dump(mode="json"),
    }
    projected_upstream["scene_deck"] = {
        "artifact_ref": upstream_artifacts["scene_deck"]["artifact_ref"],
        "artifact_kind": upstream_artifacts["scene_deck"]["artifact_kind"],
        "source_payload_digest": upstream_artifacts["scene_deck"]["payload_digest"],
        "payload": {"scenes": [current_scene.model_dump(mode="json")]},
    }
    return {
        "upstream_artifacts": projected_upstream,
        "scene_execution_contract": {
            "scene_ref": active_scene_ref,
            "heading": current_scene.heading,
            "location_and_time": current_scene.location_and_time,
            "cast_subject_refs": list(current_scene.cast_subject_refs),
            "visible_goal": current_scene.visible_goal,
            "opposition": current_scene.opposition,
            "required_outcome": current_scene.outcome,
            "boundary": (
                "one_contiguous_scene_only; use one frozen location/time; "
                "do not merge or reference another scene"
            ),
        },
        "sequential_unit": {
            "scene_ref": active_scene_ref,
            "ordinal": scene_index + 1,
            "total": len(scenes),
            "current_scene": current_scene.model_dump(mode="json"),
            "previous_scene_outcome": (
                scenes[scene_index - 1].outcome if scene_index > 0 else ""
            ),
            "previous_scene_tail": previous_blocks,
            "next_scene_goal": (
                scenes[scene_index + 1].visible_goal
                if scene_index + 1 < len(scenes)
                else ""
            ),
            "accepted_prefix": accepted_prefix,
        },
    }


def _compile_short_prose_unit_context(
    *,
    artifact_store: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    upstream_artifacts: dict[str, Any],
) -> dict[str, Any]:
    active_unit_ref = state.active_unit_ref
    progress = state.sequential_progress("text")
    if (
        not active_unit_ref
        or progress is None
        or progress.next_unit_ref != active_unit_ref
    ):
        raise Phase32ProviderContextError(
            "Short prose context requires the next frozen Section Plan cursor"
        )
    try:
        section_plan = SectionPlanArtifact.model_validate(
            upstream_artifacts["section_plan"]["payload"]
        )
        story_map = StoryMapArtifact.model_validate(
            upstream_artifacts["story_map"]["payload"]
        )
        cast = CharacterBibleArtifact.model_validate(
            upstream_artifacts["cast"]["payload"]
        )
        unit_kind = short_prose_unit_kind(definition.scale_profile.payload)
    except Exception as exc:
        raise Phase32ProviderContextError(
            "Short prose context requires committed Section Plan, Story Map and Cast Artifacts"
        ) from exc
    units = tuple(section_plan.units)
    unit_index = next(
        (index for index, unit in enumerate(units) if unit.unit_ref == active_unit_ref),
        -1,
    )
    if unit_index < 0 or progress.ordered_unit_refs != tuple(
        unit.unit_ref for unit in units
    ):
        raise Phase32ProviderContextError(
            "Short prose cursor does not match the committed Section Plan order"
        )
    current_unit = units[unit_index]
    related_subject_refs = {current_unit.pov_subject_ref}
    related_relationships = tuple(
        relationship
        for relationship in cast.relationships
        if current_unit.pov_subject_ref
        in {relationship.from_subject_ref, relationship.to_subject_ref}
    )
    for relationship in related_relationships:
        related_subject_refs.update(
            {relationship.from_subject_ref, relationship.to_subject_ref}
        )
    related_cast = cast.model_copy(
        update={
            "characters": tuple(
                character
                for character in cast.characters
                if character.subject_ref in related_subject_refs
            ),
            "relationships": related_relationships,
        }
    )
    promise_refs = set(current_unit.promise_refs)
    related_anchors = tuple(
        anchor
        for anchor in story_map.anchors
        if promise_refs.intersection(anchor.promise_refs)
    )
    projected_story_map = story_map.model_copy(update={"anchors": related_anchors})
    previous_unit = units[unit_index - 1] if unit_index > 0 else None
    previous_version_ref = ""
    previous_payload_digest = ""
    previous_tail = ""
    if previous_unit is not None:
        previous_version_ref = progress.committed_artifact_refs.get(
            previous_unit.unit_ref, ""
        )
        if not previous_version_ref:
            raise Phase32ProviderContextError(
                "Short prose accepted prefix is missing the previous unit version"
            )
        try:
            record = artifact_store.read(definition.run_id, previous_version_ref)
            previous_prose = ShortProseUnitArtifact.model_validate(record.payload)
        except Exception as exc:
            raise Phase32ProviderContextError(
                "Short prose accepted prefix contains an invalid unit version"
            ) from exc
        if (
            record.status != "committed"
            or record.stage_id != "text"
            or previous_prose.unit_ref != previous_unit.unit_ref
        ):
            raise Phase32ProviderContextError(
                "Short prose accepted prefix contains an invalid unit version"
            )
        previous_payload_digest = record.payload_digest
        previous_tail = previous_prose.content[-1_200:]
    projected_upstream = dict(upstream_artifacts)
    projected_upstream["cast"] = {
        "artifact_ref": upstream_artifacts["cast"]["artifact_ref"],
        "artifact_kind": upstream_artifacts["cast"]["artifact_kind"],
        "source_payload_digest": upstream_artifacts["cast"]["payload_digest"],
        "payload": related_cast.model_dump(mode="json"),
    }
    projected_upstream["story_map"] = {
        "artifact_ref": upstream_artifacts["story_map"]["artifact_ref"],
        "artifact_kind": upstream_artifacts["story_map"]["artifact_kind"],
        "source_payload_digest": upstream_artifacts["story_map"]["payload_digest"],
        "payload": projected_story_map.model_dump(mode="json"),
    }
    projected_upstream["section_plan"] = {
        "artifact_ref": upstream_artifacts["section_plan"]["artifact_ref"],
        "artifact_kind": upstream_artifacts["section_plan"]["artifact_kind"],
        "source_payload_digest": upstream_artifacts["section_plan"]["payload_digest"],
        "payload": {"units": [current_unit.model_dump(mode="json")]},
    }
    return {
        "upstream_artifacts": projected_upstream,
        "sequential_unit": {
            "unit_ref": active_unit_ref,
            "unit_kind": unit_kind,
            "ordinal": unit_index + 1,
            "total": len(units),
            "current_unit": current_unit.model_dump(mode="json"),
            "previous_unit_handoff": previous_unit.handoff if previous_unit else "",
            "previous_unit_tail": previous_tail,
            "previous_unit_version_ref": previous_version_ref,
            "previous_unit_payload_digest": previous_payload_digest,
            "accepted_unit_count": len(progress.committed_artifact_refs),
            "next_unit_dramatic_job": (
                units[unit_index + 1].dramatic_job
                if unit_index + 1 < len(units)
                else ""
            ),
        },
    }


def _compile_long_novel_chapter_context(
    *,
    artifact_store: Phase32ArtifactStore,
    definition: GraphRunDefinition,
    state: RouteRunStateSnapshot,
    upstream_artifacts: dict[str, Any],
) -> dict[str, Any]:
    active_chapter_ref = state.active_unit_ref
    progress = state.sequential_progress("text")
    if (
        not active_chapter_ref
        or progress is None
        or progress.next_unit_ref != active_chapter_ref
    ):
        raise Phase32ProviderContextError(
            "Chapter context requires the next frozen Rolling Detail cursor"
        )
    try:
        architecture = BookArchitectureArtifact.model_validate(
            upstream_artifacts["book_architecture"]["payload"]
        )
        volumes = VolumeArchitectureArtifact.model_validate(
            upstream_artifacts["volumes"]["payload"]
        )
        detail = DetailPlanIndexArtifact.model_validate(
            upstream_artifacts["rolling_detail"]["payload"]
        )
        cast = CharacterBibleArtifact.model_validate(
            upstream_artifacts["cast"]["payload"]
        )
    except Exception as exc:
        raise Phase32ProviderContextError(
            "Chapter context requires committed Book, Volume, Rolling Detail and Cast Artifacts"
        ) from exc

    planned = tuple(
        (window, chapter)
        for window in detail.windows
        for chapter in window.chapters
    )
    chapter_index = next(
        (
            index
            for index, (_, chapter) in enumerate(planned)
            if chapter.chapter_ref == active_chapter_ref
        ),
        -1,
    )
    if chapter_index < 0 or progress.ordered_unit_refs != tuple(
        chapter.chapter_ref for _, chapter in planned
    ):
        raise Phase32ProviderContextError(
            "Chapter cursor does not match the committed Rolling Detail order"
        )
    current_window, current_chapter = planned[chapter_index]
    current_volume = next(
        (
            volume
            for volume in volumes.volumes
            if volume.volume_ref == current_chapter.volume_ref
        ),
        None,
    )
    if current_volume is None:
        raise Phase32ProviderContextError(
            "Chapter plan references an unavailable committed Volume"
        )
    current_part = next(
        (
            part
            for part in architecture.parts
            if part.part_ref == current_volume.part_ref
        ),
        None,
    )
    if current_part is None:
        raise Phase32ProviderContextError(
            "Chapter Volume references an unavailable committed Part"
        )

    related_subject_refs = set(current_chapter.cast_subject_refs)
    related_cast = cast.model_copy(
        update={
            "characters": tuple(
                character
                for character in cast.characters
                if character.subject_ref in related_subject_refs
            ),
            "relationships": tuple(
                relationship
                for relationship in cast.relationships
                if relationship.from_subject_ref in related_subject_refs
                and relationship.to_subject_ref in related_subject_refs
            ),
        }
    )
    previous_plan = planned[chapter_index - 1][1] if chapter_index > 0 else None
    previous_version_ref = ""
    previous_payload_digest = ""
    previous_tail = ""
    if previous_plan is not None:
        previous_version_ref = progress.committed_artifact_refs.get(
            previous_plan.chapter_ref, ""
        )
        if not previous_version_ref:
            raise Phase32ProviderContextError(
                "Chapter accepted prefix is missing the previous immutable version"
            )
        try:
            record = artifact_store.read(definition.run_id, previous_version_ref)
            previous_chapter = ChapterArtifact.model_validate(record.payload)
        except Exception as exc:
            raise Phase32ProviderContextError(
                "Chapter accepted prefix contains an invalid immutable version"
            ) from exc
        if (
            record.status != "committed"
            or record.stage_id != "text"
            or previous_chapter.chapter_ref != previous_plan.chapter_ref
        ):
            raise Phase32ProviderContextError(
                "Chapter accepted prefix contains an invalid immutable version"
            )
        previous_payload_digest = record.payload_digest
        previous_tail = previous_chapter.content[-1_200:]

    projected_window = current_window.model_copy(
        update={
            "volume_refs": (current_chapter.volume_ref,),
            "chapters": (current_chapter,),
        }
    )
    projected_upstream = dict(upstream_artifacts)
    for stage_id, payload in {
        "book_architecture": architecture.model_copy(
            update={"parts": (current_part,)}
        ).model_dump(mode="json"),
        "cast": related_cast.model_dump(mode="json"),
        "volumes": volumes.model_copy(
            update={"volumes": (current_volume,)}
        ).model_dump(mode="json"),
        "rolling_detail": detail.model_copy(
            update={"windows": (projected_window,)}
        ).model_dump(mode="json"),
    }.items():
        projected_upstream[stage_id] = {
            "artifact_ref": upstream_artifacts[stage_id]["artifact_ref"],
            "artifact_kind": upstream_artifacts[stage_id]["artifact_kind"],
            "source_payload_digest": upstream_artifacts[stage_id]["payload_digest"],
            "payload": payload,
        }
    return {
        "upstream_artifacts": projected_upstream,
        "sequential_unit": {
            "chapter_ref": active_chapter_ref,
            "ordinal": chapter_index + 1,
            "total": len(planned),
            "window_ref": current_window.window_ref,
            "current_chapter": current_chapter.model_dump(mode="json"),
            "current_volume": current_volume.model_dump(mode="json"),
            "current_part": current_part.model_dump(mode="json"),
            "previous_chapter_handoff": previous_plan.handoff if previous_plan else "",
            "previous_chapter_tail": previous_tail,
            "previous_chapter_version_ref": previous_version_ref,
            "previous_chapter_payload_digest": previous_payload_digest,
            "accepted_chapter_count": len(progress.committed_artifact_refs),
            "next_chapter_dramatic_job": (
                planned[chapter_index + 1][1].dramatic_job
                if chapter_index + 1 < len(planned)
                else ""
            ),
        },
    }


def _ancestor_stage_ids(
    definition: GraphRunDefinition,
    stage: CompiledRouteStage,
) -> tuple[str, ...]:
    stages = {
        item.stage_id: item
        for item in definition.route_contract.route_manifest.stages
    }
    pending = list(stage.upstream_stage_ids)
    ancestors: set[str] = set()
    while pending:
        stage_id = pending.pop()
        if stage_id in ancestors:
            continue
        ancestors.add(stage_id)
        pending.extend(stages[stage_id].upstream_stage_ids)
    return tuple(
        item.stage_id
        for item in definition.route_contract.route_manifest.stages
        if item.stage_id in ancestors
    )


__all__ = [
    "Phase32ProviderContextError",
    "compile_phase32_provider_request",
    "compile_phase32_stage_context",
]
