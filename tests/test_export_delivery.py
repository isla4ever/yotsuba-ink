from __future__ import annotations

import hashlib
import io
import json
import zipfile

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.export_delivery import ExportDeliveryError, build_export_artifact, build_export_package
from novel_workflow.orchestration.export_snapshot import freeze_export_selection
from novel_workflow.output_contracts.validation import validate_stage_artifact
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow
from tests.fakes import fake_png_bytes


def _state(*, complete: bool = True) -> NovelRunState:
    state = NovelRunState(
        run_id="export-delivery",
        project_id="export-project",
        workflow_id="default-novel-workflow",
        inputs={"title": "雾港交付", "quality_mode": "balanced"},
        artifacts={
            "info_recommend": {"selected_title": "雾港交付"},
            "summary": {"full_synopsis": "完整梗概"},
            "chapters": {"chapters": [
                {"id": "chapter-1", "title": "第一章", "content": "第一章正文", "status": "completed" if complete else "drafting", "words": 6},
                {"id": "chapter-2", "title": "第二章", "content": "第二章正文", "status": "completed", "words": 6},
            ]},
            "cover": {
                "brief": "封面",
                "selected_candidate_id": "cover-1",
                "candidates": [{
                    "id": "cover-1", "image_url": "/assets/cover-1.png", "composition": "雾港",
                    "asset_status": "ready", "asset_source": "production", "asset_id": "cover-aaaaaaaaaaaaaaaaaaaaaaaa",
                    "sha256": "a" * 64,
                }],
            },
        },
        quality_reports=[{"node_id": "text", "chapter": "第1章", "passed": True}],
    )
    return state


def _persist_state(app, run_id: str, state: NovelRunState | None = None) -> NovelRunState:
    current = state or _state()
    current.run_id = run_id
    metadata = app.state.run_store.save_cover_asset(
        run_id,
        candidate_id="cover-1",
        generation_key="1" * 64,
        image=GeneratedImage(content=fake_png_bytes(), mime_type="image/png"),
    )
    current.artifacts["cover"]["candidates"][0].update({**metadata, "asset_status": "ready", "asset_source": "production"})
    app.state.run_store.update_state(run_id, current)
    return current


def test_build_export_artifact_requires_completed_chapters() -> None:
    artifact = build_export_artifact(_state(complete=False))

    assert artifact["validation"]["chapters"] == "blocked"
    assert artifact["package_status"]["ready"] is False


def test_build_export_artifact_requires_a_real_selected_cover_asset() -> None:
    state = _state()
    state.artifacts["cover"]["candidates"][0]["image_url"] = "   "
    state.artifacts["cover"]["candidates"].append({"id": "cover-2", "image_url": "/assets/cover-2.png"})

    artifact = build_export_artifact(state)

    assert artifact["validation"]["cover"] == "pending"
    assert artifact["package_status"]["ready"] is False


def test_export_contract_preserves_the_selected_cover_asset() -> None:
    artifact = build_export_artifact(_state())

    validation = validate_stage_artifact("export_artifact", artifact)

    assert validation.valid is True
    assert validation.artifact["cover_asset"]["candidate_id"] == "cover-1"
    assert validation.artifact["cover_asset"]["asset_id"] == "cover-aaaaaaaaaaaaaaaaaaaaaaaa"
    assert validation.artifact["cover_asset"]["sha256"] == "a" * 64


def test_export_quality_gate_keeps_chapter_reports_separate() -> None:
    state = _state()
    state.quality_reports = [
        {"node_id": "text", "chapter_id": "chapter-1", "passed": False},
        {"node_id": "text", "chapter_id": "chapter-2", "passed": True},
    ]

    artifact = build_export_artifact(state)

    assert artifact["validation"]["quality"] == "blocked"
    assert artifact["package_status"]["ready"] is False


def test_zip_export_is_a_real_archive_with_manifest_and_chapters() -> None:
    state = _state()
    content, filename, media_type = build_export_package(state, package_format="zip")

    assert filename == "雾港交付.zip"
    assert media_type == "application/zip"
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = set(archive.namelist())
        assert "manifest.json" in names
        assert "chapters/001-第一章.md" in names
        assert json.loads(archive.read("manifest.json"))["validation"]["chapters"] == "ready"


