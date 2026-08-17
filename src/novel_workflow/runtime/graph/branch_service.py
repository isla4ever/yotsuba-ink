from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from novel_workflow.memory.canon_store import CanonFact
from novel_workflow.output_contracts.artifacts_vnext import (
    STAGE_ORDER,
    CharacterBibleArtifact,
    DetailArtifact,
    StorySpineArtifact,
    StageId,
    VolumeArchitectureArtifact,
    validate_artifact_vnext,
)
from novel_workflow.runtime.graph.checkpoint_branch import (
    CheckpointBranchMode,
    CheckpointBranchError,
    build_checkpoint_branch_plan,
    copy_checkpoint_lineage,
    remap_run_identity,
)
from novel_workflow.runtime.graph.runtime import NarrativeRuntime
from novel_workflow.storage.artifact_store import ArtifactRecord
from novel_workflow.storage.narrative_run_repository import (
    BranchBindingOverride,
    BranchOrigin,
    CoverAssetBinding,
    ProviderBinding,
    RunReadModel,
)


class BranchConflictError(ValueError):
    pass


@dataclass(slots=True)
class NarrativeBranchService:
    runtime: NarrativeRuntime

    async def create(
        self,
        *,
        source_run_id: str,
        target_run_id: str,
        checkpoint_id: str,
        provider_binding_overrides: dict[StageId, ProviderBinding] | None = None,
        cover_asset_binding_override: CoverAssetBinding | None = None,
        binding_override: BranchBindingOverride | None = None,
        branch_mode: CheckpointBranchMode = "active_decision",
    ) -> RunReadModel:
        stores = self.runtime.stores
        if stores.runs.exists(target_run_id):
            raise BranchConflictError(f"Run already exists: {target_run_id}")
        source = stores.runs.definition(source_run_id)
        branch_plan = await build_checkpoint_branch_plan(
            self.runtime.checkpointer,
            source_thread_id=source_run_id,
            checkpoint_id=checkpoint_id,
            mode=branch_mode,
        )
        values = [dict(value) for value in branch_plan.frontier_values]
        if not any(values):
            raise CheckpointBranchError("Checkpoint has no narrative state")
        if any(
            _has_unresolved_domain_writeback(stores, source_run_id, value)
            for value in values
        ):
            raise CheckpointBranchError(
                "Cannot branch while Evidence or Domain Outbox reconciliation is pending"
            )
        source_projection = stores.runs.read(source_run_id)
        binding_stage = (
            _checkpoint_resume_stage(values)
            if branch_mode == "stage_boundary"
            else _checkpoint_stage(values)
        )
        current_stage_override_allowed = branch_mode == "stage_boundary" or (
            source_projection.checkpoint_id == checkpoint_id
            and source_projection.active_stage_id == binding_stage
            and bool(source_projection.pending_decisions)
            and source_projection.pending_decisions[0].get("type")
            == "stage_artifact_decision"
        )

        provider_bindings, cover_asset_binding = self._resolve_binding_overrides(
            source.provider_bindings,
            source.cover_asset_binding,
            values,
            provider_binding_overrides=provider_binding_overrides,
            cover_asset_binding_override=cover_asset_binding_override,
            binding_override=binding_override,
            binding_stage=binding_stage,
            current_stage_override_allowed=current_stage_override_allowed,
        )

        artifact_plan = self._plan_artifact_copy(source_run_id, values)
        operation_plan = self._plan_operation_receipt_copy(
            source_run_id,
            target_run_id,
            values,
        )

        stores.runs.create(
            run_id=target_run_id,
            project_id=source.project_id,
            workflow_id=source.workflow_id,
            workflow_revision=source.workflow_revision,
            workflow_digest=source.workflow_digest,
            quality_mode=source.quality_mode,
            inputs=source.inputs,
            scale_profile=source.scale_profile,
            provider_bindings=provider_bindings,
            cover_asset_binding=cover_asset_binding,
            export_preferences=source.export_preferences,
            branch_origin=BranchOrigin(
                source_run_id=source_run_id,
                source_checkpoint_id=checkpoint_id,
                frontier_mode=branch_mode,
                binding_override=binding_override,
            ),
        )
        stores.cover_assets.copy_run(source_run_id, target_run_id)
        self._copy_artifacts(target_run_id, artifact_plan)
        self._copy_context_manifests(source_run_id, target_run_id, values)
        chapter_versions = self._copy_chapters(source_run_id, target_run_id, values)
        evidence_map = self._copy_evidence(
            source_run_id,
            target_run_id,
            chapter_versions,
        )
        self._rebuild_canon(
            source_run_id,
            target_run_id,
            checkpoint_id,
            chapter_versions,
            evidence_map,
        )
        self._copy_operation_receipts(
            source_run_id,
            target_run_id,
            operation_plan,
        )
        await copy_checkpoint_lineage(
            self.runtime.checkpointer,
            source_thread_id=source_run_id,
            target_thread_id=target_run_id,
            checkpoint_id=checkpoint_id,
            plan=branch_plan,
        )
        projection = await self.runtime.refresh_projection(target_run_id)
        stores.events.append(
            target_run_id,
            event_id=f"{target_run_id}:branch-created",
            type="branch.created",
            stage_id=stores.runs.read(target_run_id).active_stage_id,
            node_id="branch_service",
            status=projection.status,
            payload={
                "source_run_id": source_run_id,
                "source_checkpoint_id": checkpoint_id,
                "frontier_mode": branch_mode,
                **(
                    {"binding_override": binding_override.model_dump(mode="json")}
                    if binding_override is not None
                    else {}
                ),
            },
            checkpoint_id=checkpoint_id,
        )
        if branch_mode == "active_decision":
            self._project_active_decision(target_run_id, projection)
        return stores.runs.read(target_run_id)

    def _resolve_binding_overrides(
        self,
        source_bindings: dict[StageId, ProviderBinding],
        source_cover_binding: CoverAssetBinding,
        values: list[dict[str, Any]],
        *,
        provider_binding_overrides: dict[StageId, ProviderBinding] | None,
        cover_asset_binding_override: CoverAssetBinding | None,
        binding_override: BranchBindingOverride | None,
        binding_stage: StageId,
        current_stage_override_allowed: bool,
    ) -> tuple[dict[StageId, ProviderBinding], CoverAssetBinding]:
        replacements = dict(provider_binding_overrides or {})
        override_stages = set(binding_override.stages if binding_override is not None else [])
        if override_stages != set(replacements):
            raise BranchConflictError(
                "Branch binding override metadata must match the replacement stages"
            )
        if binding_override is None and cover_asset_binding_override is not None:
            raise BranchConflictError("Cover binding override requires auditable metadata")
        if ("cover" in override_stages) != (cover_asset_binding_override is not None):
            raise BranchConflictError(
                "Cover stage override must replace both text and asset bindings"
            )
        if not override_stages:
            return dict(source_bindings), source_cover_binding

        checkpoint_index = STAGE_ORDER.index(binding_stage)
        allowed = {
            stage_id
            for stage_id in source_bindings
            if STAGE_ORDER.index(stage_id) > checkpoint_index
        }
        if current_stage_override_allowed:
            allowed.add(binding_stage)
        forbidden = override_stages - allowed
        if forbidden:
            raise BranchConflictError(
                "Cannot override bindings for completed or non-artifact checkpoint stages: "
                + ", ".join(
                    stage_id for stage_id in STAGE_ORDER if stage_id in forbidden
                )
            )

        merged = dict(source_bindings)
        merged.update(replacements)
        return merged, cover_asset_binding_override or source_cover_binding

    def _project_active_decision(
        self,
        target_run_id: str,
        projection: RunReadModel,
    ) -> None:
        if not projection.pending_decisions:
            raise BranchConflictError("Branch checkpoint lost its active decision")
        decision = dict(projection.pending_decisions[0])
        node_id = str(decision.get("node_id") or "")
        stage_id = node_id.partition(".")[0] or projection.active_stage_id
        artifact_ref = str(decision.get("artifact_ref") or "")
        decision_id = str(decision.get("decision_id") or "")
        chapter_id = str(decision.get("chapter_id") or "")
        if not artifact_ref or not decision_id or stage_id not in STAGE_ORDER:
            raise BranchConflictError("Branch decision projection is incomplete")
        stores = self.runtime.stores
        stores.events.append(
            target_run_id,
            event_id=f"{target_run_id}:branch-candidate:{artifact_ref}",
            type="artifact.candidate_ready",
            stage_id=stage_id,  # type: ignore[arg-type]
            node_id=f"{stage_id}.branch_candidate",
            chapter_id=chapter_id,
            payload_ref=artifact_ref,
            checkpoint_id=projection.checkpoint_id,
        )
        stores.events.append(
            target_run_id,
            event_id=f"{decision_id}:required",
            type="decision.required",
            stage_id=stage_id,  # type: ignore[arg-type]
            node_id=node_id,
            chapter_id=chapter_id,
            status="awaiting_decision",
            payload=decision,
            checkpoint_id=projection.checkpoint_id,
        )

    def _plan_artifact_copy(
        self,
        source_run_id: str,
        values: list[dict[str, Any]],
    ) -> list[tuple[ArtifactRecord, dict[str, Any]]]:
        refs: set[str] = set()
        for value in values:
            refs.update(str(item) for item in (value.get("artifact_refs") or {}).values())
            refs.update(
                str(item) for item in (value.get("candidate_artifact_refs") or {}).values()
            )
        records = [
            self.runtime.stores.artifacts.read(source_run_id, artifact_id)
            for artifact_id in refs
            if artifact_id
        ]
        order = {stage: index for index, stage in enumerate(STAGE_ORDER)}
        records.sort(key=lambda item: (order[item.stage_id], item.status, item.artifact_id))
        validation_sources: dict[StageId, ArtifactRecord] = {}
        for record in records:
            current = validation_sources.get(record.stage_id)
            if current is None or record.status == "committed":
                validation_sources[record.stage_id] = record

        character_record = validation_sources.get("cast")
        characters = (
            CharacterBibleArtifact.model_validate(character_record.payload)
            if character_record is not None
            else None
        )
        spine_record = validation_sources.get("spine")
        turn_ids = (
            {turn.id for turn in StorySpineArtifact.model_validate(spine_record.payload).turns}
            if spine_record is not None
            else None
        )
        volumes_record = validation_sources.get("volumes")
        volume_cast_ids = (
            {
                volume.id: set(volume.cast_ids)
                for volume in VolumeArchitectureArtifact.model_validate(
                    volumes_record.payload
                ).volumes
            }
            if volumes_record is not None
            else None
        )
        chapter_refs = {
            item.ref
            for record in validation_sources.values()
            if record.stage_id == "detail"
            for item in DetailArtifact.model_validate(record.payload).chapters
        }
        plan: list[tuple[ArtifactRecord, dict[str, Any]]] = []
        for record in records:
            kwargs: dict[str, Any] = {}
            if record.stage_id in {"volumes", "detail"}:
                if characters is None:
                    raise BranchConflictError(
                        f"Branch {record.stage_id} artifact has no frozen Character Bible"
                    )
                kwargs["subject_ids"] = {item.id for item in characters.subjects}
            if record.stage_id == "volumes" and turn_ids is not None:
                kwargs["turn_ids"] = turn_ids
            if record.stage_id == "detail" and chapter_refs:
                kwargs["chapter_refs"] = chapter_refs
            if record.stage_id == "detail":
                if volume_cast_ids is None:
                    raise BranchConflictError(
                        "Branch Detail artifact has no frozen Volume Architecture"
                    )
                kwargs["volume_cast_ids"] = volume_cast_ids
                kwargs["historical_subject_ids"] = {
                    item.id
                    for item in characters.subjects
                    if item.kind == "historical_record"
                }
            validate_artifact_vnext(record.stage_id, record.payload, **kwargs)
            plan.append((record, kwargs))
        return plan

    def _copy_artifacts(
        self,
        target_run_id: str,
        plan: list[tuple[ArtifactRecord, dict[str, Any]]],
    ) -> None:
        for record, kwargs in plan:
            writer = (
                self.runtime.stores.artifacts.commit
                if record.status == "committed"
                else self.runtime.stores.artifacts.save_candidate
            )
            cloned = writer(
                target_run_id,
                record.stage_id,
                record.payload,
                source=record.source,
                **kwargs,
            )
            if cloned.artifact_id != record.artifact_id:
                raise BranchConflictError("Artifact identity changed while creating branch")

    def _copy_chapters(
        self,
        source_run_id: str,
        target_run_id: str,
        values: list[dict[str, Any]],
    ) -> set[str]:
        refs: dict[str, str] = {}
        for value in values:
            refs.update(
                {
                    str(chapter_id): str(version_id)
                    for chapter_id, version_id in (value.get("chapter_version_refs") or {}).items()
                }
            )
        for chapter_id, version_id in refs.items():
            record = self.runtime.stores.chapters.read(
                source_run_id, chapter_id, version_id
            )
            self.runtime.stores.chapters.write(
                target_run_id, record.artifact.model_dump(mode="json")
            )
        return set(refs.values())

    def _copy_context_manifests(
        self,
        source_run_id: str,
        target_run_id: str,
        values: list[dict[str, Any]],
    ) -> None:
        refs = {
            str(value.get("context_manifest_ref") or "")
            for value in values
            if value.get("context_manifest_ref")
        }
        for manifest_id in sorted(refs):
            self.runtime.stores.context_manifests.copy(
                source_run_id=source_run_id,
                target_run_id=target_run_id,
                manifest_id=manifest_id,
            )

    def _copy_evidence(
        self,
        source_run_id: str,
        target_run_id: str,
        chapter_versions: set[str],
    ) -> dict[str, str]:
        mapping: dict[str, str] = {}
        for record in self.runtime.stores.evidence.list(source_run_id):
            if record.chapter_version_id not in chapter_versions:
                continue
            cloned = self.runtime.stores.evidence.write(
                run_id=target_run_id,
                chapter_id=record.chapter_id,
                chapter_version_id=record.chapter_version_id,
                kind=record.kind,
                claim=record.claim,
                spans=record.spans,
            )
            mapping[record.evidence_id] = cloned.evidence_id
        return mapping

    def _rebuild_canon(
        self,
        source_run_id: str,
        target_run_id: str,
        checkpoint_id: str,
        chapter_versions: set[str],
        evidence_map: dict[str, str],
    ) -> None:
        facts: list[CanonFact] = []
        for fact in self.runtime.stores.canon.facts(source_run_id):
            if fact.chapter_version_id not in chapter_versions:
                continue
            remapped_refs = [evidence_map[item] for item in fact.evidence_refs]
            facts.append(
                CanonFact(
                    fact_id=f"fact-{remapped_refs[0].removeprefix('evidence-')}",
                    claim=fact.claim,
                    evidence_refs=remapped_refs,
                    chapter_version_id=fact.chapter_version_id,
                )
            )
        if not facts:
            return
        suffix = hashlib.sha256(checkpoint_id.encode("utf-8")).hexdigest()[:16]
        transaction_id = f"branch-baseline-{suffix}"
        self.runtime.stores.canon.commit(target_run_id, transaction_id, facts)
        self.runtime.stores.wiki.project(target_run_id, transaction_id, facts)

    def _plan_operation_receipt_copy(
        self,
        source_run_id: str,
        target_run_id: str,
        values: list[dict[str, Any]],
    ) -> list[tuple[str, str]]:
        refs: set[str] = set()
        for value in values:
            refs.update(str(item) for item in value.get("pending_operation_refs") or [])
            refs.update(str(item) for item in value.get("review_operation_refs") or [])
        plan: list[tuple[str, str]] = []
        for operation_key in sorted(refs):
            receipt = self.runtime.stores.operations.read(
                source_run_id,
                operation_key,
            )
            if receipt.provider_input_ref:
                self.runtime.stores.operations.provider_inputs.read(
                    source_run_id,
                    receipt.provider_input_ref,
                )
            target_key = str(remap_run_identity(operation_key, source_run_id, target_run_id))
            plan.append((operation_key, target_key))
        return plan

    def _copy_operation_receipts(
        self,
        source_run_id: str,
        target_run_id: str,
        plan: list[tuple[str, str]],
    ) -> None:
        for operation_key, target_key in plan:
            self.runtime.stores.operations.copy_receipt(
                source_run_id=source_run_id,
                source_operation_key=operation_key,
                target_run_id=target_run_id,
                target_operation_key=target_key,
            )


