from __future__ import annotations

import json
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import pytest

from novel_workflow.storage import phase32_run_repository as repository_module

from novel_workflow.orchestration.phase32_run_fixture import (
    phase32_fixture_provider_bindings,
)
from novel_workflow.runtime.graph.route_run_state import (
    SequentialStageProgress,
    initial_route_run_state,
)
from novel_workflow.storage.phase32_run_repository import (
    Phase27ExecutionRejected,
    Phase32PersistenceError,
    Phase32RunRepository,
)
from novel_workflow.storage.route_run_event import create_route_run_event
from novel_workflow.storage.route_run_read_model import (
    ArtifactRefProjection,
    RunFailureProjection,
    initial_route_run_read_model,
)
from novel_workflow.workflows.frozen_route_contract import freeze_route_contract
from novel_workflow.workflows.graph_run_definition import (
    freeze_contract_payload,
    freeze_graph_run_definition,
)
from novel_workflow.workflows.phase32_language_contract import (
    PHASE32_CREATION_LANGUAGE,
    PHASE32_INPUTS_CONTRACT_REVISION,
    phase32_inputs_contract_id,
)
from novel_workflow.workflows.review_policy import SHORT_NOVEL_REVIEW_POLICY
from novel_workflow.workflows.route_compiler import RouteGraphCompiler
from novel_workflow.workflows.route_specs import SHORT_NOVEL_ROUTE


NOW = "2026-08-23T12:00:00+08:00"
requires_posix_flock = pytest.mark.skipif(
    repository_module.fcntl is None,
    reason="cross-process repository serialization requires POSIX flock",
)


def _definition(run_id: str = "run-short-novel"):
    route_contract = freeze_route_contract(
        RouteGraphCompiler().compile(SHORT_NOVEL_ROUTE),
        SHORT_NOVEL_REVIEW_POLICY,
    )
    bindings = phase32_fixture_provider_bindings(
        route_contract,
        workflow_id="workflow-short-novel",
    )
    return freeze_graph_run_definition(
        run_id=run_id,
        project_id="project-phase32-repository",
        workflow_id="workflow-short-novel",
        workflow_revision="route-r1",
        workflow_digest="b" * 64,
        route_contract=route_contract,
        scale_profile=freeze_contract_payload(
            contract_id="scale.short_novel",
            contract_revision="r1",
            payload={"target": 12_000},
        ),
        inputs=freeze_contract_payload(
            contract_id=phase32_inputs_contract_id("short_novel"),
            contract_revision=PHASE32_INPUTS_CONTRACT_REVISION,
            payload={
                "creation_language": PHASE32_CREATION_LANGUAGE,
                "creative_intent": "可重启冻结输入",
            },
        ),
        provider_bindings_by_stage=bindings,
        export_profile=route_contract.route_manifest.export_profiles[0],
        created_at=NOW,
    )


def _with_text_progress(record, progress: SequentialStageProgress):
    active_unit_ref = progress.next_unit_ref
    state = record.state.model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": active_unit_ref,
            "sequential_stage_progress": {
                "text": progress.model_dump(mode="json")
            },
        }
    )
    read_model = record.read_model.model_copy(
        update={
            "active_stage_id": "text",
            "active_unit_ref": active_unit_ref,
            "sequential_stage_progress": {"text": progress},
        }
    )
    return state, read_model


def _create_hard_exit_worker(root: str, run_id: str, stop_after_write: int) -> None:
    repository = Phase32RunRepository(Path(root))
    definition = _definition(run_id)
    original_write = repository_module.atomic_write_json
    writes = 0

    def write_then_exit(path: Path, value: dict[str, Any]) -> None:
        nonlocal writes
        original_write(path, value)
        if path.parent.name == f".{run_id}.staging":
            writes += 1
            if writes == stop_after_write:
                os._exit(73)

    repository_module.atomic_write_json = write_then_exit
    repository.create(definition, updated_at=NOW)


def _projection_hard_exit_worker(
    root: str,
    run_id: str,
    stop_after_write: int,
) -> None:
    repository = Phase32RunRepository(Path(root))
    record = repository.read(run_id)
    running_status = dict(record.state.stage_status)
    running_status["brief"] = "running"
    next_state = record.state.model_copy(
        update={"status": "running", "stage_status": running_status}
    )
    next_read_model = record.read_model.model_copy(
        update={
            "status": "running",
            "stage_status": running_status,
            "updated_at": "2026-08-23T12:01:00+08:00",
        }
    )
    original_write = repository_module.atomic_write_json
    writes = 0

    def write_then_exit(path: Path, value: dict[str, Any]) -> None:
        nonlocal writes
        original_write(path, value)
        if path.parent.name == f".{run_id}.projection.staging":
            writes += 1
            if writes == stop_after_write:
                os._exit(74)

    repository_module.atomic_write_json = write_then_exit
    repository.commit_projection(
        run_id,
        state=next_state,
        read_model=next_read_model,
    )