def test_frozen_selection_binds_chapter_content_cover_quality_and_source_artifacts() -> None:
    state = _state()
    artifact = build_export_artifact(state)

    snapshot, digest = freeze_export_selection(
        state,
        artifact,
        package_format="zip",
        chapter_ids=["chapter-2", "chapter-1"],
        metadata={"title": "冻结稿", "author": "林舟"},
    )

    assert len(digest) == 64
    assert snapshot["chapter_ids"] == ["chapter-2", "chapter-1"]
    assert snapshot["chapters"][0]["content_sha256"] == hashlib.sha256("第二章正文".encode()).hexdigest()
    assert snapshot["cover_asset"]["asset_id"] == "cover-aaaaaaaaaaaaaaaaaaaaaaaa"
    assert snapshot["quality_digest"]
    assert snapshot["source_artifact_digests"]["chapters"]


def test_frozen_selection_binds_confirmed_canon_facts() -> None:
    state = _state()
    artifact = build_export_artifact(state)
    first_snapshot, first_digest = freeze_export_selection(
        state,
        artifact,
        package_format="zip",
        chapter_ids=["chapter-1"],
        metadata={"title": "Canon 稿"},
    )
    state.canon_facts.append({
        "id": "canon-1",
        "target": "雾港",
        "claim_key": "signal",
        "fact": "雾钟每晚只响一次",
        "status": "confirmed",
        "sources": [],
    })
    second_snapshot, second_digest = freeze_export_selection(
        state,
        artifact,
        package_format="zip",
        chapter_ids=["chapter-1"],
        metadata={"title": "Canon 稿"},
    )

    assert first_snapshot["canon_digest"] != second_snapshot["canon_digest"]
    assert first_digest != second_digest


def test_export_preserves_the_frozen_chapter_order() -> None:
    content, _, _ = build_export_package(
        _state(),
        package_format="md",
        chapter_ids=["chapter-2", "chapter-1"],
    )

    rendered = content.decode("utf-8")
    assert rendered.index("## 第二章") < rendered.index("## 第一章")


def test_export_rejects_duplicate_chapter_ids() -> None:
    with pytest.raises(ExportDeliveryError, match="不能重复"):
        build_export_package(
            _state(),
            package_format="md",
            chapter_ids=["chapter-1", "chapter-1"],
        )


def test_export_api_returns_downloadable_package(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-api"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "雾港交付"})
    _persist_state(app, run_id)

    response = TestClient(app).post(f"/api/runs/{run_id}/export-package", json={"format": "zip", "chapter_ids": ["chapter-1", "chapter-2"]})

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/zip")
    assert "filename*=UTF-8''" in response.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        assert "chapters/002-第二章.md" in archive.namelist()
        assert "assets/cover.png" in archive.namelist()
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["selection_digest"] == response.headers["x-selection-digest"]
        assert manifest["frozen_selection"]["cover_asset"]["asset_id"]
    receipt = TestClient(app).get(f"/api/runs/{run_id}/exports").json()["items"][0]
    assert receipt["version"] == 1
    assert receipt["selection_digest"] == response.headers["x-selection-digest"]
    assert any(item["path"] == "assets/cover.png" for item in receipt["files"])


def test_export_api_freezes_all_chapters_when_legacy_request_omits_selection(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-default-selection"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "默认全选"})
    _persist_state(app, run_id)
    client = TestClient(app)

    response = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "md", "request_id": "default-selection-request"},
    )

    assert response.status_code == 200
    receipt = client.get(f"/api/runs/{run_id}/exports").json()["items"][0]
    assert receipt["chapter_ids"] == ["chapter-1", "chapter-2"]
    assert response.content.decode("utf-8").index("## 第一章") < response.content.decode("utf-8").index("## 第二章")


