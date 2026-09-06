from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from langgraph.checkpoint.memory import InMemorySaver

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ChapterArtifact,
    CoverArtifact,
    CoverBrief,
    CoverCandidate,
    CoverCandidateProposal,
    CoverProposal,
    ScreenplayBlock,
    ScreenplayDraftArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    BeatBoardArtifact,
    BeatBoardBeat,
    BookArchitectureArtifact,
    CharacterBibleArtifact,
    CharacterRecord,
    DetailChapterPlan,
    DetailPlanIndexArtifact,
    DetailScenePlan,
    DetailWindow,
    NovelBriefArtifact,
    PartContract,
    SceneDeckArtifact,
    SceneDeckScene,
    ScreenplayBriefArtifact,
    SectionPlanArtifact,
    SectionPlanUnit,
    StoryMapAnchor,
    StoryMapArtifact,
    VolumeArchitectureArtifact,
    VolumeContract,
)
from novel_workflow.providers.phase32_admission import (
    Phase32ProviderOperationAdmissionFence,
)
from novel_workflow.providers.phase32_contract import (
    Phase32CoverImageRequest,
    Phase32ProviderRequest,
    Phase32ProviderResponse,
    Phase32StageProviderBindingSnapshot,
)
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.runtime.graph.phase32_driver import (
    Phase32DriverError,
    Phase32RouteDriver,
)
from novel_workflow.runtime.graph.phase32_checkpointer import open_phase32_checkpointer
from novel_workflow.runtime.graph.phase32_cover_generation import Phase32CoverGenerator
from novel_workflow.runtime.graph.route_graph import RouteStageCandidate
from novel_workflow.runtime.graph.route_run_state import initial_route_run_state
from novel_workflow.runtime.graph.route_run_state import SequentialStageProgress
from novel_workflow.orchestration.phase32_graph_execution import Phase32GraphExecutionService
from novel_workflow.orchestration.phase32_run_fixture import create_phase32_run_fixture
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.storage.cover_asset_store import CoverAssetStore
from novel_workflow.storage.phase32_provider_input_store import Phase32ProviderInputStore
from novel_workflow.storage.phase32_provider_operation_store import (
    Phase32ProviderOperationStore,
)
from novel_workflow.workflows.graph_run_definition import (
    freeze_graph_run_definition,
    freeze_phase32_scale_profile,
)
from novel_workflow.workflows.phase32_scale import (
    freeze_continuity_acceptance_scale_profile,
)
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
    CreationRouteSpec,
)
from tests.fakes import fake_png_bytes
from tests.test_phase32_route_graph import _definition


class FakePhase32Gateway:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.requests: list[Phase32ProviderRequest] = []
        self.image_requests: list[Phase32CoverImageRequest] = []

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        return Phase32ProviderResponse(payload=self.payload)

    async def generate_cover_image(
        self,
        request: Phase32CoverImageRequest,
        *,
        binding,
    ) -> GeneratedImage:
        self.image_requests.append(request)
        return GeneratedImage(
            content=fake_png_bytes(seed=request.candidate_index),
            mime_type="image/png",
            provider_asset_id=f"fixture-cover-{request.candidate_index}",
            usage={"total_tokens": 1},
        )


class _TransportFlakyPhase32Gateway(FakePhase32Gateway):
    def __init__(self, payload: dict[str, object]) -> None:
        super().__init__(payload)
        self.failures_remaining = 1

    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        if self.failures_remaining:
            self.failures_remaining -= 1
            raise TimeoutError("simulated transport interruption")
        return Phase32ProviderResponse(payload=self.payload)


class _AdmissionDenied(ValueError):
    code = "phase32_run_budget_admission_denied"


class _RecordingTextOperationAdmission:
    def __init__(
        self,
        *,
        deny_run: bool = False,
        deny_operation: bool = False,
    ) -> None:
        self.deny_run = deny_run
        self.deny_operation = deny_operation
        self.required_definitions: list[object] = []
        self.admitted_requests: list[object] = []
        self.admitted_fences: list[Phase32ProviderOperationAdmissionFence] = []

    def require_run(self, definition) -> None:
        self.required_definitions.append(definition)
        if self.deny_run:
            raise _AdmissionDenied("run admission denied")

    def admit_text_operation(
        self,
        *,
        definition,
        request,
        binding,
        request_signature: str,
        max_transport_attempts: int,
    ) -> Phase32ProviderOperationAdmissionFence:
        self.admitted_requests.append(request)
        if self.deny_operation:
            raise _AdmissionDenied("operation admission denied")
        transport_attempt = 1 + sum(
            previous.operation_key == request.operation_key
            for previous in self.admitted_requests[:-1]
        )
        digest = hashlib.sha256(
            f"{request.operation_key}\0{transport_attempt}".encode("utf-8")
        ).hexdigest()
        fence = Phase32ProviderOperationAdmissionFence(
            authorization_ref=(
                "p32-run-budget-"
                + hashlib.sha256(definition.definition_digest.encode("utf-8")).hexdigest()
            ),
            run_id=definition.run_id,
            definition_digest=definition.definition_digest,
            operation_key=request.operation_key,
            request_signature=request_signature,
            admission_ref=f"p32-budget-admission-{digest}",
            transport_attempt=transport_attempt,
        )
        self.admitted_fences.append(fence)
        return fence


class _MismatchedTextOperationAdmission(_RecordingTextOperationAdmission):
    def __init__(self, identity_field: str) -> None:
        super().__init__()
        self.identity_field = identity_field

    def admit_text_operation(self, **kwargs) -> Phase32ProviderOperationAdmissionFence:
        fence = super().admit_text_operation(**kwargs)
        mismatches = {
            "operation_key": "another-operation",
            "run_id": "another-run",
            "request_signature": "f" * 64,
        }
        return fence.model_copy(
            update={self.identity_field: mismatches[self.identity_field]}
        )


def _continuity_acceptance_definition():
    base = _definition(LONG_NOVEL_ROUTE)
    return freeze_graph_run_definition(
        run_id="graph-long-novel-continuity",
        project_id=base.project_id,
        workflow_id=base.workflow_id,
        workflow_revision=base.workflow_revision,
        workflow_digest=base.workflow_digest,
        route_contract=base.route_contract,
        scale_profile=freeze_phase32_scale_profile(
            freeze_continuity_acceptance_scale_profile("long_novel")
        ),
        inputs=base.inputs,
        provider_bindings_by_stage=base.provider_bindings_by_stage,
        export_profile=base.export_profile,
        created_at=base.created_at,
    )


def _rolling_detail_payload_with_chapter_count(
    chapter_count: int,
) -> dict[str, object]:
    source_detail = DetailPlanIndexArtifact.model_validate(
        _payload_for("long_novel", "rolling_detail")
    )
    source_chapter = source_detail.windows[0].chapters[0]
    chapters = tuple(
        source_chapter.model_copy(
            update={
                "chapter_ref": f"chapter-{ordinal:02d}",
                "ordinal": ordinal,
                "title": f"证据链 {ordinal}",
                "scenes": tuple(
                    scene.model_copy(
                        update={"scene_ref": f"scene-{ordinal:02d}-{scene.ordinal:02d}"}
                    )
                    for scene in source_chapter.scenes
                ),
            }
        )
        for ordinal in range(1, chapter_count + 1)
    )
    return DetailPlanIndexArtifact(
        windows=(
            DetailWindow(
                window_ref="window-continuity-01",
                ordinal=1,
                volume_refs=("volume-1",),
                chapters=chapters,
                entry_state="主角开始核验第一份证据。",
                handoff="第十二章交付完整证据链。",
                next_window_entry_state="连续性验收窗口已经闭合。",
            ),
        )
    ).model_dump(mode="json")


