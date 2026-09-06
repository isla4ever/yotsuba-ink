from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    ContextManifest,
    ContextSnippet,
    DetailArtifact,
    DetailLayoutChapterProposal,
    DetailLayoutProposalBatch,
    StoryBriefArtifact,
    StorySpineArtifact,
    StageId,
    VolumeArchitectureArtifact,
    VolumeBoundaryProposalBatch,
)
from novel_workflow.memory.canon_store import CanonStore
from novel_workflow.output_contracts.prompt_materials import validate_prompt_material
from novel_workflow.quality.planning_contracts import project_world_rules
from novel_workflow.runtime.graph.detail_planning import DetailLayoutTurnWindow
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.runtime.graph.output_budget import OutputBudgetPlanner
from novel_workflow.runtime.graph.planning_authority import HierarchicalPlanningAuthority
from novel_workflow.storage.artifact_store import ArtifactStore
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.narrative_run_repository import NarrativeRunRepository
from novel_workflow.workflows.narrative_scale import (
    DetailChapterBeatSlot,
    DetailScaleProjection,
    NarrativeScalePlan,
    NarrativeScaleProfile,
    chapter_length_contract,
    chapter_target_band,
    count_prose_characters,
    detail_scene_count_range,
    plan_narrative_scale,
    spine_milestone_positions,
)


PLANNING_INPUTS: dict[StageId, tuple[StageId, ...]] = {
    "brief": (),
    "spine": ("brief",),
    "cast": ("brief", "spine"),
    "volumes": ("brief", "spine", "cast"),
    "detail": ("brief", "spine", "cast", "volumes"),
    "text": ("brief", "cast", "volumes", "detail"),
    "cover": ("brief",),
    "export": (),
}

DETAIL_BATCH_SIZE = 12

_TAIL_EXCERPT_CHARS = 800
_CONTEXT_STATE_CHAR_BUDGET = 9_000
_EPHEMERAL_STATE_PROPERTIES = frozenset(
    {"action", "finding", "source", "inference", "belief"}
)

