from __future__ import annotations

from pathlib import Path

import pytest

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ScreenplayBlock,
    ScreenplayDraftArtifact,
    ScriptDeliveryArtifact,
)
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from novel_workflow.workflows.route_specs import SCREENPLAY_SAMPLE_ROUTE
from tests.test_phase32_execution_api import _app


def _delivery_fixture(tmp_path: Path):
    run_id = "script-delivery-run"
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    scene_refs = ("scene-1", "scene-2")
    scenes = [
        artifacts.save_deterministic(
            run_id=run_id,
            creation_route_id="screenplay_sample",
            stage_id="script",
            artifact=ScreenplayDraftArtifact(
                scene_ref=scene_ref,
                blocks=(
                    ScreenplayBlock(
                        kind="scene_heading",
                        text=f"内景 档案室 {ordinal} - 夜",
                    ),
                    ScreenplayBlock(
                        kind="action",
                        text=f"林墨雨把第 {ordinal} 份签名记录摊在灯下。",
                    ),
                    ScreenplayBlock(
                        kind="dialogue",
                        speaker_ref="lin-moyu",
                        text="页码和时间戳都必须进入公开记录。",
                    ),
                ),
            ),
        )
        for ordinal, scene_ref in enumerate(scene_refs, start=1)
    ]
    delivery = artifacts.save_deterministic(
        run_id=run_id,
        creation_route_id="screenplay_sample",
        stage_id="export",
        artifact=ScriptDeliveryArtifact(
            title="失序档案",
            author="四叶墨工作室",
            version_note="锁定交付版 1.0",
            formats=("fountain", "pdf", "markdown"),
            scene_refs=scene_refs,
            scene_version_refs=tuple(record.artifact_ref for record in scenes),
        ),
    )
    return run_id, delivery, scenes


def test_script_delivery_materializes_all_frozen_formats_idempotently(
    tmp_path: Path,
) -> None:
    run_id, delivery, scenes = _delivery_fixture(tmp_path)
    exports = ExportStore(tmp_path / "exports")

    first = exports.materialize_script_delivery(run_id, delivery, scenes)
    second = exports.materialize_script_delivery(run_id, delivery, scenes)

    assert [record.format for record in first] == ["fountain", "pdf", "markdown"]
    assert first == second
    assert all(record.scene_refs == ("scene-1", "scene-2") for record in first)
    fountain_record, fountain = exports.script_delivery_content(
        run_id,
        next(record.export_id for record in first if record.format == "fountain"),
    )
    assert fountain_record.sha256
    assert "Title: 失序档案" in fountain.decode("utf-8")
    assert ".内景 档案室 1 - 夜" in fountain.decode("utf-8")
    assert "LIN MOYU" in fountain.decode("utf-8")
    _, markdown = exports.script_delivery_content(
        run_id,
        next(record.export_id for record in first if record.format == "markdown"),
    )
    assert "# 失序档案" in markdown.decode("utf-8")
    _, pdf = exports.script_delivery_content(
        run_id,
        next(record.export_id for record in first if record.format == "pdf"),
    )
    assert pdf.startswith(b"%PDF-")
    assert b"STSong-Light" in pdf


def test_script_delivery_rejects_out_of_order_versions_and_detects_damage(
    tmp_path: Path,
) -> None:
    run_id, delivery, scenes = _delivery_fixture(tmp_path)
    exports = ExportStore(tmp_path / "exports")

    with pytest.raises(ValueError, match="missing or out of frozen order"):
        exports.materialize_script_delivery(run_id, delivery, list(reversed(scenes)))

    records = exports.materialize_script_delivery(run_id, delivery, scenes)
    record = records[0]
    content_path = (
        exports.root / run_id / "script-files" / f"{record.export_id}.bin"
    )
    content_path.write_bytes(b"damaged")
    with pytest.raises(ValueError, match="immutable receipt"):
        exports.read_script_delivery(run_id, record.export_id)


def test_script_delivery_api_lists_and_downloads_materialized_file(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path, SCREENPLAY_SAMPLE_ROUTE)
    result = client.post(f"/api/runs/{run_id}/start").json()

    while result["run"]["read_model"]["status"] != "completed":
        decision = result["decision"]
        result = client.post(
            f"/api/runs/{run_id}/decisions",
            json={
                "decision_id": decision["decision_id"],
                "action": "accept",
                "domain_revision": decision["domain_revision"],
            },
        ).json()

    listed = client.get(f"/api/runs/{run_id}/exports")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["artifact_type"] == "script_delivery"
    assert payload["dependency_status"] == "ready"
    assert payload["deferred_reason"] == ""
    assert payload["source_artifact_refs"]
    assert payload["artifact_ref"] == result["run"]["read_model"]["artifact_refs"]["export"]["artifact_ref"]
    assert [item["format"] for item in payload["items"]] == ["fountain"]

    record = payload["items"][0]
    downloaded = client.get(f"/api/runs/{run_id}/exports/{record['export_id']}")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"Title:")
    assert downloaded.headers["x-content-sha256"] == record["sha256"]
    assert "filename*=UTF-8''" in downloaded.headers["content-disposition"]

    for receipt_path in (tmp_path / "exports" / run_id / "script-records").glob("*.json"):
        receipt_path.unlink()
    not_materialized = client.get(f"/api/runs/{run_id}/exports")
    assert not_materialized.status_code == 409
    assert not_materialized.json()["detail"]["code"] == "delivery_not_materialized"
    assert not_materialized.json()["detail"]["dependency_status"] == "blocked"

    missing = client.get(f"/api/runs/{run_id}/exports/missing-export")
    assert missing.status_code == 404
