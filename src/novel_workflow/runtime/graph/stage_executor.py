from __future__ import annotations

import asyncio
import json
import math
from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    ChapterArtifact,
    CharacterBibleArtifact,
    CharacterDossierBatch,
    CharacterRelation,
    CharacterRelationBatch,
    CharacterSubject,
    CoverArtifact,
    CoverBrief,
    DetailArtifact,
    DetailChapter,
    DetailLayoutProposalBatch,
    DetailLayoutVolumeProposal,
    DetailSegmentArtifact,
    ExportArtifact,
    ExportMetadata,
    ExportVolume,
    LengthEnvelope,
    VolumeArchitectureArtifact,
    StoryBriefArtifact,
    RoleDemandProposalBatch,
    SpineTurn,
    StorySpineDraftArtifact,
    VolumeArchitectureDraftArtifact,
    VolumeArchitectureUnitArtifact,
    VolumeBoundaryProposalBatch,
    StorySpineArtifact,
    StageId,
    VolumeContract,
    validate_artifact_vnext,
    validate_character_dossier_modes,
    validate_detail_scene_quality,
)
from novel_workflow.output_contracts.prompt_materials import (
    DetailEstablishedChapter,
    DetailSegmentHandoff,
)
from novel_workflow.output_contracts.provider_tasks import (
    CastDossierSemanticReviewResult,
    RoleDemandSemanticReviewResult,
    SpineSemanticReviewResult,
)
from novel_workflow.runtime.graph.provider_gateway import (
    CoverImageRequest,
    NarrativeProviderGateway,
    ProposalGenerationRequest,
    ProviderOperationError,
    StageGenerationRequest,
    compile_provider_input,
)
from novel_workflow.runtime.graph.context_compiler import NarrativeContextCompiler
from novel_workflow.quality.narrative_contracts import build_cast_identity_findings
from novel_workflow.runtime.graph.detail_preflight import (
    build_detail_preflight,
    require_detail_preflight,
)
from novel_workflow.runtime.graph.detail_planning import (
    DetailLayoutTurnWindow,
    bind_detail_artifact,
    detail_layout_turn_windows,
    validate_detail_layout_proposal,
    validate_detail_layout_turn_window_proposal,
)
from novel_workflow.runtime.graph.output_budget import (
    OutputBudgetPlanner,
    spine_turn_plan,
)
from novel_workflow.runtime.graph.planning_authority import HierarchicalPlanningAuthority
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.runtime.graph.spine_preflight import (
    build_spine_repair_material,
    deterministic_spine_resolution_findings,
)
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.usage import normalize_provider_usage
from novel_workflow.storage.artifact_store import ArtifactRecord, ArtifactStore
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.cover_asset_store import CoverAssetRecord, CoverAssetStore
from novel_workflow.storage.context_manifest_store import ContextManifestStore
from novel_workflow.storage.event_projection import EventProjection
from novel_workflow.storage.evidence_store import EvidenceStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.domain_outbox import DomainOutbox
from novel_workflow.storage.narrative_run_repository import NarrativeRunRepository, ProviderBinding
from novel_workflow.storage.operation_store import OperationStore
from novel_workflow.workflows.narrative_scale import (
    DetailScaleProjection,
    NarrativeScaleProfile,
    plan_narrative_scale,
    project_turn_chapter_window,
    spine_milestone_positions,
)


class StageArtifactValidationError(ValueError):
    def __init__(self, operation_key: str, error: Exception) -> None:
        super().__init__(str(error))
        self.operation_key = operation_key


# Cover image calls hit a second network path (gateway plus asset download), so a
# single transient blip must not kill an otherwise finished run.
_COVER_NETWORK_ATTEMPTS = 3

# Transport retries reuse one frozen input, operation key, and pending receipt.
_STAGE_NETWORK_ATTEMPTS = 3

# A semantic preflight is diagnostic evidence. Deterministic Artifact contracts
# remain the blocking boundary; an LLM review must not turn a low-confidence
# editorial finding into an automatic rewrite loop.
_SPINE_SEMANTIC_REPAIR_LIMIT = {"fast": 1, "balanced": 2, "deep": 2}

_TRANSIENT_NETWORK_CODES = {"network_error", "timeout", "asset_dns_failed"}


def _is_transient_network_error(error: BaseException) -> bool:
    depth = 0
    current: BaseException | None = error
    while current is not None and depth < 8:
        if isinstance(current, ProviderResponseError):
            return current.code in _TRANSIENT_NETWORK_CODES
        current = current.__cause__
        depth += 1
    return False


def proposal_operation_key(
    state: NarrativeRunState,
    *,
    proposal_type: str,
    binding_stage: StageId,
    scope_ref: str = "",
) -> str:
    attempt = int((state.get("stage_attempts") or {}).get(binding_stage) or 1)
    base = f"{state['run_id']}:{proposal_type}:proposal:{attempt}"
    return f"{base}:{scope_ref}" if scope_ref else base


def _validate_role_demand_plan(
    batch: RoleDemandProposalBatch,
    spine: StorySpineArtifact,
    *,
    recommended_min: int,
    hard_max: int,
) -> None:
    turn_ids = {turn.id for turn in spine.turns}
    unknown = {
        turn_ref
        for proposal in batch.proposals
        for turn_ref in proposal.active_turn_refs
        if turn_ref not in turn_ids
    }
    if unknown:
        raise ValueError(f"Role demand proposal references unknown spine turns: {sorted(unknown)}")
    if hard_max < 1:
        raise ValueError("Role demand proposal is missing the frozen cast hard capacity")
    if recommended_min < 1 or recommended_min > hard_max:
        raise ValueError("Role demand proposal has an invalid frozen cast minimum")
    # The lower bound is editorial capacity guidance, not a roster quota. A
    # short but causally complete story may need fewer recurring subjects; v1
    # must not invent people just to satisfy a scale heuristic.
    if len(batch.proposals) > hard_max:
        raise ValueError(
            f"Role demand proposal returned {len(batch.proposals)} subjects; "
            f"the frozen book scale allows at most {hard_max}"
        )
    protagonist_candidates = [
        proposal
        for proposal in batch.proposals
        if proposal.narrative_role == "protagonist"
    ]
    if len(protagonist_candidates) != 1:
        raise ValueError(
            "Role demand proposal must contain exactly one protagonist demand"
        )
    protagonist = protagonist_candidates[0]
    required_protagonist_turns = {spine.turns[0].id, spine.turns[-1].id}
    if not required_protagonist_turns.issubset(protagonist.active_turn_refs):
        raise ValueError(
            "The protagonist role demand must cite the opening and final Spine turns"
        )
    if len(spine.turns) >= 12:
        underdeveloped_recurring_roles = [
            proposal.demand_key
            for proposal in batch.proposals
            if proposal.narrative_role in {"opposition", "relationship", "historical_record"}
            # A single-turn relationship bridge (for example, a witness who
            # warns the protagonist and leaves one actionable lead) is not a
            # recurring role. It still participates in relationship-turn
            # coverage below, but must not force the Provider to invent a
            # second appearance.
            and not (
                proposal.narrative_role == "relationship"
                and len(proposal.active_turn_refs) == 1
            )
            and len(proposal.active_turn_refs) < 2
        ]
        if underdeveloped_recurring_roles:
            raise ValueError(
                "Long-form opposition, relationship, and historical demands must span at least two Spine turns; "
                f"underdeveloped demands: {sorted(underdeveloped_recurring_roles)}"
            )
    relationship_turns = _relationship_turn_ids(spine)
    misaligned_relationship_demands = [
        proposal.demand_key
        for proposal in batch.proposals
        if proposal.narrative_role == "relationship"
        and not relationship_turns.intersection(proposal.active_turn_refs)
    ]
    if misaligned_relationship_demands:
        raise ValueError(
            "Every relationship role demand must cite at least one relationship Spine turn: "
            f"{sorted(misaligned_relationship_demands)}"
        )
    # Exact turn-by-turn relationship coverage is advisory. A recurring wife,
    # daughter, colleague, or witness may already carry the relationship line
    # even when the proposal omits one later aftermath ref. Blocking here made
    # an evidence-labeling gap look like a missing character and caused bounded
    # repairs to invent extra people. Cast still has to connect every returned
    # non-protagonist relationship carrier below.


def _validate_cast_relationship_coverage(
    subjects: list[CharacterSubject],
    relations: list[CharacterRelation],
    demands: RoleDemandProposalBatch,
    spine: StorySpineArtifact,
) -> None:
    """Keep relationship turns executable in the frozen Character Bible.

    Role Demand proves that a relationship turn needs another subject. This
    second gate proves the Cast relation projection actually connects those
    subjects before Volumes or Detail can consume the graph.
    """

    if len(spine.turns) < 6:
        return
    relationship_turns = _relationship_turn_ids(spine)
    if not relationship_turns:
        return
    demand_by_key = {item.demand_key: item for item in demands.proposals}
    subject_by_demand = {
        demand_ref: subject
        for subject in subjects
        for demand_ref in subject.demand_refs
    }
    protagonist = next(
        (
            subject
            for subject in subjects
            if any(
                demand_by_key[ref].narrative_role == "protagonist"
                for ref in subject.demand_refs
                if ref in demand_by_key
            )
        ),
        None,
    )
    required_subjects = {
        subject_by_demand[ref].id
        for demand in demands.proposals
        if demand.narrative_role != "protagonist"
        and relationship_turns.intersection(demand.active_turn_refs)
        for ref in [demand.demand_key]
        if ref in subject_by_demand
    }
    if not required_subjects or protagonist is None:
        return
    linked: set[str] = set()
    for relation in relations:
        linked.update((relation.a, relation.b))
    missing = sorted(required_subjects - linked)
    if missing:
        raise ValueError(
            "Cast relation graph must connect every non-protagonist subject carrying "
            f"a relationship turn; missing subjects: {missing}"
        )
    protagonist_links = {
        relation.b if relation.a == protagonist.id else relation.a
        for relation in relations
        if protagonist.id in {relation.a, relation.b}
    }
    if not protagonist_links.intersection(required_subjects):
        raise ValueError(
            "Cast relation graph must connect the protagonist to a subject carrying a relationship turn"
        )


_RELATIONSHIP_PRESSURE_TERMS = (
    "关系", "亲情", "父子关系", "母女关系", "夫妻关系", "同事关系", "朋友关系",
    "信任", "背叛", "和解", "决裂", "疏离", "拒绝原谅", "共同承担",
)