@dataclass(frozen=True, slots=True)
class NarrativeContextCompiler:
    """Compile bounded, ref-based context packets for graph nodes."""

    runs: NarrativeRunRepository
    artifacts: ArtifactStore
    chapters: ChapterStore
    canon: CanonStore | None = None
    planning: HierarchicalPlanningAuthority | None = None

    def hierarchical_spine_part(
        self,
        state: NarrativeRunState,
        part_ref: str,
    ) -> dict[str, Any]:
        authority = self._planning_authority()
        version_id = self._planning_version_ref(state, "spine")
        context = authority.spine_part_context(state["run_id"], version_id, part_ref)
        return _hierarchical_context_packet(state, "spine.part", context)

    def hierarchical_volume_part(
        self,
        state: NarrativeRunState,
        part_ref: str,
    ) -> dict[str, Any]:
        authority = self._planning_authority()
        version_id = self._planning_version_ref(state, "volumes")
        context = authority.volume_part_context(state["run_id"], version_id, part_ref)
        return _hierarchical_context_packet(state, "volumes.part", context)

    def hierarchical_detail_window(
        self,
        state: NarrativeRunState,
        window_ref: str,
    ) -> dict[str, Any]:
        authority = self._planning_authority()
        version_id = self._planning_version_ref(state, "detail")
        context = authority.detail_window_context(state["run_id"], version_id, window_ref)
        return _hierarchical_context_packet(state, "detail.window", context)

    def stage(self, state: NarrativeRunState, stage_id: StageId) -> dict[str, Any]:
        if stage_id == "export":
            return {"target": "export", "sources": {}, "material": {}}
        definition = self.runs.definition(state["run_id"])
        if stage_id == "brief":
            material: dict[str, Any] = {
                "project_brief": _project_brief(definition.inputs),
                "length_envelope": _length_envelope(definition.scale_profile),
            }
            source_pack = _source_pack(definition.inputs)
            if source_pack:
                material["source_pack"] = source_pack
            return self._with_revision(state, stage_id, material, {})

        payloads, source_refs = self._planning_material(state, PLANNING_INPUTS[stage_id])
        plan = plan_narrative_scale(definition.scale_profile, definition.quality_mode)
        material: dict[str, Any]
        if stage_id == "spine":
            material = {
                "story_brief": payloads["brief"],
                "scale_plan": _spine_scale_plan(plan),
            }
            observations = _source_observations(definition.inputs)
            if observations:
                material["source_observations"] = observations
        elif stage_id == "cast":
            material = {
                "story_brief": payloads["brief"],
                "story_spine": payloads["spine"],
                "role_demand_proposals": state.get("role_demand_proposals") or [],
                "subject_refs": state.get("subject_refs") or [],
                "scale_plan": _cast_scale_plan(plan),
            }
        elif stage_id == "volumes":
            volume_candidate_cap = OutputBudgetPlanner(
                definition.scale_profile
            ).item_cap("volume_boundaries")
            material = {
                "story_brief": payloads["brief"],
                "story_spine": payloads["spine"],
                "character_bible_refs": _volume_character_refs(payloads["cast"]),
                "volume_boundaries": state.get("volume_boundary_proposal") or {"proposals": []},
                "scale_plan": _volume_scale_plan(plan, volume_candidate_cap),
            }
        elif stage_id == "detail":
            raise ValueError(
                "Detail planning context is volume-scoped; use detail_layout_volume"
            )
        elif stage_id == "cover":
            material = {
                "accepted_story_metadata": _accepted_story_metadata(
                    state, self.chapters, payloads["brief"]
                ),
                "visual_decisions": _visual_decisions(definition.inputs),
            }
        else:
            raise ValueError(f"Stage {stage_id} does not have a planning context")
        return self._with_revision(
            state,
            stage_id,
            material,
            source_refs,
            validate_material=stage_id != "volumes",
        )

    def stage_units(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
        *,
        detail_layout: DetailLayoutProposalBatch | None = None,
    ) -> list[tuple[str, dict[str, Any]]]:
        if stage_id == "detail":
            if detail_layout is None:
                raise ValueError("Detail stage units require a frozen chapter layout proposal")
            return self._detail_contexts(state, detail_layout)
        base = self.stage(state, stage_id)
        if stage_id == "cast":
            definition = self.runs.definition(state["run_id"])
            planner = OutputBudgetPlanner(definition.scale_profile)
            return _group_cast_context(base, planner.item_cap("cast_dossiers"))
        if stage_id == "volumes":
            return _volume_contexts(base)
        return [("", base)]

    def detail_layout_turn_window(
        self,
        state: NarrativeRunState,
        window: DetailLayoutTurnWindow,
        *,
        previous_chapters: list[DetailLayoutChapterProposal] | None = None,
    ) -> dict[str, Any]:
        """Compile one deterministic turn slice and its exact chapter slots."""

        payloads, refs = self._planning_material(state, PLANNING_INPUTS["detail"])
        cast = CharacterBibleArtifact.model_validate(payloads["cast"])
        architecture = VolumeArchitectureArtifact.model_validate(payloads["volumes"])
        spine = StorySpineArtifact.model_validate(payloads["spine"])
        world_rule_projection = project_world_rules(
            StoryBriefArtifact.model_validate(payloads["brief"])
        ).model_dump(mode="json")
        try:
            volume = architecture.volumes[window.volume_index]
        except IndexError as exc:
            raise ValueError("Detail layout window references an unknown volume") from exc
        if volume.id != window.volume_ref:
            raise ValueError("Detail layout window does not match the committed volume order")

        turn_ids = set(window.turn_refs)
        window_turns = [
            turn.model_dump(mode="json")
            for turn in spine.turns
            if turn.id in turn_ids
        ]
        if [turn["id"] for turn in window_turns] != list(window.turn_refs):
            raise ValueError("Detail layout turn window is not a complete Spine slice")
        selected_subjects = set(volume.cast_ids)
        volume_contract = volume.model_dump(mode="json")
        volume_contract["turn_refs"] = list(window.turn_refs)
        material = {
            "story_spine": {"turns": window_turns},
            "volume_contracts": [volume_contract],
            "selected_dossiers": [
                _detail_dossier_projection(subject)
                for subject in cast.subjects
                if subject.id in selected_subjects
            ],
            "world_rule_projection": world_rule_projection,
            "chapter_slots": [
                {"slot_index": window.chapter_offset + index}
                for index in range(1, window.chapter_target + 1)
            ],
            "scale_plan": {
                "book_chapter_target": window.book_chapter_target,
                "book_chapter_range": [
                    window.book_chapter_min,
                    window.book_chapter_max,
                ],
                "allocated_chapters": window.allocated_chapters,
                "remaining_volume_range": [
                    window.remaining_volume_min,
                    window.remaining_volume_max,
                ],
                "remaining_volume_target": window.remaining_volume_target,
                "chapter_target": window.chapter_target,
                "chapter_range": [window.chapter_min, window.chapter_max],
                "chapter_offset": window.chapter_offset,
                "volume_chapter_target": window.volume_chapter_target,
                "volume_index": window.volume_index + 1,
                "volume_count": window.volume_count,
                "turn_window_index": window.window_index,
                "turn_window_count": window.window_count,
                "turn_count": len(window.turn_refs),
                "minimum_chapter_surplus_over_turns": max(
                    0, window.chapter_min - len(window.turn_refs)
                ),
                "target_chapter_surplus_over_turns": max(
                    0, window.chapter_target - len(window.turn_refs)
                ),
                "counting_rule": "non_whitespace_characters",
            },
        }
        if previous_chapters:
            completed_jobs = list(
                dict.fromkeys(
                    chapter.dramatic_job.strip()
                    for chapter in previous_chapters
                    if chapter.dramatic_job.strip()
                )
            )
            material["previous_window_layout"] = {
                "completed_turn_refs": list(
                    dict.fromkeys(
                        turn_ref
                        for chapter in previous_chapters
                        for turn_ref in chapter.turn_refs
                    )
                ),
                "chapters": [
                    chapter.model_dump(mode="json") for chapter in previous_chapters
                ],
                "completed_dramatic_jobs": completed_jobs,
            }
        return self._with_revision(
            state,
            "detail",
            material,
            refs,
            validate_material=False,
        )

    def chapter(
        self,
        state: NarrativeRunState,
        *,
        output_tokens: int | None = None,
    ) -> dict[str, Any]:
        payloads, refs = self._planning_material(state, PLANNING_INPUTS["text"])
        chapter_number = int(state["active_chapter_number"])
        detail = DetailArtifact.model_validate(payloads["detail"])
        brief = StoryBriefArtifact.model_validate(payloads["brief"])
        world_rule_projection = project_world_rules(brief)
        chapter = detail.chapters[chapter_number - 1]
        previous = self._previous_chapter(state)
        snippets = [
            _context_snippet(
                "detail.chapter",
                "chapter_script",
                chapter.model_dump(mode="json"),
            ),
            _context_snippet(
                "cast.subjects",
                "pov_scene_and_referenced_subjects",
                _chapter_subjects(payloads["cast"], chapter),
            ),
            _context_snippet(
                "volume.contract",
                "local_promise_and_closure",
                _volume_by_ref(payloads["volumes"], chapter.volume_ref),
            ),
            _context_snippet(
                "brief.world_rules",
                "frozen_world_and_professional_rules",
                world_rule_projection.model_dump(mode="json"),
            ),
        ]
        optional: list[str] = []
        # Without a length contract the same book swings between a 1,900 and a
        # 6,700 character chapter, which breaks both the promised word target
        # and the reading rhythm the scene count was planned around.
        definition = self.runs.definition(state["run_id"])
        length_contract = chapter_length_contract(
            chapter.target_characters,
            definition.quality_mode,
            scene_count=len(chapter.scenes),
        )
        if length_contract is not None:
            optional.append("scale.chapter_length")
            snippets.append(
                _context_snippet(
                    "scale.chapter_length",
                    "chapter_length_contract",
                    length_contract.model_dump(mode="json"),
                )
            )
        # The narrative voice is a book-level contract (person, distance,
        # tone). Prose generation must see it every chapter or the person
        # silently drifts from what the brief promised.
        voice = brief.voice.strip()
        if voice:
            optional.append("brief.voice")
            snippets.append(
                _context_snippet(
                    "brief.voice",
                    "narrative_voice_contract",
                    voice,
                )
            )
        if previous:
            optional.append("previous.handoff")
            snippets.append(
                _context_snippet(
                    "previous.handoff",
                    "sequential_continuity",
                    previous["handoff"],
                )
            )
            # A one-line planned handoff cannot carry the concrete end state
            # (time of day, location, what the POV already knows), which is
            # exactly what the next chapter must continue from. A bounded tail
            # excerpt of the accepted prose closes that gap without shipping
            # the full previous chapter.
            ending = _tail_excerpt(str(previous.get("content") or ""))
            if ending:
                optional.append("previous.ending_excerpt")
                snippets.append(
                    _context_snippet(
                        "previous.ending_excerpt",
                        "seamless_opening_continuity",
                        ending,
                    )
                )
            # The tail excerpt shows how the previous chapter ended but not what
            # it dramatized earlier, so a conversation or discovery from its
            # first scene can be staged a second time here.
            staged = _staged_beats(detail, chapter_number - 1)
            if staged:
                optional.append("previous.staged_beats")
                snippets.append(
                    _context_snippet(
                        "previous.staged_beats",
                        "already_dramatized_do_not_repeat",
                        staged,
                    )
                )
            # The ending excerpt only carries the last scene; facts committed
            # to canon from earlier chapters (object states, established
            # events, what characters know) must also bind later prose so
            # props and knowledge do not silently drift between chapters.
            story_state = _context_story_state(
                self._resolved_story_state(
                    state["run_id"],
                    as_of_chapter=chapter_number - 1,
                    subject_ids=set(chapter.cast_ids),
                )
            )
            if story_state["entries"] or story_state["conflicts"]:
                optional.append("story.current_state")
                snippets.append(
                    _context_snippet(
                        "story.current_state",
                        "resolved_story_state",
                        story_state,
                    )
                )
            recent_window = self._recent_chapter_window(state, detail)
            if recent_window["chapters"]:
                optional.append("continuity.recent_window")
                snippets.append(
                    _context_snippet(
                        "continuity.recent_window",
                        "bounded_multi_chapter_continuity",
                        recent_window,
                    )
                )
        attempt = int((state.get("chapter_attempts") or {}).get(chapter.ref) or 1)
        if attempt > 1:
            direction = str(
                (state.get("chapter_revision_directions") or {}).get(chapter.ref) or ""
            ).strip()
            if not direction:
                raise ValueError(
                    "A repeated chapter generation requires an explicit revision direction"
                )
            source_version_id = str(
                (state.get("chapter_version_refs") or {}).get(chapter.ref) or ""
            )
            if not source_version_id:
                raise ValueError(
                    "A repeated chapter generation requires its immutable source draft"
                )
            source = self.chapters.read(
                state["run_id"], chapter.ref, source_version_id
            ).artifact
            if source.author_status not in {"candidate", "edited"}:
                raise ValueError(
                    "A repeated chapter generation may only replace an unaccepted draft"
                )
            optional.append("revision.source_draft")
            snippets.append(
                _context_snippet(
                    "revision.source_draft",
                    "unaccepted_draft_to_replace",
                    {
                        "scope": "chapter",
                        "measured_non_whitespace_characters": count_prose_characters(
                            source.content
                        ),
                        "content": source.content,
                    },
                )
            )
            optional.append("revision.request")
            snippets.append(
                _context_snippet(
                    "revision.request",
                    "controlling_revision_direction",
                    direction,
                )
            )
        manifest_body = {
            "task": chapter.ref,
            "required": [
                "detail.chapter",
                "cast.subjects",
                "volume.contract",
                "brief.world_rules",
            ],
            "optional": optional,
            "forbidden": ["full_canon", "full_wiki", "unrelated_subjects", "full_previous_chapter"],
            "snippets": snippets,
            "budget": {
                "input_chars": 0,
                "output_tokens": output_tokens
                or self.runs.definition(state["run_id"]).provider_bindings["text"].max_tokens,
            },
        }
        manifest_body["budget"]["input_chars"] = sum(
            len(item["text"]) for item in snippets
        )
        manifest_body["manifest_hash"] = _manifest_hash(manifest_body)
        manifest = ContextManifest.model_validate(manifest_body)
        material: dict[str, Any] = {
            "chapter_context_manifest": manifest.model_dump(mode="json")
        }
        validate_prompt_material("text", material)
        return {"target": "text", "sources": refs, "material": material}

    def _detail_contexts(
        self,
        state: NarrativeRunState,
        layout: DetailLayoutProposalBatch,
    ) -> list[tuple[str, dict[str, Any]]]:
        payloads, refs = self._planning_material(state, PLANNING_INPUTS["detail"])
        cast = CharacterBibleArtifact.model_validate(payloads["cast"])
        architecture = VolumeArchitectureArtifact.model_validate(payloads["volumes"])
        spine = StorySpineArtifact.model_validate(payloads["spine"])
        world_rule_projection = project_world_rules(
            StoryBriefArtifact.model_validate(payloads["brief"])
        ).model_dump(mode="json")
        definition = self.runs.definition(state["run_id"])
        detail_binding = definition.provider_bindings.get("detail")
        if detail_binding is None:
            raise ValueError("Detail requires a frozen Provider binding")
        chapter_capacity = OutputBudgetPlanner(
            definition.scale_profile
        ).detail_chapter_capacity(detail_binding)
        turn_by_id = {turn.id: turn for turn in spine.turns}
        dossiers = {subject.id: subject for subject in cast.subjects}
        chapter_count = sum(
            len(volume_layout.chapters) for volume_layout in layout.volumes
        )
        target_band = chapter_target_band(definition.scale_profile, chapter_count)
        scene_minimum, scene_maximum = detail_scene_count_range(
            definition.scale_profile,
            chapter_count,
        )
        final_volume_ref = architecture.volumes[-1].id if architecture.volumes else ""
        chapter_number_start = 1
        units: list[tuple[str, dict[str, Any]]] = []
        layouts = {item.volume_ref: item for item in layout.volumes}
        for volume in architecture.volumes:
            volume_layout = layouts.get(volume.id)
            if volume_layout is None:
                raise ValueError(f"Detail layout is missing {volume.id}")
            slot_groups = _partition_detail_layout_slots(
                volume_layout.chapters,
                chapter_capacity,
            )
            segment_count = len(slot_groups)
            selected = [
                _detail_dossier_projection(dossiers[subject_id])
                for subject_id in volume.cast_ids
                if subject_id in dossiers
            ]
            historical_record_ids = [
                str(subject.get("id") or "")
                for subject in selected
                if subject.get("kind") == "historical_record"
            ]
            present_actor_ids = [
                str(subject.get("id") or "")
                for subject in selected
                if subject.get("kind") != "historical_record"
            ]
            for index, layout_group in enumerate(slot_groups, start=1):
                turn_group = _ordered_unique(
                    turn_ref
                    for slot in layout_group
                    for turn_ref in slot.turn_refs
                )
                segment_ref = f"{volume.id}.segment-{index}"
                scale_projection = DetailScaleProjection(
                    volume_ref=volume.id,
                    segment_ref=segment_ref,
                    segment_index=index,
                    segment_count=segment_count,
                    chapter_target=len(layout_group),
                    chapter_beats=[
                        DetailChapterBeatSlot(
                            chapter_offset=offset,
                            turn_refs=list(slot.turn_refs),
                            dramatic_job=slot.dramatic_job,
                            length_hint=slot.length_hint,
                        )
                        for offset, slot in enumerate(layout_group, start=1)
                    ],
                    chapter_target_band=target_band,
                    scenes_per_chapter_min=scene_minimum,
                    scenes_per_chapter_max=scene_maximum,
                    is_final_volume=volume.id == final_volume_ref,
                    chapter_number_start=chapter_number_start,
                )
                chapter_number_start += len(layout_group)
                segment_chapter_end = chapter_number_start - 1
                debut_requirements = [
                    {
                        "subject_id": subject.id,
                        "name": subject.name,
                        "debut": subject.debut,
                        "latest_chapter": _chapter_end(subject.debut),
                    }
                    for subject in cast.subjects
                    if subject.kind != "historical_record"
                    and scale_projection.chapter_number_start
                    <= _chapter_end(subject.debut)
                    <= segment_chapter_end
                ]
                missing_debut_subjects = sorted(
                    requirement["subject_id"]
                    for requirement in debut_requirements
                    if requirement["subject_id"] not in present_actor_ids
                )
                if missing_debut_subjects:
                    raise ValueError(
                        "Volume cast omits subjects whose frozen debut deadline falls "
                        f"inside this segment: {missing_debut_subjects}"
                    )
                volume_context: dict[str, Any] = {
                    "id": volume.id,
                    "title": volume.title,
                }
                if index == segment_count:
                    volume_context["closing_state"] = volume.closure
                material: dict[str, Any] = {
                    "volume_contract": volume_context,
                    "volume_spine_turns": [
                        turn_by_id[turn_ref].model_dump(mode="json")
                        for turn_ref in turn_group
                    ],
                    "scale_projection": scale_projection.model_dump(mode="json"),
                    "selected_dossiers": selected,
                    "debut_requirements": debut_requirements,
                    "historical_record_ids": historical_record_ids,
                    "present_actor_ids": present_actor_ids,
                    "world_rule_projection": world_rule_projection,
                }
                packet = self._with_revision(state, "detail", material, refs)
                packet["budget_basis"] = {"expected_chapters": len(layout_group)}
                units.append((segment_ref, packet))
        if not units:
            raise ValueError("Detail requires at least one committed volume contract")
        return units

    def review(self, state: NarrativeRunState, role: str) -> dict[str, Any]:
        """Build one bounded reviewer lane from the accepted planning refs."""
        payloads, refs = self._planning_material(
            state,
            ("brief", "spine", "cast", "volumes", "detail"),
        )
        chapter_id = str(state.get("active_chapter_id") or "")
        version_id = str((state.get("chapter_version_refs") or {}).get(chapter_id) or "")
        if not chapter_id or not version_id:
            raise ValueError("Reviewer requires the current immutable chapter version")
        chapter = self.chapters.read(state["run_id"], chapter_id, version_id).artifact
        material: dict[str, Any] = {
            "chapter": {"chapter_id": chapter.chapter_id, "version_id": chapter.version_id, "content": chapter.content},
            "review_role": role,
        }
        brief = StoryBriefArtifact.model_validate(payloads["brief"])
        cast = CharacterBibleArtifact.model_validate(payloads["cast"])
        detail = DetailArtifact.model_validate(payloads["detail"])
        chapter_detail = next(item for item in detail.chapters if item.ref == chapter_id)
        chapter_number = int(state.get("active_chapter_number") or 0)
        if role == "character":
            material["spine"] = _spine_excerpt(payloads["spine"])
            eligible = {
                subject.id
                for subject in cast.subjects
                if _chapter_end(subject.debut) <= chapter_number
            } | _scheduled_subject_ids(detail, cast, chapter_number)
            material["character_bible"] = [
                subject.model_dump(mode="json")
                for subject in cast.subjects
                if subject.id in set(chapter_detail.cast_ids)
            ]
            material["appearance_policy"] = {
                "eligible_subject_ids": sorted(eligible),
                "not_yet_eligible_subject_ids": sorted({subject.id for subject in cast.subjects} - eligible),
                # `eligible` is the only appearance authority here: it already
                # merges the cast debut window with what the approved chapter
                # plan scheduled, so exposing the raw debut would invite the
                # reviewer to report a subject the outline placed earlier.
                "roster": [
                    {
                        "id": subject.id,
                        "name": subject.name,
                        "eligible": subject.id in eligible,
                    }
                    for subject in cast.subjects
                ],
                "chapter_number": chapter_number,
            }
        elif role == "continuity":
            material["current_detail_chapter"] = chapter_detail.model_dump(mode="json")
            material["world_rule_projection"] = project_world_rules(brief).model_dump(
                mode="json"
            )
            material["character_bible"] = _chapter_subjects(
                payloads["cast"], chapter_detail
            )
            previous = self._previous_chapter(state)
            if previous is None:
                # A null slot invites the reviewer to invent a predecessor and
                # judge the opening chapter against it.
                material["opening_chapter"] = True
            else:
                material["previous_accepted_chapter"] = previous
                material["recent_chapter_window"] = self._recent_chapter_window(
                    state,
                    detail,
                )
            story_state = self._resolved_story_state(
                state["run_id"],
                as_of_chapter=chapter_number - 1,
                subject_ids=set(),
            )
            if story_state["entries"] or story_state["conflicts"]:
                material["story_state"] = story_state
                material["continuity_state"] = _continuity_state_projection(
                    story_state
                )
        elif role == "prose":
            material["voice"] = brief.voice
        return {"target": "text.review", "sources": refs, "material": material}

    def evidence(self, state: NarrativeRunState) -> dict[str, Any]:
        """Bind Evidence extraction to frozen subjects and prior current state."""
        payloads, _ = self._planning_material(state, ("cast", "detail"))
        detail = DetailArtifact.model_validate(payloads["detail"])
        chapter_number = int(state.get("active_chapter_number") or 0)
        chapter_id = str(state.get("active_chapter_id") or "")
        chapter = next((item for item in detail.chapters if item.ref == chapter_id), None)
        if chapter is None or chapter_number < 1:
            raise ValueError("Evidence context requires the active frozen Detail chapter")
        subjects = _chapter_subjects(payloads["cast"], chapter)
        return {
            "frozen_subjects": [
                {"id": subject["id"], "name": subject["name"], "kind": subject["kind"]}
                for subject in subjects
            ],
            "story_state": self._resolved_story_state(
                state["run_id"],
                as_of_chapter=chapter_number - 1,
                subject_ids={subject["id"] for subject in subjects},
            ),
        }

    def _planning_material(
        self,
        state: NarrativeRunState,
        stages: tuple[StageId, ...],
    ) -> tuple[dict[StageId, dict[str, Any]], dict[str, dict[str, str]]]:
        payloads: dict[StageId, dict[str, Any]] = {}
        refs: dict[str, dict[str, str]] = {}
        artifact_refs = state.get("artifact_refs") or {}
        for stage_id in stages:
            artifact_id = artifact_refs.get(stage_id)
            if not artifact_id:
                raise ValueError(f"Missing committed {stage_id} Artifact for context compilation")
            record = self.artifacts.read(state["run_id"], artifact_id)
            payloads[stage_id] = record.payload
            refs[stage_id] = {"artifact_id": record.artifact_id, "signature": record.signature}
        return payloads, refs

    def _planning_authority(self) -> HierarchicalPlanningAuthority:
        if self.planning is None:
            raise ValueError("Hierarchical planning authority is not mounted")
        return self.planning

    @staticmethod
    def _planning_version_ref(
        state: NarrativeRunState,
        stage_id: StageId,
    ) -> str:
        version_id = str((state.get("artifact_refs") or {}).get(stage_id) or "")
        if not version_id:
            raise ValueError(f"Missing committed {stage_id} aggregate ref for Context compilation")
        return version_id

    def _resolved_story_state(
        self,
        run_id: str,
        *,
        as_of_chapter: int,
        subject_ids: set[str],
    ) -> dict[str, Any]:
        """Return relevant current state, never a recent-claim authority window."""
        if self.canon is None:
            return {"as_of_chapter": as_of_chapter, "entries": [], "conflicts": []}
        return self.canon.resolved_state(
            run_id,
            as_of_chapter=max(0, as_of_chapter),
            subject_ids=subject_ids,
        ).model_dump(mode="json")

    def _previous_chapter(self, state: NarrativeRunState) -> dict[str, Any] | None:
        number = int(state["active_chapter_number"]) - 1
        if number < 1:
            return None
        chapter_id = f"chapter-{number}"
        version_id = (state.get("chapter_version_refs") or {}).get(chapter_id, "")
        if not version_id:
            raise ValueError("Previous chapter must be accepted before generating the next chapter")
        record = self.chapters.read(state["run_id"], chapter_id, version_id)
        if record.artifact.author_status != "accepted":
            raise ValueError("Previous chapter context must come from an accepted immutable version")
        previous = record.artifact.model_dump(mode="json")
        detail_id = (state.get("artifact_refs") or {}).get("detail")
        if detail_id:
            detail = DetailArtifact.model_validate(self.artifacts.read(state["run_id"], detail_id).payload)
            previous_detail = next((item for item in detail.chapters if item.ref == chapter_id), None)
            if previous_detail is not None:
                previous["handoff"] = previous_detail.handoff
        return previous

    def _recent_chapter_window(
        self,
        state: NarrativeRunState,
        detail: DetailArtifact,
        *,
        window_size: int = 4,
    ) -> dict[str, Any]:
        current_number = int(state.get("active_chapter_number") or 0)
        if current_number <= 1:
            return {"window_size": window_size, "chapters": [], "state_projection": {}}
        start = max(1, current_number - window_size)
        refs = state.get("chapter_version_refs") or {}
        resolved = self._resolved_story_state(
            state["run_id"],
            as_of_chapter=current_number - 1,
            subject_ids=set(),
        )
        entries_by_chapter: dict[int, list[dict[str, Any]]] = {}
        for entry in resolved.get("entries") or []:
            entries_by_chapter.setdefault(int(entry.get("source_chapter") or 0), []).append(
                entry
            )
        chapters: list[dict[str, Any]] = []
        for number in range(start, current_number):
            planned = detail.chapters[number - 1]
            version_id = str(refs.get(planned.ref) or "")
            if not version_id:
                continue
            accepted = self.chapters.read(
                state["run_id"],
                planned.ref,
                version_id,
            ).artifact
            if accepted.author_status != "accepted":
                continue
            chapters.append(
                {
                    "chapter_id": planned.ref,
                    "title": planned.title,
                    "dramatic_job": planned.purpose,
                    "pov": planned.pov,
                    "cast_ids": list(planned.cast_ids),
                    "scene_results": [scene.result for scene in planned.scenes],
                    "handoff": planned.handoff,
                    "accepted_ending": _tail_excerpt(accepted.content, limit=320),
                    "state_changes": entries_by_chapter.get(number, []),
                }
            )
        return {
            "window_size": window_size,
            "chapters": chapters,
            "state_projection": _continuity_state_projection(resolved),
        }

    def _with_revision(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
        material: dict[str, Any],
        refs: dict[str, dict[str, str]],
        *,
        validate_material: bool = True,
    ) -> dict[str, Any]:
        attempt = int((state.get("stage_attempts") or {}).get(stage_id) or 1)
        if attempt > 1:
            direction = str((state.get("stage_revision_directions") or {}).get(stage_id) or "").strip()
            # A failed Provider/contract attempt retries the same frozen input.
            # Only a human redraft decision carries editorial direction; the API
            # and stage-decision validator require that direction before this
            # compiler is reached.
            if direction:
                material["revision_request"] = {"direction": direction}
        if validate_material:
            validate_prompt_material(stage_id, material)
        return {"target": stage_id, "sources": refs, "material": material}


