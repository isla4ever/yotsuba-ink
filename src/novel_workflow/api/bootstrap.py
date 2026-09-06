from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import FastAPI

from novel_workflow.knowledge import KnowledgeBase
from novel_workflow.orchestration.run_preflight import RunPreflightService
from novel_workflow.providers.registry import ProviderRegistry
from novel_workflow.runtime.graph.execution_service import NarrativeExecutionService
from novel_workflow.runtime.graph.provider_gateway import FrozenNarrativeProviderGateway
from novel_workflow.archive import Phase27ArchiveRunReader
from novel_workflow.orchestration.phase32_artifact_editing import (
    Phase32ArtifactEditingService,
)
from novel_workflow.orchestration.phase32_artifact_amendment import (
    Phase32ArtifactAmendmentService,
)
from novel_workflow.orchestration.phase32_amendment_branch import (
    Phase32AmendmentBranchService,
)
from novel_workflow.orchestration.phase32_continuity_acceptance import (
    Phase32ContinuityAcceptanceService,
)
from novel_workflow.orchestration.phase32_contract_repair import (
    Phase32ContractRepairService,
)
from novel_workflow.orchestration.phase32_creation_service import Phase32CreationService
from novel_workflow.orchestration.phase32_execution_service import Phase32RunExecutionService
from novel_workflow.orchestration.phase32_live_candidate_authorization import (
    Phase32LiveCandidateAuthorizationService,
)
from novel_workflow.orchestration.phase32_live_candidate_preflight import (
    Phase32LiveCandidatePreflightService,
)
from novel_workflow.orchestration.phase32_project_service import Phase32ProjectService
from novel_workflow.orchestration.phase32_release_evidence import (
    Phase32ReleaseEvidenceService,
)
from novel_workflow.orchestration.phase32_release_harness import Phase32ReleaseHarness
from novel_workflow.orchestration.phase32_writeback import Phase32WritebackService
from novel_workflow.providers.phase32_gateway import FrozenPhase32ProviderGateway
from novel_workflow.references import ReferenceStore, TavilySearchClient
from novel_workflow.storage.json_store import JsonStore
from novel_workflow.storage.project_store import ProjectStore
from novel_workflow.storage.phase32_creation_preparation_store import (
    Phase32CreationPreparationStore,
)
from novel_workflow.storage.phase32_artifact_draft_store import Phase32ArtifactDraftStore
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.phase32_artifact_amendment_store import (
    Phase32ArtifactAmendmentStore,
)
from novel_workflow.storage.phase32_amendment_branch_store import (
    Phase32AmendmentBranchStore,
)
from novel_workflow.storage.phase32_decision_receipt_store import (
    Phase32DecisionReceiptStore,
)
from novel_workflow.storage.phase32_contract_repair_store import (
    Phase32ContractRepairStore,
)
from novel_workflow.storage.phase32_event_projection import Phase32EventProjection
from novel_workflow.storage.phase32_run_repository import Phase32RunRepository
from novel_workflow.storage.phase32_story_bible_projection import (
    Phase32StoryBibleProjection,
)
from novel_workflow.storage.phase32_history_projection import Phase32HistoryProjection
from novel_workflow.storage.phase32_live_candidate_preflight_store import (
    Phase32LiveCandidatePreflightStore,
)
from novel_workflow.storage.phase32_project_catalog_store import Phase32ProjectCatalogStore
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationStore,
)
from novel_workflow.storage.phase32_provider_readiness_store import (
    Phase32ProviderReadinessStore,
)
from novel_workflow.storage.phase32_run_budget_store import Phase32RunBudgetStore
from novel_workflow.storage.phase32_quality_report_store import Phase32QualityReportStore
from novel_workflow.storage.phase32_release_evidence_store import (
    Phase32ReleaseEvidenceStore,
)
from novel_workflow.storage.phase32_evidence_store import Phase32EvidenceStore
from novel_workflow.storage.phase32_writeback_outbox import Phase32WritebackOutbox
from novel_workflow.memory.phase32_canon_store import Phase32CanonStore
from novel_workflow.memory.phase32_wiki_projection import Phase32WikiProjectionStore
from novel_workflow.storage.phase32_collaboration_store import (
    Phase32CollaborationStore,
)
from novel_workflow.storage.phase32_collaboration_context_store import (
    Phase32CollaborationContextStore,
)
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.cover_asset_store import CoverAssetStore
from novel_workflow.storage.collaboration_settings_store import CollaborationSettingsStore
from novel_workflow.storage.provider_profile_store import ProviderProfileStore
from novel_workflow.storage.provider_secret_store import ProviderSecretStore
from novel_workflow.storage.run_history_projection import RunHistoryProjection
from novel_workflow.workflows.schemas import PromptTemplate, ProviderProfile
from novel_workflow.workflows.templates import (
    default_prompt_templates,
    default_provider_profiles,
    official_workflows,
)
from novel_workflow.runtime.graph.phase32_driver import Phase32RouteDriver
from novel_workflow.usage.phase32_run_budget import Phase32RunBudgetAdmissionService