def test_export_receipt_is_idempotent_and_re_downloadable(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-receipt"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "雾港收据"})
    _persist_state(app, run_id)
    client = TestClient(app)
    payload = {"format": "md", "chapter_ids": ["chapter-1"], "request_id": "stable-export-request"}

    first = client.post(f"/api/runs/{run_id}/export-package", json=payload)
    second = client.post(f"/api/runs/{run_id}/export-package", json=payload)

    assert first.status_code == second.status_code == 200
    assert first.content == second.content
    assert first.headers["x-export-id"] == second.headers["x-export-id"]
    receipts = client.get(f"/api/runs/{run_id}/exports")
    assert receipts.status_code == 200
    assert len(receipts.json()["items"]) == 1
    receipt = receipts.json()["items"][0]
    assert receipt["source_state_revision"] > 0
    assert len(receipt["source_state_digest"]) == 64
    assert receipt["snapshot_id"].startswith("state-revision-")
    export_id = receipt["export_id"]
    redownload = client.get(f"/api/runs/{run_id}/exports/{export_id}")
    assert redownload.status_code == 200
    assert redownload.content == first.content


def test_export_rejects_a_state_change_during_package_build(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    import novel_workflow.api.routes.exports as export_routes

    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-revision-conflict"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "雾港冲突"})
    _persist_state(app, run_id)
    original_build = export_routes.build_export_package

    def build_while_state_changes(
        state,
        *,
        package_format: str,
        chapter_ids: list[str],
        metadata: dict[str, str],
        cover_asset_reader=None,
        frozen_selection=None,
        selection_digest: str = "",
    ):
        changed = state.model_copy(deep=True)
        changed.inputs["title"] = "并发修改后的标题"
        app.state.run_store.update_state(run_id, changed)
        return original_build(
            state,
            package_format=package_format,
            chapter_ids=chapter_ids,
            metadata=metadata,
            cover_asset_reader=cover_asset_reader,
            frozen_selection=frozen_selection,
            selection_digest=selection_digest,
        )

    monkeypatch.setattr(export_routes, "build_export_package", build_while_state_changes)
    response = TestClient(app).post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "md", "chapter_ids": ["chapter-1"], "request_id": "revision-conflict-request"},
    )

    assert response.status_code == 409
    assert "状态在导出期间发生变化" in response.json()["detail"]
    assert app.state.run_store.list_exports(run_id) == []