def _has_unresolved_domain_writeback(
    stores: Any,
    run_id: str,
    value: dict[str, Any],
) -> bool:
    evidence_refs = set(value.get("pending_evidence_refs") or [])
    operation_id = str(value.get("pending_writeback_ref") or "")
    if not operation_id:
        return bool(evidence_refs)
    try:
        operation = stores.outbox.read(run_id, operation_id)
    except (FileNotFoundError, ValueError):
        return True
    if operation.status != "committed":
        return True
    committed_refs = {
        evidence_ref
        for fact in operation.facts
        for evidence_ref in fact.evidence_refs
    }
    return not evidence_refs.issubset(committed_refs)


def _checkpoint_stage(values: list[dict[str, Any]]) -> StageId:
    active = [
        stage_id
        for value in values
        if (stage_id := value.get("active_stage_id")) in STAGE_ORDER
    ]
    if not active:
        raise CheckpointBranchError("Checkpoint has no active narrative stage")
    return max(active, key=STAGE_ORDER.index)


def _checkpoint_resume_stage(values: list[dict[str, Any]]) -> StageId:
    statuses: dict[StageId, str] = {}
    for value in values:
        for stage_id, status in (value.get("stage_status") or {}).items():
            if stage_id in STAGE_ORDER:
                statuses[stage_id] = str(status)
    for stage_id in STAGE_ORDER:
        if statuses.get(stage_id) != "completed":
            return stage_id
    raise CheckpointBranchError("Checkpoint has no unfinished narrative stage")


__all__ = ["BranchConflictError", "NarrativeBranchService"]
