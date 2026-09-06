from __future__ import annotations

import hashlib
import heapq
import json
from collections import defaultdict, deque
from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from novel_workflow.workflows.review_policy import (
    OFFICIAL_REVIEW_POLICIES,
    ReviewPolicy,
)
from novel_workflow.workflows.route_specs import (
    ArtifactKind,
    CreationRouteId,
    CreationRouteSpec,
    DeliverableKind,
    ProviderTaskKind,
    RouteStageSpec,
    Unitization,
    WorkbenchKind,
)


PHASE32_ARCHITECTURE_VERSION = "phase32-routes-v1"

_VALID_STAGE_BINDINGS: frozenset[
    tuple[str, ArtifactKind, WorkbenchKind, ProviderTaskKind | None, Unitization]
] = frozenset(
    {
        ("brief", "screenplay_brief", "screenplay_brief", "screenplay_brief", "aggregate"),
        ("brief", "novel_brief", "novel_brief", "novel_brief", "aggregate"),
        ("cast", "character_bible", "cast", "character_bible", "aggregate"),
        ("cast", "character_bible", "cast", "character_bible", "bounded_units"),
        ("beat_board", "beat_board", "beat_board", "beat_board", "aggregate"),
        ("scene_deck", "scene_deck", "scene_deck", "scene_deck", "bounded_units"),
        ("script", "screenplay_draft", "screenplay_editor", "screenplay_draft", "sequential_units"),
        ("story_map", "story_map", "story_map", "story_map", "aggregate"),
        ("section_plan", "section_plan", "section_plan", "section_plan", "bounded_units"),
        ("text", "short_prose_unit", "short_prose_editor", "short_prose_unit", "sequential_units"),
        (
            "book_architecture",
            "book_architecture",
            "book_architecture",
            "book_architecture",
            "bounded_units",
        ),
        ("volumes", "volume_architecture", "volumes", "volume_architecture", "bounded_units"),
        (
            "rolling_detail",
            "detail_plan_index",
            "rolling_detail",
            "rolling_detail",
            "bounded_units",
        ),
        ("text", "chapter", "chapter_editor", "chapter", "sequential_units"),
        ("cover", "cover", "cover_studio", "cover", "aggregate"),
        ("export", "script_delivery", "script_delivery", None, "deterministic"),
        ("export", "book_delivery", "book_delivery", None, "deterministic"),
    }
)


