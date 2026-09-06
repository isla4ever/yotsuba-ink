from __future__ import annotations

import json
import multiprocessing as mp
import os
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.providers.usage import (
    Phase32ProviderCostBreakdown,
    Phase32ProviderUsageSummary,
)
from novel_workflow.storage import phase32_creation_preparation_store as preparation_store_module
from novel_workflow.workflows.frozen_route_contract import canonical_digest
from novel_workflow.workflows.schemas import ProviderProfile


def _client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.chdir(tmp_path)
    return TestClient(create_app())


def _payload(*, key: str = "phase32-project-test") -> dict[str, object]:
    return {
        "selection": {
            "intent": {
                "creative_intent": "一名档案修复师在暴雨夜收到一份尚未发生的失踪报告。",
                "creation_language": "zh-CN",
                "creation_kind": "novel",
                "novel_length_class": "short_novel",
                "requested_target": 20_000,
            },
            "mode": "existing",
            "workflow_id": "official.short_novel",
        },
        "idempotency_key": key,
    }


def _definition(api: TestClient, project: dict[str, object]) -> dict[str, object]:
    record = api.app.state.phase32_run_repository.read(str(project["latest_run_id"]))
    return record.definition.model_dump(mode="json")


def _spawn_prepare_worker(
    root: str,
    payload: dict[str, object],
    created_at: str,
    result_queue: Any,
    *,
    start_barrier: Any | None = None,
    started_event: Any | None = None,
    reserved_event: Any | None = None,
    release_event: Any | None = None,
    hard_exit_after_reservation: bool = False,
) -> None:
    """Run one preparation from a fresh interpreter and report its outcome."""

    os.chdir(root)
    service = create_app().state.phase32_creation_service
    service.clock = lambda: created_at

    if reserved_event is not None:

        def fail_after_reservation(*args: Any, **kwargs: Any) -> None:
            reserved_event.set()
            if release_event is None or not release_event.wait(timeout=20):
                raise RuntimeError("timed out while simulating preparation stop")
            if hard_exit_after_reservation:
                os._exit(73)
            raise RuntimeError("simulated process stop after reservation")

        service.repository.create = fail_after_reservation

    if start_barrier is not None:
        start_barrier.wait(timeout=20)
    if started_event is not None:
        started_event.set()

    try:
        prepared = service.prepare(service_request(payload))
        definition = prepared.definition.model_dump(mode="json")
        result_queue.put(
            {
                "kind": "prepared",
                "reused": prepared.reused,
                "run_id": prepared.definition.run_id,
                "preparation_created_at": prepared.preparation.created_at,
                "definition_created_at": prepared.definition.created_at,
                "definition_digest": prepared.definition.definition_digest,
                "creative_intent": definition["inputs"]["payload"]["creative_intent"],
            }
        )
    except Exception as exc:
        result: dict[str, object] = {
            "kind": "error",
            "error_type": type(exc).__name__,
            "code": getattr(exc, "code", None),
            "message": str(exc),
        }
        try:
            persisted = service.preparations.read(str(payload["idempotency_key"]))
        except Exception:
            pass
        else:
            result["preparation_created_at"] = persisted.created_at
        result_queue.put(result)


def _collect_spawn_results(
    processes: list[Any],
    result_queue: Any,
    *,
    result_count: int | None = None,
    expected_exitcodes: list[int] | None = None,
) -> list[dict[str, object]]:
    try:
        results = [
            result_queue.get(timeout=30)
            for _ in range(result_count if result_count is not None else len(processes))
        ]
    finally:
        for process in processes:
            process.join(timeout=30)
            if process.is_alive():
                process.terminate()
                process.join(timeout=5)
    assert [process.exitcode for process in processes] == (
        expected_exitcodes if expected_exitcodes is not None else [0] * len(processes)
    )
    return results