def test_production_bootstrap_injects_phase32_writeback_into_the_only_driver() -> None:
    source = (
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/api/bootstrap.py"
    ).read_text(encoding="utf-8")

    assert "app.state.phase32_writeback = Phase32WritebackService(" in source
    assert "writeback=app.state.phase32_writeback" in source


def _brief_payload() -> dict[str, object]:
    return ScreenplayBriefArtifact(
        title="失序档案",
        sample_type="调查悬疑样片",
        target_minutes=12,
        premise="公共档案的签名链正在被有意抹除。",
        audience_promise="一部节奏克制、证据驱动的调查样片。",
        visible_conflict="主角必须在闭馆前证明签名页被替换。",
        ending_effect="被撕开的签名页在听证会上重新拼合。",
        tone="冷峻、克制、证据驱动",
    ).model_dump(mode="json")


@pytest.mark.asyncio
async def test_continuity_driver_requires_run_admission_before_input_or_receipt(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    gateway = FakePhase32Gateway(_payload_for("long_novel", "brief"))
    inputs = Phase32ProviderInputStore(tmp_path / "inputs")
    operations = Phase32ProviderOperationStore(
        tmp_path / "operations",
        provider_inputs=inputs,
    )
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"),
        gateway,
        provider_inputs=inputs,
        provider_operations=operations,
    )

    with pytest.raises(Phase32DriverError) as exc:
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )
    assert exc.value.code == "phase32_text_operation_admission_required"
    assert inputs.list(definition.run_id) == []
    assert operations.list(definition.run_id) == []
    assert gateway.requests == []


@pytest.mark.asyncio
async def test_continuity_driver_denies_operation_before_claim_and_gateway(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    gateway = FakePhase32Gateway(_payload_for("long_novel", "brief"))
    admission = _RecordingTextOperationAdmission(deny_operation=True)
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"),
        gateway,
        text_operation_admission=admission,
    )

    with pytest.raises(Phase32DriverError) as exc:
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )
    assert exc.value.code == "phase32_run_budget_admission_denied"
    receipts = driver.provider_operations.list(definition.run_id)
    assert len(admission.required_definitions) == 1
    assert len(admission.admitted_requests) == 1
    assert len(receipts) == 1
    assert receipts[0].status == "pending"
    assert receipts[0].transport_attempts == 0
    assert receipts[0].transport_admission_refs == ()
    assert gateway.requests == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "identity_field",
    ("operation_key", "run_id", "request_signature"),
)
async def test_continuity_driver_rejects_mismatched_admission_identity_before_gateway(
    tmp_path: Path,
    identity_field: str,
) -> None:
    definition = _continuity_acceptance_definition()
    gateway = FakePhase32Gateway(_payload_for("long_novel", "brief"))
    admission = _MismatchedTextOperationAdmission(identity_field)
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"),
        gateway,
        text_operation_admission=admission,
    )

    with pytest.raises(Phase32DriverError) as exc:
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )

    assert exc.value.code == "provider_transport_failed"
    receipts = driver.provider_operations.list(definition.run_id)
    assert len(receipts) == 1
    assert receipts[0].transport_attempts == 0
    assert receipts[0].transport_admission_refs == ()
    assert receipts[0].lease_owner == ""
    assert gateway.requests == []


@pytest.mark.asyncio
async def test_continuity_driver_replay_does_not_readmit_terminal_operation(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    gateway = FakePhase32Gateway(_payload_for("long_novel", "brief"))
    admission = _RecordingTextOperationAdmission()
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"),
        gateway,
        text_operation_admission=admission,
    )
    state = initial_route_run_state(definition)
    stage = definition.stage("brief")

    first = await driver.generate_stage(definition=definition, state=state, stage=stage)
    replay = await driver.generate_stage(definition=definition, state=state, stage=stage)

    assert replay == first
    assert len(admission.required_definitions) == 2
    assert len(admission.admitted_requests) == 1
    assert len(gateway.requests) == 1
    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.transport_admission_refs == (
        admission.admitted_fences[0].admission_ref,
    )


@pytest.mark.asyncio
async def test_continuity_driver_transport_retry_requests_a_new_admission(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    gateway = _TransportFlakyPhase32Gateway(_payload_for("long_novel", "brief"))
    admission = _RecordingTextOperationAdmission()
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts"),
        gateway,
        text_operation_admission=admission,
    )
    state = initial_route_run_state(definition)
    stage = definition.stage("brief")

    with pytest.raises(Phase32DriverError) as exc:
        await driver.generate_stage(definition=definition, state=state, stage=stage)
    assert exc.value.code == "provider_transport_failed"
    candidate = await driver.generate_stage(
        definition=definition,
        state=state,
        stage=stage,
    )

    assert candidate.artifact_ref
    assert len(admission.admitted_requests) == 2
    assert len(gateway.requests) == 2
    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.transport_attempts == 2
    assert receipt.transport_admission_refs == tuple(
        fence.admission_ref for fence in admission.admitted_fences
    )
    assert receipt.status == "succeeded"