def _project_brief(inputs: dict[str, Any]) -> dict[str, Any]:
    value = inputs.get("project_brief")
    if not isinstance(value, dict):
        raise ValueError("Frozen Run inputs are missing project_brief")
    return dict(value)


def _group_cast_context(
    context: dict[str, Any],
    group_size: int,
) -> list[tuple[str, dict[str, Any]]]:
    material = context["material"]
    refs = list(material["subject_refs"])
    proposals = {
        str(item["demand_key"]): item for item in material["role_demand_proposals"]
    }
    units: list[tuple[str, dict[str, Any]]] = []
    for offset in range(0, len(refs), group_size):
        group_refs = refs[offset : offset + group_size]
        demand_keys = [str(item["demand_key"]) for item in group_refs]
        if any(key not in proposals for key in demand_keys):
            raise ValueError("Cast group references an unknown role demand")
        group_material = {
            **material,
            "subject_refs": group_refs,
            "role_demand_proposals": [proposals[key] for key in demand_keys],
        }
        units.append(
            (
                f"dossier-group-{len(units) + 1}",
                {**context, "material": group_material},
            )
        )
    if not units:
        raise ValueError("Cast requires at least one preallocated subject ref")
    return units


def _volume_contexts(
    context: dict[str, Any],
) -> list[tuple[str, dict[str, Any]]]:
    material = context["material"]
    spine = StorySpineArtifact.model_validate(material["story_spine"])
    boundaries = VolumeBoundaryProposalBatch.model_validate(
        material["volume_boundaries"]
    )
    turns = {turn.id: turn.model_dump(mode="json") for turn in spine.turns}
    proposals = boundaries.proposals
    units: list[tuple[str, dict[str, Any]]] = []
    for index, proposal in enumerate(proposals, start=1):
        unknown = [turn_ref for turn_ref in proposal.turn_refs if turn_ref not in turns]
        if unknown:
            raise ValueError(
                f"Volume boundary references unknown Spine turns: {sorted(unknown)}"
            )
        group_material = {
            "story_brief": material["story_brief"],
            "volume_spine_turns": [turns[turn_ref] for turn_ref in proposal.turn_refs],
            "character_bible_refs": material["character_bible_refs"],
            "volume_boundary": proposal.model_dump(mode="json"),
            "scale_plan": material["scale_plan"],
            "closure_policy": {
                "volume_index": index,
                "volume_total": len(proposals),
                "is_first_volume": index == 1,
                "contains_final_volume": index == len(proposals),
            },
        }
        if "revision_request" in material:
            group_material["revision_request"] = material["revision_request"]
        validate_prompt_material("volumes", group_material)
        units.append(
            (
                f"volume-{index}",
                {**context, "material": group_material},
            )
        )
    if not units:
        raise ValueError("Volumes require at least one validated boundary proposal")
    return units