requires_posix_flock = pytest.mark.skipif(
    preparation_store_module.fcntl is None,
    reason="cross-process preparation serialization requires POSIX flock",
)


def test_project_creation_freezes_native_route_scale_review_and_provider_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)

    response = api.post("/api/projects", json=_payload())

    assert response.status_code == 200
    project = response.json()
    definition = _definition(api, project)
    assert definition["architecture_version"] == "phase32-routes-v1"
    assert definition["route_contract"]["creation_route_id"] == "short_novel"
    assert definition["route_contract"]["review_policy"]["route_id"] == "short_novel"
    assert definition["inputs"]["contract_id"] == "inputs.short_novel.v2"
    assert definition["inputs"]["contract_revision"] == "r2"
    assert definition["inputs"]["payload"]["creation_language"] == "zh-CN"
    assert definition["scale_profile"]["payload"]["target"] == 20_000
    assert [item["stage_id"] for item in definition["provider_bindings_by_stage"]] == [
        "brief",
        "story_map",
        "cast",
        "section_plan",
        "text",
        "cover",
    ]
    cover_binding = definition["provider_bindings_by_stage"][-1]["binding"]["payload"]
    assert cover_binding["image_execution"] is None
    assert "image_provider_profile_id" not in cover_binding
    assert project["run_status"] == "created"


def test_project_creation_accepts_canonical_route_identity_without_legacy_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="canonical-short-route")
    payload["selection"]["workflow_id"] = "official.short_novel"

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 200
    project = response.json()
    definition = _definition(api, project)
    assert definition["workflow_id"] == "official.short_novel"
    assert definition["route_contract"]["creation_route_id"] == "short_novel"
    assert {
        stage["binding"]["payload"]["execution"]["provider_profile_id"]
        for stage in definition["provider_bindings_by_stage"]
    } == {"provider-deepseek-text"}


def test_canonical_screenplay_route_keeps_the_bounded_flash_model_split(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="canonical-screenplay-model")
    payload["selection"]["intent"]["creation_kind"] = "screenplay"
    payload["selection"]["intent"]["novel_length_class"] = None
    payload["selection"]["intent"]["requested_target"] = 3
    payload["selection"]["workflow_id"] = "official.screenplay_sample"

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 200
    definition = _definition(api, response.json())
    models = {
        stage["binding"]["payload"]["execution"]["model_id"]
        for stage in definition["provider_bindings_by_stage"]
    }
    assert models == {"deepseek-v4-flash"}


def test_canonical_short_route_freezes_stage_budgets_without_legacy_template(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="canonical-short-budget")
    payload["selection"]["workflow_id"] = "official.short_novel"

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 200
    definition = _definition(api, response.json())
    settings = {
        stage["stage_id"]: stage["binding"]["payload"]["execution"]["model_settings"]
        for stage in definition["provider_bindings_by_stage"]
    }
    assert settings["brief"]["max_tokens"] == 4_600
    assert settings["story_map"]["max_tokens"] == 8_000
    assert settings["cast"]["max_tokens"] == 10_000
    assert settings["section_plan"]["max_tokens"] == 6_000
    assert settings["text"]["max_tokens"] == 6_000


