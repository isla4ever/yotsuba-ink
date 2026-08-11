from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from novel_workflow.output_contracts.artifacts_vnext import (
    ChapterArtifact,
    ChapterPlan,
    CharacterBibleArtifact,
    CoverArtifact,
    CoverBrief,
    DetailArtifact,
    ExportArtifact,
    ExportMetadata,
    OutlineArtifact,
    StoryBriefArtifact,
    StageId,
    VolumePlan,
    detail_obligation_ref_ids,
    required_summary_outcome_ids,
)
from novel_workflow.runtime.graph.provider_gateway import (
    CoverImageRequest,
    NarrativeProviderGateway,
    ProviderOperationError,
    StageGenerationRequest,
)
from novel_workflow.runtime.graph.context_compiler import NarrativeContextCompiler
from novel_workflow.runtime.graph.state import NarrativeRunState
from novel_workflow.providers.usage import normalize_provider_usage
from novel_workflow.storage.artifact_store import ArtifactRecord, ArtifactStore
from novel_workflow.storage.chapter_store import ChapterStore
from novel_workflow.storage.cover_asset_store import CoverAssetRecord, CoverAssetStore
from novel_workflow.storage.event_projection import EventProjection
from novel_workflow.storage.evidence_store import EvidenceStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.domain_outbox import DomainOutbox
from novel_workflow.storage.narrative_run_repository import NarrativeRunRepository, ProviderBinding
from novel_workflow.storage.operation_store import OperationStore


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
            return self.artifacts.save_candidate(
                run_id,
                stage_id,
                payload,
                source=f"deterministic:{operation_key}",
                **self._validation_refs(state, stage_id),
            )

        definition = self.runs.definition(run_id)
        binding = definition.provider_bindings.get(stage_id)
        if binding is None:
            raise ProviderOperationError(f"No frozen Provider binding for stage {stage_id}")
        unit_payloads: list[tuple[str, dict[str, Any]]] = []
        for unit_id, context in self.context_compiler().stage_units(state, stage_id):
            unit_operation_key = f"{operation_key}:{unit_id}" if unit_id else operation_key
            payload = await self._generate_stage_unit(
                run_id=run_id,
                stage_id=stage_id,
                attempt=attempt,
                operation_key=unit_operation_key,
                binding=binding,
                context=context,
                unit_id=unit_id,
            )
            unit_payloads.append((unit_id, payload))
        payload = _aggregate_stage_units(stage_id, unit_payloads)
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
        self.events.append(
            run_id,
            event_id=f"{operation_key}:candidate",
            type="artifact.candidate_ready",
            stage_id=stage_id,
            node_id=f"{stage_id}.generate_candidate",
            payload_ref=candidate.artifact_id,
        )
        return candidate

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
            raise ProviderOperationError.for_operation(
                operation_key, f"Provider operation already failed: {operation_key}"
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
                image = await self.provider.generate_cover_image(request)
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
        return NarrativeContextCompiler(self.runs, self.artifacts, self.chapters)

    def character_ids(self, state: NarrativeRunState) -> set[str]:
        return {item.id for item in self.character_bible(state).characters}

    def character_bible(self, state: NarrativeRunState) -> CharacterBibleArtifact:
        artifact_id = (state.get("artifact_refs") or {}).get("characters")
        if not artifact_id:
            raise ValueError("Character Bible must be committed before downstream execution")
        return CharacterBibleArtifact.model_validate(
            self.artifacts.read(state["run_id"], artifact_id).payload
        )

    def npc_slot_ids(self, state: NarrativeRunState) -> set[str]:
        return {item.id for item in self.character_bible(state).npc_slots}

    def detail(self, state: NarrativeRunState) -> DetailArtifact:
        artifact_id = (state.get("artifact_refs") or {}).get("detail")
        if not artifact_id:
            raise ValueError("Detail artifact must be committed before chapter execution")
        return DetailArtifact.model_validate(
            self.artifacts.read(state["run_id"], artifact_id).payload
        )

    def _validation_refs(self, state: NarrativeRunState, stage_id: StageId) -> dict[str, Any]:
        kwargs: dict[str, Any] = {}
        if stage_id in {"summary", "outline", "detail"}:
            kwargs["character_ids"] = self.character_ids(state)
        if stage_id == "summary":
            kwargs["required_outcome_character_ids"] = required_summary_outcome_ids(
                self.character_bible(state)
            )
        if stage_id in {"characters", "outline", "detail"}:
            plan = self.runs.definition(state["run_id"]).book_scale_plan
            total = plan.total_chapters
            kwargs["chapter_ids"] = {f"chapter-{number}" for number in range(1, total + 1)}
        if stage_id == "detail":
            kwargs["npc_slot_ids"] = self.npc_slot_ids(state)
            refs = state.get("artifact_refs") or {}
            story = StoryBriefArtifact.model_validate(
                self.artifacts.read(state["run_id"], refs["info"]).payload
            )
            outline = OutlineArtifact.model_validate(
                self.artifacts.read(state["run_id"], refs["outline"]).payload
            )
            kwargs["obligation_ref_ids"] = detail_obligation_ref_ids(
                story,
                self.character_bible(state),
                outline,
            )
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
            info_id = (state.get("artifact_refs") or {}).get("info")
            if not info_id:
                raise ValueError("Story Brief must be committed before export")
            kwargs["export_title"] = str(
                self.artifacts.read(state["run_id"], info_id).payload["title"]
            )
        return kwargs

    def _build_export(self, state: NarrativeRunState) -> dict[str, Any]:
        info_id = (state.get("artifact_refs") or {}).get("info")
        if not info_id:
            raise ValueError("Story Brief must be committed before export")
        info = self.artifacts.read(state["run_id"], info_id)
        detail = self.detail(state)
        chapter_refs = state.get("chapter_version_refs") or {}
        accepted = [chapter_refs[chapter.id] for chapter in detail.chapters]
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
                title=str(info.payload["title"]),
                author=preferences.author,
                version_note=preferences.version_note,
            ),
        ).model_dump(mode="json")

    def _accepted_version_ids(self, state: NarrativeRunState) -> list[str]:
        refs = state.get("chapter_version_refs") or {}
        return [refs[chapter.id] for chapter in self.detail(state).chapters]

    def _accepted_chapters(self, state: NarrativeRunState) -> list[ChapterArtifact]:
        detail = self.detail(state)
        refs = state.get("chapter_version_refs") or {}
        return [
            self.chapters.read(state["run_id"], chapter.id, refs[chapter.id]).artifact
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
    if stage_id == "outline":
        volumes = payload.get("volumes")
        if not isinstance(volumes, list) or len(volumes) != 1:
            raise ValueError("An Outline unit must return exactly one volume")
        volume = VolumePlan.model_validate(volumes[0])
        target = context["material"]["target_volume"]
        if volume.id != target["id"] or volume.chapter_window != target["chapter_window"]:
            raise ValueError("Outline unit does not match its frozen volume target")
    if stage_id == "detail":
        chapters = payload.get("chapters")
        if not isinstance(chapters, list):
            raise ValueError("A Detail unit must return a chapters array")
        validated = [ChapterPlan.model_validate(item) for item in chapters]
        target = context["material"]["target_chapters"]
        expected = [(item["id"], item["number"]) for item in target]
        actual = [(item.id, item.number) for item in validated]
        if actual != expected:
            raise ValueError("Detail unit must exactly match its frozen chapter targets")


def _aggregate_stage_units(
    stage_id: StageId,
    units: list[tuple[str, dict[str, Any]]],
) -> dict[str, Any]:
    if len(units) == 1 and not units[0][0]:
        return units[0][1]
    if stage_id == "outline":
        payload = {"volumes": [volume for _, unit in units for volume in unit["volumes"]]}
        return OutlineArtifact.model_validate(payload).model_dump(mode="json")
    if stage_id == "detail":
        payload = {"chapters": [chapter for _, unit in units for chapter in unit["chapters"]]}
        return DetailArtifact.model_validate(payload).model_dump(mode="json")
    raise ValueError(f"Stage {stage_id} does not support structured unit aggregation")


__all__ = ["StageExecutor"]
