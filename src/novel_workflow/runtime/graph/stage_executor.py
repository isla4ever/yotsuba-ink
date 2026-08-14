from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    ChapterArtifact,
    CharacterBibleArtifact,
    CharacterDossierBatch,
    CharacterRelationBatch,
    CharacterSubject,
    CoverArtifact,
    CoverBrief,
    DetailArtifact,
    DetailChapter,
    DetailSegmentArtifact,
    ExportArtifact,
    ExportMetadata,
    VolumeArchitectureArtifact,
    StoryBriefArtifact,
    RoleDemandProposalBatch,
    SpineTurn,
    StorySpineDraftArtifact,
    VolumeArchitectureDraftArtifact,
    VolumeBoundaryProposalBatch,
    StorySpineArtifact,
    StageId,
    VolumeContract,
)
from novel_workflow.runtime.graph.provider_gateway import (
    CoverImageRequest,
    NarrativeProviderGateway,
    ProposalGenerationRequest,
    ProviderOperationError,
    StageGenerationRequest,
)
from novel_workflow.runtime.graph.context_compiler import NarrativeContextCompiler
from novel_workflow.runtime.graph.output_budget import OutputBudgetPlanner
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.providers.errors import ProviderResponseError
from novel_workflow.providers.usage import normalize_provider_usage
from pydantic import ValidationError as PydanticValidationError
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
from novel_workflow.workflows.narrative_scale import DetailScaleProjection


class StageArtifactValidationError(ValueError):
    def __init__(self, operation_key: str, error: Exception) -> None:
        super().__init__(str(error))
        self.operation_key = operation_key


# Extra provider calls per unit when the model breaks the output contract
# (schema violation, JSON parse failure, truncation, cross-group name reuse).
# Transport and auth failures never trigger a repair round. Real DeepSeek runs
# showed one repair round is not always enough for semantic rules like name
# uniqueness, so allow two before declaring the run failed.
_UNIT_CONTRACT_ATTEMPTS = 3

_REPAIRABLE_PROVIDER_CODES = {
    "json_parse_failed",
    "output_truncated",
    "empty_content",
    "structured_empty_content",
}

# Cover image calls hit a second network path (gateway plus asset download), so a
# single transient blip must not kill an otherwise finished run.
_COVER_NETWORK_ATTEMPTS = 3

# Structured stage calls get the same tolerance for dropped connections and
# timeouts; contract repair rounds are counted separately.
_UNIT_NETWORK_ATTEMPTS = 3

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


def _contract_repair_note(error: BaseException) -> str:
    """Return the violation text when a unit failure is worth one repair retry."""
    depth = 0
    current: BaseException | None = error
    while current is not None and depth < 8:
        if isinstance(current, PydanticValidationError):
            return str(current)
        if isinstance(current, ProviderResponseError):
            return str(current) if current.code in _REPAIRABLE_PROVIDER_CODES else ""
        if isinstance(current, ProviderOperationError) and (
            "already failed" in str(current)
        ):
            # Replay of a session whose first attempt failed: run the repair
            # round so recovery can complete instead of re-raising forever.
            return str(current)
        if type(current) is ValueError:
            return str(current)
        current = current.__cause__
        depth += 1
    return ""