def _partition_detail_layout_slots(
    slots: list[DetailLayoutChapterProposal],
    capacity: int,
) -> list[list[DetailLayoutChapterProposal]]:
    if capacity < 1:
        raise ValueError("Detail Provider capacity must be positive")
    if not slots:
        raise ValueError("Detail layout must contain at least one chapter slot")
    return [slots[index : index + capacity] for index in range(0, len(slots), capacity)]


def _ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _length_envelope(plan: NarrativeScaleProfile) -> dict[str, Any]:
    return {"word_target_soft": plan.word_target_soft}


def _source_pack(inputs: dict[str, Any]) -> dict[str, Any]:
    strategy = inputs.get("knowledge_strategy")
    if not isinstance(strategy, dict):
        return {}
    ids = [str(item) for item in strategy.get("knowledge_base_doc_ids") or [] if item]
    summary = str(strategy.get("reference_summary") or "").strip()
    return {"document_ids": ids, "adopted_summary": summary} if ids and summary else {}


def _source_observations(inputs: dict[str, Any]) -> dict[str, Any]:
    source_pack = _source_pack(inputs)
    if not source_pack:
        return {}
    return {
        "source_refs": source_pack["document_ids"],
        "adopted_observations": source_pack["adopted_summary"],
    }


def _volume_character_refs(payload: dict[str, Any]) -> list[dict[str, Any]]:
    cast = CharacterBibleArtifact.model_validate(payload)
    return [
        {
            "id": subject.id,
            "kind": subject.kind,
            "function": subject.function,
            "drive": subject.drive,
            "change": subject.change,
            "debut": subject.debut,
        }
        for subject in cast.subjects
    ]