@pytest.mark.asyncio
async def test_route_driver_freezes_request_and_persists_valid_candidate(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    state = initial_route_run_state(definition)
    gateway = FakePhase32Gateway(_brief_payload())
    driver = Phase32RouteDriver(Phase32ArtifactStore(tmp_path), gateway)
    stage = definition.stage("brief")

    candidate = await driver.generate_stage(
        definition=definition,
        state=state,
        stage=stage,
        direction="",
    )

    assert candidate.artifact_ref.startswith("p32-brief-candidate-")
    assert gateway.requests[0].operation_key.startswith(f"{definition.run_id}:brief:1:")
    assert gateway.requests[0].provider_profile_id == "phase32-fixture-provider"
    assert gateway.requests[0].rendered_prompt_digest
    assert gateway.requests[0].output_schema_digest
    assert gateway.requests[0].context["inputs"]["creative_intent"] == "graph fixture"
    assert gateway.requests[0].context["inputs"]["creation_language"] == "zh-CN"
    await driver.validate_stage(
        definition=definition,
        state=state,
        stage=stage,
        candidate=candidate,
    )
    committed = await driver.commit_stage(
        definition=definition,
        state=state,
        stage=stage,
        candidate=candidate,
    )
    assert committed.startswith("p32-brief-committed-")


@pytest.mark.asyncio
async def test_route_driver_rejects_provider_payload_for_wrong_stage(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    gateway = FakePhase32Gateway({"unexpected": "payload"})
    driver = Phase32RouteDriver(Phase32ArtifactStore(tmp_path), gateway)
    with pytest.raises(Phase32DriverError, match="Artifact payload"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )


@pytest.mark.asyncio
async def test_route_driver_rejects_brief_target_that_drifts_from_frozen_scale(
    tmp_path: Path,
) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    payload = _brief_payload()
    payload["target_minutes"] = 11
    gateway = FakePhase32Gateway(payload)
    driver = Phase32RouteDriver(Phase32ArtifactStore(tmp_path), gateway)

    with pytest.raises(Phase32DriverError, match="Artifact payload"):
        await driver.generate_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("brief"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"
    assert receipt.transport_attempts == 1


@pytest.mark.asyncio
async def test_route_driver_rejects_volume_refs_outside_committed_part_and_cast(
    tmp_path: Path,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path)
    architecture = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="book_architecture",
        artifact=BookArchitectureArtifact.model_validate(
            _payload_for("long_novel", "book_architecture")
        ),
    )
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact.model_validate(
            _payload_for("long_novel", "cast")
        ),
    )
    payload = _payload_for("long_novel", "volumes")
    payload["volumes"][0]["part_ref"] = "part-ghost"  # type: ignore[index]
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "book_architecture": architecture.artifact_ref,
                "cast": cast.artifact_ref,
            }
        }
    )

    with pytest.raises(Phase32DriverError, match="committed Part and Cast"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("volumes"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"
    assert receipt.transport_attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ("volume", "cast"))
async def test_route_driver_rejects_rolling_detail_refs_outside_committed_upstream(
    tmp_path: Path,
    mutation: str,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / mutation)
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact.model_validate(
            _payload_for("long_novel", "cast")
        ),
    )
    volumes = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="volumes",
        artifact=VolumeArchitectureArtifact.model_validate(
            _payload_for("long_novel", "volumes")
        ),
    )
    payload = _payload_for("long_novel", "rolling_detail")
    window = payload["windows"][0]  # type: ignore[index]
    chapter = window["chapters"][0]  # type: ignore[index]
    if mutation == "volume":
        window["volume_refs"] = ["volume-ghost"]  # type: ignore[index]
        window["chapters"] = [chapter]  # type: ignore[index]
        chapter["volume_ref"] = "volume-ghost"  # type: ignore[index]
    else:
        chapter["pov_subject_ref"] = "ghost"  # type: ignore[index]
        chapter["cast_subject_refs"] = ["ghost"]  # type: ignore[index]
        chapter["scenes"][0]["cast_subject_refs"] = ["ghost"]  # type: ignore[index]
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "volumes": volumes.artifact_ref,
            }
        }
    )

    with pytest.raises(Phase32DriverError, match="committed upstream"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("rolling_detail"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"
    assert receipt.transport_attempts == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("chapter_count", (8, 10, 11, 13))
async def test_route_driver_rejects_non_exact_continuity_acceptance_detail_scale(
    tmp_path: Path,
    chapter_count: int,
) -> None:
    definition = _continuity_acceptance_definition()
    store = Phase32ArtifactStore(tmp_path / f"chapters-{chapter_count}")
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact.model_validate(
            _payload_for("long_novel", "cast")
        ),
    )
    volumes = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="volumes",
        artifact=VolumeArchitectureArtifact.model_validate(
            _payload_for("long_novel", "volumes")
        ),
    )
    driver = Phase32RouteDriver(
        store,
        FakePhase32Gateway(_rolling_detail_payload_with_chapter_count(chapter_count)),
        text_operation_admission=_RecordingTextOperationAdmission(),
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "volumes": volumes.artifact_ref,
            }
        }
    )

    with pytest.raises(
        Phase32DriverError,
        match=rf"exactly 12 chapters in total; received {chapter_count}",
    ):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("rolling_detail"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"
    assert receipt.transport_attempts == 1


@pytest.mark.asyncio
async def test_route_driver_accepts_exact_12_chapter_continuity_detail_scale(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    store = Phase32ArtifactStore(tmp_path / "chapters-12")
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact.model_validate(
            _payload_for("long_novel", "cast")
        ),
    )
    volumes = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="volumes",
        artifact=VolumeArchitectureArtifact.model_validate(
            _payload_for("long_novel", "volumes")
        ),
    )
    driver = Phase32RouteDriver(
        store,
        FakePhase32Gateway(_rolling_detail_payload_with_chapter_count(12)),
        text_operation_admission=_RecordingTextOperationAdmission(),
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "volumes": volumes.artifact_ref,
            }
        }
    )

    candidate = await driver.generate_stage(
        definition=definition,
        state=state,
        stage=definition.stage("rolling_detail"),
    )

    artifact = DetailPlanIndexArtifact.model_validate(
        store.read(definition.run_id, candidate.artifact_ref).payload
    )
    assert tuple(len(window.chapters) for window in artifact.windows) == (12,)
    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "succeeded"
    assert receipt.transport_attempts == 1