def _relationship_turn_ids(spine: StorySpineArtifact) -> set[str]:
    """Include turns whose prose explicitly carries relationship pressure."""
    return {
        turn.id
        for turn in spine.turns
        if turn.progress_type == "relationship"
        or any(term in f"{turn.cause}{turn.change}" for term in _RELATIONSHIP_PRESSURE_TERMS)
    }


@dataclass(frozen=True, slots=True)
class StageExecutor:
    runs: NarrativeRunRepository
    artifacts: ArtifactStore
    planning: HierarchicalPlanningAuthority
    chapters: ChapterStore
    operations: OperationStore
    events: EventProjection
    evidence: EvidenceStore
    exports: ExportStore
    cover_assets: CoverAssetStore
    context_manifests: ContextManifestStore
    outbox: DomainOutbox
    provider: NarrativeProviderGateway

    async def generate_candidate(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
    ) -> ArtifactRecord:
        run_id = state["run_id"]
        attempt = int((state.get("stage_attempts") or {}).get(stage_id) or 1)
        operation_key = f"{run_id}:{stage_id}:generate:{attempt}"
        if stage_id == "export":
            payload = self._build_export(state)
            candidate = self.artifacts.save_candidate(
                run_id,
                stage_id,
                payload,
                source=f"deterministic:{operation_key}",
                **self._validation_refs(state, stage_id),
            )
        else:
            definition = self.runs.definition(run_id)
            binding = definition.provider_bindings.get(stage_id)
            if binding is None:
                raise ProviderOperationError(f"No frozen Provider binding for stage {stage_id}")
            unit_payloads: list[tuple[str, dict[str, Any]]] = []
            last_operation_key = operation_key
            try:
                previous_segment_handoff: DetailSegmentHandoff | None = None
                previous_volume_handoff: dict[str, Any] | None = None
                detail_chapter_count = 0
                completed_detail_turn_refs: list[str] = []
                established_detail_chapters: list[DetailEstablishedChapter] = []
                taken_cast_names: list[str] = []
                taken_volume_titles: list[str] = []
                taken_chapter_titles: list[str] = []
                detail_layout: DetailLayoutProposalBatch | None = None
                if stage_id == "detail":
                    layout_keys = self.detail_layout_operation_keys(state)
                    if layout_keys:
                        last_operation_key = layout_keys[0]
                    detail_layout = await self.generate_detail_layout_proposal(state)
                stage_units = self.context_compiler().stage_units(
                    state,
                    stage_id,
                    detail_layout=detail_layout,
                )
                for unit_index, (unit_id, context) in enumerate(stage_units):
                    if stage_id == "detail" and previous_segment_handoff is not None:
                        context["material"]["previous_segment_handoff"] = (
                            previous_segment_handoff.model_dump(mode="json")
                        )
                        # Chapter counts are deterministic; carrying the actual
                        # count here also makes replay reject a corrupted segment.
                        context["material"]["scale_projection"] = {
                            **context["material"]["scale_projection"],
                            "chapter_number_start": detail_chapter_count + 1,
                        }
                    if stage_id == "cast" and taken_cast_names:
                        # Dossier groups run sequentially and cannot see each
                        # other; without this, later groups reinvent the same
                        # character names and the merged bible fails validation.
                        context["material"]["reserved_names"] = list(taken_cast_names)
                    if stage_id == "volumes" and taken_volume_titles:
                        context["material"]["reserved_titles"] = list(taken_volume_titles)
                    if stage_id == "volumes" and previous_volume_handoff is not None:
                        context["material"]["previous_volume_handoff"] = previous_volume_handoff
                    if stage_id == "detail" and taken_chapter_titles:
                        context["material"]["reserved_titles"] = list(taken_chapter_titles)
                    planner = self.output_budget_planner(state)
                    budget = planner.for_stage(stage_id, binding, context)
                    context = planner.attach(context, budget)
                    unit_operation_key = f"{operation_key}:{unit_id}" if unit_id else operation_key
                    last_operation_key = unit_operation_key
                    payload = await self._generate_stage_unit(
                        run_id=run_id,
                        stage_id=stage_id,
                        attempt=attempt,
                        operation_key=unit_operation_key,
                        binding=budget.bind(binding),
                        context=context,
                        unit_id=unit_id,
                    )
                    if stage_id == "cast":
                        payload, last_operation_key = await self._preflight_cast_dossier_unit(
                            state,
                            payload,
                            binding=binding,
                            provider_context=context,
                            generation_operation_key=unit_operation_key,
                            unit_id=unit_id,
                            attempt=attempt,
                        )
                    unit_payloads.append((unit_id, payload))
                    if stage_id == "cast":
                        taken_cast_names.extend(
                            name
                            for item in (payload.get("subjects") or [])
                            if (name := str(item.get("name") or "").strip())
                        )
                    if stage_id == "volumes":
                        generated_volume = VolumeArchitectureUnitArtifact.model_validate(
                            payload
                        ).volumes[0]
                        taken_volume_titles.append(generated_volume.title)
                        previous_volume_handoff = {
                            "title": generated_volume.title,
                            "closure": generated_volume.closure,
                        }
                    if stage_id == "detail":
                        segment_chapter_start = detail_chapter_count + 1
                        volume_ref = unit_id.split(".segment-", maxsplit=1)[0]
                        segment_chapters = [
                            DetailChapter.model_validate(
                                {
                                    "ref": f"chapter-{segment_chapter_start + offset}",
                                    "volume_ref": volume_ref,
                                    **chapter,
                                }
                            )
                            for offset, chapter in enumerate(payload["chapters"])
                        ]
                        reused_titles = _detail_reused_titles(
                            [item.title for item in segment_chapters],
                            taken_chapter_titles,
                        )
                        if reused_titles:
                            self.events.append(
                                run_id,
                                event_id=f"{unit_operation_key}:title-reuse-warning",
                                type="quality.warning",
                                stage_id="detail",
                                node_id="detail.generate_candidate",
                                status="warning",
                                payload={
                                    "code": "detail_title_reused",
                                    "titles": reused_titles,
                                    "unit_id": unit_id,
                                },
                                payload_ref=unit_operation_key,
                            )
                        taken_chapter_titles.extend(
                            item.title for item in segment_chapters
                        )
                        last = segment_chapters[-1]
                        detail_chapter_count += len(segment_chapters)
                        established_detail_chapters.extend(
                            DetailEstablishedChapter(
                                chapter_ref=f"chapter-{segment_chapter_start + offset}",
                                title=chapter.title,
                                turn_refs=list(chapter.turn_refs),
                                purpose=chapter.purpose,
                                final_result=chapter.scenes[-1].result,
                            )
                            for offset, chapter in enumerate(segment_chapters)
                        )
                        for turn_ref in (
                            turn_ref
                            for chapter in segment_chapters
                            for turn_ref in chapter.turn_refs
                        ):
                            if turn_ref not in completed_detail_turn_refs:
                                completed_detail_turn_refs.append(turn_ref)
                        if unit_index + 1 < len(stage_units):
                            previous_segment_handoff = DetailSegmentHandoff(
                                previous_ref=f"chapter-{detail_chapter_count}",
                                completed_turn_refs=completed_detail_turn_refs,
                                established_chapters=list(established_detail_chapters),
                                unresolved=[last.handoff],
                                next_ref=stage_units[unit_index + 1][0],
                            )
                payload = _aggregate_stage_units(stage_id, unit_payloads)
                if stage_id == "brief":
                    payload = _bind_story_brief(payload, definition.scale_profile)
                if stage_id == "spine":
                    payload = _bind_story_spine(payload)
                    payload, last_operation_key = await self._preflight_spine_candidate(
                        state,
                        payload,
                        binding=binding,
                        provider_context=context,
                        generation_operation_key=operation_key,
                        attempt=attempt,
                    )
                if stage_id == "cast":
                    payload = await self._assemble_character_bible(
                        state,
                        payload,
                    )
                if stage_id == "volumes":
                    payload = _bind_volume_architecture(state, payload)
                if stage_id == "detail":
                    if detail_layout is None:
                        raise ValueError("Detail binding requires its frozen layout proposal")
                    payload = bind_detail_artifact(
                        payload,
                        definition.scale_profile,
                        detail_layout,
                    )
                if stage_id == "cover":
                    brief = CoverBrief.model_validate(payload)
                    include_image = definition.export_preferences.include_cover_image
                    assets = (
                        await self._generate_cover_assets(state, brief)
                        if include_image
                        else []
                    )
                    payload = CoverArtifact(
                        brief=brief,
                        selected_asset_id=(
                            assets[0].asset_id
                            if include_image and definition.quality_mode == "fast"
                            else ""
                        ),
                    ).model_dump(mode="json")

                kwargs = self._validation_refs(state, stage_id)
                candidate = self.artifacts.save_candidate(
                    run_id,
                    stage_id,
                    payload,
                    source=f"provider:{last_operation_key if stage_id == 'spine' else operation_key}",
                    **kwargs,
                )
            except (ProviderOperationError, StageArtifactValidationError):
                raise
            except Exception as exc:
                raise StageArtifactValidationError(last_operation_key, exc) from exc
        self.events.append(
            run_id,
            event_id=f"{operation_key}:candidate",
            type="artifact.candidate_ready",
            stage_id=stage_id,
            node_id=f"{stage_id}.generate_candidate",
            payload_ref=candidate.artifact_id,
        )
        return candidate

    async def _preflight_spine_candidate(
        self,
        state: NarrativeRunState,
        payload: dict[str, Any],
        *,
        binding: ProviderBinding,
        provider_context: dict[str, Any],
        generation_operation_key: str,
        attempt: int,
    ) -> tuple[dict[str, Any], str]:
        definition = self.runs.definition(state["run_id"])
        repair_limit = _SPINE_SEMANTIC_REPAIR_LIMIT[definition.quality_mode]
        current = payload
        source_operation_key = generation_operation_key
        review_scope = "initial"
        repair_failures: list[str] = []
        last_findings: list[Any] = []

        for repair_index in range(0, repair_limit + 1):
            review, review_operation_key = await self._review_spine_candidate(
                state,
                current,
                provider_context=provider_context,
                scope_ref=review_scope,
            )
            deterministic_findings = deterministic_spine_resolution_findings(current)
            if deterministic_findings:
                existing = {
                    (item.code, tuple(item.turn_refs)) for item in review.findings
                }
                findings = list(review.findings)
                findings.extend(
                    item
                    for item in deterministic_findings
                    if (item.code, tuple(item.turn_refs)) not in existing
                )
                review = SpineSemanticReviewResult(
                    verdict="revise",
                    findings=findings[:5],
                )
            # The LLM review remains an evidence receipt. Only the
            # deterministic resolver can block this candidate semantically.
            blocking_findings = list(deterministic_findings)
            if repair_failures and not blocking_findings:
                blocking_findings = list(last_findings)
            if not blocking_findings:
                return current, source_operation_key
            if repair_index >= repair_limit:
                summary = "; ".join(
                    f"{finding.code}({','.join(finding.turn_refs)}): {finding.claim}"
                    for finding in blocking_findings
                )
                raise StageArtifactValidationError(
                    review_operation_key,
                    ValueError(f"Spine semantic preflight still has blocking findings: {summary}"),
                )

            last_findings = list(blocking_findings)

            repair_context = {
                    **provider_context,
                    "material": build_spine_repair_material(
                        dict(provider_context["material"]),
                        current,
                        blocking_findings,
                    ),
            }
            if repair_failures:
                revision = repair_context["material"].setdefault(
                    "revision_request", {"direction": ""}
                )
                revision["direction"] = (
                    f"{revision.get('direction', '').strip()}\n"
                    "此前私有修复曾触发结构合同错误："
                    f"{'；'.join(repair_failures)}。"
                    "本次必须先静默核对每三项推进类型、锚点和因果交接，再输出完整 turns。"
                ).strip()
            planner = self.output_budget_planner(state)
            budget = planner.for_stage("spine", binding, repair_context)
            repair_context = planner.attach(repair_context, budget)
            source_operation_key = (
                f"{generation_operation_key}:semantic-repair-{repair_index + 1}"
            )
            try:
                repaired = await self._generate_stage_unit(
                    run_id=state["run_id"],
                    stage_id="spine",
                    attempt=attempt,
                    operation_key=source_operation_key,
                    binding=budget.bind(binding),
                    context=repair_context,
                    unit_id="",
                )
            except ProviderOperationError as exc:
                # A private semantic repair may return a JSON object that still
                # violates the frozen Spine contract. Keep that response
                # private and spend the next bounded repair slot. Transport,
                # auth, balance, and configuration failures must still stop the
                # Run immediately; they are not content defects to hide.
                cause = exc.__cause__
                if not isinstance(cause, ValueError):
                    raise
                repair_failures.append(str(exc))
                if repair_index >= repair_limit:
                    raise
                review_scope = f"repair-{repair_index}-contract-failure"
                continue
            current = _bind_story_spine(repaired)
            repair_failures.clear()
            review_scope = f"repair-{repair_index + 1}"

        raise AssertionError("Spine semantic preflight exhausted without a verdict")

    async def _review_spine_candidate(
        self,
        state: NarrativeRunState,
        payload: dict[str, Any],
        *,
        provider_context: dict[str, Any],
        scope_ref: str,
    ) -> tuple[SpineSemanticReviewResult, str]:
        material = provider_context.get("material")
        if not isinstance(material, dict) or not isinstance(material.get("story_brief"), dict):
            raise ValueError("Spine semantic preflight requires the frozen Story Brief")
        review_context = {
            "target": "spine.semantic_review",
            "sources": dict(provider_context.get("sources") or {}),
            "material": {
                "story_brief": material["story_brief"],
                "story_spine": payload,
            },
        }
        result = await self._generate_proposal(
            state,
            proposal_type="spine_review",
            binding_stage="spine",
            context=review_context,
            scope_ref=scope_ref,
        )
        review = SpineSemanticReviewResult.model_validate(result)
        known_turns = {str(turn["id"]) for turn in payload.get("turns") or []}
        unknown = {
            turn_ref
            for finding in review.findings
            for turn_ref in finding.turn_refs
            if turn_ref not in known_turns
        }
        if unknown:
            raise ValueError(
                f"Spine semantic review references unknown turns: {sorted(unknown)}"
            )
        return review, proposal_operation_key(
            state,
            proposal_type="spine_review",
            binding_stage="spine",
            scope_ref=scope_ref,
        )

    async def generate_role_demand_proposal(
        self,
        state: NarrativeRunState,
    ) -> dict[str, Any]:
        base_context = self.context_compiler().stage(state, "cast")
        pending_operation_refs: list[str] = []
        spine = StorySpineArtifact.model_validate(base_context["material"]["story_spine"])
        repair_error: ValueError | None = None
        batch: RoleDemandProposalBatch | None = None
        for scope_ref in ("", "contract-repair-1"):
            context = base_context
            if repair_error is not None:
                context = {
                    **base_context,
                    "material": {
                        **base_context["material"],
                        "revision_request": {
                            "direction": (
                                "上一份 Role Demand 候选未通过冻结合同："
                                f"{repair_error}。请返回完整替代候选；每个 relationship demand 必须引用至少一个 relationship Spine turn，"
                                "长篇 opposition/relationship/historical_record demand 必须跨至少两个 turn；不得凑人、改写 Spine 或新增职责。"
                            )
                        },
                    },
                }
            try:
                result = await self._generate_proposal(
                    state,
                    proposal_type="role_demand",
                    binding_stage="cast",
                    context=context,
                    scope_ref=scope_ref,
                )
            except ProviderOperationError as exc:
                # The gateway has already persisted this Provider receipt. A
                # parsed object that fails the frozen proposal schema gets one
                # private replacement request; operational failures remain
                # terminal and are never hidden as content repair.
                if (
                    scope_ref
                    or exc.diagnostic.get("code") != "structured_contract_invalid"
                ):
                    raise
                repair_error = ValueError(str(exc))
                continue
            generation_key = proposal_operation_key(
                state,
                proposal_type="role_demand",
                binding_stage="cast",
                scope_ref=scope_ref,
            )
            pending_operation_refs.append(generation_key)
            try:
                candidate = RoleDemandProposalBatch.model_validate(result)
                self._validate_role_demand_batch(candidate, spine, context)
            except (KeyError, TypeError, ValueError) as exc:
                if scope_ref:
                    raise ValueError("Role demand proposal failed its bounded contract repair") from exc
                repair_error = exc if isinstance(exc, ValueError) else ValueError(str(exc))
                continue
            batch = candidate
            break
        if batch is None:
            raise ValueError("Role demand proposal context or payload is invalid")
        # Keep the reviewer receipt for evidence, but do not let an advisory
        # mergeability or agency finding trigger a hidden regeneration.
        _, review_key = await self._review_role_demand_candidate(
            state,
            batch,
            provider_context=base_context,
            scope_ref="initial",
        )
        pending_operation_refs.append(review_key)

        subject_refs = [
            {
                "id": f"subject-{index}",
                "demand_key": proposal.demand_key,
                "subject_mode": proposal.subject_mode,
                "narrative_role": proposal.narrative_role,
            }
            for index, proposal in enumerate(batch.proposals, start=1)
        ]
        return {
            "role_demand_proposals": [item.model_dump(mode="json") for item in batch.proposals],
            "subject_refs": subject_refs,
            "pending_operation_refs": pending_operation_refs,
        }

    def _validate_role_demand_batch(
        self,
        batch: RoleDemandProposalBatch,
        spine: StorySpineArtifact,
        context: dict[str, Any],
    ) -> None:
        scale_plan = context["material"].get("scale_plan")
        recommended = (
            scale_plan.get("cast_recommended_range")
            if isinstance(scale_plan, dict)
            else None
        )
        hard_max = scale_plan.get("cast_hard_max") if isinstance(scale_plan, dict) else None
        if (
            not isinstance(recommended, list)
            or len(recommended) != 2
            or not all(isinstance(value, int) for value in recommended)
            or not isinstance(hard_max, int)
            or hard_max < 1
        ):
            raise ValueError("Role demand proposal is missing the frozen cast capacity")
        _validate_role_demand_plan(
            batch,
            spine,
            recommended_min=recommended[0],
            hard_max=hard_max,
        )

    async def _review_role_demand_candidate(
        self,
        state: NarrativeRunState,
        batch: RoleDemandProposalBatch,
        *,
        provider_context: dict[str, Any],
        scope_ref: str,
    ) -> tuple[RoleDemandSemanticReviewResult, str]:
        material = provider_context.get("material")
        if not isinstance(material, dict):
            raise ValueError("Role Demand semantic preflight requires frozen planning material")
        review_context = {
            "target": "cast.role_demand.semantic_review",
            "sources": dict(provider_context.get("sources") or {}),
            "material": {
                "story_brief": material.get("story_brief"),
                "story_spine": material.get("story_spine"),
                "scale_plan": material.get("scale_plan"),
                "proposed_role_demands": batch.model_dump(mode="json"),
            },
        }
        result = await self._generate_proposal(
            state,
            proposal_type="role_demand_review",
            binding_stage="cast",
            context=review_context,
            scope_ref=scope_ref,
        )
        review = RoleDemandSemanticReviewResult.model_validate(result)
        known_demands = {item.demand_key for item in batch.proposals}
        known_turns = {
            str(item["id"])
            for item in (material.get("story_spine") or {}).get("turns", [])
        }
        unknown_demands = {
            demand_ref
            for finding in review.findings
            for demand_ref in finding.demand_refs
            if demand_ref not in known_demands
        }
        unknown_turns = {
            turn_ref
            for finding in review.findings
            for turn_ref in finding.turn_refs
            if turn_ref not in known_turns
        }
        if unknown_demands or unknown_turns:
            raise ValueError(
                "Role Demand semantic review references unknown planning refs: "
                f"demands={sorted(unknown_demands)}, turns={sorted(unknown_turns)}"
            )
        return review, proposal_operation_key(
            state,
            proposal_type="role_demand_review",
            binding_stage="cast",
            scope_ref=scope_ref,
        )

    async def generate_volume_boundary_proposal(
        self,
        state: NarrativeRunState,
    ) -> dict[str, Any]:
        operation_key = proposal_operation_key(
            state,
            proposal_type="volume_boundary",
            binding_stage="volumes",
        )
        context = self.context_compiler().stage(state, "volumes")
        # A stage regeneration must reconsider the natural boundaries rather
        # than anchor the proposal call on its own previous answer.
        context["material"]["volume_boundaries"] = {"proposals": []}
        result = await self._generate_proposal(
            state,
            proposal_type="volume_boundary",
            binding_stage="volumes",
            context=context,
        )
        try:
            batch = VolumeBoundaryProposalBatch.model_validate(result)
            spine = StorySpineArtifact.model_validate(context["material"]["story_spine"])
            scale_plan = context["material"]["scale_plan"]
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Volume boundary proposal context or payload is invalid") from exc
        if not isinstance(scale_plan, dict):
            raise ValueError("Volume boundary proposal scale plan is invalid")
        proposal_count = len(batch.proposals)
        chapter_range = scale_plan.get("chapter_range")
        candidate_cap = scale_plan.get("volume_candidate_cap")
        if (
            not isinstance(chapter_range, list)
            or len(chapter_range) != 2
            or not all(isinstance(value, int) for value in chapter_range)
            or not isinstance(candidate_cap, int)
            or isinstance(candidate_cap, bool)
            or candidate_cap < 1
        ):
            raise ValueError("Volume boundary proposal capacity is invalid")
        volume_target = scale_plan.get("volume_target")
        volume_range = scale_plan.get("volume_range")
        if (
            not isinstance(volume_target, int)
            or isinstance(volume_target, bool)
            or volume_target < 1
            or not isinstance(volume_range, list)
            or len(volume_range) != 2
            or not all(isinstance(value, int) for value in volume_range)
        ):
            raise ValueError("Volume boundary proposal target is invalid")
        capacity_cap = min(candidate_cap, volume_range[1], chapter_range[1])
        if volume_target > capacity_cap:
            raise ValueError(
                f"Frozen volume target {volume_target} exceeds Provider capacity {capacity_cap}"
            )
        if proposal_count != volume_target:
            raise ValueError(
                f"Volume boundary proposal returned {proposal_count} volumes; "
                f"the frozen scale requires exactly {volume_target}"
            )
        turn_ids = [turn.id for turn in spine.turns]
        refs = [turn_ref for proposal in batch.proposals for turn_ref in proposal.turn_refs]
        if refs != list(dict.fromkeys(refs)) or set(refs) != set(turn_ids):
            raise ValueError("Volume boundary proposal must cover every spine turn exactly once")
        keys = [proposal.boundary_key for proposal in batch.proposals]
        if keys != [f"boundary-{index}" for index in range(1, len(keys) + 1)]:
            raise ValueError("Volume boundary proposal keys must be deterministic and contiguous")
        return {
            "volume_boundary_proposal": {
                "proposals": [item.model_dump(mode="json") for item in batch.proposals]
            },
            "pending_operation_refs": [operation_key],
        }

    async def generate_detail_layout_proposal(
        self,
        state: NarrativeRunState,
    ) -> DetailLayoutProposalBatch:
        definition = self.runs.definition(state["run_id"])
        architecture_ref = (state.get("artifact_refs") or {}).get("volumes")
        spine_ref = (state.get("artifact_refs") or {}).get("spine")
        if not architecture_ref or not spine_ref:
            raise ValueError("Detail layout requires committed Spine and Volume artifacts")
        architecture = VolumeArchitectureArtifact.model_validate(
            self.artifacts.read(state["run_id"], architecture_ref).payload
        )
        spine = StorySpineArtifact.model_validate(
            self.artifacts.read(state["run_id"], spine_ref).payload
        )
        allocated_chapters = 0
        volume_layouts: list[DetailLayoutVolumeProposal] = []
        last_operation_key = ""
        for volume_index, volume in enumerate(architecture.volumes):
            windows = detail_layout_turn_windows(
                architecture=architecture,
                profile=definition.scale_profile,
                spine_turn_count=len(spine.turns),
                volume_index=volume_index,
                allocated_chapters=allocated_chapters,
            )
            volume_chapters = []
            for window in windows:
                last_operation_key = proposal_operation_key(
                    state,
                    proposal_type="detail_layout",
                    binding_stage="detail",
                    scope_ref=window.scope_ref,
                )
                context = self.context_compiler().detail_layout_turn_window(
                    state,
                    window,
                    previous_chapters=volume_chapters,
                )
                result = await self._generate_proposal(
                    state,
                    proposal_type="detail_layout",
                    binding_stage="detail",
                    context=context,
                    scope_ref=window.scope_ref,
                )
                try:
                    window_batch = DetailLayoutProposalBatch.model_validate(result)
                    validate_detail_layout_turn_window_proposal(
                        window_batch,
                        volume=volume,
                        spine=spine,
                        window=window,
                    )
                except (TypeError, ValueError) as exc:
                    raise StageArtifactValidationError(last_operation_key, exc) from exc
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
                profile=definition.scale_profile,
            )
        except ValueError as exc:
            raise StageArtifactValidationError(last_operation_key, exc) from exc
        return batch

    async def _preflight_cast_dossier_unit(
        self,
        state: NarrativeRunState,
        payload: dict[str, Any],
        *,
        binding: ProviderBinding,
        provider_context: dict[str, Any],
        generation_operation_key: str,
        unit_id: str,
        attempt: int,
    ) -> tuple[dict[str, Any], str]:
        current = CharacterDossierBatch.model_validate(payload).model_dump(mode="json")
        source_operation_key = generation_operation_key
        await self._review_cast_dossier_unit(
            state,
            current,
            provider_context=provider_context,
            scope_ref=f"{unit_id}:initial",
        )
        return current, source_operation_key

    async def _review_cast_dossier_unit(
        self,
        state: NarrativeRunState,
        payload: dict[str, Any],
        *,
        provider_context: dict[str, Any],
        scope_ref: str,
    ) -> tuple[CastDossierSemanticReviewResult, str]:
        material = provider_context.get("material")
        if not isinstance(material, dict):
            raise ValueError("Cast semantic preflight requires frozen planning material")
        review_context = {
            "target": "cast.dossier.semantic_review",
            "sources": dict(provider_context.get("sources") or {}),
            "material": {
                "story_brief": material.get("story_brief"),
                "story_spine": material.get("story_spine"),
                "role_demand_proposals": material.get("role_demand_proposals"),
                "subject_refs": material.get("subject_refs"),
                "proposed_dossiers": payload,
            },
        }
        result = await self._generate_proposal(
            state,
            proposal_type="cast_review",
            binding_stage="cast",
            context=review_context,
            scope_ref=scope_ref,
        )
        review = CastDossierSemanticReviewResult.model_validate(result)
        known_subjects = {
            str(item["id"]) for item in material.get("subject_refs") or []
        }
        known_demands = {
            str(item["demand_key"])
            for item in material.get("role_demand_proposals") or []
        }
        story_spine = material.get("story_spine")
        known_turns = {
            str(item["id"])
            for item in story_spine.get("turns", [])
        } if isinstance(story_spine, dict) else set()
        unknown_subjects = {
            subject_ref
            for finding in review.findings
            for subject_ref in finding.subject_refs
            if subject_ref not in known_subjects
        }
        unknown_demands = {
            demand_ref
            for finding in review.findings
            for demand_ref in finding.demand_refs
            if demand_ref not in known_demands
        }
        unknown_turns = {
            turn_ref
            for finding in review.findings
            for turn_ref in finding.turn_refs
            if turn_ref not in known_turns
        }
        if unknown_subjects or unknown_demands or unknown_turns:
            raise ValueError(
                "Cast semantic review references unknown planning refs: "
                f"subjects={sorted(unknown_subjects)}, demands={sorted(unknown_demands)}, "
                f"turns={sorted(unknown_turns)}"
            )
        return review, proposal_operation_key(
            state,
            proposal_type="cast_review",
            binding_stage="cast",
            scope_ref=scope_ref,
        )

    async def _assemble_character_bible(
        self,
        state: NarrativeRunState,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        dossiers = CharacterDossierBatch.model_validate(payload)
        subject_refs = state.get("subject_refs") or []
        if len(dossiers.subjects) != len(subject_refs):
            raise ValueError("Cast must return exactly one dossier for every preallocated subject ref")
        validate_character_dossier_modes(dossiers, subject_refs)
        cast_context = self.context_compiler().stage(state, "cast")
        material = cast_context["material"]
        spine = StorySpineArtifact.model_validate(material["story_spine"])
        turn_positions = {turn.id: index for index, turn in enumerate(spine.turns, start=1)}
        demands = {
            proposal.demand_key: proposal
            for proposal in RoleDemandProposalBatch.model_validate(
                {"proposals": material["role_demand_proposals"]}
            ).proposals
        }
        scale_plan = material.get("scale_plan")
        chapter_target = (
            scale_plan.get("chapter_target") if isinstance(scale_plan, dict) else None
        )
        if not isinstance(chapter_target, int) or chapter_target < 1:
            raise ValueError("Cast scale plan is missing its frozen chapter target")
        # Bind dossiers by demand key, not array position: providers may reorder
        # dossiers across unit groups, and order must never be a correctness input.
        unassigned = list(dossiers.subjects)
        subjects: list[CharacterSubject] = []
        for subject_ref in subject_refs:
            demand_key = str(subject_ref["demand_key"])
            matches = [item for item in unassigned if demand_key in item.demand_refs]
            if not matches:
                raise ValueError(
                    f"No returned dossier covers {demand_key} for {subject_ref['id']}"
                )
            primary = [item for item in matches if item.demand_refs[0] == demand_key]
            dossier = (primary or matches)[0]
            unassigned.remove(dossier)
            unknown_demand_refs = set(dossier.demand_refs) - set(demands)
            if unknown_demand_refs:
                raise ValueError(
                    "Character dossier references unknown role demands: "
                    f"{sorted(unknown_demand_refs)}"
                )
            active_turn_refs = [
                turn_ref
                for demand_ref in dossier.demand_refs
                for turn_ref in demands[demand_ref].active_turn_refs
            ]
            narrative_role = demands[demand_key].narrative_role
            if narrative_role == "protagonist" and dossier.kind != "protagonist":
                raise ValueError("The protagonist role demand must remain the protagonist dossier")
            if narrative_role == "historical_record" and dossier.kind != "historical_record":
                raise ValueError("The historical_record role demand must remain historical_record")
            first_turn_number = min(turn_positions[turn_ref] for turn_ref in active_turn_refs)
            debut = (
                "chapter:1"
                if dossier.kind == "protagonist"
                else _format_chapter_window(
                    project_turn_chapter_window(
                        turn_number=first_turn_number,
                        turn_count=len(spine.turns),
                        chapter_count=chapter_target,
                    )
                )
            )
            subjects.append(
                CharacterSubject(
                    id=str(subject_ref["id"]),
                    debut=debut,
                    **dossier.model_dump(mode="python", exclude={"debut"}),
                )
            )
        names = [subject.name.strip() for subject in subjects]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise ValueError(
                "Character subjects must be distinct named characters; "
                f"duplicated names: {duplicated}"
            )
        relation_material: dict[str, Any] = {
            "subjects": [item.model_dump(mode="json") for item in subjects],
        }
        if "revision_request" in cast_context["material"]:
            relation_material["revision_request"] = cast_context["material"][
                "revision_request"
            ]
        relation_context = {
            "target": "cast.relations",
            "sources": cast_context["sources"],
            "material": relation_material,
        }
        relation_payload = await self._generate_proposal(
            state,
            proposal_type="cast_relation",
            binding_stage="cast",
            context=relation_context,
        )
        relations = CharacterRelationBatch.model_validate(relation_payload)
        known = {subject.id for subject in subjects}
        unknown = {
            ref
            for relation in relations.relations
            for ref in (relation.a, relation.b)
            if ref not in known
        }
        if unknown:
            raise ValueError(f"Cast relation proposal references unknown subjects: {sorted(unknown)}")
        _validate_cast_relationship_coverage(
            subjects,
            relations.relations,
            RoleDemandProposalBatch.model_validate(
                {"proposals": material["role_demand_proposals"]}
            ),
            spine,
        )
        artifact = CharacterBibleArtifact(
            subjects=subjects,
            relations=relations.relations,
        )
        return validate_artifact_vnext(
            "cast",
            artifact,
            chapter_target=chapter_target,
        ).model_dump(mode="json")

    async def _generate_proposal(
        self,
        state: NarrativeRunState,
        *,
        proposal_type: str,
        binding_stage: StageId,
        context: dict[str, Any],
        scope_ref: str = "",
    ) -> dict[str, Any]:
        run_id = state["run_id"]
        attempt = int((state.get("stage_attempts") or {}).get(binding_stage) or 1)
        operation_key = proposal_operation_key(
            state,
            proposal_type=proposal_type,
            binding_stage=binding_stage,
            scope_ref=scope_ref,
        )
        binding = self.runs.definition(run_id).provider_bindings.get(binding_stage)
        if binding is None:
            raise ProviderOperationError(
                f"No frozen Provider binding for {binding_stage} proposal"
            )
        planner = self.output_budget_planner(state)
        budget = planner.for_proposal(proposal_type, binding, context)
        request = ProposalGenerationRequest(
            operation_key=operation_key,
            run_id=run_id,
            stage_id=binding_stage,
            proposal_type=proposal_type,  # type: ignore[arg-type]
            attempt=attempt,
            binding=budget.bind(binding),
            context=planner.attach(context, budget),
        )
        receipt = self.operations.begin_provider(
            run_id=run_id,
            operation_key=operation_key,
            kind=f"{proposal_type}_proposal",
            provider_profile_id=binding.provider_profile_id,
            model=binding.model,
            provider_input=compile_provider_input(request),
        )
        if receipt.status == "failed":
            raise ProviderOperationError.for_operation(
                operation_key,
                f"Proposal operation already failed: {operation_key}",
            )
        if receipt.status == "succeeded":
            return receipt.result
        response = None
        transport_attempts = 0
        try:
            for round_index in range(_STAGE_NETWORK_ATTEMPTS):
                transport_attempts = round_index + 1
                try:
                    response = await self.provider.generate_proposal(request)
                    break
                except Exception as exc:
                    if (
                        round_index >= _STAGE_NETWORK_ATTEMPTS - 1
                        or not _is_transient_network_error(exc)
                    ):
                        raise
                    await asyncio.sleep(2 * (round_index + 1))
        except Exception as exc:
            # A parsed JSON object that fails the frozen proposal model is a
            # Provider return with a domain-contract rejection, not a transport
            # failure. Preserve the paid response and usage for the monitor.
            returned = getattr(exc, "provider_result", None)
            if (
                isinstance(exc, ProviderOperationError)
                and isinstance(returned, dict)
                and exc.diagnostic.get("code") == "structured_contract_invalid"
            ):
                self.operations.record_provider_return(
                    run_id,
                    operation_key,
                    returned,
                    usage=exc.usage,
                    diagnostic={**exc.diagnostic, "transport_attempts": transport_attempts},
                )
                self.operations.reject_provider_contract(
                    run_id,
                    operation_key,
                    {"type": type(exc).__name__, "message": str(exc)},
                    diagnostic=exc.diagnostic,
                )
                raise ProviderOperationError.for_operation(operation_key, exc) from exc
            self.operations.fail(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                usage=response.usage if response is not None else getattr(exc, "usage", {}),
                diagnostic={
                    **(
                        response.diagnostic
                        if response is not None
                        else getattr(exc, "diagnostic", {})
                    ),
                    "transport_attempts": transport_attempts,
                },
            )
            raise ProviderOperationError.for_operation(operation_key, exc) from exc
        if response is None:
            raise ProviderOperationError.for_operation(
                operation_key,
                "Proposal generation ended without a Provider response",
            )
        self.operations.succeed(
            run_id,
            operation_key,
            response.payload,
            usage=response.usage,
            diagnostic={
                **response.diagnostic,
                "transport_attempts": transport_attempts,
            },
        )
        return response.payload

    def detail_layout_operation_keys(
        self,
        state: NarrativeRunState,
    ) -> list[str]:
        architecture_ref = (state.get("artifact_refs") or {}).get("volumes")
        if not architecture_ref:
            return []
        windows = self.detail_layout_windows(state)
        return [
            proposal_operation_key(
                state,
                proposal_type="detail_layout",
                binding_stage="detail",
                scope_ref=window.scope_ref,
            )
            for window in windows
        ]

    def detail_layout_windows(
        self,
        state: NarrativeRunState,
    ) -> list[DetailLayoutTurnWindow]:
        architecture_ref = (state.get("artifact_refs") or {}).get("volumes")
        spine_ref = (state.get("artifact_refs") or {}).get("spine")
        if not architecture_ref or not spine_ref:
            return []
        architecture = VolumeArchitectureArtifact.model_validate(
            self.artifacts.read(state["run_id"], architecture_ref).payload
        )
        spine = StorySpineArtifact.model_validate(
            self.artifacts.read(state["run_id"], spine_ref).payload
        )
        profile = self.runs.definition(state["run_id"]).scale_profile
        windows: list[DetailLayoutTurnWindow] = []
        allocated_chapters = 0
        for volume_index in range(len(architecture.volumes)):
            volume_windows = detail_layout_turn_windows(
                architecture=architecture,
                profile=profile,
                spine_turn_count=len(spine.turns),
                volume_index=volume_index,
                allocated_chapters=allocated_chapters,
            )
            windows.extend(volume_windows)
            allocated_chapters += sum(
                window.chapter_target for window in volume_windows
            )
        return windows

    def stage_operation_keys(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
    ) -> list[str]:
        attempt = int((state.get("stage_attempts") or {}).get(stage_id) or 1)
        base = f"{state['run_id']}:{stage_id}:generate:{attempt}"
        detail_layout: DetailLayoutProposalBatch | None = None
        layout_operation_keys: list[str] = []
        if stage_id == "detail":
            layout_windows = self.detail_layout_windows(state)
            layout_operation_keys = [
                proposal_operation_key(
                    state,
                    proposal_type="detail_layout",
                    binding_stage="detail",
                    scope_ref=window.scope_ref,
                )
                for window in layout_windows
            ]
            completed_layout_keys: list[str] = []
            chapters_by_volume: dict[str, list[Any]] = {}
            for window, operation_key in zip(
                layout_windows,
                layout_operation_keys,
                strict=True,
            ):
                receipt = self.operations.find(state["run_id"], operation_key)
                if receipt is None or receipt.status != "succeeded":
                    return [*completed_layout_keys, operation_key]
                batch = DetailLayoutProposalBatch.model_validate(receipt.result)
                completed_layout_keys.append(operation_key)
                if batch.status != "sufficient" or len(batch.volumes) != 1:
                    return completed_layout_keys
                if batch.volumes[0].volume_ref != window.volume_ref:
                    return completed_layout_keys
                chapters_by_volume.setdefault(window.volume_ref, []).extend(
                    batch.volumes[0].chapters
                )
            architecture_ref = (state.get("artifact_refs") or {}).get("volumes")
            if not architecture_ref:
                return completed_layout_keys
            architecture = VolumeArchitectureArtifact.model_validate(
                self.artifacts.read(state["run_id"], architecture_ref).payload
            )
            volume_layouts = [
                DetailLayoutVolumeProposal(
                    volume_ref=volume.id,
                    chapters=chapters_by_volume.get(volume.id, []),
                )
                for volume in architecture.volumes
            ]
            detail_layout = DetailLayoutProposalBatch(
                status="sufficient",
                diagnosis="",
                volumes=volume_layouts,
            )
        stage_units = self.context_compiler().stage_units(
            state,
            stage_id,
            detail_layout=detail_layout,
        )
        operation_keys = [
            f"{base}:{unit_id}" if unit_id else base
            for unit_id, _ in stage_units
        ]
        if stage_id == "spine":
            operation_keys.append(
                proposal_operation_key(
                    state,
                    proposal_type="spine_review",
                    binding_stage="spine",
                    scope_ref="initial",
                )
            )
            for repair_index in range(
                1,
                _SPINE_SEMANTIC_REPAIR_LIMIT[
                    self.runs.definition(state["run_id"]).quality_mode
                ]
                + 1,
            ):
                repair_key = f"{base}:semantic-repair-{repair_index}"
                if self.operations.find(state["run_id"], repair_key) is None:
                    break
                operation_keys.extend(
                    [
                        repair_key,
                        proposal_operation_key(
                            state,
                            proposal_type="spine_review",
                            binding_stage="spine",
                            scope_ref=f"repair-{repair_index}",
                        ),
                    ]
                )
        if layout_operation_keys:
            operation_keys[0:0] = layout_operation_keys
        if stage_id == "cast":
            repair_key = proposal_operation_key(
                state,
                proposal_type="role_demand",
                binding_stage="cast",
                scope_ref="contract-repair-1",
            )
            if self.operations.find(state["run_id"], repair_key) is not None:
                operation_keys.append(repair_key)
            for unit_id, _ in stage_units:
                unit_operation_key = f"{base}:{unit_id}" if unit_id else base
                operation_keys.append(
                    proposal_operation_key(
                        state,
                        proposal_type="cast_review",
                        binding_stage="cast",
                        scope_ref=f"{unit_id}:initial",
                    )
                )
            operation_keys.append(
                proposal_operation_key(
                    state,
                    proposal_type="cast_relation",
                    binding_stage="cast",
                )
            )
        return operation_keys

    async def _generate_stage_unit(
        self,
        *,
        run_id: str,
        stage_id: StageId,
        attempt: int,
        operation_key: str,
        binding: ProviderBinding,
        context: dict[str, Any],
        unit_id: str,
    ) -> dict[str, Any]:
        return await self._generate_stage_unit_once(
            run_id=run_id,
            stage_id=stage_id,
            attempt=attempt,
            operation_key=operation_key,
            binding=binding,
            context=context,
            unit_id=unit_id,
        )

    async def _generate_stage_unit_once(
        self,
        *,
        run_id: str,
        stage_id: StageId,
        attempt: int,
        operation_key: str,
        binding: ProviderBinding,
        context: dict[str, Any],
        unit_id: str,
    ) -> dict[str, Any]:
        request = StageGenerationRequest(
            operation_key=operation_key,
            run_id=run_id,
            stage_id=stage_id,
            attempt=attempt,
            binding=binding,
            context=context,
        )
        receipt = self.operations.begin_provider(
            run_id=run_id,
            operation_key=operation_key,
            kind="stage_generation_unit" if unit_id else "stage_generation",
            provider_profile_id=binding.provider_profile_id,
            model=binding.model,
            provider_input=compile_provider_input(request),
        )
        if receipt.status == "failed":
            stored = receipt.error or {}
            raise ProviderOperationError.for_operation(
                operation_key,
                "Provider operation already failed: "
                f"{stored.get('type', '')}: {stored.get('message', operation_key)}",
            )
        if receipt.status == "contract_rejected":
            stored = receipt.error or {}
            raise ProviderOperationError.for_operation(
                operation_key,
                "Provider return was already rejected by the stage contract: "
                f"{stored.get('type', '')}: {stored.get('message', operation_key)}",
            )
        if receipt.status == "succeeded":
            payload = receipt.result
            _validate_stage_unit(stage_id, unit_id, context, payload)
            if stage_id == "detail":
                payload = _bind_detail_segment_turn_refs(payload, context)
            return payload
        if receipt.status == "provider_returned":
            payload = receipt.provider_result
            try:
                _validate_stage_unit(stage_id, unit_id, context, payload)
                if stage_id == "detail":
                    payload = _bind_detail_segment_turn_refs(payload, context)
            except Exception as exc:
                self.operations.reject_provider_contract(
                    run_id,
                    operation_key,
                    {"type": type(exc).__name__, "message": str(exc)},
                )
                raise ProviderOperationError.for_operation(operation_key, exc) from exc
            self.operations.accept_provider_result(
                run_id,
                operation_key,
                receipt.provider_result,
            )
            return payload
        response = None
        transport_attempts = 0
        try:
            for round_index in range(_STAGE_NETWORK_ATTEMPTS):
                transport_attempts = round_index + 1
                try:
                    response = await self.provider.generate_stage(request)
                    break
                except Exception as exc:
                    if (
                        round_index >= _STAGE_NETWORK_ATTEMPTS - 1
                        or not _is_transient_network_error(exc)
                    ):
                        raise
                    await asyncio.sleep(2 * (round_index + 1))
        except Exception as exc:
            self.operations.fail(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                usage=response.usage if response is not None else getattr(exc, "usage", {}),
                diagnostic={
                    **(
                        response.diagnostic
                        if response is not None
                        else getattr(exc, "diagnostic", {})
                    ),
                    "transport_attempts": transport_attempts,
                },
            )
            raise ProviderOperationError.for_operation(operation_key, exc) from exc
        if response is None:
            raise ProviderOperationError.for_operation(
                operation_key,
                "Stage unit generation ended without a Provider response",
            )
        self.operations.record_provider_return(
            run_id,
            operation_key,
            response.payload,
            usage=response.usage,
            diagnostic={
                **response.diagnostic,
                "transport_attempts": transport_attempts,
            },
        )
        payload = response.payload
        try:
            _validate_stage_unit(stage_id, unit_id, context, payload)
            if stage_id == "detail":
                payload = _bind_detail_segment_turn_refs(payload, context)
        except Exception as exc:
            self.operations.reject_provider_contract(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
            )
            raise ProviderOperationError.for_operation(operation_key, exc) from exc
        self.operations.accept_provider_result(
            run_id,
            operation_key,
            response.payload,
        )
        return payload

    async def _generate_cover_assets(
        self,
        state: NarrativeRunState,
        brief: CoverBrief,
    ) -> list[CoverAssetRecord]:
        run_id = state["run_id"]
        attempt = int((state.get("stage_attempts") or {}).get("cover") or 1)
        binding = self.runs.definition(run_id).cover_asset_binding
        prompt = _cover_image_prompt(brief)
        records: list[CoverAssetRecord] = []
        for candidate_index in range(1, binding.candidate_count + 1):
            operation_key = (
                f"{run_id}:cover:image:{attempt}:candidate:{candidate_index}"
            )
            request = CoverImageRequest(
                operation_key=operation_key,
                run_id=run_id,
                candidate_index=candidate_index,
                generation_attempt=attempt,
                binding=binding,
                prompt=prompt,
            )
            receipt = self.operations.begin_provider(
                run_id=run_id,
                operation_key=operation_key,
                kind="cover_image_generation",
                provider_profile_id=binding.provider_profile_id,
                model=binding.model,
                provider_input=compile_provider_input(request),
            )
            if receipt.status == "failed":
                raise ProviderOperationError.for_operation(
                    operation_key,
                    f"Cover image operation already failed: {operation_key}",
                )
            if receipt.status == "succeeded":
                if not isinstance(receipt.result, dict):
                    raise ProviderOperationError.for_operation(
                        operation_key, "Cover image receipt is invalid"
                    )
                asset_id = str(receipt.result.get("asset_id") or "")
                records.append(self.cover_assets.read(run_id, asset_id))
                continue
            image = None
            try:
                image = await self._generate_cover_image_with_retry(request)
                record = self.cover_assets.save(
                    run_id,
                    operation_key=operation_key,
                    candidate_index=candidate_index,
                    generation_attempt=attempt,
                    image=image,
                    expected_ratio=binding.aspect_ratio(),
                )
            except Exception as exc:
                self.operations.fail(
                    run_id,
                    operation_key,
                    {"type": type(exc).__name__, "message": str(exc)},
                    usage=(
                        normalize_provider_usage(image.usage)
                        if image is not None
                        else getattr(exc, "usage", {})
                    ),
                    diagnostic=getattr(exc, "diagnostic", {}),
                )
                raise ProviderOperationError.for_operation(operation_key, exc) from exc
            self.operations.succeed(
                run_id,
                operation_key,
                {
                    "asset_id": record.asset_id,
                    "sha256": record.sha256,
                    "mime_type": record.mime_type,
                    "width": record.width,
                    "height": record.height,
                },
                usage=normalize_provider_usage(image.usage),
            )
            self.events.append(
                run_id,
                event_id=f"{operation_key}:asset-ready",
                type="cover.asset_ready",
                stage_id="cover",
                node_id="cover.generate_assets",
                payload_ref=record.asset_id,
            )
            records.append(record)
        if len({record.asset_id for record in records}) != binding.candidate_count:
            raise ProviderOperationError(
                "Image Provider returned duplicate bytes instead of the frozen candidate set"
            )
        return records

    async def _generate_cover_image_with_retry(self, request: CoverImageRequest) -> Any:
        for round_index in range(_COVER_NETWORK_ATTEMPTS):
            try:
                return await self.provider.generate_cover_image(request)
            except Exception as exc:
                if (
                    round_index >= _COVER_NETWORK_ATTEMPTS - 1
                    or not _is_transient_network_error(exc)
                ):
                    raise
                await asyncio.sleep(2 * (round_index + 1))
        raise ProviderOperationError.for_operation(
            request.operation_key, "Cover image generation exhausted network retries"
        )

    def validate_candidate(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
    ) -> ArtifactRecord:
        candidate_id = (state.get("candidate_artifact_refs") or {}).get(stage_id)
        if not candidate_id:
            raise ValueError(f"Missing {stage_id} candidate reference")
        candidate = self.artifacts.read(state["run_id"], candidate_id)
        if stage_id == "cast":
            artifact_refs = state.get("artifact_refs") or {}
            spine_ref = artifact_refs.get("spine")
            if not spine_ref:
                raise ValueError("Cast preflight requires the committed Spine Artifact")
            findings = build_cast_identity_findings(
                spine=StorySpineArtifact.model_validate(
                    self.artifacts.read(state["run_id"], spine_ref).payload
                ),
                cast=CharacterBibleArtifact.model_validate(candidate.payload),
            )
            if findings:
                summary = "; ".join(
                    f"{finding.code}: {finding.evidence}" for finding in findings
                )
                raise ValueError(f"Cast identity preflight blocked the candidate: {summary}")
        if stage_id == "detail":
            artifact_refs = state.get("artifact_refs") or {}

            def committed_payload(source_stage: StageId) -> dict[str, Any]:
                artifact_id = artifact_refs.get(source_stage)
                if not artifact_id:
                    raise ValueError(
                        f"Detail preflight requires committed {source_stage} Artifact"
                    )
                return self.artifacts.read(state["run_id"], artifact_id).payload

            report = build_detail_preflight(
                brief=StoryBriefArtifact.model_validate(committed_payload("brief")),
                spine=StorySpineArtifact.model_validate(committed_payload("spine")),
                cast=CharacterBibleArtifact.model_validate(committed_payload("cast")),
                volumes=VolumeArchitectureArtifact.model_validate(
                    committed_payload("volumes")
                ),
                detail=DetailArtifact.model_validate(candidate.payload),
            )
            require_detail_preflight(report)
        return candidate

    def commit_candidate(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
        *,
        decision_id: str,
    ) -> ArtifactRecord:
        candidate = self.validate_candidate(state, stage_id)
        if stage_id == "cover":
            cover = CoverArtifact.model_validate(candidate.payload)
            include_image = self.runs.definition(
                state["run_id"]
            ).export_preferences.include_cover_image
            if include_image and not cover.selected_asset_id:
                raise ValueError("Cover must select one immutable candidate before commit")
            if cover.selected_asset_id:
                self.cover_assets.read(state["run_id"], cover.selected_asset_id)
        committed = self.artifacts.commit(
            state["run_id"],
            stage_id,
            candidate.payload,
            source=f"decision:{decision_id}",
            **self._validation_refs(state, stage_id),
        )
        if stage_id == "export":
            export = ExportArtifact.model_validate(committed.payload)
            cover_asset = (
                self.cover_assets.content(state["run_id"], export.cover_asset_id)
                if export.cover_asset_id
                else None
            )
            self.exports.materialize(
                state["run_id"],
                committed,
                self._accepted_chapters(state),
                cover_asset=cover_asset,
            )
        self.events.append(
            state["run_id"],
            event_id=f"{decision_id}:committed",
            type="artifact.committed",
            stage_id=stage_id,
            node_id=f"{stage_id}.commit_artifact",
            payload_ref=committed.artifact_id,
        )
        return committed

    def context_for(self, state: NarrativeRunState, stage_id: StageId) -> dict[str, Any]:
        if stage_id == "detail":
            architecture_ref = (state.get("artifact_refs") or {}).get("volumes")
            spine_ref = (state.get("artifact_refs") or {}).get("spine")
            if not architecture_ref or not spine_ref:
                raise ValueError("Detail context requires committed Spine and Volume artifacts")
            architecture = VolumeArchitectureArtifact.model_validate(
                self.artifacts.read(state["run_id"], architecture_ref).payload
            )
            spine = StorySpineArtifact.model_validate(
                self.artifacts.read(state["run_id"], spine_ref).payload
            )
            window = detail_layout_turn_windows(
                architecture=architecture,
                profile=self.runs.definition(state["run_id"]).scale_profile,
                spine_turn_count=len(spine.turns),
                volume_index=0,
                allocated_chapters=0,
            )[0]
            return self.context_compiler().detail_layout_turn_window(state, window)
        return self.context_compiler().stage(state, stage_id)

    def context_compiler(self) -> NarrativeContextCompiler:
        return NarrativeContextCompiler(
            self.runs,
            self.artifacts,
            self.chapters,
            canon=self.outbox.canon,
            planning=self.planning,
        )

    def output_budget_planner(
        self,
        state: NarrativeRunState,
    ) -> OutputBudgetPlanner:
        profile = self.runs.definition(state["run_id"]).scale_profile
        return OutputBudgetPlanner(profile)

    def character_ids(self, state: NarrativeRunState) -> set[str]:
        return {item.id for item in self.character_bible(state).subjects}

    def character_bible(self, state: NarrativeRunState) -> CharacterBibleArtifact:
        artifact_id = (state.get("artifact_refs") or {}).get("cast")
        if not artifact_id:
            raise ValueError("Character Bible must be committed before downstream execution")
        return CharacterBibleArtifact.model_validate(
            self.artifacts.read(state["run_id"], artifact_id).payload
        )

    def npc_slot_ids(self, state: NarrativeRunState) -> set[str]:
        return set()

    def detail(self, state: NarrativeRunState) -> DetailArtifact:
        artifact_id = (state.get("artifact_refs") or {}).get("detail")
        if not artifact_id:
            raise ValueError("Detail artifact must be committed before chapter execution")
        return DetailArtifact.model_validate(
            self.artifacts.read(state["run_id"], artifact_id).payload
        )

    def _validation_refs(self, state: NarrativeRunState, stage_id: StageId) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if stage_id == "cast":
            definition = self.runs.definition(state["run_id"])
            kwargs["chapter_target"] = plan_narrative_scale(
                definition.scale_profile,
                definition.quality_mode,
            ).chapter_target
            kwargs["demand_keys"] = {
                str(item["demand_key"])
                for item in state.get("role_demand_proposals") or []
            }
            kwargs["subject_ids"] = {
                str(item["id"])
                for item in state.get("subject_refs") or []
            }
        if stage_id in {"volumes", "detail"}:
            kwargs["subject_ids"] = self.character_ids(state)
        if stage_id == "detail":
            kwargs["historical_subject_ids"] = {
                subject.id
                for subject in self.character_bible(state).subjects
                if subject.kind == "historical_record"
            }
            volumes_id = (state.get("artifact_refs") or {}).get("volumes")
            if not volumes_id:
                raise ValueError("Volume Architecture must be committed before Detail validation")
            architecture = VolumeArchitectureArtifact.model_validate(
                self.artifacts.read(state["run_id"], volumes_id).payload
            )
            kwargs["volume_cast_ids"] = {
                volume.id: set(volume.cast_ids) for volume in architecture.volumes
            }
        if stage_id == "volumes":
            spine_id = (state.get("artifact_refs") or {}).get("spine")
            if not spine_id:
                raise ValueError("Story Spine must be committed before volume validation")
            spine = StorySpineArtifact.model_validate(
                self.artifacts.read(state["run_id"], spine_id).payload
            )
            kwargs["turn_ids"] = {turn.id for turn in spine.turns}
        if stage_id == "cover":
            attempt = int((state.get("stage_attempts") or {}).get("cover") or 1)
            kwargs["cover_asset_ids"] = {
                item.asset_id
                for item in self.cover_assets.list(
                    state["run_id"], generation_attempt=attempt
                )
            }
        if stage_id == "export":
            kwargs["chapter_version_ids"] = self._accepted_version_ids(state)
            kwargs["cover_asset_ids"] = {
                item.asset_id for item in self.cover_assets.list(state["run_id"])
            }
            brief_artifact_id = (state.get("artifact_refs") or {}).get("brief")
            if not brief_artifact_id:
                raise ValueError("Story Brief must be committed before export")
            kwargs["export_title"] = str(
                self.artifacts.read(state["run_id"], brief_artifact_id).payload["title"]
            )
        return kwargs

    def _build_export(self, state: NarrativeRunState) -> dict[str, Any]:
        brief_artifact_id = (state.get("artifact_refs") or {}).get("brief")
        if not brief_artifact_id:
            raise ValueError("Story Brief must be committed before export")
        brief_artifact = self.artifacts.read(state["run_id"], brief_artifact_id)
        detail = self.detail(state)
        chapter_refs = state.get("chapter_version_refs") or {}
        accepted = [chapter_refs[chapter.ref] for chapter in detail.chapters]
        if any(not version.endswith("-accepted") for version in accepted):
            raise ValueError("Export requires an accepted version for every frozen chapter")
        cover_ref = (state.get("artifact_refs") or {}).get("cover", "")
        cover_id = (
            str(self.artifacts.read(state["run_id"], cover_ref).payload["selected_asset_id"])
            if cover_ref
            else ""
        )
        preferences = self.runs.definition(state["run_id"]).export_preferences
        if preferences.include_cover_image and not cover_id:
            raise ValueError("Export requires the committed Cover asset")
        if cover_id:
            self.cover_assets.read(state["run_id"], cover_id)
        volumes_ref = (state.get("artifact_refs") or {}).get("volumes")
        if not volumes_ref:
            raise ValueError("Volume Architecture must be committed before export")
        architecture = VolumeArchitectureArtifact.model_validate(
            self.artifacts.read(state["run_id"], volumes_ref).payload
        )
        chapter_counts = {
            volume.id: sum(1 for chapter in detail.chapters if chapter.volume_ref == volume.id)
            for volume in architecture.volumes
        }
        return ExportArtifact(
            format=preferences.format,
            chapter_version_ids=accepted,
            cover_asset_id=cover_id,
            metadata=ExportMetadata(
                title=str(brief_artifact.payload["title"]),
                author=preferences.author,
                version_note=preferences.version_note,
            ),
            volumes=[
                ExportVolume(title=volume.title, chapter_count=chapter_counts[volume.id])
                for volume in architecture.volumes
            ],
        ).model_dump(mode="json")

    def _accepted_version_ids(self, state: NarrativeRunState) -> list[str]:
        refs = state.get("chapter_version_refs") or {}
        return [refs[chapter.ref] for chapter in self.detail(state).chapters]

    def _accepted_chapters(self, state: NarrativeRunState) -> list[ChapterArtifact]:
        detail = self.detail(state)
        refs = state.get("chapter_version_refs") or {}
        return [
            self.chapters.read(state["run_id"], chapter.ref, refs[chapter.ref]).artifact
            for chapter in detail.chapters
        ]


def _cover_image_prompt(brief: CoverBrief) -> str:
    constraints = "\n".join(f"- {item}" for item in brief.negative_constraints)
    return (
        f"Concept: {brief.concept}\n"
        f"Image direction: {brief.image_prompt}\n"
        f"Palette: {', '.join(brief.palette)}\n"
        "Do not render letters, logos, watermarks, UI, borders, or mockup frames.\n"
        f"Additional exclusions:\n{constraints or '- none'}"
    )


def _detail_reused_titles(
    titles: list[str],
    reserved_titles: list[str],
) -> list[str]:
    normalized = [title.strip().casefold() for title in titles]
    reserved = {title.strip().casefold() for title in reserved_titles}
    return sorted(
        {
            title.strip()
            for title, key in zip(titles, normalized, strict=True)
            if normalized.count(key) > 1 or key in reserved
        }
    )


def _validate_stage_unit(
    stage_id: StageId,
    unit_id: str,
    context: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    if stage_id == "spine":
        normalized_payload = _normalize_spine_progress_aliases(payload)
        draft = StorySpineDraftArtifact.model_validate(normalized_payload)
        target, _, _ = spine_turn_plan(context)
        turn_count = len(draft.turns)
        if turn_count != target:
            raise ValueError(
                f"Spine returned {turn_count} turns; the frozen editorial plan requires "
                f"exactly {target}"
            )
        budget = context.get("output_budget")
        item_cap = budget.get("item_cap") if isinstance(budget, dict) else None
        if not isinstance(item_cap, int) or turn_count > item_cap:
            raise ValueError("Spine exceeds its frozen Provider output capacity")
        # Validate semantic structure before the Provider receipt can succeed;
        # otherwise an invalid first draft would be persisted and fail only
        # during later candidate aggregation.
        _bind_story_spine(normalized_payload)
        return
    if stage_id == "brief":
        StoryBriefArtifact.model_validate(payload)
        return
    if stage_id == "cover":
        CoverBrief.model_validate(payload)
        return
    if not unit_id:
        return
    if stage_id == "cast":
        dossiers = CharacterDossierBatch.model_validate(payload)
        subject_refs = context["material"]["subject_refs"]
        expected = len(subject_refs)
        if len(dossiers.subjects) != expected:
            raise ValueError(
                f"Cast unit returned {len(dossiers.subjects)} dossiers for "
                f"{expected} subject refs; return exactly one dossier per subject ref"
            )
        validate_character_dossier_modes(dossiers, subject_refs)
        # Checked per unit so a name collision hits the contract repair loop
        # instead of failing the whole run at the merged-bible validation.
        names = [subject.name.strip() for subject in dossiers.subjects]
        normalized_names = [name.casefold() for name in names]
        reserved = {
            str(name).strip().casefold()
            for name in (context["material"].get("reserved_names") or [])
        }
        duplicated = sorted(
            {
                name
                for name, normalized in zip(names, normalized_names, strict=True)
                if normalized_names.count(normalized) > 1 or normalized in reserved
            }
        )
        if duplicated:
            raise ValueError(
                "Cast unit reused character names that must stay unique across "
                f"the whole cast: {duplicated}; invent distinct new names"
            )
        return
    if stage_id == "volumes":
        draft = VolumeArchitectureUnitArtifact.model_validate(payload)
        titles = [volume.title.strip() for volume in draft.volumes]
        if any(not title for title in titles):
            raise ValueError(
                "Volumes unit must give every volume a non-empty 2-12 character title"
            )
        if len(titles) != len(set(titles)):
            raise ValueError("Volumes unit reused a volume title; titles must be distinct")
        reserved = {
            str(title).strip().casefold()
            for title in context["material"].get("reserved_titles", [])
        }
        reused = sorted(title for title in titles if title.casefold() in reserved)
        if reused:
            raise ValueError(
                f"Volumes unit reused titles from an earlier unit: {reused}"
            )
        volume = draft.volumes[0]
        spine_turns = context["material"].get("volume_spine_turns") or []
        owned_turn_refs = [str(turn.get("id") or "") for turn in spine_turns]
        if volume.climax_turn_ref not in owned_turn_refs:
            raise ValueError("Volume climax must bind to a turn owned by the volume")
        climax_position = owned_turn_refs.index(volume.climax_turn_ref) + 1
        if climax_position < max(1, math.ceil(len(owned_turn_refs) * 0.6)):
            raise ValueError("Volume climax must land in the final 40 percent of its turns")
        closure_policy = context["material"].get("closure_policy") or {}
        if closure_policy.get("contains_final_volume"):
            global_climax_refs = [
                str(turn.get("id") or "")
                for turn in spine_turns
                if "climax" in (turn.get("milestones") or [])
            ]
            if global_climax_refs != [volume.climax_turn_ref]:
                raise ValueError(
                    "The final volume climax must bind to the frozen whole-book climax turn"
                )
        return
    if stage_id == "detail":
        segment = DetailSegmentArtifact.model_validate(payload)
        for chapter in segment.chapters:
            validate_detail_scene_quality(chapter.scenes)
        chapter_titles = [chapter.title.strip() for chapter in segment.chapters]
        if any(not title for title in chapter_titles):
            raise ValueError(
                "Detail unit must give every chapter a non-empty 2-12 character title"
            )
        allowed = {item["id"] for item in context["material"]["selected_dossiers"]}
        unknown = {
            subject_id
            for chapter in segment.chapters
            for subject_id in chapter.cast_ids
        } - allowed
        if unknown:
            raise ValueError(f"Detail unit references subjects outside its volume: {sorted(unknown)}")
        historical = {
            item["id"]
            for item in context["material"]["selected_dossiers"]
            if item["kind"] == "historical_record"
        }
        forbidden = {
            subject_id
            for chapter in segment.chapters
            for subject_id in chapter.cast_ids
            if subject_id in historical
        }
        if forbidden:
            raise ValueError(
                "Detail unit placed historical_record subjects in present-action cast_ids: "
                f"{sorted(forbidden)}"
            )
        scale = DetailScaleProjection.model_validate(
            context["material"]["scale_projection"]
        )
        if len(segment.chapters) != scale.chapter_target:
            raise ValueError(
                f"Detail unit returned {len(segment.chapters)} chapters; "
                f"the frozen allocation requires exactly {scale.chapter_target}"
            )
        budget = context.get("output_budget")
        scene_cap = budget.get("scene_cap") if isinstance(budget, dict) else None
        if isinstance(scene_cap, int) and any(
            len(chapter.scenes) > scene_cap for chapter in segment.chapters
        ):
            raise ValueError("Detail unit exceeds its frozen per-chapter scene capacity")
        scene_counts = [len(chapter.scenes) for chapter in segment.chapters]
        if any(
            count < scale.scenes_per_chapter_min
            or count > scale.scenes_per_chapter_max
            for count in scene_counts
        ):
            raise ValueError("Detail unit returned a scene load outside its frozen capacity range")


def _bind_detail_segment_turn_refs(
    payload: dict[str, Any],
    context: dict[str, Any],
) -> dict[str, Any]:
    """Bind causal ownership after the Provider returns the editable script card."""
    segment = DetailSegmentArtifact.model_validate(payload)
    scale = DetailScaleProjection.model_validate(
        context["material"]["scale_projection"]
    )
    if len(segment.chapters) != len(scale.chapter_beats):
        raise ValueError(
            "Detail chapter count does not match the frozen chapter beat slots"
        )
    chapters = [
        {
            **chapter.model_dump(mode="json"),
            "turn_refs": list(beat.turn_refs),
        }
        for chapter, beat in zip(segment.chapters, scale.chapter_beats, strict=True)
    ]
    return {"chapters": chapters}


def _aggregate_stage_units(
    stage_id: StageId,
    units: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    if len(units) == 1 and not units[0][0]:
        return units[0][1]
    if stage_id == "cast":
        payload = {
            "subjects": [
                subject
                for _, unit in units
                for subject in unit["subjects"]
            ]
        }
        return CharacterDossierBatch.model_validate(payload).model_dump(mode="json")
    if stage_id == "volumes":
        payload = {"volumes": [volume for _, unit in units for volume in unit["volumes"]]}
        return VolumeArchitectureDraftArtifact.model_validate(payload).model_dump(mode="json")
    if stage_id == "detail":
        chapters: list[dict[str, Any]] = []
        for unit_id, unit in units:
            volume_ref = unit_id.split(".segment-", maxsplit=1)[0]
            for chapter in unit["chapters"]:
                chapters.append(
                    {
                        "ref": f"chapter-{len(chapters) + 1}",
                        "volume_ref": volume_ref,
                        **chapter,
                    }
                )
        return {"chapters": chapters}
    raise ValueError(f"Stage {stage_id} does not support structured unit aggregation")


def _format_chapter_window(window: tuple[int, int]) -> str:
    start, end = window
    return f"chapter:{start}" if start == end else f"chapter:{start}-{end}"


_SPINE_PROGRESS_ALIASES = {
    "inciting": "external",
    "commitment": "internal",
    "midpoint_reversal": "information",
    "crisis": "external",
    "climax": "external",
    "aftermath": "internal",
}


def _normalize_spine_progress_aliases(payload: dict[str, Any]) -> dict[str, Any]:
    """Normalize known milestone labels without rewriting story content."""

    turns = payload.get("turns")
    if not isinstance(turns, list):
        return payload
    normalized_turns: list[Any] = []
    for turn in turns:
        if not isinstance(turn, dict):
            normalized_turns.append(turn)
            continue
        progress_type = turn.get("progress_type")
        normalized_turns.append(
            {
                **turn,
                "progress_type": _SPINE_PROGRESS_ALIASES.get(
                    str(progress_type).strip().casefold(), progress_type
                ),
            }
        )
    return {**payload, "turns": normalized_turns}


def _bind_story_spine(payload: dict[str, Any]) -> dict[str, Any]:
    draft = StorySpineDraftArtifact.model_validate(
        _normalize_spine_progress_aliases(payload)
    )
    milestone_positions = spine_milestone_positions(len(draft.turns))
    return StorySpineArtifact(
        turns=[
            SpineTurn(
                id=f"turn-{index}",
                **turn.model_dump(mode="python"),
                milestones=[
                    milestone
                    for milestone, position in milestone_positions.items()
                    if position == index
                ],
            )
            for index, turn in enumerate(draft.turns, start=1)
        ],
        ending=draft.ending,
        open_questions=draft.open_questions,
        progress_types=list(dict.fromkeys(turn.progress_type for turn in draft.turns)),
    ).model_dump(mode="json")


def _bind_story_brief(
    payload: dict[str, Any],
    profile: NarrativeScaleProfile,
) -> dict[str, Any]:
    """Keep the model-authored promise while preserving the frozen Run scale."""

    draft = StoryBriefArtifact.model_validate(payload)
    return draft.model_copy(
        update={
            "length_envelope": LengthEnvelope(
                word_target_soft=profile.word_target_soft,
            )
        }
    ).model_dump(mode="json")


def _bind_volume_architecture(
    state: NarrativeRunState,
    payload: dict[str, Any],
) -> dict[str, Any]:
    draft = VolumeArchitectureDraftArtifact.model_validate(payload)
    proposals = (state.get("volume_boundary_proposal") or {}).get("proposals") or []
    if len(draft.volumes) != len(proposals):
        raise ValueError("Volumes must return exactly one contract for every validated boundary")
    return VolumeArchitectureArtifact(
        volumes=[
            VolumeContract(
                id=f"volume-{index}",
                turn_refs=list(proposal["turn_refs"]),
                **volume.model_dump(mode="python"),
            )
            for index, (volume, proposal) in enumerate(
                zip(draft.volumes, proposals), start=1
            )
        ]
    ).model_dump(mode="json")


__all__ = ["StageArtifactValidationError", "StageExecutor"]