def _detail_dossier_projection(subject: Any) -> dict[str, Any]:
    """Expose only the frozen character facts needed to stage current scenes.

    The full Character Bible contains each subject's book-long `change`. That
    field is authoritative for the cast stage, but it is a future-arc spoiler
    when a Detail segment is still planning an earlier turn. Detail receives
    role identity, motivation, limits, and debut window; the full arc remains
    available to later text context through the committed Cast artifact.
    """
    return {
        "id": subject.id,
        "name": subject.name,
        "kind": subject.kind,
        "function": subject.function,
        "drive": subject.drive,
        "debut": subject.debut,
        "limits": list(subject.limits),
    }


def _scheduled_subject_ids(
    detail: DetailArtifact,
    cast: CharacterBibleArtifact,
    chapter_number: int,
) -> set[str]:
    """Subjects the approved chapter plan already puts on stage by this chapter.

    The character reviewer exists to catch a chapter that features someone the
    plan did not schedule. Debut windows come from the cast stage, which is
    written before any chapter exists, so a subject the author later approved
    into an earlier scene would be reported as an early appearance on every
    chapter. The committed detail outline is the later and more specific
    decision, and a name written into its scenes counts as scheduled even when
    the segment omitted it from cast_ids.
    """
    scheduled: set[str] = set()
    for index, chapter in enumerate(detail.chapters, start=1):
        if index > max(chapter_number, 0):
            break
        scheduled.update(chapter.cast_ids)
        text = _chapter_planning_text(chapter)
        scheduled.update(subject.id for subject in cast.subjects if subject.name in text)
    return scheduled