@pytest.mark.asyncio
async def test_route_driver_rejects_two_volume_continuity_acceptance_window(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    store = Phase32ArtifactStore(tmp_path / "two-volume-window")
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact.model_validate(
            _payload_for("long_novel", "cast")
        ),
    )
    volumes = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="volumes",
        artifact=VolumeArchitectureArtifact.model_validate(
            _payload_for("long_novel", "volumes")
        ),
    )
    payload = _rolling_detail_payload_with_chapter_count(12)
    window = payload["windows"][0]  # type: ignore[index]
    window["volume_refs"] = ["volume-1", "volume-2"]  # type: ignore[index]
    for chapter in window["chapters"][6:]:  # type: ignore[index]
        chapter["volume_ref"] = "volume-2"
    driver = Phase32RouteDriver(
        store,
        FakePhase32Gateway(payload),
        text_operation_admission=_RecordingTextOperationAdmission(),
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "volumes": volumes.artifact_ref,
            }
        }
    )

    with pytest.raises(
        Phase32DriverError,
        match=r"exactly one single-volume window; received \(2,\)",
    ):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("rolling_detail"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"
    assert receipt.transport_attempts == 1


@pytest.mark.asyncio
async def test_continuity_acceptance_detail_must_plan_the_first_volume_prefix(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    store = Phase32ArtifactStore(tmp_path / "later-volume-window")
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact.model_validate(
            _payload_for("long_novel", "cast")
        ),
    )
    volumes = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="volumes",
        artifact=VolumeArchitectureArtifact.model_validate(
            _payload_for("long_novel", "volumes")
        ),
    )
    payload = _rolling_detail_payload_with_chapter_count(12)
    window = payload["windows"][0]  # type: ignore[index]
    window["volume_refs"] = ["volume-2"]  # type: ignore[index]
    for chapter in window["chapters"]:  # type: ignore[index]
        chapter["volume_ref"] = "volume-2"
    driver = Phase32RouteDriver(
        store,
        FakePhase32Gateway(payload),
        text_operation_admission=_RecordingTextOperationAdmission(),
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "volumes": volumes.artifact_ref,
            }
        }
    )

    with pytest.raises(
        Phase32DriverError,
        match="must plan the first Volume prefix volume-1",
    ):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("rolling_detail"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"


@pytest.mark.asyncio
async def test_continuity_acceptance_detail_covers_first_volume_cast_scope(
    tmp_path: Path,
) -> None:
    definition = _continuity_acceptance_definition()
    store = Phase32ArtifactStore(tmp_path / "first-volume-cast-coverage")
    secondary = CharacterRecord(
        subject_ref="witness",
        display_name="周警卫",
        role="档案馆保安",
        desire="按程序完成闭馆清场",
        stakes="违规放行会失去工作",
        constraints=("不能擅自放行",),
        voice="程序化短句",
        arc_scope="从执行规定到面对证据",
    )
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact(characters=(_character(), secondary)),
    )
    volume_artifact = VolumeArchitectureArtifact.model_validate(
        _payload_for("long_novel", "volumes")
    )
    first_volume = volume_artifact.volumes[0].model_copy(
        update={"cast_subject_refs": ("maya", "witness")}
    )
    volumes = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="volumes",
        artifact=volume_artifact.model_copy(
            update={"volumes": (first_volume, *volume_artifact.volumes[1:])}
        ),
    )
    driver = Phase32RouteDriver(
        store,
        FakePhase32Gateway(_rolling_detail_payload_with_chapter_count(12)),
        text_operation_admission=_RecordingTextOperationAdmission(),
    )
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "volumes": volumes.artifact_ref,
            }
        }
    )

    with pytest.raises(
        Phase32DriverError,
        match=r"does not cover the first Volume Cast scope: \['witness'\]",
    ):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("rolling_detail"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"


@pytest.mark.asyncio
@pytest.mark.parametrize("leak_level", ("chapter", "scene"))
async def test_rolling_detail_registered_names_require_local_cast_refs(
    tmp_path: Path,
    leak_level: str,
) -> None:
    definition = _definition(LONG_NOVEL_ROUTE)
    store = Phase32ArtifactStore(tmp_path / f"registered-name-{leak_level}")
    secondary = CharacterRecord(
        subject_ref="witness",
        display_name="周警卫",
        role="档案馆保安",
        desire="按程序完成闭馆清场",
        stakes="违规放行会失去工作",
        constraints=("不能擅自放行",),
        voice="程序化短句",
        arc_scope="从执行规定到面对证据",
    )
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="cast",
        artifact=CharacterBibleArtifact(characters=(_character(), secondary)),
    )
    volume_artifact = VolumeArchitectureArtifact.model_validate(
        _payload_for("long_novel", "volumes")
    )
    if leak_level == "scene":
        volume_artifact = volume_artifact.model_copy(
            update={
                "volumes": (
                    volume_artifact.volumes[0].model_copy(
                        update={"cast_subject_refs": ("maya", "witness")}
                    ),
                    *volume_artifact.volumes[1:],
                )
            }
        )
    volumes = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="long_novel",
        stage_id="volumes",
        artifact=volume_artifact,
    )
    payload = _payload_for("long_novel", "rolling_detail")
    chapter = payload["windows"][0]["chapters"][0]  # type: ignore[index]
    if leak_level == "chapter":
        chapter["dramatic_job"] = "周警卫要求主角交出证据。"
    else:
        chapter["cast_subject_refs"] = ["maya", "witness"]
        chapter["scenes"][0]["opposition"] = "周警卫要求主角立即离开。"
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "volumes": volumes.artifact_ref,
            }
        }
    )

    expected_boundary = "Chapter" if leak_level == "chapter" else "Scene"
    with pytest.raises(
        Phase32DriverError,
        match=rf"Detail {expected_boundary} .* names registered subjects outside its Cast scope",
    ):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("rolling_detail"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"


@pytest.mark.asyncio
async def test_route_driver_rejects_screenplay_speaker_outside_frozen_scene_cast(
    tmp_path: Path,
) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    store = Phase32ArtifactStore(tmp_path)
    cast = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="screenplay_sample",
        stage_id="cast",
        artifact=CharacterBibleArtifact(
            characters=(
                _character(),
                CharacterRecord(
                    subject_ref="guard",
                    display_name="周警卫",
                    role="档案馆保安",
                    desire="按程序完成闭馆清场",
                    stakes="违规放行会失去工作",
                    constraints=("不能擅自放行",),
                    voice="程序化短句",
                    arc_scope="从执行规定到面对证据",
                ),
            ),
        ),
    )
    scene_deck = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="screenplay_sample",
        stage_id="scene_deck",
        artifact=SceneDeckArtifact(
            scenes=(
                SceneDeckScene(
                    scene_ref="scene-1",
                    heading="INT. 档案室 - NIGHT",
                    location_and_time="闭馆前十分钟",
                    cast_subject_refs=("maya",),
                    visible_goal="找到被调换的签名页。",
                    opposition="闭馆时间正在逼近。",
                    outcome="玛雅取得带水印的复印件。",
                    soft_page_target=2.5,
                ),
            )
        ),
    )
    payload = ScreenplayDraftArtifact(
        scene_ref="scene-1",
        blocks=(
            ScreenplayBlock(kind="scene_heading", text="INT. 档案室 - NIGHT"),
            ScreenplayBlock(
                kind="dialogue",
                speaker_ref="guard",
                text="现在离开。",
            ),
        ),
    ).model_dump(mode="json")
    state = initial_route_run_state(definition).model_copy(
        update={
            "active_stage_id": "script",
            "active_unit_ref": "scene-1",
            "artifact_refs": {
                "cast": cast.artifact_ref,
                "scene_deck": scene_deck.artifact_ref,
            },
            "sequential_stage_progress": {
                "script": SequentialStageProgress(
                    ordered_unit_refs=("scene-1",),
                ).model_dump(mode="json")
            }
        }
    )
    driver = Phase32RouteDriver(store, FakePhase32Gateway(payload))

    with pytest.raises(Phase32DriverError, match="frozen Scene Deck and Cast"):
        await driver.generate_stage(
            definition=definition,
            state=state,
            stage=definition.stage("script"),
        )

    receipt = driver.provider_operations.list(definition.run_id)[0]
    assert receipt.status == "contract_rejected"
    assert receipt.transport_attempts == 1


@pytest.mark.asyncio
async def test_route_driver_builds_ordered_screenplay_delivery_without_provider(
    tmp_path: Path,
) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    store = Phase32ArtifactStore(tmp_path)
    brief = store.save_deterministic(
        run_id=definition.run_id,
        creation_route_id="screenplay_sample",
        stage_id="brief",
        artifact=ScreenplayBriefArtifact.model_validate(_brief_payload()),
    )
    scene_refs = ("scene-1", "scene-2", "scene-3")
    scripts = []
    for ordinal, scene_ref in enumerate(scene_refs, start=1):
        scripts.append(
            store.save_deterministic(
                run_id=definition.run_id,
                creation_route_id="screenplay_sample",
                stage_id="script",
                artifact=ScreenplayDraftArtifact(
                    scene_ref=scene_ref,
                    blocks=(
                        ScreenplayBlock(
                            kind="scene_heading",
                            text=f"INT. 档案室 {ordinal} - NIGHT",
                        ),
                        ScreenplayBlock(
                            kind="action",
                            text=f"Maya 完成第 {ordinal} 场的可见行动。",
                        ),
                    ),
                ),
            )
        )
    state = initial_route_run_state(definition).model_copy(
        update={
            "artifact_refs": {"brief": brief.artifact_ref},
            "sequential_stage_progress": {
                "script": SequentialStageProgress(
                    ordered_unit_refs=scene_refs,
                    committed_artifact_refs={
                        scene_ref: script.artifact_ref
                        for scene_ref, script in zip(scene_refs, scripts, strict=True)
                    },
                ).model_dump(mode="json")
            }
        }
    )
    driver = Phase32RouteDriver(store, FakePhase32Gateway({}))
    delivery_ref = await driver.commit_stage(
        definition=definition,
        state=state,
        stage=definition.stage("export"),
        candidate=RouteStageCandidate(),
    )
    delivery = store.read(definition.run_id, delivery_ref)
    assert delivery.artifact_kind == "script_delivery"
    assert delivery.payload["scene_refs"] == list(scene_refs)
    assert delivery.payload["scene_version_refs"] == [
        script.artifact_ref for script in scripts
    ]