def test_canonical_route_skips_an_incomplete_default_provider_profile(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    api.app.state.provider_store.write(
        "000-empty-text",
        ProviderProfile(
            id="000-empty-text",
            name="空配置（不应被选中）",
            kind="openai-compatible",
            template_id="openai-compatible-text",
            base_url="",
            default_model="",
            enabled=True,
        ).model_dump(),
    )
    payload = _payload(key="canonical-skips-empty-provider")
    payload["selection"]["workflow_id"] = "official.short_novel"

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 200
    definition = _definition(api, response.json())
    assert {
        stage["binding"]["payload"]["execution"]["provider_profile_id"]
        for stage in definition["provider_bindings_by_stage"]
    } == {"provider-deepseek-text"}


def test_project_creation_is_idempotent_and_rejects_input_conflict(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="phase32-idempotent")

    first = api.post("/api/projects", json=payload)
    second = api.post("/api/projects", json=payload)
    conflict_payload = _payload(key="phase32-idempotent")
    conflict_payload["selection"]["intent"]["creative_intent"] = "同一 key 的输入已经发生变化。"
    conflict = api.post("/api/projects", json=conflict_payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json() == first.json()
    assert conflict.status_code == 409
    assert conflict.json()["detail"]["code"] == "phase32_creation_conflict"


def test_release_smoke_creation_is_explicitly_namespaced_and_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="release-smoke-short")
    payload["selection"]["intent"]["requested_target"] = 3_500
    payload["project_id"] = "release-smoke-project-short"
    payload["run_id"] = "release-smoke-run-short"
    request = service_request(payload)
    service = api.app.state.phase32_creation_service

    prepared = service.prepare_release_smoke(request)
    profile = prepared.definition.scale_profile.payload
    assert profile["profile_kind"] == "release_smoke"
    assert profile["smoke_capacity"]["max_units"] == 3
    assert prepared.preparation.profile_kind == "release_smoke"

    replay = service.prepare_release_smoke(request)
    assert replay.reused is True
    assert replay.definition == prepared.definition


def test_release_smoke_creation_rejects_non_namespaced_identifiers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="release-smoke-invalid-id")
    payload["project_id"] = "production-project"

    with pytest.raises(ValueError, match="release-smoke- project id"):
        api.app.state.phase32_creation_service.prepare_release_smoke(
            service_request(payload)
        )


def test_continuity_acceptance_creation_freezes_canonical_exact_12_definition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="continuity-acceptance-exact-12")
    payload["selection"]["intent"]["novel_length_class"] = "long_novel"
    payload["selection"]["intent"]["requested_target"] = 150_000
    payload["selection"]["workflow_id"] = "official.long_novel"
    payload["project_id"] = "continuity-acceptance-project-exact-12"
    payload["run_id"] = "continuity-acceptance-run-exact-12"
    request = service_request(payload)
    service = api.app.state.phase32_creation_service

    prepared = service.prepare_continuity_acceptance(request)
    replay = service.prepare_continuity_acceptance(request)

    profile = prepared.definition.scale_profile.payload
    assert prepared.definition.creation_route_id == "long_novel"
    assert prepared.definition.workflow_id == "official.long_novel"
    assert profile["profile_kind"] == "continuity_acceptance"
    assert profile["policy_id"] == "length.long_novel.continuity_acceptance.v1"
    assert profile["rolling_window"] == {
        "min_chapters": 12,
        "max_chapters": 12,
        "min_volumes": 1,
        "max_volumes": 1,
    }
    assert prepared.preparation.profile_kind == "continuity_acceptance"
    assert replay.reused is True
    assert replay.definition == prepared.definition
    assert api.app.state.phase32_provider_operations.list(prepared.definition.run_id) == []


@pytest.mark.parametrize(
    "profile_kind",
    ("production", "release_smoke", "continuity_acceptance"),
)
def test_preparation_record_binding_accepts_all_profile_kinds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile_kind: str,
) -> None:
    api = _client(tmp_path, monkeypatch)
    key = f"preparation-binding-{profile_kind}"
    payload = _payload(key=key)
    service = api.app.state.phase32_creation_service
    request = service_request(payload)
    if profile_kind == "release_smoke":
        payload["selection"]["intent"]["requested_target"] = 3_500
        request = service_request(payload)
        prepared = service.prepare_release_smoke(request)
    elif profile_kind == "continuity_acceptance":
        payload["selection"]["intent"]["novel_length_class"] = "long_novel"
        payload["selection"]["intent"]["requested_target"] = 150_000
        payload["selection"]["workflow_id"] = "official.long_novel"
        request = service_request(payload)
        prepared = service.prepare_continuity_acceptance(request)
    else:
        prepared = service.prepare(request)

    persisted = service.preparations.read(key)
    expected_project_id, expected_run_id = (
        preparation_store_module.derive_phase32_creation_identifiers(
            key,
            profile_kind,
        )
    )
    digest_request = dict(persisted.request_payload)
    assert digest_request.pop("idempotency_key") == key

    assert persisted == prepared.preparation
    assert persisted.project_id == expected_project_id
    assert persisted.run_id == expected_run_id
    assert persisted.request_digest == canonical_digest(
        {"profile_kind": profile_kind, "request": digest_request}
    )
    assert persisted.status == "prepared"
    assert persisted.definition_digest == prepared.definition.definition_digest