def _spine_excerpt(payload: dict[str, Any]) -> dict[str, Any]:
    spine = StorySpineArtifact.model_validate(payload)
    return {"ending": spine.ending, "open_questions": spine.open_questions}


def _chapter_subjects(payload: dict[str, Any], chapter: Any) -> list[dict[str, Any]]:
    cast = CharacterBibleArtifact.model_validate(payload)
    refs = set(chapter.cast_ids) | {
        subject.id
        for subject in cast.subjects
        if subject.name in _chapter_planning_text(chapter)
    }
    subjects = [
        subject.model_dump(mode="json") for subject in cast.subjects if subject.id in refs
    ]
    if {subject["id"] for subject in subjects} != refs:
        raise ValueError("Chapter context references an unknown frozen subject")
    return subjects


def _chapter_planning_text(chapter: Any) -> str:
    scenes = " ".join(
        f"{scene.place} {scene.objective} {scene.conflict} {scene.turn} {scene.result}"
        for scene in chapter.scenes
    )
    return f"{chapter.purpose} {scenes} {chapter.handoff}"


def _volume_by_ref(payload: dict[str, Any], volume_ref: str) -> dict[str, Any]:
    architecture = VolumeArchitectureArtifact.model_validate(payload)
    volume = next((item for item in architecture.volumes if item.id == volume_ref), None)
    if volume is None:
        raise ValueError(f"Detail references unknown volume contract: {volume_ref}")
    return volume.model_dump(mode="json")