@pytest.mark.asyncio
async def test_export_rejects_missing_selected_cover(tmp_path: Path) -> None:
    definition = _definition(SCREENPLAY_SAMPLE_ROUTE)
    driver = Phase32RouteDriver(Phase32ArtifactStore(tmp_path), FakePhase32Gateway({}))
    with pytest.raises(Phase32DriverError, match="every frozen Script scene"):
        await driver.commit_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("export"),
            candidate=RouteStageCandidate(),
        )


def _character() -> CharacterRecord:
    return CharacterRecord(
        subject_ref="maya",
        display_name="Maya",
        role="档案记者",
        desire="找出被删去的真相",
        stakes="失去职业与家人的信任",
        constraints=("不能公开未核实的证据",),
        voice="短句，先核对事实再表达",
        arc_scope="从旁观者变成承担后果的人",
    )


def _cover() -> CoverArtifact:
    return CoverArtifact(
        brief=CoverBrief(
            concept="冷色档案与一束被撕开的光",
            image_prompt="现代城市档案室，冷色胶片质感",
            palette=("深靛蓝", "银灰"),
        ),
        candidates=(
            CoverCandidate(
                asset_ref="asset-cover-1",
                alt_text="档案室中的单束顶光",
                visual_notes="主体留出标题安全区",
            ),
        ),
        selected_asset_ref="asset-cover-1",
    )


def _cover_proposal() -> CoverProposal:
    return CoverProposal(
        brief=CoverBrief(
            concept="冷色档案与一束被撕开的光",
            image_prompt="现代城市档案室，冷色胶片质感",
            palette=("深靛蓝", "银灰"),
        ),
        candidates=tuple(
            CoverCandidateProposal(
                alt_text=f"档案室封面候选 {index}",
                visual_notes=f"候选 {index} 为标题保留安全区",
                image_prompt=f"现代城市档案室，竖版封面构图，视觉方向 {index}",
            )
            for index in range(1, 4)
        ),
    )


@pytest.mark.asyncio
async def test_canonical_novel_cover_persists_brief_without_image_call(
    tmp_path: Path,
) -> None:
    definition = _definition(
        SHORT_NOVEL_ROUTE,
        workflow_id="official.short_novel",
    )
    gateway = FakePhase32Gateway(_cover_proposal().model_dump(mode="json"))
    store = Phase32ArtifactStore(tmp_path / "artifacts")
    driver = Phase32RouteDriver(store, gateway)
    state = initial_route_run_state(definition)
    stage = definition.stage("cover")

    candidate = await driver.generate_stage(
        definition=definition,
        state=state,
        stage=stage,
    )
    record = store.read(definition.run_id, candidate.artifact_ref)
    artifact = CoverArtifact.model_validate(record.payload)

    assert gateway.image_requests == []
    assert artifact.image_acceptance_status == "image_deferred"
    assert artifact.candidates == ()
    await driver.validate_stage(
        definition=definition,
        state=state,
        stage=stage,
        candidate=candidate,
    )
    committed = await driver.commit_stage(
        definition=definition,
        state=state,
        stage=stage,
        candidate=candidate,
    )
    assert committed
    assert gateway.image_requests == []


def _select_first_cover(
    store: Phase32ArtifactStore,
    *,
    run_id: str,
    route_id: str,
    candidate_ref: str,
) -> RouteStageCandidate:
    source = store.read(run_id, candidate_ref)
    cover = CoverArtifact.model_validate(source.payload)
    selected = cover.model_copy(
        update={"selected_asset_ref": cover.candidates[0].asset_ref}
    )
    record = store.save_candidate(
        run_id=run_id,
        creation_route_id=route_id,
        stage_id="cover",
        artifact=selected,
        source_operation_key=f"test-cover-selection:{candidate_ref}",
    )
    return RouteStageCandidate(artifact_ref=record.artifact_ref)