@pytest.mark.parametrize(
    "mutation",
    (
        "payload",
        "digest",
        "idempotency_key",
        "derived_project_id",
        "explicit_project_id",
        "derived_run_id",
        "explicit_run_id",
        "reserved_with_digest",
        "prepared_without_digest",
    ),
)
def test_preparation_store_rejects_unbound_persisted_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    api = _client(tmp_path, monkeypatch)
    key = f"preparation-corrupt-{mutation}"
    payload = _payload(key=key)
    if mutation == "explicit_project_id":
        payload["project_id"] = "p32-explicit-project"
    if mutation == "explicit_run_id":
        payload["run_id"] = "p32-explicit-run"
    service = api.app.state.phase32_creation_service
    service.prepare(service_request(payload))
    path = service.preparations.root / f"{key}.json"
    record = json.loads(path.read_text(encoding="utf-8"))

    if mutation == "payload":
        record["request_payload"]["selection"]["intent"]["creative_intent"] = (
            "被修改但没有重新冻结摘要的创建输入。"
        )
    elif mutation == "digest":
        record["request_digest"] = "f" * 64
    elif mutation == "idempotency_key":
        record["request_payload"]["idempotency_key"] = "another-preparation-key"
    elif mutation in {"derived_project_id", "explicit_project_id"}:
        record["project_id"] = "p32-project-mismatch"
    elif mutation in {"derived_run_id", "explicit_run_id"}:
        record["run_id"] = "p32-run-mismatch"
    elif mutation == "reserved_with_digest":
        record["status"] = "reserved"
    else:
        record["definition_digest"] = ""
    path.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(
        preparation_store_module.Phase32PreparationConflict,
        match="Malformed Phase 32 creation preparation",
    ):
        service.preparations.read(key)


@pytest.mark.parametrize(
    ("mutation", "message"),
    (
        ("short_route", "private to the long_novel route"),
        ("legacy_workflow", "requires the official.long_novel workflow"),
        ("custom_workflow", "requires the official.long_novel workflow"),
        ("missing_idempotency", "requires an explicit idempotency key"),
        ("project_namespace", "continuity-acceptance- project id"),
        ("run_namespace", "continuity-acceptance- run id"),
    ),
)
def test_continuity_acceptance_creation_rejects_noncanonical_input(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
    message: str,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key=f"continuity-acceptance-invalid-{mutation}")
    payload["selection"]["intent"]["novel_length_class"] = "long_novel"
    payload["selection"]["intent"]["requested_target"] = 150_000
    payload["selection"]["workflow_id"] = "official.long_novel"
    if mutation == "short_route":
        payload["selection"]["intent"]["novel_length_class"] = "short_novel"
        payload["selection"]["intent"]["requested_target"] = 20_000
        payload["selection"]["workflow_id"] = "official.short_novel"
    elif mutation == "legacy_workflow":
        payload["selection"]["workflow_id"] = "official-deepseek-deep"
    elif mutation == "custom_workflow":
        payload["selection"] = {
            "intent": payload["selection"]["intent"],
            "mode": "existing",
            "workflow_id": "custom.long-novel",
        }
    elif mutation == "missing_idempotency":
        payload.pop("idempotency_key")
    elif mutation == "project_namespace":
        payload["project_id"] = "production-project"
    else:
        payload["run_id"] = "production-run"

    with pytest.raises(ValueError, match=message):
        api.app.state.phase32_creation_service.prepare_continuity_acceptance(
            service_request(payload)
        )


