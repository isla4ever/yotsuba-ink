from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.archive import (
    ArchiveRunReadOnlyError,
    Phase27ArchiveArchitectureError,
    Phase27ArchiveFormatError,
    Phase27ArchiveRunReader,
)
@pytest.fixture
def archive_root(tmp_path: Path) -> Path:
    source = tmp_path / "phase27-source"
    write_phase27_archive_run(
        source,
        run_id="run-completed",
        status="completed",
        updated_at="2026-08-20T03:00:00+00:00",
    )
    write_phase27_archive_run(
        source,
        run_id="run-failed",
        status="failed",
        updated_at="2026-08-20T02:00:00+00:00",
    )
    write_phase27_archive_run(
        source,
        run_id="run-awaiting",
        status="awaiting_decision",
        updated_at="2026-08-20T01:00:00+00:00",
    )
    archive = tmp_path / "archive-copy"
    shutil.copytree(source, archive)
    return archive


def test_phase27_archive_list_detail_and_event_pagination(archive_root: Path) -> None:
    reader = _reader(archive_root)

    first_page = reader.list(limit=2)
    assert [item.run_id for item in first_page.items] == [
        "run-completed",
        "run-failed",
    ]
    assert first_page.next_cursor == 2
    second_page = reader.list(cursor=first_page.next_cursor, limit=2)
    assert [item.run_id for item in second_page.items] == ["run-awaiting"]
    assert second_page.next_cursor is None

    completed = reader.read("run-completed")
    failed = reader.read("run-failed")
    awaiting = reader.read("run-awaiting")
    assert completed.summary.status == "completed"
    assert failed.failure is not None
    assert failed.failure.code == "SceneProseContractError"
    assert awaiting.summary.status == "awaiting_decision"
    assert awaiting.pending_decisions[0].kind == "stage_failure_decision"
    assert awaiting.pending_decisions[0].allowed_actions == ("regenerate", "cancel")
    assert set(completed.summary.capabilities.model_dump().values()) == {False}

    events = reader.events("run-completed", limit=2)
    assert [event.sequence for event in events.items] == [1, 2]
    assert events.items[1].has_payload is True
    assert "payload" not in events.items[1].model_dump()
    assert events.next_cursor == 2
    tail = reader.events("run-completed", after=events.next_cursor, limit=2)
    assert [event.sequence for event in tail.items] == [3]
    assert tail.next_cursor is None


def test_phase27_archive_rejects_unknown_architecture_and_malformed_records(
    archive_root: Path,
) -> None:
    unknown = archive_root / "runs" / "run-completed" / "definition.json"
    payload = json.loads(unknown.read_text(encoding="utf-8"))
    payload["architecture_version"] = "phase32-routes-v1"
    unknown.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Phase27ArchiveArchitectureError):
        _reader(archive_root).read("run-completed")

    malformed = archive_root / "runs" / "run-failed" / "read_model.json"
    payload = json.loads(malformed.read_text(encoding="utf-8"))
    payload["stage_status"].pop("export")
    malformed.write_text(json.dumps(payload), encoding="utf-8")
    with pytest.raises(Phase27ArchiveFormatError):
        _reader(archive_root).read("run-failed")


def test_phase27_archive_reads_do_not_change_file_hashes_or_mtimes(
    archive_root: Path,
) -> None:
    before = _fingerprints(archive_root)
    reader = _reader(archive_root)

    reader.list(limit=3)
    reader.read("run-completed")
    reader.events("run-completed", limit=2)
    with pytest.raises(ArchiveRunReadOnlyError) as exc:
        reader.reject_mutation("run-completed")

    assert exc.value.code == "archived_run_read_only"
    assert _fingerprints(archive_root) == before