def _accepted_story_metadata(
    state: NarrativeRunState,
    chapters: ChapterStore,
    brief_payload: dict[str, Any],
) -> dict[str, Any]:
    brief = StoryBriefArtifact.model_validate(brief_payload)
    refs = state.get("chapter_version_refs") or {}
    titles = [
        chapters.read(state["run_id"], chapter_id, version_id).artifact.title
        for chapter_id, version_id in sorted(
            refs.items(), key=lambda item: int(item[0].removeprefix("chapter-"))
        )
    ]
    return {
        "title": brief.title,
        "premise": brief.premise,
        "theme": brief.theme,
        "ending_promise": brief.ending_promise,
        "accepted_chapter_titles": titles,
    }


def _visual_decisions(inputs: dict[str, Any]) -> dict[str, Any]:
    value = inputs.get("visual_decisions")
    return dict(value) if isinstance(value, dict) else {}


def _staged_beats(detail: DetailArtifact, chapter_number: int) -> list[str]:
    """What the previous chapter already put on the page, one line per scene."""
    if chapter_number < 1 or chapter_number > len(detail.chapters):
        return []
    chapter = detail.chapters[chapter_number - 1]
    return [f"{scene.place}：{scene.turn} → {scene.result}" for scene in chapter.scenes]


def _spine_scale_plan(plan: NarrativeScalePlan) -> dict[str, Any]:
    return {
        "turn_target": plan.turn_target,
        "turn_capacity_range": [plan.turn_min, plan.turn_max],
        "milestone_positions": spine_milestone_positions(plan.turn_target),
        "chapter_target": plan.chapter_target,
        "chapter_range": [plan.chapter_min, plan.chapter_max],
        "volume_target": plan.volume_target,
        "volume_range": [plan.volume_min, plan.volume_max],
        "turn_target_source": (
            "user_override" if "turn_target" in plan.user_locked else "editorial_policy"
        ),
    }


def _cast_scale_plan(plan: NarrativeScalePlan) -> dict[str, Any]:
    return {
        "chapter_target": plan.chapter_target,
        "chapter_range": [plan.chapter_min, plan.chapter_max],
        "cast_recommended_range": [
            plan.cast_recommended_min,
            plan.cast_recommended_max,
        ],
        "cast_hard_max": plan.cast_hard_max,
    }