def test_continuity_acceptance_creation_recovers_reserved_definition(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="continuity-acceptance-recovery")
    payload["selection"]["intent"]["novel_length_class"] = "long_novel"
    payload["selection"]["intent"]["requested_target"] = 150_000
    payload["selection"]["workflow_id"] = "official.long_novel"
    request = service_request(payload)
    service = api.app.state.phase32_creation_service
    original_create = service.repository.create
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated continuity launcher stop")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(service.repository, "create", fail_once)
    with pytest.raises(RuntimeError, match="simulated continuity launcher stop"):
        service.prepare_continuity_acceptance(request)

    recovered = service.prepare_continuity_acceptance(request)

    assert recovered.reused is True
    assert recovered.preparation.status == "prepared"
    assert recovered.preparation.profile_kind == "continuity_acceptance"
    assert recovered.definition.scale_profile.payload["profile_kind"] == (
        "continuity_acceptance"
    )
    assert service.read("continuity-acceptance-recovery").definition == recovered.definition


def test_continuity_acceptance_creation_recovers_after_run_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="continuity-acceptance-recovery-after-run")
    payload["selection"]["intent"]["novel_length_class"] = "long_novel"
    payload["selection"]["intent"]["requested_target"] = 150_000
    payload["selection"]["workflow_id"] = "official.long_novel"
    request = service_request(payload)
    service = api.app.state.phase32_creation_service
    original_mark_prepared = service.preparations.mark_prepared
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated stop after continuity Run write")
        return original_mark_prepared(*args, **kwargs)

    monkeypatch.setattr(service.preparations, "mark_prepared", fail_once)
    with pytest.raises(RuntimeError, match="stop after continuity Run write"):
        service.prepare_continuity_acceptance(request)

    reservation = service.preparations.read(
        "continuity-acceptance-recovery-after-run"
    )
    persisted = service.repository.read(reservation.run_id)
    assert reservation.status == "reserved"

    recovered = service.prepare_continuity_acceptance(request)

    assert recovered.reused is True
    assert recovered.definition == persisted.definition
    assert recovered.preparation.definition_digest == persisted.definition.definition_digest


def test_continuity_acceptance_idempotency_key_cannot_cross_profile_scopes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="continuity-acceptance-profile-isolation")
    payload["selection"]["intent"]["novel_length_class"] = "long_novel"
    payload["selection"]["intent"]["requested_target"] = 150_000
    payload["selection"]["workflow_id"] = "official.long_novel"
    request = service_request(payload)
    service = api.app.state.phase32_creation_service

    production = service.prepare(request)

    with pytest.raises(ValueError, match="Idempotency key"):
        service.prepare_continuity_acceptance(request)
    assert production.preparation.profile_kind == "production"


def test_public_project_creation_rejects_private_continuity_profile_selector(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="private-continuity-selector")
    payload["profile_kind"] = "continuity_acceptance"

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert any(
        error["type"] == "extra_forbidden"
        and error["loc"][-1] == "profile_kind"
        for error in response.json()["detail"]
    )


