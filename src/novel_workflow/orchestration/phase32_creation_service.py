"""Prepare an immutable Phase 32 Run from the two-step creation wizard.

This module is deliberately a pre-execution boundary.  It compiles the
selected route, freezes scale/review/provider contracts, and persists the
definition through the native Phase 32 repository.  It never invokes a
Provider and never mutates the legacy project or Run stores.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from novel_workflow.storage.phase32_creation_preparation_store import (
    Phase32CreationPreparation,
    Phase32CreationPreparationStore,
    PreparationProfileKind,
    Phase32PreparationConflict as PreparationStoreConflict,
    derive_phase32_creation_identifiers,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase32RunRecord,
    Phase32RunRepository,
)
from novel_workflow.workflows.definition_schemas import ProviderProfile
from novel_workflow.workflows.frozen_route_contract import (
    canonical_digest,
    freeze_route_contract,
)
from novel_workflow.workflows.graph_run_definition import (
    GraphRunDefinition,
    freeze_contract_payload,
    freeze_graph_run_definition,
    freeze_phase32_scale_profile,
)
from novel_workflow.workflows.phase32_creation_wizard import (
    WorkflowCatalogEntry,
    WorkflowSelection,
    official_workflow_catalog,
    resolve_workflow_selection,
)
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_INPUTS_CONTRACT_REVISION,
    phase32_inputs_contract_id,
)
from novel_workflow.workflows.phase32_scale import (
    continuity_acceptance_scale_policy,
    freeze_continuity_acceptance_scale_profile,
    freeze_release_smoke_scale_profile,
    freeze_scale_profile,
    release_smoke_scale_policy,
)
from novel_workflow.workflows.phase32_provider_binding import (
    ProviderBindingError as Phase32ProviderBindingError,
    build_phase32_provider_bindings,
)
from novel_workflow.workflows.review_policy import OFFICIAL_REVIEW_POLICIES
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import official_creation_routes
from novel_workflow.workflows.workflow_ids import (
    OFFICIAL_LONG_NOVEL_WORKFLOW_ID,
    is_canonical_workflow_id,
)


class Phase32CreationError(ValueError):
    """Domain error mapped to a stable API error code."""

    code = "phase32_creation_invalid"


class Phase32CreationConflict(Phase32CreationError):
    code = "phase32_creation_conflict"


class Phase32WorkflowUnavailable(Phase32CreationError):
    code = "phase32_workflow_unavailable"


class CreationPreparationRequest(BaseModel):
    """HTTP/domain input for preparing one native Phase 32 Run."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    selection: WorkflowSelection
    idempotency_key: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$",
    )
    project_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$",
    )
    run_id: str | None = Field(
        default=None,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,239}$",
    )
    export_profile: str | None = Field(
        default=None,
        pattern=r"^[a-z][a-z0-9_.-]{1,79}$",
    )


@dataclass(frozen=True, slots=True)
class PreparedPhase32Run:
    preparation: Phase32CreationPreparation
    record: Phase32RunRecord
    reused: bool

    @property
    def definition(self) -> GraphRunDefinition:
        return self.record.definition


ProviderReader = Callable[[], Iterable[ProviderProfile | dict[str, Any]]]
LegacyProjectExists = Callable[[str], bool]
Clock = Callable[[], str]