def _payload_for(route_id: str, stage_id: str) -> dict[str, object]:
    character = _character()
    if route_id == "screenplay_sample":
        values: dict[str, object] = {
            "brief": _brief_payload(),
            "cast": CharacterBibleArtifact(characters=(character,)).model_dump(mode="json"),
            "beat_board": BeatBoardArtifact(
                beats=(
                    BeatBoardBeat(
                        beat_ref="beat-1",
                        dramatic_job="让主角决定是否越权查档。",
                        visible_pressure="档案室即将关闭。",
                        character_decision="主角复制一份未授权记录。",
                        outcome="她留下了可追查的证据。",
                        setup_or_payoff_refs=("setup-signature-chain",),
                        timing_hint="约 90 秒",
                    ),
                    BeatBoardBeat(
                        beat_ref="beat-2",
                        dramatic_job="让越权调查转化为公开风险。",
                        visible_pressure="保安封锁出口并要求检查随身物品。",
                        character_decision="主角当面提交证据备份并拒绝交出原件。",
                        outcome="签名链进入正式记录，她也暴露为调查目标。",
                        setup_or_payoff_refs=("setup-signature-chain",),
                        timing_hint="约 120 秒",
                    ),
                )
            ).model_dump(mode="json"),
            "scene_deck": SceneDeckArtifact(
                scenes=(
                    SceneDeckScene(
                        scene_ref="scene-1",
                        heading="INT. 档案室 - NIGHT",
                        location_and_time="市档案馆，闭馆前十分钟",
                        cast_subject_refs=("maya",),
                        visible_goal="找到被调换的签名页。",
                        opposition="保安要求她离开。",
                        outcome="她带走一张带水印的复印件。",
                        soft_page_target=2.5,
                    ),
                )
            ).model_dump(mode="json"),
            "script": ScreenplayDraftArtifact(
                scene_ref="scene-1",
                blocks=(
                    ScreenplayBlock(kind="scene_heading", text="INT. 档案室 - NIGHT"),
                    ScreenplayBlock(kind="action", text="Maya 在关灯前翻开最后一页。"),
                ),
            ).model_dump(mode="json"),
        }
    elif route_id == "short_novel":
        values = {
            "brief": NovelBriefArtifact(
                title="失序档案",
                premise="一名记者追查一份被篡改的城市档案。",
                audience_promise="让读者看到真相代价。",
                theme_question="记录真相是否值得牺牲安全？",
                world_rules=("所有公共档案都有可追溯的签名。",),
                ending_direction="主角公开证据并承担代价。",
                narrative_voice="克制、具体、贴近现场",
                target_characters=20_000,
            ).model_dump(mode="json"),
            "story_map": StoryMapArtifact(
                opening_state="主角只相信公开档案。",
                story_question="谁在修改城市记忆？",
                anchors=(
                    StoryMapAnchor(
                        anchor_ref="anchor-1",
                        dramatic_job="建立档案被篡改的压力。",
                        pressure="关键记录在公开前消失。",
                        choice_or_revelation="主角决定追查签名链。",
                        consequence_or_open_effect="她被卷入机构内部调查。",
                        promise_refs=("promise-signature-chain",),
                    ),
                ),
                ending_state="真相公开，但主角失去原职。",
            ).model_dump(mode="json"),
            "cast": CharacterBibleArtifact(characters=(character,)).model_dump(mode="json"),
            "section_plan": SectionPlanArtifact(
                units=(
                    SectionPlanUnit(
                        unit_ref="unit-1",
                        ordinal=1,
                        title="签名链",
                        dramatic_job="让调查获得第一条可验证线索。",
                        pov_subject_ref="maya",
                        scene_load="档案室与走廊两场短场景。",
                        handoff="下一单元从复印件上的时间戳开始。",
                        soft_character_budget=3_000,
                        promise_refs=("promise-signature-chain",),
                    ),
                )
            ).model_dump(mode="json"),
            "text": ShortProseUnitArtifact(
                unit_ref="unit-1",
                unit_kind="section",
                title="签名链",
                pov_subject_ref="maya",
                content="Maya 先核对了签名，再把复印件放进证物袋。",
            ).model_dump(mode="json"),
            "cover": _cover_proposal().model_dump(mode="json"),
        }
    else:
        values = {
            "brief": NovelBriefArtifact(
                title="失序档案",
                premise="一名记者追查一份被篡改的城市档案。",
                audience_promise="让读者看到长期调查的真相代价。",
                theme_question="记录真相是否值得牺牲安全？",
                world_rules=("所有公共档案都有可追溯的签名。",),
                ending_direction="主角公开证据并承担长期代价。",
                narrative_voice="克制、具体、贴近现场",
                target_characters=150_000,
            ).model_dump(mode="json"),
            "book_architecture": BookArchitectureArtifact(
                book_promise="一场关于城市记忆的长期调查。",
                ending_conditions=("证据链公开且主角承担后果。",),
                parts=(
                    PartContract(
                        part_ref="part-1",
                        ordinal=1,
                        entry_state="主角开始调查。",
                        dramatic_question="她愿意承担多大代价？",
                        promise_refs=("promise-1",),
                        turning_point_refs=("turn-1",),
                        exit_state="她公开第一份证据。",
                    ),
                    PartContract(
                        part_ref="part-hearing",
                        ordinal=2,
                        entry_state="调查从机构内部转向公共听证。",
                        dramatic_question="她愿意为公开全部证据付出什么？",
                        promise_refs=("promise-1", "promise-cost"),
                        turning_point_refs=("turn-hearing", "turn-choice"),
                        exit_state="事实被承认，但主角失去原职。",
                        unresolved_obligations=(),
                    ),
                ),
            ).model_dump(mode="json"),
            "cast": CharacterBibleArtifact(characters=(character,)).model_dump(mode="json"),
            "volumes": VolumeArchitectureArtifact(
                volumes=(
                    VolumeContract(
                        volume_ref="volume-1",
                        ordinal=1,
                        part_ref="part-1",
                        promise="找到第一份原始档案。",
                        conflict="机构试图销毁备份。",
                        climax="主角在听证会上提交证据。",
                        closure="调查进入公众视野。",
                        cast_subject_refs=("maya",),
                        length_hint=40_000,
                    ),
                    VolumeContract(
                        volume_ref="volume-2",
                        ordinal=2,
                        part_ref="part-hearing",
                        promise="把第一份证据推进为可公开核验的完整签名链。",
                        conflict="证人安全与公开时限迫使主角作出不可逆选择。",
                        climax="主角公开自己的违规取证过程以保住证据可信度。",
                        closure="事实进入公共记录，主角也失去原有职业身份。",
                        cast_subject_refs=("maya",),
                        length_hint=55_000,
                    ),
                )
            ).model_dump(mode="json"),
            "rolling_detail": DetailPlanIndexArtifact(
                windows=(
                    DetailWindow(
                        window_ref="window-1",
                        ordinal=1,
                        volume_refs=("volume-1", "volume-2"),
                        chapters=(
                            DetailChapterPlan(
                                chapter_ref="chapter-1",
                                ordinal=1,
                                volume_ref="volume-1",
                                title="第一份证据",
                                pov_subject_ref="maya",
                                cast_subject_refs=("maya",),
                                dramatic_job="建立可公开核验的第一条证据链。",
                                entry_state="主角只有一张来源不明的复印件。",
                                scenes=(
                                    DetailScenePlan(
                                        scene_ref="scene-chapter-1-archive",
                                        ordinal=1,
                                        location="市档案馆修复室",
                                        time_context="闭馆前十分钟",
                                        cast_subject_refs=("maya",),
                                        goal="核对复印件的纸张水印。",
                                        opposition="值班员要求她立即离开。",
                                        outcome="她确认复印件来自封存卷宗。",
                                    ),
                                ),
                                conflict="离馆期限与证据核验互相冲突。",
                                stakes="失败会让复印件失去公开价值。",
                                exit_state="主角掌握可追溯到原卷宗的水印证据。",
                                hook="水印日期晚于官方封存日期。",
                                handoff="下一章追查异常封存日期。",
                                length_hint=3_000,
                            ),
                            DetailChapterPlan(
                                chapter_ref="chapter-2",
                                ordinal=2,
                                volume_ref="volume-2",
                                title="公开听证",
                                pov_subject_ref="maya",
                                cast_subject_refs=("maya",),
                                dramatic_job="把证据异常推进为公开回应。",
                                entry_state="异常封存日期已经进入议程。",
                                scenes=(
                                    DetailScenePlan(
                                        scene_ref="scene-chapter-2-hearing",
                                        ordinal=1,
                                        location="市政听证厅",
                                        time_context="公开听证开始后",
                                        cast_subject_refs=("maya",),
                                        goal="提交完整签名链。",
                                        opposition="主持人质疑违规取证。",
                                        outcome="主角公开取证过程换取证据入档。",
                                    ),
                                ),
                                conflict="证据可信度与职业安全发生冲突。",
                                stakes="公开过程会让主角失去原职。",
                                exit_state="证据进入公共记录，职业代价同时落地。",
                                hook="原始封存单在公开前被撤回。",
                                handoff="下一窗口进入证人保护与责任追查。",
                                length_hint=4_000,
                            ),
                        ),
                        entry_state="主角拿到复印件。",
                        handoff="下一窗口进入听证准备。",
                        next_window_entry_state="公众开始关注调查。",
                    ),
                )
            ).model_dump(mode="json"),
            "text": ChapterArtifact(
                chapter_ref="chapter-1",
                volume_ref="volume-1",
                title="第一份证据",
                pov_subject_ref="maya",
                content="她在听证前一夜重新整理了每个时间戳。",
            ).model_dump(mode="json"),
            "cover": _cover_proposal().model_dump(mode="json"),
        }
    return values[stage_id]  # type: ignore[return-value]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route",
    (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE),
    ids=lambda route: route.route_id,
)
async def test_route_driver_validates_and_commits_every_route_stage(
    tmp_path: Path,
    route: CreationRouteSpec,
) -> None:
    definition = _definition(route)
    store = Phase32ArtifactStore(tmp_path / route.route_id)
    gateway = FakePhase32Gateway({})
    driver = Phase32RouteDriver(store, gateway)
    state = initial_route_run_state(definition)
    for stage in definition.route_contract.route_manifest.stages:
        if stage.unitization == "sequential_units":
            unit_refs = driver.sequential_unit_refs(
                definition=definition,
                state=state,
                stage=stage,
            )
            state = state.model_copy(
                update={
                    "active_stage_id": stage.stage_id,
                    "active_unit_ref": unit_refs[0],
                    "sequential_stage_progress": {
                        stage.stage_id: SequentialStageProgress(
                            ordered_unit_refs=unit_refs,
                        ).model_dump(mode="json")
                    },
                }
            )
        if stage.provider_task_kind is None:
            committed_ref = await driver.commit_stage(
                definition=definition,
                state=state,
                stage=stage,
                candidate=RouteStageCandidate(),
            )
        else:
            while True:
                gateway.payload = _payload_for(route.route_id, stage.stage_id)
                if route.route_id == "long_novel" and stage.stage_id == "text":
                    detail = DetailPlanIndexArtifact.model_validate(
                        _payload_for("long_novel", "rolling_detail")
                    )
                    planned = next(
                        chapter
                        for window in detail.windows
                        for chapter in window.chapters
                        if chapter.chapter_ref == state.active_unit_ref
                    )
                    gateway.payload = ChapterArtifact(
                        chapter_ref=planned.chapter_ref,
                        volume_ref=planned.volume_ref,
                        title=planned.title,
                        pov_subject_ref=planned.pov_subject_ref,
                        content=f"{planned.title}的正文内容。",
                    ).model_dump(mode="json")
                candidate = await driver.generate_stage(
                    definition=definition,
                    state=state,
                    stage=stage,
                )
                await driver.validate_stage(
                    definition=definition,
                    state=state,
                    stage=stage,
                    candidate=candidate,
                )
                if stage.stage_id == "cover":
                    candidate = _select_first_cover(
                        store,
                        run_id=definition.run_id,
                        route_id=definition.creation_route_id,
                        candidate_ref=candidate.artifact_ref,
                    )
                committed_ref = await driver.commit_stage(
                    definition=definition,
                    state=state,
                    stage=stage,
                    candidate=candidate,
                )
                progress = state.sequential_progress(stage.stage_id)
                if progress is None:
                    break
                progress = progress.accept(
                    state.active_unit_ref,
                    committed_ref,
                )
                state = state.model_copy(
                    update={
                        "active_unit_ref": progress.next_unit_ref,
                        "sequential_stage_progress": {
                            stage.stage_id: progress.model_dump(mode="json")
                        },
                    }
                )
                if progress.complete:
                    break
        if stage.unitization != "sequential_units":
            state = state.model_copy(
                update={"artifact_refs": {**state.artifact_refs, stage.stage_id: committed_ref}}
            )
    expected_artifact_stages = set(definition.stage_ids) - (
        (
            {"script"}
            if route.route_id == "screenplay_sample"
            else {"text"}
            if route.route_id == "short_novel"
            else {"text"}
            if route.route_id == "long_novel"
            else set()
        )
    )
    assert set(state.artifact_refs) == expected_artifact_stages
    assert store.list(definition.run_id, status="committed")