def test_project_creation_recovers_after_reservation_before_run_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="phase32-recovery")
    service = api.app.state.phase32_creation_service
    original_create = service.repository.create
    calls = 0

    def fail_once(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("simulated process stop")
        return original_create(*args, **kwargs)

    monkeypatch.setattr(service.repository, "create", fail_once)
    with pytest.raises(RuntimeError, match="simulated process stop"):
        service.prepare(service_request(payload))

    recovered = api.post("/api/projects", json=payload)

    assert recovered.status_code == 200
    assert service.read("phase32-recovery").reused is True
    assert api.get("/api/projects").json() == [recovered.json()]


@requires_posix_flock
def test_same_request_is_serialized_across_processes_and_uses_winning_timestamp(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="phase32-process-same-request")
    context = mp.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    timestamps = (
        "2026-09-05T09:01:00+08:00",
        "2026-09-05T09:02:00+08:00",
    )
    processes = [
        context.Process(
            target=_spawn_prepare_worker,
            args=(str(tmp_path), payload, created_at, result_queue),
            kwargs={"start_barrier": barrier},
        )
        for created_at in timestamps
    ]

    for process in processes:
        process.start()
    results = _collect_spawn_results(processes, result_queue)

    assert {result["kind"] for result in results} == {"prepared"}
    assert {result["reused"] for result in results} == {False, True}
    assert len({result["run_id"] for result in results}) == 1
    assert len({result["definition_digest"] for result in results}) == 1
    assert len({result["preparation_created_at"] for result in results}) == 1
    assert len({result["definition_created_at"] for result in results}) == 1
    winning_timestamp = results[0]["preparation_created_at"]
    assert winning_timestamp in timestamps
    assert results[0]["definition_created_at"] == winning_timestamp
    assert results[1]["definition_created_at"] == winning_timestamp

    preparation = api.app.state.phase32_creation_preparations.read(
        "phase32-process-same-request"
    )
    record = api.app.state.phase32_run_repository.read(preparation.run_id)
    assert preparation.status == "prepared"
    assert preparation.created_at == winning_timestamp
    assert record.definition.created_at == winning_timestamp
    assert record.definition.definition_digest == results[0]["definition_digest"]
    assert len(list(api.app.state.phase32_run_repository.runs_root.iterdir())) == 1


@requires_posix_flock
def test_different_keys_cannot_commit_different_definitions_to_the_same_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    first_payload = _payload(key="phase32-shared-run-first")
    second_payload = _payload(key="phase32-shared-run-second")
    for payload in (first_payload, second_payload):
        payload["project_id"] = "p32-shared-project"
        payload["run_id"] = "p32-shared-run"
    first_payload["selection"]["intent"]["creative_intent"] = "第一份冻结定义。"
    second_payload["selection"]["intent"]["creative_intent"] = "第二份冲突定义。"
    context = mp.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    process_specs = (
        (first_payload, "2026-09-05T09:11:00+08:00"),
        (second_payload, "2026-09-05T09:12:00+08:00"),
    )
    processes = [
        context.Process(
            target=_spawn_prepare_worker,
            args=(str(tmp_path), payload, created_at, result_queue),
            kwargs={"start_barrier": barrier},
        )
        for payload, created_at in process_specs
    ]

    for process in processes:
        process.start()
    results = _collect_spawn_results(processes, result_queue)

    successes = [result for result in results if result["kind"] == "prepared"]
    conflicts = [result for result in results if result["kind"] == "error"]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0]["code"] == "phase32_creation_conflict"
    repository = api.app.state.phase32_run_repository
    record = repository.read("p32-shared-run")
    assert record.definition.inputs.payload["creative_intent"] == successes[0][
        "creative_intent"
    ]
    assert len(repository.list_read_models()) == 1
    assert not (repository.runs_root / ".p32-shared-run.staging").exists()