def init_app_state(app: FastAPI, data_dir: Path | None = None) -> None:
    root = data_dir or Path("runtime/novel_workflow")
    app.state.workflow_store = JsonStore(root / "workflows")
    app.state.provider_store = ProviderProfileStore(root / "provider_profiles.sqlite3")
    app.state.provider_secret_store = ProviderSecretStore(root / "provider_secrets.sqlite3")
    app.state.prompt_store = JsonStore(root / "prompts")
    app.state.reference_store = ReferenceStore(root / "references")
    app.state.reference_search = TavilySearchClient()
    app.state.knowledge_base = KnowledgeBase(root / "knowledge")
    app.state.collaboration_settings_store = CollaborationSettingsStore(
        root / "collaboration_settings"
    )
    app.state.providers = ProviderRegistry.from_env()
    seed_defaults(app)
    app.state.run_preflight = RunPreflightService(
        provider_store=app.state.provider_store,
        prompt_store=app.state.prompt_store,
        secret_store=app.state.provider_secret_store,
    )
    app.state.narrative_execution = NarrativeExecutionService(
        root / "native_runtime",
        lambda: FrozenNarrativeProviderGateway(
            app.state.provider_secret_store.get_api_key,
        ),
    )
    app.state.narrative_stores = app.state.narrative_execution.stores
    app.state.run_history = RunHistoryProjection(
        app.state.narrative_stores.runs,
        app.state.narrative_stores.exports,
        app.state.narrative_stores.chapters,
        app.state.narrative_stores.artifacts,
    )
    app.state.project_store = ProjectStore(
        root / "projects",
        workflow_store=app.state.workflow_store,
        run_history=app.state.run_history,
    )
    phase32_root = root / "phase32_runtime"
    app.state.phase32_run_repository = Phase32RunRepository(phase32_root)
    app.state.phase32_history_projection = Phase32HistoryProjection(
        app.state.phase32_run_repository
    )
    app.state.phase32_event_projection = Phase32EventProjection(
        app.state.phase32_run_repository
    )
    app.state.phase32_artifact_store = Phase32ArtifactStore(phase32_root / "artifacts")
    app.state.phase32_cover_assets = CoverAssetStore(phase32_root / "cover_assets")
    app.state.phase32_exports = ExportStore(phase32_root / "exports")
    app.state.phase32_artifact_drafts = Phase32ArtifactDraftStore(
        phase32_root / "artifact_drafts"
    )
    app.state.phase32_artifact_editing = Phase32ArtifactEditingService(
        app.state.phase32_run_repository,
        app.state.phase32_artifact_store,
        app.state.phase32_artifact_drafts,
    )
    app.state.phase32_artifact_amendments = Phase32ArtifactAmendmentStore(
        phase32_root / "artifact_amendments"
    )
    app.state.phase32_artifact_amendment_service = Phase32ArtifactAmendmentService(
        app.state.phase32_run_repository,
        app.state.phase32_artifact_store,
        app.state.phase32_artifact_amendments,
    )
    app.state.phase32_provider_inputs = Phase32ProviderInputStore(
        phase32_root / "artifacts" / ".provider_inputs"
    )
    app.state.phase32_provider_operations = Phase32ProviderOperationStore(
        phase32_root / "artifacts" / ".provider_operations",
        provider_inputs=app.state.phase32_provider_inputs,
    )
    app.state.phase32_creation_preparations = Phase32CreationPreparationStore(
        phase32_root / "preparations"
    )
    app.state.phase32_creation_service = Phase32CreationService(
        repository=app.state.phase32_run_repository,
        preparations=app.state.phase32_creation_preparations,
        provider_reader=lambda: list_provider_profiles(app),
        legacy_project_exists=_legacy_project_exists(app),
    )
    app.state.phase32_provider_readiness_store = Phase32ProviderReadinessStore(
        phase32_root / "provider_readiness"
    )
    app.state.phase32_run_budget_store = Phase32RunBudgetStore(
        phase32_root / "run_budgets"
    )
    app.state.phase32_run_budget_admission = Phase32RunBudgetAdmissionService(
        app.state.phase32_run_budget_store,
        app.state.phase32_provider_operations,
    )
    app.state.phase32_live_candidate_preflight_store = (
        Phase32LiveCandidatePreflightStore(phase32_root / "live_candidate_preflight")
    )
    app.state.phase32_live_candidate_preflight = (
        Phase32LiveCandidatePreflightService(
            profiles=app.state.provider_store,
            store=app.state.phase32_live_candidate_preflight_store,
            secret_resolver=app.state.provider_secret_store.get_api_key,
        )
    )
    app.state.phase32_live_candidate_authorization = (
        Phase32LiveCandidateAuthorizationService(
            preflight=app.state.phase32_live_candidate_preflight,
            store=app.state.phase32_live_candidate_preflight_store,
        )
    )
    app.state.phase32_continuity_acceptance = Phase32ContinuityAcceptanceService(
        creation=app.state.phase32_creation_service,
        readiness=app.state.phase32_provider_readiness_store,
        budgets=app.state.phase32_run_budget_store,
        budget_admission=app.state.phase32_run_budget_admission,
        live_candidate_authorization=app.state.phase32_live_candidate_authorization,
        secret_resolver=app.state.provider_secret_store.get_api_key,
    )
    app.state.phase32_collaboration = Phase32CollaborationStore(
        phase32_root / "collaboration"
    )
    app.state.phase32_collaboration_contexts = Phase32CollaborationContextStore(
        phase32_root / "collaboration_contexts"
    )
    app.state.phase32_decisions = Phase32DecisionReceiptStore(
        phase32_root / "decisions"
    )
    app.state.phase32_provider_gateway = FrozenPhase32ProviderGateway(
        app.state.provider_secret_store.get_api_key
    )
    app.state.phase32_evidence = Phase32EvidenceStore(phase32_root / "evidence")
    app.state.phase32_canon = Phase32CanonStore(phase32_root / "canon")
    app.state.phase32_wiki = Phase32WikiProjectionStore(phase32_root / "wiki")
    app.state.phase32_writeback_outbox = Phase32WritebackOutbox(
        phase32_root / "outbox",
        canon=app.state.phase32_canon,
        wiki=app.state.phase32_wiki,
    )
    app.state.phase32_quality_reports = Phase32QualityReportStore(
        phase32_root / "quality_reports"
    )
    app.state.phase32_release_evidence_store = Phase32ReleaseEvidenceStore(
        phase32_root / "release_evidence"
    )
    app.state.phase32_release_evidence = Phase32ReleaseEvidenceService(
        repository=app.state.phase32_run_repository,
        readiness=app.state.phase32_provider_readiness_store,
        budgets=app.state.phase32_run_budget_store,
        provider_inputs=app.state.phase32_provider_inputs,
        provider_operations=app.state.phase32_provider_operations,
        artifacts=app.state.phase32_artifact_store,
        evidence=app.state.phase32_evidence,
        outbox=app.state.phase32_writeback_outbox,
        canon=app.state.phase32_canon,
        wiki=app.state.phase32_wiki,
        quality_reports=app.state.phase32_quality_reports,
        bundles=app.state.phase32_release_evidence_store,
    )
    app.state.phase32_writeback = Phase32WritebackService(
        artifacts=app.state.phase32_artifact_store,
        evidence=app.state.phase32_evidence,
        canon=app.state.phase32_canon,
        outbox=app.state.phase32_writeback_outbox,
        provider_inputs=app.state.phase32_provider_inputs,
        provider_operations=app.state.phase32_provider_operations,
        gateway=app.state.phase32_provider_gateway,
        text_operation_admission=app.state.phase32_continuity_acceptance,
    )
    app.state.phase32_story_bible = Phase32StoryBibleProjection(
        app.state.phase32_run_repository,
        app.state.phase32_artifact_store,
        app.state.phase32_evidence,
        app.state.phase32_canon,
        app.state.phase32_wiki,
        app.state.phase32_writeback_outbox,
    )
    app.state.phase32_execution_service = Phase32RunExecutionService(
        app.state.phase32_run_repository,
        checkpoint_root=phase32_root / "checkpoints",
        decisions=app.state.phase32_decisions,
        run_admission=app.state.phase32_continuity_acceptance.require_run,
        artifact_editing=app.state.phase32_artifact_editing,
        driver_factory=lambda _definition: Phase32RouteDriver(
            app.state.phase32_artifact_store,
            app.state.phase32_provider_gateway,
            provider_operations=app.state.phase32_provider_operations,
            provider_inputs=app.state.phase32_provider_inputs,
            cover_assets=app.state.phase32_cover_assets,
            exports=app.state.phase32_exports,
            writeback=app.state.phase32_writeback,
            text_operation_admission=app.state.phase32_continuity_acceptance,
        ),
    )
    app.state.phase32_contract_repair_store = Phase32ContractRepairStore(
        phase32_root / "contract_repairs"
    )
    app.state.phase32_contract_repairs = Phase32ContractRepairService(
        app.state.phase32_run_repository,
        app.state.phase32_artifact_store,
        app.state.phase32_provider_operations,
        app.state.phase32_contract_repair_store,
        app.state.phase32_execution_service,
    )
    app.state.phase32_release_harness = Phase32ReleaseHarness(
        continuity=app.state.phase32_continuity_acceptance,
        execution=app.state.phase32_execution_service,
        provider_operations=app.state.phase32_provider_operations,
        evidence=app.state.phase32_release_evidence,
        live_candidate_authorization=app.state.phase32_live_candidate_authorization,
    )
    app.state.phase32_project_catalog = Phase32ProjectCatalogStore(
        phase32_root / "projects"
    )
    app.state.phase32_amendment_branches = Phase32AmendmentBranchStore(
        phase32_root / "amendment_branches"
    )
    app.state.phase32_amendment_branch_service = Phase32AmendmentBranchService(
        app.state.phase32_run_repository,
        app.state.phase32_artifact_store,
        app.state.phase32_artifact_amendments,
        app.state.phase32_amendment_branches,
        app.state.phase32_project_catalog,
    )
    app.state.phase32_project_service = Phase32ProjectService(
        creation=app.state.phase32_creation_service,
        catalog=app.state.phase32_project_catalog,
        history=app.state.phase32_history_projection,
        artifacts=app.state.phase32_artifact_store,
    )
    # This root remains dormant until the Phase 32 persistence cutover can move
    # historical files once, without exposing the production Run repository.
    app.state.phase27_archive_reader = Phase27ArchiveRunReader(
        root / "archive" / "runs",
        root / "archive" / "events",
    )