def test_phase27_archive_api_is_typed_paginated_and_read_only(
    archive_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    app.state.phase27_archive_reader = _reader(archive_root)
    client = TestClient(app)

    page = client.get("/api/archive/runs", params={"limit": 1})
    assert page.status_code == 200
    assert page.json()["items"][0]["run_id"] == "run-completed"
    assert page.json()["next_cursor"] == 1
    detail = client.get("/api/archive/runs/run-awaiting")
    assert detail.status_code == 200
    assert detail.json()["summary"]["capabilities"]["provider"] is False
    assert "raw" not in detail.json()
    events = client.get(
        "/api/archive/runs/run-completed/events",
        params={"limit": 1},
    )
    assert events.status_code == 200
    assert events.json()["next_cursor"] == 1
    assert client.post("/api/archive/runs/run-completed").status_code == 405
    assert client.post("/api/runs/run-completed/start").status_code == 404


def test_archive_reader_has_no_runtime_provider_or_writer_dependency() -> None:
    source = (
        Path("src/novel_workflow/archive/phase27_archive_reader.py")
        .read_text(encoding="utf-8")
    )
    forbidden = (
        "legacy_run_viewer",
        "LegacyRunViewer",
        "NarrativeRunRepository",
        "RunDefinition",
        "runtime.graph",
        "novel_workflow.providers",
        "atomic_write",
        ".write_text(",
        ".open(\"w\"",
        ".open(\"a\"",
        '"run.json"',
    )
    assert all(token not in source for token in forbidden)


def _reader(root: Path) -> Phase27ArchiveRunReader:
    return Phase27ArchiveRunReader(root / "runs", root / "events")


ArchiveFixtureStatus = Literal["completed", "failed", "awaiting_decision"]


def write_phase27_archive_run(
    root: Path,
    *,
    run_id: str,
    status: ArchiveFixtureStatus,
    updated_at: str,
) -> None:
    run_dir = root / "runs" / run_id
    event_dir = root / "events" / run_id
    run_dir.mkdir(parents=True)
    event_dir.mkdir(parents=True)

    active_stage = {
        "completed": "export",
        "failed": "text",
        "awaiting_decision": "detail",
    }[status]
    stage_status = _stage_status(status)
    failure = None
    pending_decisions: list[dict[str, object]] = []
    if status == "failed":
        failure = {
            "node_id": "text.generate_prose",
            "code": "SceneProseContractError",
            "retryable": False,
            "message": "Frozen context rejected an unregistered subject.",
        }
    elif status == "awaiting_decision":
        failure = {
            "node_id": "detail.generate_candidate",
            "code": "ProviderOperationError",
            "retryable": True,
            "message": "Provider did not return one complete object.",
        }
        pending_decisions = [
            {
                "type": "stage_failure_decision",
                "decision_id": f"{run_id}:detail:failure-1",
                "thread_id": run_id,
                "node_id": "detail.failure_decision",
                "artifact_ref": "",
                "allowed_actions": ["regenerate", "cancel"],
                "failure": failure,
            }
        ]

    _write_json(
        run_dir / "definition.json",
        {
            "architecture_version": "phase27-vnext",
            "run_id": run_id,
            "project_id": "project-archive",
            "workflow_id": "workflow-phase27",
            "workflow_revision": "29.34.0",
            "workflow_digest": "a" * 64,
            "quality_mode": "balanced",
            "inputs": {"idea": "fixture material that must not reach the API"},
            "scale_profile": {"target_length": 50_000},
            "provider_bindings": {"brief": {"secret": "not-projected"}},
            "cover_asset_binding": {"secret": "not-projected"},
            "export_preferences": {"formats": ["markdown"]},
            "branch_origin": None,
            "created_at": "2026-08-20T00:00:00+00:00",
        },
    )
    _write_json(
        run_dir / "read_model.json",
        {
            "run_id": run_id,
            "project_id": "project-archive",
            "thread_id": run_id,
            "status": status,
            "active_stage_id": active_stage,
            "active_chapter_number": 3 if active_stage == "text" else 0,
            "context_manifest_ref": "context/private-ref",
            "stage_status": stage_status,
            "artifact_refs": {
                stage: f"artifact/private-{stage}"
                for stage, value in stage_status.items()
                if value == "completed" and stage != "text"
            },
            "pending_decisions": pending_decisions,
            "provider_usage": {
                "provider_operations": 4,
                "returned_operations": 4,
                "succeeded_operations": 3,
                "contract_rejected_operations": 1,
                "failed_operations": 0,
                "pending_operations": 0,
                "prompt_tokens": 100,
                "completion_tokens": 50,
                "total_tokens": 150,
                "reasoning_tokens": 0,
            },
            "failure": failure,
            "checkpoint_id": "checkpoint-private",
            "updated_at": updated_at,
        },
    )
    events = [
        {
            "event_id": f"{run_id}:started",
            "sequence": 1,
            "occurred_at": "2026-08-20T00:00:01+00:00",
            "run_id": run_id,
            "thread_id": run_id,
            "type": "run.started",
            "stage_id": "brief",
            "node_id": "load_run",
            "chapter_id": "",
            "status": "running",
            "payload": None,
            "payload_ref": "",
            "checkpoint_id": "",
        },
        {
            "event_id": f"{run_id}:brief-completed",
            "sequence": 2,
            "occurred_at": "2026-08-20T00:00:02+00:00",
            "run_id": run_id,
            "thread_id": run_id,
            "type": "node.completed",
            "stage_id": "brief",
            "node_id": "brief.commit",
            "chapter_id": "",
            "status": "completed",
            "payload": {"private": "must not reach the archive API"},
            "payload_ref": "payload/private-ref",
            "checkpoint_id": "",
        },
        {
            "event_id": f"{run_id}:checkpoint",
            "sequence": 3,
            "occurred_at": "2026-08-20T00:00:03+00:00",
            "run_id": run_id,
            "thread_id": run_id,
            "type": "checkpoint.saved",
            "stage_id": active_stage,
            "node_id": "graph.checkpoint",
            "chapter_id": "chapter-3" if active_stage == "text" else "",
            "status": "saved",
            "payload": {"next": []},
            "payload_ref": "",
            "checkpoint_id": "checkpoint-private",
        },
    ]
    (event_dir / "events.jsonl").write_text(
        "\n".join(json.dumps(item) for item in events) + "\n",
        encoding="utf-8",
    )


def _stage_status(status: ArchiveFixtureStatus) -> dict[str, str]:
    if status == "completed":
        return {
            stage: "completed"
            for stage in (
                "brief",
                "spine",
                "cast",
                "volumes",
                "detail",
                "text",
                "cover",
                "export",
            )
        }
    if status == "failed":
        return {
            "brief": "completed",
            "spine": "completed",
            "cast": "completed",
            "volumes": "completed",
            "detail": "completed",
            "text": "failed",
            "cover": "locked",
            "export": "locked",
        }
    return {
        "brief": "completed",
        "spine": "completed",
        "cast": "completed",
        "volumes": "completed",
        "detail": "awaiting_decision",
        "text": "locked",
        "cover": "locked",
        "export": "locked",
    }


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _fingerprints(root: Path) -> dict[str, tuple[int, int, str]]:
    fingerprints: dict[str, tuple[int, int, str]] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        content = path.read_bytes()
        fingerprints[str(path.relative_to(root))] = (
            path.stat().st_mtime_ns,
            len(content),
            hashlib.sha256(content).hexdigest(),
        )
    return fingerprints