class Phase32CreationService:
    """Compile and durably prepare a route Run with bounded recovery."""

    def __init__(
        self,
        *,
        repository: Phase32RunRepository,
        preparations: Phase32CreationPreparationStore,
        provider_reader: ProviderReader,
        legacy_project_exists: LegacyProjectExists | None = None,
        clock: Clock | None = None,
    ) -> None:
        self.repository = repository
        self.preparations = preparations
        self.provider_reader = provider_reader
        self.legacy_project_exists = legacy_project_exists or (lambda _project_id: False)
        self.clock = clock or _now

    def prepare(self, request: CreationPreparationRequest) -> PreparedPhase32Run:
        return self._prepare(request, profile_kind="production")

    def prepare_release_smoke(self, request: CreationPreparationRequest) -> PreparedPhase32Run:
        """Prepare an isolated release-smoke Run outside the HTTP wizard.

        The public creation API intentionally has no profile selector.  This
        explicit harness boundary is used only by the 0.1.0 acceptance run;
        its identifiers are namespaced so the result cannot be mistaken for a
        normal production Project.
        """

        if request.project_id and not request.project_id.startswith("release-smoke-"):
            raise Phase32CreationError(
                "Release smoke projects must use a release-smoke- project id"
            )
        if request.run_id and not request.run_id.startswith("release-smoke-"):
            raise Phase32CreationError(
                "Release smoke Runs must use a release-smoke- run id"
            )
        requested_target = request.selection.intent.requested_target
        if requested_target is not None:
            release_smoke_scale_policy(
                request.selection.intent.creation_route_id
            ).validate_target(requested_target)
        return self._prepare(request, profile_kind="release_smoke")

    def prepare_continuity_acceptance(
        self,
        request: CreationPreparationRequest,
    ) -> PreparedPhase32Run:
        """Prepare the private exact-12 long-novel continuity Run.

        This domain-only entry point deliberately accepts only the canonical
        official long-novel workflow.  The public creation request has no
        profile selector, so a client cannot opt into this acceptance scope.
        """

        if request.idempotency_key is None:
            raise Phase32CreationError(
                "Continuity acceptance requires an explicit idempotency key"
            )
        selection = request.selection
        if selection.intent.creation_route_id != "long_novel":
            raise Phase32CreationError(
                "Continuity acceptance is private to the long_novel route"
            )
        if (
            selection.mode != "existing"
            or selection.workflow_id != OFFICIAL_LONG_NOVEL_WORKFLOW_ID
        ):
            raise Phase32CreationError(
                "Continuity acceptance requires the official.long_novel workflow"
            )
        if request.project_id and not request.project_id.startswith(
            "continuity-acceptance-"
        ):
            raise Phase32CreationError(
                "Continuity acceptance projects must use a continuity-acceptance- project id"
            )
        if request.run_id and not request.run_id.startswith(
            "continuity-acceptance-"
        ):
            raise Phase32CreationError(
                "Continuity acceptance Runs must use a continuity-acceptance- run id"
            )
        requested_target = selection.intent.requested_target
        if requested_target is not None:
            continuity_acceptance_scale_policy("long_novel").validate_target(
                requested_target
            )
        return self._prepare(request, profile_kind="continuity_acceptance")

    def _prepare(
        self,
        request: CreationPreparationRequest,
        *,
        profile_kind: PreparationProfileKind,
    ) -> PreparedPhase32Run:
        key = request.idempotency_key or f"prep-{uuid4().hex}"
        normalized = request.model_copy(update={"idempotency_key": key})
        request_payload = normalized.model_dump(mode="json")
        request_payload.pop("idempotency_key", None)
        request_digest = canonical_digest(
            {"profile_kind": profile_kind, "request": request_payload}
        )

        with self.preparations.transaction(key):
            try:
                existing = self.preparations.read(key)
            except FileNotFoundError:
                existing = None
            except PreparationStoreConflict as exc:
                raise Phase32CreationConflict(str(exc)) from exc
            if existing is not None:
                if (
                    existing.request_digest != request_digest
                    or existing.profile_kind != profile_kind
                ):
                    raise Phase32CreationConflict(
                        "Idempotency key 已用于另一组创建参数，请更换 key 或恢复原请求。"
                    )
                return self._recover_reserved(existing)

            derived_project_id, derived_run_id = derive_phase32_creation_identifiers(
                key,
                profile_kind,
            )
            project_id = normalized.project_id or derived_project_id
            run_id = normalized.run_id or derived_run_id
            self._reject_legacy_project(project_id)
            reserved = Phase32CreationPreparation(
                idempotency_key=key,
                request_digest=request_digest,
                request_payload=normalized.model_dump(mode="json"),
                project_id=project_id,
                run_id=run_id,
                created_at=self.clock(),
                status="reserved",
                profile_kind=profile_kind,
            )
            # Reserve first. If the process stops before repository.create(),
            # the stored request and timestamp let the next identical request
            # resume. Always freeze from the persisted winner: concurrent
            # callers may have observed different clocks.
            try:
                winner, reused = self.preparations.reserve_or_read(reserved)
            except PreparationStoreConflict as exc:
                raise Phase32CreationConflict(str(exc)) from exc
            if reused:
                if (
                    winner.request_digest != request_digest
                    or winner.profile_kind != profile_kind
                ):
                    raise Phase32CreationConflict(
                        "Idempotency key 已用于另一组创建参数，请更换 key 或恢复原请求。"
                    )
                return self._recover_reserved(winner)

            stored = CreationPreparationRequest.model_validate(winner.request_payload)
            try:
                definition = self._build_definition(
                    stored,
                    project_id=winner.project_id,
                    run_id=winner.run_id,
                    created_at=winner.created_at,
                    profile_kind=winner.profile_kind,
                )
            except ValidationError as exc:
                raise Phase32CreationError(
                    "Phase 32 Run definition could not be frozen from the selected configuration"
                ) from exc
            record = self._create_or_reuse_definition(definition)
            try:
                prepared = self.preparations.mark_prepared(
                    key,
                    definition_digest=record.definition.definition_digest,
                )
            except PreparationStoreConflict as exc:
                raise Phase32CreationConflict(str(exc)) from exc
            return PreparedPhase32Run(prepared, record, reused=False)

    def read(self, idempotency_key: str) -> PreparedPhase32Run:
        try:
            preparation = self.preparations.read(idempotency_key)
        except FileNotFoundError as exc:
            raise Phase32CreationError("Unknown Phase 32 creation preparation") from exc
        except PreparationStoreConflict as exc:
            raise Phase32CreationConflict(str(exc)) from exc
        except ValueError as exc:
            raise Phase32CreationError("Invalid Phase 32 creation preparation key") from exc
        try:
            record = self.repository.read(preparation.run_id)
        except FileNotFoundError as exc:
            raise Phase32CreationError(
                "Phase 32 preparation is reserved but its Run definition is not available"
            ) from exc
        if preparation.definition_digest and preparation.definition_digest != record.definition.definition_digest:
            raise Phase32CreationConflict("Preparation and Run definition digests differ")
        if preparation.status != "prepared":
            try:
                preparation = self.preparations.mark_prepared(
                    preparation.idempotency_key,
                    definition_digest=record.definition.definition_digest,
                )
            except PreparationStoreConflict as exc:
                raise Phase32CreationConflict(str(exc)) from exc
        return PreparedPhase32Run(preparation, record, reused=True)

    def _recover_reserved(
        self,
        preparation: Phase32CreationPreparation,
    ) -> PreparedPhase32Run:
        try:
            record = self.repository.read(preparation.run_id)
        except FileNotFoundError:
            stored = CreationPreparationRequest.model_validate(preparation.request_payload)
            # Current input was already compared by digest.  Use the original
            # reservation timestamp/ids so the definition digest is stable.
            try:
                definition = self._build_definition(
                    stored,
                    project_id=preparation.project_id,
                    run_id=preparation.run_id,
                    created_at=preparation.created_at,
                    profile_kind=preparation.profile_kind,
                )
            except ValidationError as exc:
                raise Phase32CreationError(
                    "Reserved Phase 32 Run definition could not be reconstructed"
                ) from exc
            record = self._create_or_reuse_definition(definition)
        if preparation.definition_digest and preparation.definition_digest != record.definition.definition_digest:
            raise Phase32CreationConflict("Preparation and Run definition digests differ")
        try:
            prepared = self.preparations.mark_prepared(
                preparation.idempotency_key,
                definition_digest=record.definition.definition_digest,
            )
        except PreparationStoreConflict as exc:
            raise Phase32CreationConflict(str(exc)) from exc
        return PreparedPhase32Run(prepared, record, reused=True)

    def _create_or_reuse_definition(self, definition: GraphRunDefinition) -> Phase32RunRecord:
        try:
            return self.repository.create(definition, updated_at=definition.created_at)
        except FileExistsError:
            try:
                existing = self.repository.read(definition.run_id)
            except Exception as exc:
                raise Phase32CreationConflict(
                    "Run id 已存在但无法读取其 Phase 32 定义。"
                ) from exc
            if existing.definition != definition:
                raise Phase32CreationConflict(
                    "Run id 已存在且其冻结定义与本次请求冲突。"
                )
            return existing

    def _build_definition(
        self,
        request: CreationPreparationRequest,
        *,
        project_id: str,
        run_id: str,
        created_at: str,
        profile_kind: PreparationProfileKind = "production",
    ) -> GraphRunDefinition:
        route_id = request.selection.intent.creation_route_id
        route = next(
            (item for item in official_creation_routes() if item.route_id == route_id),
            None,
        )
        if route is None:  # pragma: no cover - CreationIntent already restricts ids.
            raise Phase32CreationError(f"Unknown Phase 32 route: {route_id}")
        review_policy = OFFICIAL_REVIEW_POLICIES[route.default_review_policy_ref]
        manifest = RouteGraphCompiler().compile(route)
        route_contract = freeze_route_contract(manifest, review_policy)
        catalog_entry = self._resolve_workflow(request.selection)
        providers = self._provider_map()
        bindings = build_phase32_provider_bindings(
            route_id,
            manifest,
            None,
            providers,
            workflow_id=catalog_entry.workflow_id,
        )
        workflow_digest = catalog_entry.workflow_digest
        inputs_payload = {
            "creation_route_id": route_id,
            "creation_language": request.selection.intent.creation_language,
            "creation_kind": request.selection.intent.creation_kind,
            "novel_length_class": request.selection.intent.novel_length_class,
            "requested_target": request.selection.intent.requested_target,
            "creative_intent": request.selection.intent.creative_intent,
            "workflow_selection_mode": request.selection.mode,
            "workflow_id": catalog_entry.workflow_id,
            "workflow_revision": catalog_entry.revision,
            "workflow_digest": workflow_digest,
        }
        if profile_kind == "release_smoke":
            scale_profile = freeze_release_smoke_scale_profile(
                route_id,
                target=request.selection.intent.requested_target,
            )
        elif profile_kind == "continuity_acceptance":
            scale_profile = freeze_continuity_acceptance_scale_profile(
                route_id,
                target=request.selection.intent.requested_target,
            )
        else:
            scale_profile = freeze_scale_profile(
                route_id,
                target=request.selection.intent.requested_target,
            )
        return freeze_graph_run_definition(
            run_id=run_id,
            project_id=project_id,
            workflow_id=catalog_entry.workflow_id,
            workflow_revision=catalog_entry.revision,
            workflow_digest=workflow_digest,
            route_contract=route_contract,
            scale_profile=freeze_phase32_scale_profile(scale_profile),
            inputs=freeze_contract_payload(
                contract_id=phase32_inputs_contract_id(route_id),
                contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
                payload=inputs_payload,
            ),
            provider_bindings_by_stage=bindings,
            export_profile=request.export_profile or manifest.export_profiles[0],
            created_at=created_at,
        )

    def _resolve_workflow(
        self,
        selection: WorkflowSelection,
    ) -> WorkflowCatalogEntry:
        catalog = official_workflow_catalog()
        try:
            resolved = resolve_workflow_selection(selection, catalog)
        except ValueError as exc:
            raise Phase32WorkflowUnavailable(str(exc)) from exc
        if not is_canonical_workflow_id(resolved.workflow_id):
            raise Phase32WorkflowUnavailable("Only canonical official workflows may seed a Run")
        return resolved

    def _provider_map(self) -> dict[str, ProviderProfile]:
        profiles: dict[str, ProviderProfile] = {}
        for raw in self.provider_reader():
            try:
                profile = raw if isinstance(raw, ProviderProfile) else ProviderProfile.model_validate(raw)
            except ValidationError as exc:
                raise Phase32ProviderBindingError(
                    "Provider profile does not satisfy the binding contract"
                ) from exc
            if profile.id in profiles:
                raise Phase32ProviderBindingError(f"Duplicate Provider profile: {profile.id}")
            profiles[profile.id] = profile
        if not profiles:
            raise Phase32ProviderBindingError("No Provider profiles are available")
        return profiles

    def _reject_legacy_project(self, project_id: str) -> None:
        if self.legacy_project_exists(project_id):
            raise Phase32CreationConflict(
                "Phase 32 Run 不能挂到旧 ProjectRecord；请使用新的 Phase 32 project_id。"
            )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


__all__ = [
    "CreationPreparationRequest",
    "Phase32CreationError",
    "Phase32CreationConflict",
    "Phase32CreationService",
    "Phase32ProviderBindingError",
    "Phase32WorkflowUnavailable",
    "PreparedPhase32Run",
]