def test_export_metadata_is_frozen_into_package_and_receipt(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-metadata"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "元数据交付"})
    _persist_state(app, run_id)
    client = TestClient(app)
    metadata = {
        "title": "雾港校订本",
        "author": "林舟",
        "bundle_name": "雾港_投稿版.zip",
        "version_note": "编辑定稿版",
    }

    response = client.post(
        f"/api/runs/{run_id}/export-package",
        json={
            "format": "zip",
            "chapter_ids": ["chapter-2", "chapter-1"],
            "metadata": metadata,
            "request_id": "metadata-export-request",
        },
    )

    assert response.status_code == 200
    assert response.headers["x-artifact-signature"]
    assert response.headers["x-export-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert "%E9%9B%BE%E6%B8%AF_%E6%8A%95%E7%A8%BF%E7%89%88.zip" in response.headers["content-disposition"]
    receipt = client.get(f"/api/runs/{run_id}/exports").json()["items"][0]
    assert receipt["chapter_ids"] == ["chapter-2", "chapter-1"]
    assert receipt["metadata"] == {**metadata, "bundle_name": "雾港_投稿版"}
    with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        readme = archive.read("README.md").decode("utf-8")
        assert manifest["delivery_metadata"] == receipt["metadata"]
        assert "作者：林舟" in readme
        assert "版本说明：编辑定稿版" in readme
        assert archive.read("chapters/001-第二章.md").decode("utf-8") == "第二章正文"


def test_export_request_id_rejects_changed_metadata(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-metadata-conflict"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "参数冲突"})
    _persist_state(app, run_id)
    client = TestClient(app)
    payload = {
        "format": "md",
        "chapter_ids": ["chapter-1"],
        "metadata": {"title": "雾港", "author": "林舟"},
        "request_id": "metadata-conflict-request",
    }

    first = client.post(f"/api/runs/{run_id}/export-package", json=payload)
    changed = client.post(
        f"/api/runs/{run_id}/export-package",
        json={**payload, "metadata": {**payload["metadata"], "author": "另一位作者"}},
    )

    assert first.status_code == 200
    assert changed.status_code == 409
    assert "不能复用不同的导出参数" in changed.json()["detail"]


def test_export_receipt_remains_bound_to_its_snapshot_after_run_changes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-snapshot-link"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "快照关联"})
    _persist_state(app, run_id)
    app.state.run_store.append_event(run_id, {"type": "run_export_ready", "run_id": run_id, "node_id": "export"})
    source_snapshot_id = app.state.run_store.latest_snapshot(run_id)["snapshot_id"]
    client = TestClient(app)
    payload = {"format": "md", "chapter_ids": ["chapter-1"], "request_id": "snapshot-linked-export"}

    first = client.post(f"/api/runs/{run_id}/export-package", json=payload)
    receipt = client.get(f"/api/runs/{run_id}/exports").json()["items"][0]
    first_sha = hashlib.sha256(first.content).hexdigest()

    changed = _state()
    changed.inputs["title"] = "运行变化后的标题"
    changed.artifacts["chapters"]["chapters"][0]["content"] = "变化后的正文"
    app.state.run_store.update_state(run_id, changed)
    repeated = client.post(f"/api/runs/{run_id}/export-package", json=payload)
    redownload = client.get(f"/api/runs/{run_id}/exports/{receipt['export_id']}")

    assert first.status_code == repeated.status_code == redownload.status_code == 200
    assert receipt["snapshot_id"] == source_snapshot_id
    assert receipt["sha256"] == first_sha
    assert repeated.headers["x-export-id"] == receipt["export_id"]
    assert repeated.content == first.content
    assert redownload.content == first.content
    assert hashlib.sha256(redownload.content).hexdigest() == receipt["sha256"]


def test_identical_frozen_selection_reuses_version_across_request_ids(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-semantic-idempotency"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": run_id, "title": "版本去重"})
    _persist_state(app, run_id)
    client = TestClient(app)
    base = {"format": "zip", "chapter_ids": ["chapter-1"], "metadata": {"version_note": "投稿版"}}

    first = client.post(f"/api/runs/{run_id}/export-package", json={**base, "request_id": "semantic-request-one"})
    second = client.post(f"/api/runs/{run_id}/export-package", json={**base, "request_id": "semantic-request-two"})
    repeated_conflict = client.post(
        f"/api/runs/{run_id}/export-package",
        json={**base, "format": "md", "request_id": "semantic-request-two"},
    )

    assert first.status_code == second.status_code == 200
    assert first.headers["x-export-id"] == second.headers["x-export-id"]
    assert first.headers["x-export-version"] == second.headers["x-export-version"] == "1"
    assert len(client.get(f"/api/runs/{run_id}/exports").json()["items"]) == 1
    assert repeated_conflict.status_code == 409
    assert "不能复用不同的导出参数" in repeated_conflict.json()["detail"]


def test_cover_change_creates_a_new_delivery_version(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-cover-version"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": run_id, "title": "封面版本"})
    state = _persist_state(app, run_id)
    client = TestClient(app)

    first = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "zip", "chapter_ids": ["chapter-1"], "request_id": "cover-version-one"},
    )
    second_cover = app.state.run_store.save_cover_asset(
        run_id,
        candidate_id="cover-2",
        generation_key="2" * 64,
        image=GeneratedImage(content=fake_png_bytes(width=300, height=450), mime_type="image/png"),
    )
    state.artifacts["cover"]["candidates"].append({
        "id": "cover-2",
        **second_cover,
        "asset_status": "ready",
        "asset_source": "production",
    })
    state.artifacts["cover"]["selected_candidate_id"] = "cover-2"
    app.state.run_store.update_state(run_id, state)
    second = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "zip", "chapter_ids": ["chapter-1"], "request_id": "cover-version-two"},
    )

    receipts = client.get(f"/api/runs/{run_id}/exports").json()["items"]
    assert first.status_code == second.status_code == 200
    assert first.headers["x-export-id"] != second.headers["x-export-id"]
    assert [item["version"] for item in receipts] == [2, 1]
    assert receipts[0]["cover_asset"]["candidate_id"] == "cover-2"
    assert receipts[0]["selection_digest"] != receipts[1]["selection_digest"]


def test_history_download_rejects_a_tampered_export_file(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-integrity"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": "export-project", "title": "完整性校验"})
    _persist_state(app, run_id)
    client = TestClient(app)
    response = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "md", "chapter_ids": ["chapter-1"], "request_id": "integrity-export"},
    )
    assert response.status_code == 200
    receipt = app.state.run_store.list_exports(run_id)[0]
    export_path = app.state.run_store.run_dir(run_id) / "exports" / f"{receipt['export_id']}.md"
    export_path.write_bytes(b"tampered")

    redownload = client.get(f"/api/runs/{run_id}/exports/{receipt['export_id']}")

    assert redownload.status_code == 400
    assert "校验失败" in redownload.json()["detail"]