def _concurrent_projection_worker(
    root: str,
    run_id: str,
    marker: str,
    barrier: Any,
    result_queue: Any,
) -> None:
    repository = Phase32RunRepository(Path(root))
    record = repository.read(run_id)
    running_status = dict(record.state.stage_status)
    running_status["brief"] = "running"
    next_state = record.state.model_copy(
        update={"status": "running", "stage_status": running_status}
    )
    next_read_model = record.read_model.model_copy(
        update={
            "status": "running",
            "stage_status": running_status,
            "updated_at": marker,
        }
    )
    event = create_route_run_event(
        record.definition,
        event_id=f"event-{marker[-2:]}",
        sequence=1,
        occurred_at=marker,
        type="stage.started",
        stage_id="brief",
        status="running",
    )
    barrier.wait(timeout=20)
    try:
        repository.commit_projection_with_event(
            run_id,
            state=next_state,
            read_model=next_read_model,
            event=event,
        )
    except Exception as exc:
        result_queue.put(("error", marker, type(exc).__name__))
    else:
        result_queue.put(("committed", marker, ""))


def test_phase32_repository_round_trips_record_and_events(tmp_path: Path) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    state = initial_route_run_state(definition)
    read_model = initial_route_run_read_model(definition, updated_at=NOW)
    record = repository.create(definition, state=state, read_model=read_model)

    event = create_route_run_event(
        definition,
        event_id="event-brief-started",
        sequence=1,
        occurred_at=NOW,
        type="stage.started",
        stage_id="brief",
        status="running",
    )
    assert repository.append_event(event) == event
    assert repository.append_event(event) == event

    restored = repository.read(definition.run_id)
    assert restored == record
    assert repository.events(definition.run_id) == [event]
    assert repository.events(definition.run_id, after=1) == []
    assert repository.list_read_models() == [read_model]


@requires_posix_flock
@pytest.mark.parametrize("stop_after_write", (1, 2, 3))
def test_phase32_repository_recovers_create_after_hard_exit_at_each_staging_write(
    tmp_path: Path,
    stop_after_write: int,
) -> None:
    root = tmp_path / "native-runtime"
    run_id = f"run-create-exit-{stop_after_write}"
    process = mp.get_context("spawn").Process(
        target=_create_hard_exit_worker,
        args=(str(root), run_id, stop_after_write),
    )
    process.start()
    process.join(timeout=30)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    assert process.exitcode == 73

    repository = Phase32RunRepository(root)
    definition = _definition(run_id)
    assert repository.list_read_models() == []
    recovered = repository.create(definition)

    assert recovered.definition == definition
    if stop_after_write == 3:
        assert recovered.read_model.updated_at == NOW
    assert repository.read(run_id) == recovered
    assert repository.list_read_models() == [recovered.read_model]
    assert not (repository.runs_root / f".{run_id}.staging").exists()


