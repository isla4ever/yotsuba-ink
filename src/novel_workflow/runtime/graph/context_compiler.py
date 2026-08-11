from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    CharacterBibleArtifact,
    OutlineArtifact,
    StageId,
    StoryBriefArtifact,
    detail_obligation_registry,
)
from novel_workflow.output_contracts.prompt_materials import validate_prompt_material
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.storage.artifact_store import ArtifactStore
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.narrative_run_repository import NarrativeRunRepository


PLANNING_INPUTS: dict[StageId, tuple[StageId, ...]] = {
    "info": (),
    "characters": ("info",),
    "summary": ("info", "characters"),
    "outline": ("info", "characters", "summary"),
    "detail": ("info", "characters", "summary", "outline"),
    "text": ("info", "characters", "summary", "outline", "detail"),
    "cover": ("info", "characters", "summary", "outline", "detail"),
    "export": (),
}

DETAIL_BATCH_SIZE = 8


@dataclass(frozen=True, slots=True)
class NarrativeContextCompiler:
    """Build the only Provider-facing context packets used by the graph runtime."""

    runs: NarrativeRunRepository
    artifacts: ArtifactStore
    chapters: ChapterStore

    def stage(self, state: NarrativeRunState, stage_id: StageId) -> dict[str, Any]:
        if stage_id == "export":
            return {"target": "export", "sources": {}, "material": {}}
        definition = self.runs.definition(state["run_id"])
        book_scale_plan = definition.book_scale_plan.model_dump(mode="json")
        if stage_id == "info":
            material: dict[str, Any] = {
                "project_brief": _project_brief(definition.inputs),
                "book_scale_plan": book_scale_plan,
            }
            source_pack = _source_pack(definition.inputs)
            if source_pack:
                material["source_pack"] = source_pack
            return self._with_revision(state, stage_id, material, {})

        payloads, source_refs = self._planning_material(state, PLANNING_INPUTS[stage_id])
        if stage_id == "cover":
            material = _cover_material(payloads)
        else:
            material = {
                "book_scale_plan": book_scale_plan,
                **{_material_key(source): payloads[source] for source in PLANNING_INPUTS[stage_id]},
            }
            if stage_id == "detail":
                material["obligation_registry"] = detail_obligation_registry(
                    StoryBriefArtifact.model_validate(payloads["info"]),
                    CharacterBibleArtifact.model_validate(payloads["characters"]),
                    OutlineArtifact.model_validate(payloads["outline"]),
                )
        return self._with_revision(state, stage_id, material, source_refs)

    def stage_units(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
    ) -> list[tuple[str, dict[str, Any]]]:
        base = self.stage(state, stage_id)
        definition = self.runs.definition(state["run_id"])
        if stage_id == "outline":
            volumes = definition.book_scale_plan.volumes
            units: list[tuple[str, dict[str, Any]]] = []
            for index, volume in enumerate(volumes, start=1):
                context = deepcopy(base)
                context["material"]["target_volume"] = {
                    "id": f"volume-{index}",
                    "chapter_window": (
                        f"chapter:{volume.chapter_start}-{volume.chapter_end}"
                    ),
                    "scale": volume.model_dump(mode="json"),
                }
                validate_prompt_material("outline", context["material"])
                units.append((f"volume-{index}", context))
            return units
        if stage_id == "detail":
            total = definition.book_scale_plan.total_chapters
            units = []
            for start in range(1, total + 1, DETAIL_BATCH_SIZE):
                end = min(total, start + DETAIL_BATCH_SIZE - 1)
                context = deepcopy(base)
                context["material"]["target_chapters"] = [
                    {"id": f"chapter-{number}", "number": number}
                    for number in range(start, end + 1)
                ]
                context["material"]["outline"] = {
                    "volumes": [
                        volume
                        for volume in base["material"]["outline"]["volumes"]
                        if _windows_overlap(volume["chapter_window"], start, end)
                    ]
                }
                validate_prompt_material("detail", context["material"])
                units.append((f"chapters-{start}-{end}", context))
            return units
        return [("", base)]

    def chapter(self, state: NarrativeRunState) -> dict[str, Any]:
        run_id = state["run_id"]
        definition = self.runs.definition(run_id)
        payloads, source_refs = self._planning_material(
            state,
            PLANNING_INPUTS["text"],
        )
        number = int(state["active_chapter_number"])
        chapter_plan = payloads["detail"]["chapters"][number - 1]
        previous_plan = payloads["detail"]["chapters"][number - 2] if number > 1 else None
        previous_chapter = self._previous_chapter(state)
        material: dict[str, Any] = {
            "book_scale": _chapter_scale(definition.book_scale_plan.model_dump(mode="json")),
            "story_constraints": _story_constraints(payloads["info"]),
            "character_bible": payloads["characters"],
            "summary_commitments": _summary_commitments(payloads["summary"]),
            "volume_plan": _volume_for_chapter(payloads["outline"], number),
            "chapter_plan": chapter_plan,
            "previous_handoff": previous_plan["handoff"] if previous_plan else None,
            "previous_accepted_chapter": previous_chapter,
        }
        attempt = int((state.get("chapter_attempts") or {}).get(state["active_chapter_id"]) or 1)
        if attempt > 1:
            direction = str(
                (state.get("chapter_revision_directions") or {}).get(state["active_chapter_id"])
                or ""
            ).strip()
            if not direction:
                raise ValueError("A repeated chapter generation requires an explicit revision direction")
            source_version = (state.get("chapter_version_refs") or {}).get(
                state["active_chapter_id"], ""
            )
            source = self.chapters.read(run_id, state["active_chapter_id"], source_version)
            material["revision_request"] = {
                "direction": direction,
                "source_chapter": source.artifact.model_dump(mode="json"),
            }
        if previous_chapter:
            source_refs["previous_chapter"] = {
                "version_id": previous_chapter["version_id"],
                "signature": previous_chapter["signature"],
            }
        validate_prompt_material("text", material)
        return {"target": "text", "sources": source_refs, "material": material}

    def review(self, state: NarrativeRunState, role: str) -> dict[str, Any]:
        chapter_context = self.chapter(state)
        material = chapter_context["material"]
        chapter_id = state["active_chapter_id"]
        version_id = (state.get("chapter_version_refs") or {})[chapter_id]
        candidate = self.chapters.read(state["run_id"], chapter_id, version_id)
        shared = {
            "chapter": candidate.artifact.model_dump(mode="json"),
            "chapter_plan": material["chapter_plan"],
        }
        lane_material: dict[str, Any]
        if role == "continuity":
            lane_material = {
                **shared,
                "story_constraints": material["story_constraints"],
                "summary_commitments": material["summary_commitments"],
                "volume_plan": material["volume_plan"],
                "previous_handoff": material["previous_handoff"],
                "previous_accepted_chapter": material["previous_accepted_chapter"],
            }
        elif role == "character":
            lane_material = {
                **shared,
                "character_bible": material["character_bible"],
                "previous_handoff": material["previous_handoff"],
            }
        elif role == "prose":
            lane_material = {
                **shared,
                "voice": material["story_constraints"]["voice"],
                "book_scale": material["book_scale"],
            }
        else:
            raise ValueError(f"Unknown frozen review role: {role}")
        return {
            "target": f"text.review.{role}",
            "sources": {
                **chapter_context["sources"],
                "candidate_chapter": {
                    "version_id": candidate.version_id,
                    "signature": candidate.signature,
                },
            },
            "material": lane_material,
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
            refs[stage_id] = {
                "artifact_id": record.artifact_id,
                "signature": record.signature,
            }
        return payloads, refs

    def _previous_chapter(self, state: NarrativeRunState) -> dict[str, Any] | None:
        previous_number = int(state["active_chapter_number"]) - 1
        if previous_number < 1:
            return None
        chapter_id = f"chapter-{previous_number}"
        version_id = (state.get("chapter_version_refs") or {}).get(chapter_id, "")
        if not version_id:
            raise ValueError("Previous chapter must be accepted before generating the next chapter")
        record = self.chapters.read(state["run_id"], chapter_id, version_id)
        if record.artifact.author_status != "accepted":
            raise ValueError("Previous chapter context must come from an accepted immutable version")
        return {
            **record.artifact.model_dump(mode="json"),
            "signature": record.signature,
        }

    def _with_revision(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
        material: dict[str, Any],
        source_refs: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        attempt = int((state.get("stage_attempts") or {}).get(stage_id) or 1)
        if attempt > 1:
            direction = str(
                (state.get("stage_revision_directions") or {}).get(stage_id) or ""
            ).strip()
            if not direction:
                raise ValueError("A repeated stage generation requires an explicit revision direction")
            candidate_id = (state.get("candidate_artifact_refs") or {}).get(stage_id, "")
            if not candidate_id:
                raise ValueError("A repeated stage generation requires its immutable source Artifact")
            candidate = self.artifacts.read(state["run_id"], candidate_id)
            material["revision_request"] = {
                "direction": direction,
                "source_artifact": candidate.payload,
            }
            source_refs["revision_source"] = {
                "artifact_id": candidate.artifact_id,
                "signature": candidate.signature,
            }
        validate_prompt_material(stage_id, material)
        return {"target": stage_id, "sources": source_refs, "material": material}


def _material_key(stage_id: StageId) -> str:
    return {
        "info": "story_brief",
        "characters": "character_bible",
        "summary": "summary",
        "outline": "outline",
        "detail": "detail",
        "text": "text",
        "cover": "cover",
        "export": "export",
    }[stage_id]


def _project_brief(inputs: dict[str, Any]) -> dict[str, Any]:
    intent = inputs.get("run_intent")
    if isinstance(intent, dict) and isinstance(intent.get("project_brief"), dict):
        return dict(intent["project_brief"])
    return dict(inputs)


def _source_pack(inputs: dict[str, Any]) -> dict[str, Any]:
    intent = inputs.get("run_intent")
    strategy = intent.get("knowledge_strategy") if isinstance(intent, dict) else None
    if not isinstance(strategy, dict):
        return {}
    document_ids = [str(item) for item in strategy.get("knowledge_base_doc_ids") or [] if item]
    summary = str(strategy.get("reference_summary") or "").strip()
    if not document_ids or not summary:
        return {}
    return {"document_ids": document_ids, "adopted_summary": summary}


def _story_constraints(story: dict[str, Any]) -> dict[str, Any]:
    return {
        "premise": story["premise"],
        "world_rules": story["world_rules"],
        "thematic_question": story["thematic_question"],
        "ending_promise": story["ending_promise"],
        "voice": story["voice"],
    }


def _summary_commitments(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "beats": summary["beats"],
        "climax": summary["climax"],
        "resolution": summary["resolution"],
        "character_outcomes": summary["character_outcomes"],
    }


def _chapter_scale(plan: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "chapter_target_chars",
        "chapter_soft_min_chars",
        "chapter_soft_max_chars",
        "chapter_hard_min_chars",
        "chapter_hard_max_chars",
    )
    values = {key: plan[key] for key in keys if key in plan}
    if not values and "total_chapters" in plan:
        values["total_chapters"] = plan["total_chapters"]
    return values


def _volume_for_chapter(outline: dict[str, Any], chapter_number: int) -> dict[str, Any] | None:
    for volume in outline["volumes"]:
        window = str(volume["chapter_window"])
        bounds = window.removeprefix("chapter:").split("-", maxsplit=1)
        try:
            start = int(bounds[0])
            end = int(bounds[-1])
        except ValueError:
            continue
        if start <= chapter_number <= end:
            return volume
    return None


def _cover_material(payloads: dict[StageId, dict[str, Any]]) -> dict[str, Any]:
    detail_chapters = payloads["detail"]["chapters"]
    sample_indexes = sorted({0, len(detail_chapters) // 2, len(detail_chapters) - 1})
    return {
        "story": {
            "title": payloads["info"]["title"],
            **_story_constraints(payloads["info"]),
            "story_promise": payloads["info"]["story_promise"],
        },
        "cast": [
            {
                "id": item["id"],
                "name": item["name"],
                "tier": item["tier"],
                "narrative_function": item["narrative_function"],
            }
            for item in payloads["characters"]["characters"]
            if item["tier"] in {"protagonist", "major"}
        ],
        "narrative_arc": _summary_commitments(payloads["summary"]),
        "volume_objectives": [
            {
                "chapter_window": item["chapter_window"],
                "objective": item["objective"],
                "ending_state": item["ending_state"],
            }
            for item in payloads["outline"]["volumes"]
        ],
        "chapter_motifs": [
            {
                "number": detail_chapters[index]["number"],
                "purpose": detail_chapters[index]["purpose"],
                "locations": [scene["location"] for scene in detail_chapters[index]["scenes"]],
            }
            for index in sample_indexes
        ],
    }


def _windows_overlap(value: str, start: int, end: int) -> bool:
    bounds = value.removeprefix("chapter:").split("-", maxsplit=1)
    window_start = int(bounds[0])
    window_end = int(bounds[-1])
    return window_start <= end and window_end >= start


__all__ = ["DETAIL_BATCH_SIZE", "NarrativeContextCompiler", "PLANNING_INPUTS"]