def seed_defaults(app: FastAPI) -> None:
    # Official templates are code-owned. User templates and project workflows
    # in the same store remain untouched.
    for workflow in official_workflows():
        expected = workflow.model_dump()
        try:
            existing = app.state.workflow_store.read(workflow.id)
            if _workflow_digest(existing) != _workflow_digest(expected):
                app.state.workflow_store.write(workflow.id, expected)
        except FileNotFoundError:
            app.state.workflow_store.write(workflow.id, expected)

    for provider in default_provider_profiles():
        try:
            stored = ProviderProfile.model_validate(
                app.state.provider_store.read(provider.id)
            )
        except FileNotFoundError:
            app.state.provider_store.write(provider.id, provider.model_dump())
            continue
        missing_model_pricing = {
            model_id: pricing
            for model_id, pricing in provider.model_pricing.items()
            if model_id not in stored.model_pricing
        }
        if stored.template_id == provider.template_id and missing_model_pricing:
            app.state.provider_store.write(
                provider.id,
                stored.model_copy(
                    update={
                        "model_pricing": {
                            **stored.model_pricing,
                            **missing_model_pricing,
                        }
                    }
                ).model_dump(),
            )
    for prompt in default_prompt_templates():
        try:
            existing = app.state.prompt_store.read(prompt.id)
            if existing != prompt.model_dump():
                app.state.prompt_store.write(prompt.id, prompt.model_dump())
        except FileNotFoundError:
            app.state.prompt_store.write(prompt.id, prompt.model_dump())

    valid_prompt_ids = {prompt.id for prompt in default_prompt_templates()}
    for prompt in app.state.prompt_store.list():
        if prompt.get("id") not in valid_prompt_ids or prompt.get("stage_type") == "quality_gate":
            app.state.prompt_store.delete(str(prompt.get("id") or ""))

    refresh_provider_registry(app)


def _workflow_digest(payload: dict) -> str:
    """Canonical content digest for the seeded default workflow comparison."""
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def list_provider_profiles(app: FastAPI) -> list[ProviderProfile]:
    return [ProviderProfile.model_validate(item) for item in app.state.provider_store.list()]


def refresh_provider_registry(app: FastAPI) -> None:
    secret_store = getattr(app.state, "provider_secret_store", None)
    app.state.providers = ProviderRegistry.from_profiles(
        list_provider_profiles(app),
        secret_resolver=secret_store.get_api_key if secret_store is not None else None,
    )


def list_prompt_templates(app: FastAPI) -> list[PromptTemplate]:
    return [PromptTemplate.model_validate(item) for item in app.state.prompt_store.list()]


def _legacy_project_exists(app: FastAPI):
    """Keep the new Run root from attaching to an old ProjectRecord."""

    def exists(project_id: str) -> bool:
        try:
            app.state.project_store.get(project_id)
        except FileNotFoundError:
            return False
        return True

    return exists