def test_phase32_repository_rejects_linked_or_unknown_create_staging(
    tmp_path: Path,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    linked_definition = _definition("run-linked-staging")
    external = tmp_path / "external"
    external.mkdir()
    sentinel = external / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")
    linked_staging = repository.runs_root / f".{linked_definition.run_id}.staging"
    linked_staging.symlink_to(external, target_is_directory=True)

    with pytest.raises(Phase32PersistenceError, match="internal directory"):
        repository.create(linked_definition)
    assert sentinel.read_text(encoding="utf-8") == "keep"
    assert not repository.exists(linked_definition.run_id)

    unknown_definition = _definition("run-unknown-staging")
    unknown_staging = repository.runs_root / f".{unknown_definition.run_id}.staging"
    unknown_staging.mkdir()
    unknown = unknown_staging / "foreign.data"
    unknown.write_text("keep", encoding="utf-8")

    with pytest.raises(Phase32PersistenceError, match="unknown file"):
        repository.create(unknown_definition)
    assert unknown.read_text(encoding="utf-8") == "keep"
    assert not repository.exists(unknown_definition.run_id)


@requires_posix_flock
@pytest.mark.parametrize("stop_after_write", (1, 2))
def test_phase32_repository_discards_prejournal_projection_after_hard_exit(
    tmp_path: Path,
    stop_after_write: int,
) -> None:
    root = tmp_path / "native-runtime"
    repository = Phase32RunRepository(root)
    definition = _definition(f"run-projection-exit-{stop_after_write}")
    original = repository.create(definition, updated_at=NOW)
    process = mp.get_context("spawn").Process(
        target=_projection_hard_exit_worker,
        args=(str(root), definition.run_id, stop_after_write),
    )
    process.start()
    process.join(timeout=30)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
    assert process.exitcode == 74
    assert not repository._projection_journal_path(definition.run_id).exists()

    cold_repository = Phase32RunRepository(root)
    cold = cold_repository.read(definition.run_id)
    assert cold.state == original.state
    assert cold.read_model == original.read_model
    assert not (
        cold_repository.runs_root
        / f".{definition.run_id}.projection.staging"
    ).exists()

    running_status = dict(cold.state.stage_status)
    running_status["brief"] = "running"
    next_state = cold.state.model_copy(
        update={"status": "running", "stage_status": running_status}
    )
    next_read_model = cold.read_model.model_copy(
        update={
            "status": "running",
            "stage_status": running_status,
            "updated_at": "2026-08-23T12:01:00+08:00",
        }
    )
    committed = cold_repository.commit_projection(
        definition.run_id,
        state=next_state,
        read_model=next_read_model,
    )
    assert committed.state == next_state
    assert committed.read_model == next_read_model


def test_phase32_repository_rejects_unknown_projection_staging_without_mutating_run(
    tmp_path: Path,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition("run-unknown-projection-staging")
    original = repository.create(definition, updated_at=NOW)
    staging = repository.runs_root / f".{definition.run_id}.projection.staging"
    staging.mkdir()
    unknown = staging / "foreign.data"
    unknown.write_text("keep", encoding="utf-8")

    with pytest.raises(Phase32PersistenceError, match="unknown file"):
        repository.read(definition.run_id)

    assert unknown.read_text(encoding="utf-8") == "keep"
    assert json.loads(
        (repository.runs_root / definition.run_id / "state.json").read_text(
            encoding="utf-8"
        )
    ) == original.state.model_dump(mode="json")
    assert json.loads(
        (repository.runs_root / definition.run_id / "read_model.json").read_text(
            encoding="utf-8"
        )
    ) == original.read_model.model_dump(mode="json")


@requires_posix_flock
def test_phase32_repository_serializes_concurrent_projection_and_event_commit(
    tmp_path: Path,
) -> None:
    root = tmp_path / "native-runtime"
    repository = Phase32RunRepository(root)
    definition = _definition("run-concurrent-projection")
    repository.create(definition, updated_at=NOW)
    context = mp.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    markers = (
        "2026-08-23T12:01:01+08:00",
        "2026-08-23T12:01:02+08:00",
    )
    processes = [
        context.Process(
            target=_concurrent_projection_worker,
            args=(str(root), definition.run_id, marker, barrier, result_queue),
        )
        for marker in markers
    ]
    for process in processes:
        process.start()
    results = [result_queue.get(timeout=30) for _ in processes]
    for process in processes:
        process.join(timeout=30)
        if process.is_alive():
            process.terminate()
            process.join(timeout=5)
    assert [process.exitcode for process in processes] == [0, 0]

    committed = [result for result in results if result[0] == "committed"]
    rejected = [result for result in results if result[0] == "error"]
    assert len(committed) == 1
    assert len(rejected) == 1
    assert rejected[0][2] == "Phase32PersistenceError"
    record = repository.read(definition.run_id)
    events = repository.events(definition.run_id)
    assert record.read_model.updated_at == committed[0][1]
    assert len(events) == 1
    assert events[0].occurred_at == committed[0][1]
    assert record.state.status == record.read_model.status == "running"


def test_phase32_repository_commits_validated_projection_pair(tmp_path: Path) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    state = initial_route_run_state(definition)
    read_model = initial_route_run_read_model(definition, updated_at=NOW)
    repository.create(definition, state=state, read_model=read_model)

    running_status = dict(state.stage_status)
    running_status["brief"] = "running"
    next_state = state.model_copy(update={"status": "running", "stage_status": running_status})
    next_read_model = read_model.model_copy(
        update={
            "status": "running",
            "stage_status": running_status,
            "updated_at": "2026-08-23T12:01:00+08:00",
        }
    )
    committed = repository.commit_projection(
        definition.run_id,
        state=next_state,
        read_model=next_read_model,
    )
    assert committed.state.status == "running"
    assert committed.read_model.updated_at == "2026-08-23T12:01:00+08:00"

    invalid_state = next_state.model_copy(update={"definition_digest": "f" * 64})
    with pytest.raises(Phase32PersistenceError, match="projection|state"):
        repository.commit_projection(
            definition.run_id,
            state=invalid_state,
            read_model=next_read_model,
        )


def test_phase32_repository_rejects_projection_pair_reference_and_cursor_drift(
    tmp_path: Path,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    record = repository.create(definition, updated_at=NOW)

    artifact_state = record.state.model_copy(
        update={"artifact_refs": {"brief": "artifact-brief-v1"}}
    )
    with pytest.raises(Phase32PersistenceError, match="Artifact refs differ"):
        repository.commit_projection(
            definition.run_id,
            state=artifact_state,
            read_model=record.read_model,
        )

    cursor_state = record.state.model_copy(
        update={"active_stage_id": "text", "active_unit_ref": "unit-001"}
    )
    cursor_read_model = record.read_model.model_copy(
        update={"active_stage_id": "text", "active_unit_ref": "unit-002"}
    )
    with pytest.raises(Phase32PersistenceError, match="active units differ"):
        repository.commit_projection(
            definition.run_id,
            state=cursor_state,
            read_model=cursor_read_model,
        )

    state_progress = SequentialStageProgress(
        ordered_unit_refs=("unit-001", "unit-002")
    )
    read_progress = SequentialStageProgress(
        ordered_unit_refs=("unit-001", "unit-003")
    )
    progress_state = record.state.model_copy(
        update={
            "sequential_stage_progress": {
                "text": state_progress.model_dump(mode="json")
            }
        }
    )
    progress_read_model = record.read_model.model_copy(
        update={"sequential_stage_progress": {"text": read_progress}}
    )
    with pytest.raises(Phase32PersistenceError, match="sequential stage progress"):
        repository.commit_projection(
            definition.run_id,
            state=progress_state,
            read_model=progress_read_model,
        )

    matching_read_model = record.read_model.model_copy(
        update={
            "artifact_refs": {
                "brief": ArtifactRefProjection(
                    artifact_kind=definition.stage("brief").artifact_kind,
                    artifact_ref="artifact-brief-v1",
                )
            }
        }
    )
    committed = repository.commit_projection(
        definition.run_id,
        state=artifact_state,
        read_model=matching_read_model,
    )
    assert committed.state.artifact_refs == {"brief": "artifact-brief-v1"}


def test_phase32_repository_preserves_accepted_prefix_across_batch_appends(
    tmp_path: Path,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    record = repository.create(definition, updated_at=NOW)
    unit_refs = ("unit-001", "unit-002", "unit-003", "unit-004")
    first_prefix = SequentialStageProgress(
        ordered_unit_refs=unit_refs,
        committed_artifact_refs={
            "unit-001": "artifact-unit-001-v1",
            "unit-002": "artifact-unit-002-v1",
        },
    )
    state, read_model = _with_text_progress(record, first_prefix)
    record = repository.commit_projection(
        definition.run_id,
        state=state,
        read_model=read_model,
    )

    complete_prefix = SequentialStageProgress(
        ordered_unit_refs=unit_refs,
        committed_artifact_refs={
            **first_prefix.committed_artifact_refs,
            "unit-003": "artifact-unit-003-v1",
            "unit-004": "artifact-unit-004-v1",
        },
    )
    state, read_model = _with_text_progress(record, complete_prefix)
    record = repository.commit_projection(
        definition.run_id,
        state=state,
        read_model=read_model,
    )
    assert record.state.sequential_progress("text") == complete_prefix

    shorter_prefix = SequentialStageProgress(
        ordered_unit_refs=unit_refs,
        committed_artifact_refs={
            unit_ref: artifact_ref
            for unit_ref, artifact_ref in tuple(
                complete_prefix.committed_artifact_refs.items()
            )[:3]
        },
    )
    state, read_model = _with_text_progress(record, shorter_prefix)
    with pytest.raises(Phase32PersistenceError, match="prefix cannot shrink"):
        repository.commit_projection(
            definition.run_id,
            state=state,
            read_model=read_model,
        )

    replaced_refs = dict(complete_prefix.committed_artifact_refs)
    replaced_refs["unit-002"] = "artifact-unit-002-v2"
    replaced_prefix = SequentialStageProgress(
        ordered_unit_refs=unit_refs,
        committed_artifact_refs=replaced_refs,
    )
    state, read_model = _with_text_progress(record, replaced_prefix)
    with pytest.raises(Phase32PersistenceError, match="prefix cannot change"):
        repository.commit_projection(
            definition.run_id,
            state=state,
            read_model=read_model,
        )

    reordered_unit_refs = ("unit-001", "unit-003", "unit-002", "unit-004")
    reordered_prefix = SequentialStageProgress(
        ordered_unit_refs=reordered_unit_refs,
        committed_artifact_refs={
            unit_ref: complete_prefix.committed_artifact_refs[unit_ref]
            for unit_ref in reordered_unit_refs
        },
    )
    state, read_model = _with_text_progress(record, reordered_prefix)
    with pytest.raises(Phase32PersistenceError, match="ordered unit refs cannot change"):
        repository.commit_projection(
            definition.run_id,
            state=state,
            read_model=read_model,
        )

    state = record.state.model_copy(
        update={"active_unit_ref": "", "sequential_stage_progress": {}}
    )
    read_model = record.read_model.model_copy(
        update={"active_unit_ref": "", "sequential_stage_progress": {}}
    )
    with pytest.raises(Phase32PersistenceError, match="progress cannot be removed"):
        repository.commit_projection(
            definition.run_id,
            state=state,
            read_model=read_model,
        )


def test_phase32_projection_journal_cannot_roll_back_accepted_prefix(
    tmp_path: Path,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    record = repository.create(definition, updated_at=NOW)
    complete = SequentialStageProgress(
        ordered_unit_refs=("unit-001", "unit-002", "unit-003"),
        committed_artifact_refs={
            "unit-001": "artifact-unit-001-v1",
            "unit-002": "artifact-unit-002-v1",
            "unit-003": "artifact-unit-003-v1",
        },
    )
    state, read_model = _with_text_progress(record, complete)
    record = repository.commit_projection(
        definition.run_id,
        state=state,
        read_model=read_model,
    )

    stale_prefix = SequentialStageProgress(
        ordered_unit_refs=complete.ordered_unit_refs,
        committed_artifact_refs={"unit-001": "artifact-unit-001-v1"},
    )
    stale_state, stale_read_model = _with_text_progress(record, stale_prefix)
    journal = repository._projection_journal_path(definition.run_id)
    journal.write_text(
        json.dumps(
            {
                "architecture_version": "phase32-routes-v1",
                "run_id": definition.run_id,
                "definition_digest": definition.definition_digest,
                "state": stale_state.model_dump(mode="json"),
                "read_model": stale_read_model.model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(Phase32PersistenceError, match="journal does not match"):
        repository.read(definition.run_id)
    journal.unlink()
    restored = repository.read(definition.run_id)
    assert restored.state.sequential_progress("text") == complete


def test_phase32_projection_journal_recovers_after_partial_file_replace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    state = initial_route_run_state(definition)
    read_model = initial_route_run_read_model(definition, updated_at=NOW)
    repository.create(definition, state=state, read_model=read_model)

    running_status = dict(state.stage_status)
    running_status["brief"] = "running"
    next_state = state.model_copy(update={"status": "running", "stage_status": running_status})
    next_read_model = read_model.model_copy(
        update={
            "status": "running",
            "stage_status": running_status,
            "updated_at": "2026-08-23T12:01:00+08:00",
        }
    )
    original_replace = repository._replace_projection_file
    replacements = 0

    def fail_after_first_replace(source: Path, target: Path) -> None:
        nonlocal replacements
        replacements += 1
        original_replace(source, target)
        if replacements == 1:
            raise RuntimeError("simulated process stop after state projection")

    monkeypatch.setattr(repository, "_replace_projection_file", fail_after_first_replace)
    with pytest.raises(RuntimeError, match="simulated process stop"):
        repository.commit_projection(
            definition.run_id,
            state=next_state,
            read_model=next_read_model,
        )

    journal = repository._projection_journal_path(definition.run_id)
    assert journal.exists()
    monkeypatch.setattr(repository, "_replace_projection_file", original_replace)
    recovered = repository.read(definition.run_id)
    assert recovered.state == next_state
    assert recovered.read_model == next_read_model
    assert not journal.exists()


def test_phase32_projection_journal_rejects_definition_drift(tmp_path: Path) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    repository.create(definition)
    journal = repository._projection_journal_path(definition.run_id)
    journal.write_text(
        json.dumps(
            {
                "architecture_version": "phase32-routes-v1",
                "run_id": definition.run_id,
                "definition_digest": "f" * 64,
                "state": initial_route_run_state(definition).model_dump(mode="json"),
                "read_model": initial_route_run_read_model(
                    definition,
                    updated_at=NOW,
                ).model_dump(mode="json"),
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(Phase32PersistenceError, match="journal definition digest"):
        repository.read(definition.run_id)


def test_phase32_projection_journal_replays_failure_event_after_append_interrupt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    state = initial_route_run_state(definition)
    read_model = initial_route_run_read_model(definition, updated_at=NOW)
    repository.create(definition, state=state, read_model=read_model)

    running_status = dict(state.stage_status)
    running_status["brief"] = "running"
    next_state = state.model_copy(update={"status": "running", "stage_status": running_status})
    next_read_model = read_model.model_copy(
        update={
            "status": "running",
            "stage_status": running_status,
            "failure": RunFailureProjection(
                code="provider_transport_failed",
                stage_id="brief",
                retryable=True,
                message="simulated timeout",
            ),
            "updated_at": "2026-08-23T12:02:00+08:00",
        }
    )
    event = create_route_run_event(
        definition,
        event_id="event-brief-failed",
        sequence=1,
        occurred_at="2026-08-23T12:02:00+08:00",
        type="stage.failed",
        stage_id="brief",
        status="running",
        payload={
            "code": "provider_transport_failed",
            "retryable": True,
            "message": "simulated timeout",
        },
    )
    original_append = repository._append_event_unlocked

    def fail_after_append(candidate):
        result = original_append(candidate)
        raise RuntimeError("simulated process stop after failure event")

    monkeypatch.setattr(repository, "_append_event_unlocked", fail_after_append)
    with pytest.raises(RuntimeError, match="failure event"):
        repository.commit_projection_with_event(
            definition.run_id,
            state=next_state,
            read_model=next_read_model,
            event=event,
        )

    journal = repository._projection_journal_path(definition.run_id)
    assert journal.exists()
    monkeypatch.setattr(repository, "_append_event_unlocked", original_append)
    recovered = repository.read(definition.run_id)
    assert recovered.state == next_state
    assert recovered.read_model == next_read_model
    assert repository.events(definition.run_id) == [event]
    assert not journal.exists()


def test_phase32_repository_rejects_phase27_definition_as_executable_input(
    tmp_path: Path,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    legacy_dir = repository.runs_root / "phase27-run"
    legacy_dir.mkdir(parents=True)
    (legacy_dir / "definition.json").write_text(
        json.dumps({"architecture_version": "phase27-vnext"}),
        encoding="utf-8",
    )

    with pytest.raises(Phase27ExecutionRejected) as exc:
        repository.definition("phase27-run")
    assert exc.value.code == "phase27_run_requires_archive_reader"


def test_phase32_repository_rejects_event_sequence_and_payload_drift(
    tmp_path: Path,
) -> None:
    repository = Phase32RunRepository(tmp_path / "native-runtime")
    definition = _definition()
    repository.create(definition)
    event = create_route_run_event(
        definition,
        event_id="event-brief-started",
        sequence=1,
        occurred_at=NOW,
        type="stage.started",
        stage_id="brief",
    )
    repository.append_event(event)
    gap = create_route_run_event(
        definition,
        event_id="event-gap",
        sequence=3,
        occurred_at=NOW,
        type="checkpoint.saved",
        stage_id="brief",
    )
    with pytest.raises(Phase32PersistenceError, match="sequence"):
        repository.append_event(gap)

    path = repository.events_root / definition.run_id / "events.jsonl"
    path.write_text(path.read_text(encoding="utf-8") + "{\"sequence\": 2}\n", encoding="utf-8")
    with pytest.raises(Phase32PersistenceError, match="Malformed Phase 32 event"):
        repository.events(definition.run_id)


def test_phase32_repository_is_not_imported_by_current_legacy_runtime() -> None:
    runtime_source = Path("src/novel_workflow/runtime/graph/runtime.py").read_text(
        encoding="utf-8"
    )
    assert "phase32_run_repository" not in runtime_source