def _volume_scale_plan(
    plan: NarrativeScalePlan,
    volume_candidate_cap: int,
) -> dict[str, Any]:
    return {
        "chapter_target": plan.chapter_target,
        "chapter_range": [plan.chapter_min, plan.chapter_max],
        "volume_target": plan.volume_target,
        "volume_range": [plan.volume_min, plan.volume_max],
        "volume_candidate_cap": volume_candidate_cap,
    }


def _tail_excerpt(content: str, limit: int = _TAIL_EXCERPT_CHARS) -> str:
    """Last paragraphs of accepted prose, bounded and cut on a paragraph edge."""
    text = content.strip()
    if not text:
        return ""
    if len(text) <= limit:
        return text
    tail = text[-limit:]
    boundary = tail.find("\n")
    if 0 <= boundary < limit // 2:
        tail = tail[boundary + 1 :]
    return tail.strip()


def _context_snippet(ref: str, purpose: str, value: Any) -> dict[str, str]:
    text = value if isinstance(value, str) else json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return ContextSnippet(
        ref=ref,
        purpose=purpose,
        text=text,
        source_hash=hashlib.sha256(text.encode("utf-8")).hexdigest(),
    ).model_dump(mode="json")


def _hierarchical_context_packet(
    state: NarrativeRunState,
    target: str,
    context: dict[str, Any],
) -> dict[str, Any]:
    source = dict(context["source"])
    material = {key: value for key, value in context.items() if key != "source"}
    return {
        "target": target,
        "sources": {source["stage_id"]: source},
        "material": material,
        "domain_revision": int(state.get("domain_revision") or 0),
    }


def _context_story_state(state: Any) -> dict[str, Any]:
    """Project durable current state into a bounded prose-context packet.

    Canon remains the complete immutable authority. Evidence also receives
    that complete projection so source ids and conflicts stay auditable. The
    prose prompt needs the smaller, stable slice: unbound claims and one-off
    event labels are not current properties, while duplicate observations of
    the same value do not need to be repeated on every chapter.
    """
    payload = (
        state.model_dump(mode="json")
        if hasattr(state, "model_dump")
        else dict(state)
    )
    entries: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for entry in payload.get("entries", []):
        subject_id = str(entry.get("subject_id") or "")
        property_key = str(entry.get("property_key") or "")
        if property_key in _EPHEMERAL_STATE_PROPERTIES:
            continue
        if subject_id == "story" and property_key.startswith("claim:"):
            continue
        key = (
            subject_id,
            property_key,
            str(entry.get("value") or ""),
            str(entry.get("epistemic_status") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        entries.append(entry)

    conflicts = [
        conflict
        for conflict in payload.get("conflicts", [])
        if conflict.get("property_key") not in _EPHEMERAL_STATE_PROPERTIES
        and not (
            conflict.get("subject_id") == "story"
            and str(conflict.get("property_key") or "").startswith("claim:")
        )
    ]
    projected = {
        "as_of_chapter": payload.get("as_of_chapter"),
        "entries": entries,
        "conflicts": conflicts,
    }
    encoded = json.dumps(projected, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if len(encoded) <= _CONTEXT_STATE_CHAR_BUDGET:
        return projected

    # Keep explicit conflict evidence and the newest durable entries first.
    # This is a prompt-size projection only; the resolver above remains the
    # complete source of truth and is still used by Evidence and review lanes.
    ranked = sorted(
        entries,
        key=lambda item: (
            str(item.get("epistemic_status") or "") in {"reveal", "refutation"},
            int(item.get("source_chapter") or 0),
            str(item.get("source_fact_id") or ""),
        ),
        reverse=True,
    )
    compact: list[dict[str, Any]] = []
    for entry in ranked:
        trial = {
            "as_of_chapter": projected["as_of_chapter"],
            "entries": [*compact, entry],
            "conflicts": conflicts,
        }
        if len(json.dumps(trial, ensure_ascii=False, sort_keys=True, separators=(",", ":"))) > _CONTEXT_STATE_CHAR_BUDGET:
            continue
        compact.append(entry)
    return {
        "as_of_chapter": projected["as_of_chapter"],
        "entries": compact,
        "conflicts": conflicts,
        "omitted_entry_count": len(entries) - len(compact),
    }


def _continuity_state_projection(state: Any) -> dict[str, Any]:
    payload = state.model_dump(mode="json") if hasattr(state, "model_dump") else dict(state)
    categories: dict[str, list[dict[str, Any]]] = {
        "evidence_provenance": [],
        "character_knowledge": [],
        "object_states": [],
        "unresolved_clues": [],
    }
    for entry in payload.get("entries") or []:
        property_key = str(entry.get("property_key") or "").casefold()
        epistemic = str(entry.get("epistemic_status") or "")
        if property_key.startswith("evidence.") and property_key.endswith(
            (".source", ".owner", ".custody")
        ):
            categories["evidence_provenance"].append(entry)
        if property_key.startswith("knowledge."):
            categories["character_knowledge"].append(entry)
        if property_key.startswith("object.") and property_key.endswith(".state"):
            categories["object_states"].append(entry)
        if property_key.startswith("clue.") and property_key.endswith(".status") and epistemic in {
            "rumour",
            "belief",
        }:
            categories["unresolved_clues"].append(entry)
    return {
        **categories,
        "conflicts": list(payload.get("conflicts") or []),
    }


def _manifest_hash(value: dict[str, Any]) -> str:
    unsigned = {key: item for key, item in value.items() if key != "manifest_hash"}
    encoded = json.dumps(unsigned, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _chapter_end(window: str) -> int:
    bounds = window.removeprefix("chapter:").split("-", maxsplit=1)
    return int(bounds[-1])


__all__ = ["DETAIL_BATCH_SIZE", "NarrativeContextCompiler", "PLANNING_INPUTS"]