def test_history_download_returns_immutable_receipt_headers(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-history-headers"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": run_id, "title": "下载校验头"})
    _persist_state(app, run_id)
    client = TestClient(app)
    generated = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "md", "chapter_ids": ["chapter-1"], "request_id": "history-header-request"},
    )

    redownload = client.get(f"/api/runs/{run_id}/exports/{generated.headers['x-export-id']}")

    assert redownload.status_code == 200
    assert redownload.headers["cache-control"].endswith("immutable")
    assert redownload.headers["etag"] == f'"{generated.headers["x-export-sha256"]}"'
    assert redownload.headers["x-selection-digest"] == generated.headers["x-selection-digest"]
    assert redownload.headers["x-export-version"] == "1"
    assert redownload.headers["x-content-type-options"] == "nosniff"


def test_history_download_keeps_legacy_receipts_available(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-legacy-receipt"
    app.state.run_store.create(run_id, default_workflow(), {"project_id": run_id, "title": "旧版收据"})
    _persist_state(app, run_id)
    client = TestClient(app)
    generated = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "md", "chapter_ids": ["chapter-1"], "request_id": "legacy-source-request"},
    )
    export_id = generated.headers["x-export-id"]
    run_path = app.state.run_store.run_dir(run_id) / "run.json"
    stored = json.loads(run_path.read_text(encoding="utf-8"))
    for key in ("schema_version", "selection_digest", "selection_snapshot", "files", "cover_asset"):
        stored["exports"][0].pop(key, None)
    run_path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")

    redownload = client.get(f"/api/runs/{run_id}/exports/{export_id}")

    assert redownload.status_code == 200
    assert redownload.content == generated.content


def test_export_store_rejects_a_tampered_frozen_selection(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-tampered-selection"
    workflow = default_workflow()
    app.state.run_store.create(run_id, workflow, {"project_id": run_id, "title": "冻结摘要校验"})
    _persist_state(app, run_id)
    client = TestClient(app)
    generated = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "md", "chapter_ids": ["chapter-1"], "request_id": "selection-source-request"},
    )
    receipt = app.state.run_store.list_exports(run_id)[0]
    forged = {**receipt, "export_id": "export-" + "f" * 32, "request_id": "selection-forged-request"}
    forged["selection_snapshot"] = {**receipt["selection_snapshot"], "chapter_ids": ["chapter-2"]}

    with pytest.raises(ValueError, match="冻结选择摘要不一致"):
        app.state.run_store.save_export(run_id, forged, generated.content)


def test_export_store_rejects_an_incomplete_zip_file_manifest(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-incomplete-file-manifest"
    app.state.run_store.create(run_id, default_workflow(), {"project_id": run_id, "title": "文件清单校验"})
    _persist_state(app, run_id)
    generated = TestClient(app).post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "zip", "chapter_ids": ["chapter-1"], "request_id": "manifest-source-request"},
    )
    receipt = app.state.run_store.list_exports(run_id)[0]
    forged = {
        **receipt,
        "export_id": "export-" + "e" * 32,
        "request_id": "manifest-forged-request",
        "files": [item for item in receipt["files"] if item.get("path") != "assets/cover.png"],
    }

    with pytest.raises(ValueError, match="ZIP 内部文件清单不一致"):
        app.state.run_store.save_export(run_id, forged, generated.content)


def test_history_download_rejects_a_tampered_receipt_manifest(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "export-tampered-receipt-manifest"
    app.state.run_store.create(run_id, default_workflow(), {"project_id": run_id, "title": "收据清单校验"})
    _persist_state(app, run_id)
    client = TestClient(app)
    generated = client.post(
        f"/api/runs/{run_id}/export-package",
        json={"format": "zip", "chapter_ids": ["chapter-1"], "request_id": "receipt-manifest-request"},
    )
    export_id = generated.headers["x-export-id"]
    run_path = app.state.run_store.run_dir(run_id) / "run.json"
    stored = json.loads(run_path.read_text(encoding="utf-8"))
    stored["exports"][0]["files"] = [
        item for item in stored["exports"][0]["files"]
        if item.get("path") != "assets/cover.png"
    ]
    run_path.write_text(json.dumps(stored, ensure_ascii=False, indent=2), encoding="utf-8")

    redownload = client.get(f"/api/runs/{run_id}/exports/{export_id}")

    assert redownload.status_code == 400
    assert "ZIP 内部文件清单不一致" in redownload.json()["detail"]