class RouteCompileError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CompiledRouteStage(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    ordinal: int = Field(ge=0)
    stage_id: str
    label: str
    artifact_kind: ArtifactKind
    workbench_kind: WorkbenchKind
    provider_task_kind: ProviderTaskKind | None
    upstream_stage_ids: tuple[str, ...]
    downstream_stage_ids: tuple[str, ...]
    unitization: Unitization
    decision_policy_ref: str
    context_policy_ref: str
    collaboration_enabled: bool


class CompiledRouteManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    architecture_version: Literal["phase32-routes-v1"] = PHASE32_ARCHITECTURE_VERSION
    route_id: CreationRouteId
    route_revision: str
    route_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    deliverable_kind: DeliverableKind
    length_policy_ref: str
    default_review_policy_ref: str
    start_stage_id: str
    terminal_stage_id: Literal["export"]
    stages: tuple[CompiledRouteStage, ...]
    capabilities: tuple[str, ...]
    export_profiles: tuple[str, ...]


class RouteGraphCompiler:
    def __init__(
        self,
        review_policies: Mapping[str, ReviewPolicy] = OFFICIAL_REVIEW_POLICIES,
    ) -> None:
        self._review_policies = review_policies

    def compile(
        self,
        raw: CreationRouteSpec | Mapping[str, Any],
    ) -> CompiledRouteManifest:
        try:
            route = (
                raw
                if isinstance(raw, CreationRouteSpec)
                else CreationRouteSpec.model_validate(raw)
            )
        except ValidationError as exc:
            raise RouteCompileError(
                "route_contract_invalid",
                "Creation route does not satisfy the Phase 32 contract",
            ) from exc

        stages_by_id = {stage.stage_id: stage for stage in route.stages}
        if len(stages_by_id) != len(route.stages):
            raise RouteCompileError("duplicate_stage_id", "Route stage ids must be unique")
        if len(route.capabilities) != len(set(route.capabilities)):
            raise RouteCompileError("duplicate_capability", "Route capabilities must be unique")
        if len(route.export_profiles) != len(set(route.export_profiles)):
            raise RouteCompileError("duplicate_export_profile", "Export profiles must be unique")

        outgoing: dict[str, set[str]] = defaultdict(set)
        incoming_count = {stage_id: 0 for stage_id in stages_by_id}
        for stage in route.stages:
            if len(stage.upstream_stage_ids) != len(set(stage.upstream_stage_ids)):
                raise RouteCompileError(
                    "duplicate_stage_dependency",
                    f"Stage {stage.stage_id} repeats an upstream dependency",
                )
            for upstream_id in stage.upstream_stage_ids:
                if upstream_id not in stages_by_id:
                    raise RouteCompileError(
                        "unknown_stage_dependency",
                        f"Stage {stage.stage_id} depends on unknown stage {upstream_id}",
                    )
                outgoing[upstream_id].add(stage.stage_id)
                incoming_count[stage.stage_id] += 1

        roots = sorted(stage_id for stage_id, count in incoming_count.items() if count == 0)
        if len(roots) != 1:
            raise RouteCompileError(
                "route_start_invalid",
                f"Route must have exactly one start stage; found {len(roots)}",
            )
        terminals = sorted(stage_id for stage_id in stages_by_id if not outgoing[stage_id])
        if terminals != ["export"]:
            raise RouteCompileError(
                "route_terminal_invalid",
                "Route must have exactly one terminal export stage",
            )

        pending = dict(incoming_count)
        queue = roots.copy()
        heapq.heapify(queue)
        ordered_ids: list[str] = []
        while queue:
            stage_id = heapq.heappop(queue)
            ordered_ids.append(stage_id)
            for target_id in sorted(outgoing[stage_id]):
                pending[target_id] -= 1
                if pending[target_id] == 0:
                    heapq.heappush(queue, target_id)
        if len(ordered_ids) != len(stages_by_id):
            raise RouteCompileError("route_cycle", "Creation route graph contains a cycle")

        reachable = self._reachable_stage_ids(roots[0], outgoing)
        if reachable != set(stages_by_id):
            missing = ", ".join(sorted(set(stages_by_id) - reachable))
            raise RouteCompileError(
                "route_stage_unreachable",
                f"Route contains unreachable stages: {missing}",
            )

        for stage in route.stages:
            binding = (
                stage.stage_id,
                stage.artifact_kind,
                stage.workbench_kind,
                stage.provider_task_kind,
                stage.unitization,
            )
            if binding not in _VALID_STAGE_BINDINGS:
                raise RouteCompileError(
                    "stage_binding_invalid",
                    f"Stage {stage.stage_id} has an incompatible Artifact, "
                    "workbench, Provider task, or unitization",
                )
            if (
                stage.provider_task_kind == "character_bible"
                and not stage.context_policy_ref.endswith(".cast.v2")
            ):
                raise RouteCompileError(
                    "cast_context_policy_invalid",
                    "New Character Bible stages must use the Cast v2 epistemic context",
                )

        self._validate_review_policy(route, stages_by_id)
        compiled_stages = tuple(
            CompiledRouteStage(
                ordinal=index,
                **{
                    **stages_by_id[stage_id].model_dump(),
                    "upstream_stage_ids": tuple(
                        sorted(stages_by_id[stage_id].upstream_stage_ids)
                    ),
                    "downstream_stage_ids": tuple(sorted(outgoing[stage_id])),
                },
            )
            for index, stage_id in enumerate(ordered_ids)
        )
        return CompiledRouteManifest(
            route_id=route.route_id,
            route_revision=route.revision,
            route_digest=_route_digest(route),
            deliverable_kind=route.deliverable_kind,
            length_policy_ref=route.length_policy_ref,
            default_review_policy_ref=route.default_review_policy_ref,
            start_stage_id=roots[0],
            terminal_stage_id="export",
            stages=compiled_stages,
            capabilities=tuple(sorted(route.capabilities)),
            export_profiles=tuple(sorted(route.export_profiles)),
        )

    @staticmethod
    def _reachable_stage_ids(
        start_stage_id: str,
        outgoing: Mapping[str, set[str]],
    ) -> set[str]:
        reachable: set[str] = set()
        queue = deque([start_stage_id])
        while queue:
            stage_id = queue.popleft()
            if stage_id in reachable:
                continue
            reachable.add(stage_id)
            queue.extend(sorted(outgoing[stage_id]))
        return reachable

    def _validate_review_policy(
        self,
        route: CreationRouteSpec,
        stages_by_id: Mapping[str, RouteStageSpec],
    ) -> None:
        policy = self._review_policies.get(route.default_review_policy_ref)
        if policy is None:
            raise RouteCompileError(
                "review_policy_unknown",
                f"Unknown default ReviewPolicy: {route.default_review_policy_ref}",
            )
        if policy.route_id != route.route_id:
            raise RouteCompileError(
                "review_policy_route_mismatch",
                "Default ReviewPolicy belongs to a different creation route",
            )
        referenced_stage_ids = (
            set(policy.auto_continue_stages)
            | set(policy.mandatory_decision_stages)
            | set(policy.directed_redraft_limit_by_stage)
        )
        unknown = referenced_stage_ids - set(stages_by_id)
        if unknown:
            raise RouteCompileError(
                "review_policy_stage_unknown",
                "ReviewPolicy references unknown stages: " + ", ".join(sorted(unknown)),
            )
        invalid_redraft_stages = {
            stage_id
            for stage_id in policy.directed_redraft_limit_by_stage
            if stages_by_id[stage_id].provider_task_kind is None
        }
        if invalid_redraft_stages:
            raise RouteCompileError(
                "review_policy_redraft_invalid",
                "Directed redraft requires a Provider stage: "
                + ", ".join(sorted(invalid_redraft_stages)),
            )


def _route_digest(route: CreationRouteSpec) -> str:
    payload = route.model_dump(mode="json")
    payload["capabilities"] = sorted(payload["capabilities"])
    payload["export_profiles"] = sorted(payload["export_profiles"])
    payload["stages"] = sorted(payload["stages"], key=lambda stage: stage["stage_id"])
    for stage in payload["stages"]:
        stage["upstream_stage_ids"] = sorted(stage["upstream_stage_ids"])
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def compile_official_routes() -> tuple[CompiledRouteManifest, ...]:
    from novel_workflow.workflows.route_specs import official_creation_routes

    compiler = RouteGraphCompiler()
    return tuple(compiler.compile(route) for route in official_creation_routes())


__all__ = [
    "CompiledRouteManifest",
    "CompiledRouteStage",
    "PHASE32_ARCHITECTURE_VERSION",
    "RouteCompileError",
    "RouteGraphCompiler",
    "compile_official_routes",
]