class _FixtureGateway(FakePhase32Gateway):
    async def generate(
        self,
        request: Phase32ProviderRequest,
        *,
        binding,
    ) -> Phase32ProviderResponse:
        self.requests.append(request)
        if request.stage_id == "script":
            sequential = request.context.get("sequential_unit", {})
            current_scene = (
                sequential.get("current_scene", {})
                if isinstance(sequential, dict)
                else {}
            )
            return Phase32ProviderResponse(
                payload=ScreenplayDraftArtifact(
                    scene_ref=str(current_scene.get("scene_ref") or "scene-1"),
                    blocks=(
                        ScreenplayBlock(
                            kind="scene_heading",
                            text=str(
                                current_scene.get("heading")
                                or "INT. 档案室 - NIGHT"
                            ),
                        ),
                        ScreenplayBlock(
                            kind="action",
                            text="Maya 在关灯前翻开最后一页。",
                        ),
                    ),
                ).model_dump(mode="json")
            )
        if request.creation_route_id == "short_novel" and request.stage_id == "text":
            sequential = request.context.get("sequential_unit", {})
            current_unit = (
                sequential.get("current_unit", {})
                if isinstance(sequential, dict)
                else {}
            )
            return Phase32ProviderResponse(
                payload=ShortProseUnitArtifact(
                    unit_ref=str(current_unit.get("unit_ref") or "unit-1"),
                    unit_kind=str(sequential.get("unit_kind") or "section"),
                    title=str(current_unit.get("title") or "签名链"),
                    pov_subject_ref=str(
                        current_unit.get("pov_subject_ref") or "maya"
                    ),
                    content="玛雅先核对签名，再把带水印的复印件封入证物袋。",
                ).model_dump(mode="json")
            )
        if request.creation_route_id == "long_novel" and request.stage_id == "text":
            sequential = request.context.get("sequential_unit", {})
            current_chapter = (
                sequential.get("current_chapter", {})
                if isinstance(sequential, dict)
                else {}
            )
            return Phase32ProviderResponse(
                payload=ChapterArtifact(
                    chapter_ref=str(current_chapter.get("chapter_ref") or "chapter-1"),
                    volume_ref=str(current_chapter.get("volume_ref") or "volume-1"),
                    title=str(current_chapter.get("title") or "第一份证据"),
                    pov_subject_ref=str(
                        current_chapter.get("pov_subject_ref") or "maya"
                    ),
                    content=f"{current_chapter.get('title') or '第一份证据'}的正文内容。",
                ).model_dump(mode="json")
            )
        return Phase32ProviderResponse(
            payload=_payload_for(request.creation_route_id, request.stage_id)
        )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "route",
    (SCREENPLAY_SAMPLE_ROUTE, SHORT_NOVEL_ROUTE, LONG_NOVEL_ROUTE),
    ids=lambda route: route.route_id,
)
async def test_graph_execution_with_route_driver_reaches_export(
    tmp_path: Path,
    route: CreationRouteSpec,
) -> None:
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime" / route.route_id,
        route=route,
        run_id=f"integration-{route.route_id}",
        project_id=f"project-{route.route_id}",
        creative_intent="使用 fake Provider 验证 Phase 32 图、Artifact 和恢复边界。",
    )
    gateway = _FixtureGateway({})
    driver = Phase32RouteDriver(
        Phase32ArtifactStore(tmp_path / "artifacts" / route.route_id),
        gateway,
    )
    service = Phase32GraphExecutionService(fixture.repository)
    checkpointer = InMemorySaver()
    result = await service.step(
        fixture.definition.run_id,
        driver=driver,
        checkpointer=checkpointer,
    )
    decision_count = 0
    while result.interrupted:
        assert result.decision is not None
        decision_count += 1
        assert decision_count <= len(fixture.definition.stage_ids) + 8
        resume = {
            "decision_id": result.decision["decision_id"],
            "action": "accept",
            "domain_revision": result.decision["domain_revision"],
        }
        if result.decision["stage_id"] == "cover":
            selected = _select_first_cover(
                driver.artifact_store,
                run_id=fixture.definition.run_id,
                route_id=fixture.definition.creation_route_id,
                candidate_ref=result.decision["artifact_ref"],
            )
            resume["candidate_ref"] = selected.artifact_ref
        result = await service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
            resume=resume,
        )

    assert result.record.state.status == "completed"
    expected_artifact_stages = set(fixture.definition.stage_ids) - (
        (
            {"script"}
            if route.route_id == "screenplay_sample"
            else {"text"}
            if route.route_id == "short_novel"
            else {"text"}
            if route.route_id == "long_novel"
            else set()
        )
    )
    assert set(result.record.state.artifact_refs) == expected_artifact_stages
    if route.route_id == "screenplay_sample":
        progress = result.record.state.sequential_progress("script")
        assert progress is not None and progress.complete
    if route.route_id == "short_novel":
        progress = result.record.state.sequential_progress("text")
        assert progress is not None and progress.complete
    if route.route_id == "long_novel":
        progress = result.record.state.sequential_progress("text")
        assert progress is not None and progress.complete
        assert progress.ordered_unit_refs == ("chapter-1", "chapter-2")
    assert result.record.read_model.status == "completed"
    assert any(
        event.type == "export.ready"
        for event in fixture.repository.events(fixture.definition.run_id)
    )
    expected_requests = len(fixture.definition.route_contract.provider_stage_ids)
    if route.route_id == "long_novel":
        expected_requests += 1
    assert len(gateway.requests) == expected_requests
    assert len(gateway.image_requests) == (0 if route.route_id == "screenplay_sample" else 3)
    usage = driver.provider_operations.usage_summary(fixture.definition.run_id)
    assert result.record.read_model.provider_usage == usage
    assert usage.provider_operations == len(gateway.requests) + len(
        gateway.image_requests
    )


