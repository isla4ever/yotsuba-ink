from __future__ import annotations

import io
import zipfile

import pytest
from fastapi.testclient import TestClient

from novel_workflow.api.app import create_app
from novel_workflow.orchestration.export_delivery import ExportDeliveryError
from novel_workflow.orchestration.export_preview import build_export_preview
from novel_workflow.workflows.schemas import NovelRunState
from novel_workflow.workflows.templates import default_workflow


def _preview_state(run_id: str = "preview-run") -> NovelRunState:
    return NovelRunState(
        run_id=run_id,
        project_id="preview-project",
        workflow_id="default-novel-workflow",
        inputs={"title": "雾港预览", "quality_mode": "balanced"},
        artifacts={
            "chapters": {
                "chapters": [
                    {
                        "id": "chapter-1",
                        "title": "第一章",
                        "content": "第一章已完成正文",
                        "status": "completed",
                        "words": 8,
                    },
                    {
                        "id": "chapter-2",
                        "title": "第二章",
                        "content": "第二章仍在创作",
                        "status": "drafting",
                        "words": 7,
                    },
                ],
            },
        },
    )


def test_preview_only_uses_completed_chapters_and_marks_the_file() -> None:
    content, filename, media_type = build_export_preview(
        _preview_state(),
        package_format="md",
        chapter_ids=["chapter-1"],
    )

    rendered = content.decode("utf-8")
    assert filename == "雾港预览-preview.md"
    assert media_type.startswith("text/markdown")
    assert "雾港预览（预览稿）" in rendered
    assert "第一章已完成正文" in rendered
    assert "第二章仍在创作" not in rendered


def test_preview_rejects_drafting_chapters() -> None:
    with pytest.raises(ExportDeliveryError, match="只能包含已完成"):
        build_export_preview(
            _preview_state(),
            package_format="md",
            chapter_ids=["chapter-2"],
        )


def test_preview_zip_has_an_explicit_non_final_manifest() -> None:
    content, _, _ = build_export_preview(_preview_state(), package_format="zip")

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        assert "PREVIEW.md" in archive.namelist()
        assert "preview-manifest.json" in archive.namelist()
        assert "chapters/001-第一章.md" in archive.namelist()


def test_preview_api_does_not_create_a_formal_export_receipt(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    app = create_app()
    run_id = "preview-api"
    app.state.run_store.create(run_id, default_workflow(), {"project_id": "preview-project"})
    app.state.run_store.update_state(run_id, _preview_state(run_id))
    client = TestClient(app)

    response = client.post(
        f"/api/runs/{run_id}/export-preview",
        json={"format": "md", "chapter_ids": ["chapter-1"]},
    )

    assert response.status_code == 200
    assert response.headers["x-export-mode"] == "preview"
    assert "no-store" in response.headers["cache-control"]
    assert app.state.run_store.list_exports(run_id) == []