@dataclass(frozen=True, slots=True)
class StageExecutor:
    runs: NarrativeRunRepository
    artifacts: ArtifactStore
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
                previous_segment_handoff: dict[str, Any] | None = None
                detail_chapter_count = 0
                taken_cast_names: list[str] = []
                for unit_id, context in self.context_compiler().stage_units(state, stage_id):
                    if stage_id == "detail" and previous_segment_handoff is not None:
                        context["material"]["previous_segment_handoff"] = previous_segment_handoff
                        # Earlier segments may return more or fewer chapters
                        # than their soft target, so the planned start number
                        # is corrected against what actually exists.
                        context["material"]["scale_projection"] = {
                            **context["material"]["scale_projection"],
                            "chapter_number_start": detail_chapter_count + 1,
                        }
                    if stage_id == "cast" and taken_cast_names:
                        # Dossier groups run sequentially and cannot see each
                        # other; without this, later groups reinvent the same
                        # character names and the merged bible fails validation.
                        context["material"]["reserved_names"] = list(taken_cast_names)
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
                    unit_payloads.append((unit_id, payload))
                    if stage_id == "cast":
                        taken_cast_names.extend(
                            name
                            for item in (payload.get("subjects") or [])
                            if (name := str(item.get("name") or "").strip())
                        )
                    if stage_id == "detail":
                        segment = DetailSegmentArtifact.model_validate(payload)
                        last = segment.chapters[-1]
                        detail_chapter_count += len(segment.chapters)
                        previous_segment_handoff = {
                            "previous_ref": f"chapter-{detail_chapter_count}",
                            "unresolved": [last.handoff],
                        }
                payload = _aggregate_stage_units(stage_id, unit_payloads)
                if stage_id == "spine":
                    payload = _bind_story_spine(payload)
                if stage_id == "cast":
                    payload = await self._assemble_character_bible(
                        state,
                        payload,
                    )
                if stage_id == "volumes":
                    payload = _bind_volume_architecture(state, payload)
                if stage_id == "cover":
                    brief = CoverBrief.model_validate(payload)
                    assets = await self._generate_cover_assets(state, brief)
                    payload = CoverArtifact(
                        brief=brief,
                        selected_asset_id=(
                            assets[0].asset_id if definition.quality_mode == "fast" else ""
                        ),
                    ).model_dump(mode="json")

                kwargs = self._validation_refs(state, stage_id)
                candidate = self.artifacts.save_candidate(
                    run_id,
                    stage_id,
                    payload,
                    source=f"provider:{operation_key}",
                    **kwargs,
                )
            except ProviderOperationError:
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

    async def generate_role_demand_proposal(
        self,
        state: NarrativeRunState,
    ) -> dict[str, Any]:
        context = self.context_compiler().stage(state, "cast")
        result = await self._generate_proposal(
            state,
            proposal_type="role_demand",
            binding_stage="spine",
            context=context,
        )
        try:
            batch = RoleDemandProposalBatch.model_validate(result)
            spine = StorySpineArtifact.model_validate(context["material"]["story_spine"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Role demand proposal context or payload is invalid") from exc
        turn_ids = {turn.id for turn in spine.turns}
        unknown = {
            turn_ref
            for proposal in batch.proposals
            for turn_ref in proposal.active_turn_refs
            if turn_ref not in turn_ids
        }
        if unknown:
            raise ValueError(f"Role demand proposal references unknown spine turns: {sorted(unknown)}")
        demand_keys = [proposal.demand_key for proposal in batch.proposals]
        if len(demand_keys) != len(set(demand_keys)):
            raise ValueError("Role demand proposal keys must be unique")
        subject_refs = [
            {"id": f"subject-{index}", "demand_key": proposal.demand_key}
            for index, proposal in enumerate(batch.proposals, start=1)
        ]
        return {
            "role_demand_proposals": [item.model_dump(mode="json") for item in batch.proposals],
            "subject_refs": subject_refs,
        }

    async def generate_volume_boundary_proposal(
        self,
        state: NarrativeRunState,
    ) -> dict[str, Any]:
        context = self.context_compiler().stage(state, "volumes")
        result = await self._generate_proposal(
            state,
            proposal_type="volume_boundary",
            binding_stage="volumes",
            context=context,
        )
        try:
            batch = VolumeBoundaryProposalBatch.model_validate(result)
            spine = StorySpineArtifact.model_validate(context["material"]["story_spine"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Volume boundary proposal context or payload is invalid") from exc
        turn_ids = [turn.id for turn in spine.turns]
        refs = [turn_ref for proposal in batch.proposals for turn_ref in proposal.turn_refs]
        if refs != list(dict.fromkeys(refs)) or set(refs) != set(turn_ids):
            raise ValueError("Volume boundary proposal must cover every spine turn exactly once")
        keys = [proposal.boundary_key for proposal in batch.proposals]
        if keys != [f"boundary-{index}" for index in range(1, len(keys) + 1)]:
            raise ValueError("Volume boundary proposal keys must be deterministic and contiguous")
        return {"volume_boundary_proposal": {"proposals": [item.model_dump(mode="json") for item in batch.proposals]}}

    async def _assemble_character_bible(
        self,
        state: NarrativeRunState,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        dossiers = CharacterDossierBatch.model_validate(payload)
        subject_refs = state.get("subject_refs") or []
        if len(dossiers.subjects) != len(subject_refs):
            raise ValueError("Cast must return exactly one dossier for every preallocated subject ref")
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
            subjects.append(
                CharacterSubject(
                    id=str(subject_ref["id"]),
                    **dossier.model_dump(mode="python"),
                )
            )
        names = [subject.name.strip() for subject in subjects]
        duplicated = sorted({name for name in names if names.count(name) > 1})
        if duplicated:
            raise ValueError(
                "Character subjects must be distinct named characters; "
                f"duplicated names: {duplicated}"
            )
        relation_context = {
            "target": "cast.relations",
            "sources": self.context_compiler().stage(state, "cast")["sources"],
            "material": {
                "subjects": [item.model_dump(mode="json") for item in subjects],
            },
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
        return CharacterBibleArtifact(
            subjects=subjects,
            relations=relations.relations,
        ).model_dump(mode="json")

    async def _generate_proposal(
        self,
        state: NarrativeRunState,
        *,
        proposal_type: str,
        binding_stage: StageId,
        context: dict[str, Any],
    ) -> dict[str, Any]:
        run_id = state["run_id"]
        attempt = int((state.get("stage_attempts") or {}).get(binding_stage) or 1)
        operation_key = f"{run_id}:{proposal_type}:proposal:{attempt}"
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
            proposal_type=proposal_type,  # type: ignore[arg-type]
            binding=budget.bind(binding),
            context=planner.attach(context, budget),
        )
        receipt = self.operations.begin(
            run_id=run_id,
            operation_key=operation_key,
            kind=f"{proposal_type}_proposal",
            request_signature=_signature(request.model_dump(mode="json")),
            provider_profile_id=binding.provider_profile_id,
            model=binding.model,
        )
        if receipt.status == "failed":
            raise ProviderOperationError.for_operation(
                operation_key,
                f"Proposal operation already failed: {operation_key}",
            )
        if receipt.status == "succeeded":
            return receipt.result
        response = None
        try:
            response = await self.provider.generate_proposal(request)
        except Exception as exc:
            self.operations.fail(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                usage=response.usage if response is not None else getattr(exc, "usage", {}),
                diagnostic=response.diagnostic if response is not None else getattr(exc, "diagnostic", {}),
            )
            raise ProviderOperationError.for_operation(operation_key, exc) from exc
        self.operations.succeed(
            run_id,
            operation_key,
            response.payload,
            usage=response.usage,
            diagnostic=response.diagnostic,
        )
        return response.payload

    def stage_operation_keys(
        self,
        state: NarrativeRunState,
        stage_id: StageId,
    ) -> list[str]:
        attempt = int((state.get("stage_attempts") or {}).get(stage_id) or 1)
        base = f"{state['run_id']}:{stage_id}:generate:{attempt}"
        return [
            f"{base}:{unit_id}" if unit_id else base
            for unit_id, _ in self.context_compiler().stage_units(state, stage_id)
        ]

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
        repair_note = ""
        network_round = 0
        repair_round = 0
        while repair_round < _UNIT_CONTRACT_ATTEMPTS:
            unit_key = operation_key
            if network_round:
                unit_key = f"{unit_key}:net-{network_round}"
            if repair_round:
                unit_key = f"{unit_key}:repair-{repair_round}"
            unit_context = context if not repair_note else {
                **context,
                "contract_repair": {
                    "previous_attempt_error": repair_note[:2000],
                    "directive": (
                        "The previous attempt violated the output contract. Regenerate the "
                        "complete JSON object, fix exactly the reported violation, and follow "
                        "the supplied schema and counting rules strictly."
                    ),
                },
            }
            try:
                return await self._generate_stage_unit_once(
                    run_id=run_id,
                    stage_id=stage_id,
                    attempt=attempt,
                    operation_key=unit_key,
                    binding=binding,
                    context=unit_context,
                    unit_id=unit_id,
                )
            except ProviderOperationError as exc:
                # Structured planning calls ride the same network as prose and
                # cover calls; one dropped connection must not fail the run
                # when a fresh attempt can succeed.
                if (
                    _is_transient_network_error(exc)
                    and network_round < _UNIT_NETWORK_ATTEMPTS - 1
                ):
                    network_round += 1
                    await asyncio.sleep(2 * network_round)
                    continue
                if repair_round >= _UNIT_CONTRACT_ATTEMPTS - 1:
                    raise
                note = _contract_repair_note(exc)
                if not note:
                    raise
                repair_note = note
                repair_round += 1
        raise ProviderOperationError.for_operation(
            operation_key, "Stage unit generation exhausted contract repair attempts"
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
        receipt = self.operations.begin(
            run_id=run_id,
            operation_key=operation_key,
            kind="stage_generation_unit" if unit_id else "stage_generation",
            request_signature=_signature(request.model_dump(mode="json")),
            provider_profile_id=binding.provider_profile_id,
            model=binding.model,
        )
        if receipt.status == "failed":
            stored = receipt.error or {}
            raise ProviderOperationError.for_operation(
                operation_key,
                "Provider operation already failed: "
                f"{stored.get('type', '')}: {stored.get('message', operation_key)}",
            )
        if receipt.status == "succeeded":
            return receipt.result
        response = None
        try:
            response = await self.provider.generate_stage(request)
            payload = response.payload
            _validate_stage_unit(stage_id, unit_id, context, payload)
        except Exception as exc:
            self.operations.fail(
                run_id,
                operation_key,
                {"type": type(exc).__name__, "message": str(exc)},
                usage=response.usage if response is not None else getattr(exc, "usage", {}),
                diagnostic=response.diagnostic if response is not None else getattr(exc, "diagnostic", {}),
            )
            raise ProviderOperationError.for_operation(operation_key, exc) from exc
        self.operations.succeed(
            run_id,
            operation_key,
            payload,
            usage=response.usage,
            diagnostic=response.diagnostic,
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
            receipt = self.operations.begin(
                run_id=run_id,
                operation_key=operation_key,
                kind="cover_image_generation",
                request_signature=_signature(request.model_dump(mode="json")),
                provider_profile_id=binding.provider_profile_id,
                model=binding.model,
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
        return self.artifacts.read(state["run_id"], candidate_id)

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
            if not cover.selected_asset_id:
                raise ValueError("Cover must select one immutable candidate before commit")
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
        return self.context_compiler().stage(state, stage_id)

    def context_compiler(self) -> NarrativeContextCompiler:
        return NarrativeContextCompiler(
            self.runs, self.artifacts, self.chapters, canon=self.outbox.canon
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
        if not cover_id:
            raise ValueError("Export requires the committed Cover asset")
        self.cover_assets.read(state["run_id"], cover_id)
        preferences = self.runs.definition(state["run_id"]).export_preferences
        return ExportArtifact(
            format=preferences.format,
            chapter_version_ids=accepted,
            cover_asset_id=cover_id,
            metadata=ExportMetadata(
                title=str(brief_artifact.payload["title"]),
                author=preferences.author,
                version_note=preferences.version_note,
            ),
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


def _signature(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _cover_image_prompt(brief: CoverBrief) -> str:
    constraints = "\n".join(f"- {item}" for item in brief.negative_constraints)
    return (
        f"Concept: {brief.concept}\n"
        f"Image direction: {brief.image_prompt}\n"
        f"Palette: {', '.join(brief.palette)}\n"
        "Do not render letters, logos, watermarks, UI, borders, or mockup frames.\n"
        f"Additional exclusions:\n{constraints or '- none'}"
    )


def _validate_stage_unit(
    stage_id: StageId,
    unit_id: str,
    context: dict[str, Any],
    payload: dict[str, Any],
) -> None:
    if not unit_id:
        return
    if stage_id == "cast":
        dossiers = CharacterDossierBatch.model_validate(payload)
        expected = len(context["material"]["subject_refs"])
        if len(dossiers.subjects) != expected:
            raise ValueError(
                f"Cast unit returned {len(dossiers.subjects)} dossiers for "
                f"{expected} subject refs; return exactly one dossier per subject ref"
            )
        # Checked per unit so a name collision hits the contract repair loop
        # instead of failing the whole run at the merged-bible validation.
        names = [subject.name.strip() for subject in dossiers.subjects]
        reserved = {
            str(name).strip()
            for name in (context["material"].get("reserved_names") or [])
        }
        duplicated = sorted(
            {name for name in names if names.count(name) > 1 or name in reserved}
        )
        if duplicated:
            raise ValueError(
                "Cast unit reused character names that must stay unique across "
                f"the whole cast: {duplicated}; invent distinct new names"
            )
        return
    if stage_id == "volumes":
        draft = VolumeArchitectureDraftArtifact.model_validate(payload)
        expected = len(context["material"]["volume_boundaries"]["proposals"])
        if len(draft.volumes) != expected:
            raise ValueError(
                f"Volumes unit returned {len(draft.volumes)} contracts for "
                f"{expected} validated boundaries; return exactly one contract per boundary"
            )
        titles = [volume.title.strip() for volume in draft.volumes]
        if any(not title for title in titles):
            raise ValueError(
                "Volumes unit must give every volume a non-empty 2-12 character title"
            )
        if len(titles) != len(set(titles)):
            raise ValueError("Volumes unit reused a volume title; titles must be distinct")
        return
    if stage_id == "detail":
        segment = DetailSegmentArtifact.model_validate(payload)
        chapter_titles = [chapter.title.strip() for chapter in segment.chapters]
        if any(not title for title in chapter_titles):
            raise ValueError(
                "Detail unit must give every chapter a non-empty 2-12 character title"
            )
        if len(chapter_titles) != len(set(chapter_titles)):
            raise ValueError(
                "Detail unit reused a chapter title; titles must be distinct"
            )
        allowed = {item["id"] for item in context["material"]["selected_dossiers"]}
        unknown = {
            subject_id
            for chapter in segment.chapters
            for subject_id in chapter.cast_ids
        } - allowed
        if unknown:
            raise ValueError(f"Detail unit references subjects outside its volume: {sorted(unknown)}")
        scale = DetailScaleProjection.model_validate(
            context["material"]["scale_projection"]
        )
        if not (
            scale.chapter_min_reasonable
            <= len(segment.chapters)
            <= scale.chapter_max_reasonable
        ):
            raise ValueError(
                f"Detail unit returned {len(segment.chapters)} chapters outside its frozen reasonable range {scale.chapter_min_reasonable}-{scale.chapter_max_reasonable}"
            )
        budget = context.get("output_budget")
        scene_cap = budget.get("scene_cap") if isinstance(budget, dict) else None
        if isinstance(scene_cap, int) and any(
            len(chapter.scenes) > scene_cap for chapter in segment.chapters
        ):
            raise ValueError("Detail unit exceeds its frozen per-chapter scene capacity")


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
        payload = {"chapters": chapters}
        return DetailArtifact.model_validate(payload).model_dump(mode="json")
    raise ValueError(f"Stage {stage_id} does not support structured unit aggregation")


def _bind_story_spine(payload: dict[str, Any]) -> dict[str, Any]:
    draft = StorySpineDraftArtifact.model_validate(payload)
    return StorySpineArtifact(
        turns=[
            SpineTurn(id=f"turn-{index}", **turn.model_dump(mode="python"))
            for index, turn in enumerate(draft.turns, start=1)
        ],
        ending=draft.ending,
        open_questions=draft.open_questions,
        progress_types=draft.progress_types,
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