@pytest.mark.asyncio
async def test_phase32_checkpointer_reopens_and_resumes_pending_decision(
    tmp_path: Path,
) -> None:
    route = SHORT_NOVEL_ROUTE
    fixture = create_phase32_run_fixture(
        tmp_path / "runtime",
        route=route,
        run_id="durable-short-novel",
        project_id="project-durable-short-novel",
        creative_intent="验证 SQLite checkpoint 跨 context 恢复。",
    )
    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    gateway = _FixtureGateway({})
    driver = Phase32RouteDriver(artifact_store, gateway)
    first_service = Phase32GraphExecutionService(fixture.repository)
    async with open_phase32_checkpointer(tmp_path / "phase32") as checkpointer:
        first = await first_service.step(
            fixture.definition.run_id,
            driver=driver,
            checkpointer=checkpointer,
        )
    assert first.interrupted is True
    assert first.decision is not None
    assert first.record.read_model.checkpoint_id

    reopened_repository = type(fixture.repository)(fixture.repository.root)
    reopened_service = Phase32GraphExecutionService(reopened_repository)
    async with open_phase32_checkpointer(tmp_path / "phase32") as checkpointer:
        result = first
        resume_count = 0
        while result.interrupted:
            assert result.decision is not None
            resume_count += 1
            assert resume_count <= len(fixture.definition.stage_ids)
            resume = {
                "decision_id": result.decision["decision_id"],
                "action": "accept",
                "domain_revision": result.decision["domain_revision"],
            }
            if result.decision["stage_id"] == "cover":
                selected = _select_first_cover(
                    artifact_store,
                    run_id=fixture.definition.run_id,
                    route_id=fixture.definition.creation_route_id,
                    candidate_ref=result.decision["artifact_ref"],
                )
                resume["candidate_ref"] = selected.artifact_ref
            result = await reopened_service.step(
                fixture.definition.run_id,
                driver=driver,
                checkpointer=checkpointer,
                resume=resume,
            )

    assert result.record.state.status == "completed"
    assert result.record.read_model.status == "completed"
    assert len(gateway.requests) == len(fixture.definition.route_contract.provider_stage_ids)
    assert len(gateway.image_requests) == 3


@pytest.mark.asyncio
async def test_cover_images_recover_after_asset_write_without_recalling_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = _definition(SHORT_NOVEL_ROUTE)
    frozen_cover = next(
        entry for entry in definition.provider_bindings_by_stage if entry.stage_id == "cover"
    )
    stage_binding = Phase32StageProviderBindingSnapshot.model_validate(
        frozen_cover.binding.payload
    )
    assert stage_binding.image_execution is not None

    gateway = FakePhase32Gateway({})
    inputs = Phase32ProviderInputStore(tmp_path / "inputs")
    operations = Phase32ProviderOperationStore(
        tmp_path / "operations",
        provider_inputs=inputs,
    )
    assets = CoverAssetStore(tmp_path / "assets")
    generator = Phase32CoverGenerator(
        gateway=gateway,
        provider_operations=operations,
        provider_inputs=inputs,
        cover_assets=assets,
        lease_seconds=120,
        max_transport_attempts=3,
    )
    original_record_return = operations.record_return
    interrupted = False

    def interrupt_after_first_asset(**kwargs):
        nonlocal interrupted
        if str(kwargs.get("operation_key") or "").endswith(":image:1") and not interrupted:
            interrupted = True
            raise RuntimeError("simulated process exit after cover bytes were persisted")
        return original_record_return(**kwargs)

    monkeypatch.setattr(operations, "record_return", interrupt_after_first_asset)
    with pytest.raises(RuntimeError, match="simulated process exit"):
        await generator.materialize(
            definition=definition,
            proposal=_cover_proposal(),
            binding=stage_binding.image_execution,
            proposal_operation_key=f"{definition.run_id}:cover:1:proposal",
            generation_attempt=1,
        )

    assert len(gateway.image_requests) == 1
    persisted = assets.list(definition.run_id)
    assert len(persisted) == 1
    pending = operations.list(definition.run_id)[0]
    assert pending.status == "pending"
    operations.release_pending(
        run_id=definition.run_id,
        operation_key=pending.operation_key,
        request_signature=pending.request_signature,
        lease_owner=pending.lease_owner,
        diagnostic={"code": "simulated_process_exit"},
    )
    monkeypatch.setattr(operations, "record_return", original_record_return)

    cover = await generator.materialize(
        definition=definition,
        proposal=_cover_proposal(),
        binding=stage_binding.image_execution,
        proposal_operation_key=f"{definition.run_id}:cover:1:proposal",
        generation_attempt=1,
    )

    assert len(gateway.image_requests) == 3
    assert len(cover.candidates) == 3
    assert len({candidate.asset_ref for candidate in cover.candidates}) == 3
    records = assets.list(definition.run_id)
    assert len({record.sha256 for record in records}) == 3
    assert all(record.usage == {"total_tokens": 1} for record in records)
    assert all(receipt.status == "succeeded" for receipt in operations.list(definition.run_id))

    artifact_store = Phase32ArtifactStore(tmp_path / "artifacts")
    candidate = artifact_store.save_candidate(
        run_id=definition.run_id,
        creation_route_id="short_novel",
        stage_id="cover",
        artifact=cover,
        source_operation_key="test:cover:unselected",
    )
    driver = Phase32RouteDriver(
        artifact_store,
        gateway,
        provider_operations=operations,
        provider_inputs=inputs,
        cover_assets=assets,
    )
    with pytest.raises(Phase32DriverError, match="Cannot commit Artifact"):
        await driver.commit_stage(
            definition=definition,
            state=initial_route_run_state(definition),
            stage=definition.stage("cover"),
            candidate=RouteStageCandidate(artifact_ref=candidate.artifact_ref),
        )