@requires_posix_flock
def test_conflicting_requests_cannot_overwrite_cross_process_reservation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    key = "phase32-process-conflicting-request"
    first_payload = _payload(key=key)
    second_payload = _payload(key=key)
    second_payload["selection"]["intent"]["creative_intent"] = (
        "另一名记录员试图用相同 key 覆盖已经冻结的请求。"
    )
    context = mp.get_context("spawn")
    barrier = context.Barrier(2)
    result_queue = context.Queue()
    process_specs = (
        (first_payload, "2026-09-05T10:01:00+08:00"),
        (second_payload, "2026-09-05T10:02:00+08:00"),
    )
    processes = [
        context.Process(
            target=_spawn_prepare_worker,
            args=(str(tmp_path), payload, created_at, result_queue),
            kwargs={"start_barrier": barrier},
        )
        for payload, created_at in process_specs
    ]

    for process in processes:
        process.start()
    results = _collect_spawn_results(processes, result_queue)

    successes = [result for result in results if result["kind"] == "prepared"]
    conflicts = [result for result in results if result["kind"] == "error"]
    assert len(successes) == 1
    assert len(conflicts) == 1
    assert conflicts[0]["code"] == "phase32_creation_conflict"
    assert conflicts[0]["error_type"] == "Phase32CreationConflict"

    winner = successes[0]
    preparation = api.app.state.phase32_creation_preparations.read(key)
    record = api.app.state.phase32_run_repository.read(preparation.run_id)
    assert preparation.created_at == winner["preparation_created_at"]
    assert preparation.request_payload["selection"]["intent"]["creative_intent"] == (
        winner["creative_intent"]
    )
    assert record.definition.inputs.payload["creative_intent"] == winner["creative_intent"]
    assert record.definition.definition_digest == winner["definition_digest"]
    assert len(list(api.app.state.phase32_run_repository.runs_root.iterdir())) == 1


@requires_posix_flock
def test_cross_process_recovery_reuses_reservation_after_winner_stops(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="phase32-process-recovery")
    context = mp.get_context("spawn")
    result_queue = context.Queue()
    reserved_event = context.Event()
    release_event = context.Event()
    recovery_started = context.Event()
    reserved_at = "2026-09-05T11:01:00+08:00"
    recovery_clock = "2026-09-05T11:02:00+08:00"
    interrupted = context.Process(
        target=_spawn_prepare_worker,
        args=(str(tmp_path), payload, reserved_at, result_queue),
        kwargs={
            "reserved_event": reserved_event,
            "release_event": release_event,
            "hard_exit_after_reservation": True,
        },
    )
    interrupted.start()
    assert reserved_event.wait(timeout=30)

    recovering = context.Process(
        target=_spawn_prepare_worker,
        args=(str(tmp_path), payload, recovery_clock, result_queue),
        kwargs={"started_event": recovery_started},
    )
    recovering.start()
    assert recovery_started.wait(timeout=30)
    release_event.set()

    results = _collect_spawn_results(
        [interrupted, recovering],
        result_queue,
        result_count=1,
        expected_exitcodes=[73, 0],
    )

    assert results[0]["kind"] == "prepared"
    assert results[0]["reused"] is True
    assert results[0]["preparation_created_at"] == reserved_at
    assert results[0]["definition_created_at"] == reserved_at

    preparation = api.app.state.phase32_creation_preparations.read(
        "phase32-process-recovery"
    )
    record = api.app.state.phase32_run_repository.read(preparation.run_id)
    assert preparation.status == "prepared"
    assert preparation.created_at == reserved_at
    assert record.definition.created_at == reserved_at
    assert len(list(api.app.state.phase32_run_repository.runs_root.iterdir())) == 1


@pytest.mark.parametrize(
    ("workflow_id", "creation_kind", "novel_length_class", "target", "stage_ids"),
    (
        (
            "official.screenplay_sample",
            "screenplay",
            None,
            12,
            ("brief", "cast", "beat_board", "scene_deck", "script", "export"),
        ),
        (
            "official.long_novel",
            "novel",
            "long_novel",
            150_000,
            ("brief", "book_architecture", "cast", "volumes", "rolling_detail", "text", "cover", "export"),
        ),
    ),
)
def test_project_creation_uses_the_selected_route_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    workflow_id: str,
    creation_kind: str,
    novel_length_class: str | None,
    target: int,
    stage_ids: tuple[str, ...],
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key=f"route-{workflow_id}")
    intent = payload["selection"]["intent"]
    intent["creation_kind"] = creation_kind
    intent["novel_length_class"] = novel_length_class
    intent["requested_target"] = target
    payload["selection"]["workflow_id"] = workflow_id

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 200
    definition = _definition(api, response.json())
    assert tuple(
        stage["stage_id"]
        for stage in definition["route_contract"]["route_manifest"]["stages"]
    ) == stage_ids
    first_pricing = definition["provider_bindings_by_stage"][0]["binding"]["payload"][
        "execution"
    ]["pricing_snapshot"]
    if workflow_id == "official.screenplay_sample":
        assert first_pricing["model_id"] == "deepseek-v4-flash"
        assert first_pricing["source"] == "profile"
        assert first_pricing["estimate_basis"] == "conservative_upper_bound"
        assert first_pricing["input_usd_per_million_tokens"] == 0.44
        assert first_pricing["output_usd_per_million_tokens"] == 1.32
    else:
        assert first_pricing["model_id"] == "deepseek-v4-pro"
        assert first_pricing["source"] == "profile"
        assert first_pricing["estimate_basis"] == "conservative_upper_bound"
        assert first_pricing["input_usd_per_million_tokens"] == 1.32
        assert first_pricing["output_usd_per_million_tokens"] == 3.96


def test_project_creation_rejects_the_unreleased_new_workflow_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    payload = _payload(key="route-new-seed")
    payload["selection"] = {
        "intent": payload["selection"]["intent"],
        "mode": "new",
        "new_workflow_label": "我的短篇试验线",
    }

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 422
    assert api.get("/api/projects").json() == []


def test_project_creation_rejects_attaching_to_a_legacy_project_record(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    legacy = api.app.state.project_store.create(idea="旧项目不应成为 Phase 32 Run 容器")
    payload = _payload(key="legacy-project-rejection")
    payload["project_id"] = legacy.id

    response = api.post("/api/projects", json=payload)

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "phase32_creation_conflict"
    assert api.get("/api/projects").json() == []


def test_phase32_read_projection_exposes_cost_without_frozen_bindings(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    api = _client(tmp_path, monkeypatch)
    project = api.post("/api/projects", json=_payload(key="cost-read-model")).json()
    run_id = project["latest_run_id"]
    repository = api.app.state.phase32_run_repository
    record = repository.read(run_id)
    usage = Phase32ProviderUsageSummary(
        provider_operations=1,
        returned_operations=1,
        succeeded_operations=1,
        prompt_tokens=1_000,
        completion_tokens=2_000,
        total_tokens=3_000,
        estimated_cost_usd=0.0042,
        cost_status="known",
        balance_status="unknown",
        by_provider=(
            Phase32ProviderCostBreakdown(
                provider_profile_id="deepseek",
                provider_template_id="deepseek-text",
                model_id="deepseek-chat",
                operations=1,
                estimated_cost_usd=0.0042,
                cost_status="known",
                balance_status="unknown",
            ),
        ),
    )
    repository.commit_projection(
        run_id,
        state=record.state,
        read_model=record.read_model.model_copy(
            update={
                "provider_usage": usage,
                "updated_at": "2026-08-23T12:01:00+08:00",
            }
        ),
    )

    detail = api.get(f"/api/runs/{run_id}")
    listed = api.get("/api/runs").json()

    assert detail.status_code == 200
    assert detail.json()["read_model"]["stage_manifest"]
    assert detail.json()["read_model"]["provider_usage"]["estimated_cost_usd"] == 0.0042
    assert detail.json()["summary"]["progress"]["total"] == 7
    assert "provider_bindings_by_stage" not in detail.json()["read_model"]
    assert listed["items"][0]["provider_usage"]["balance_status"] == "unknown"


def service_request(payload: dict[str, object]):
    from novel_workflow.orchestration.phase32_creation_service import (
        CreationPreparationRequest,
    )

    return CreationPreparationRequest.model_validate(payload)
