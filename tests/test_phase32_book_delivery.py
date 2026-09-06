from __future__ import annotations

import io
import zipfile
from pathlib import Path
from xml.etree import ElementTree

import pytest

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    BookDeliveryArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.providers.base import GeneratedImage
from novel_workflow.storage.cover_asset_store import CoverAssetStore
from novel_workflow.storage.export_store import ExportStore
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactStore
from tests.fakes import fake_png_bytes
from tests.test_phase32_execution_api import _app


def _delivery_fixture(tmp_path: Path):
    run_id = "book-delivery-run"
    artifacts = Phase32ArtifactStore(tmp_path / "artifacts")
    chapter_refs = ("section-1", "section-2")
    chapters = [
        artifacts.save_deterministic(
            run_id=run_id,
            creation_route_id="short_novel",
            stage_id="text",
            artifact=ShortProseUnitArtifact(
                unit_ref=chapter_ref,
                unit_kind="chapter",
                title=title,
                pov_subject_ref="maya",
                content=content,
            ),
        )
        for chapter_ref, title, content in (
            ("section-1", "失踪页", "雨水沿着档案盒的折痕落下。\n\n她找到第一枚签章。"),
            ("section-2", "公开记录", "听证厅安静下来。\n\n原始记录终于被投上大屏。"),
        )
    ]
    covers = CoverAssetStore(tmp_path / "covers")
    cover_bytes = fake_png_bytes(width=512, height=768, seed=7)
    cover = covers.save(
        run_id,
        operation_key=f"{run_id}:cover:image:1",
        candidate_index=1,
        generation_attempt=1,
        image=GeneratedImage(content=cover_bytes, mime_type="image/png"),
        expected_ratio=2 / 3,
    )
    delivery = artifacts.save_deterministic(
        run_id=run_id,
        creation_route_id="short_novel",
        stage_id="export",
        artifact=BookDeliveryArtifact(
            title="被删去的城市",
            author="四叶墨工作室",
            version_note="锁定交付版 1.0",
            formats=("epub", "docx", "markdown"),
            chapter_refs=chapter_refs,
            chapter_version_refs=tuple(record.artifact_ref for record in chapters),
            cover_asset_ref=cover.asset_id,
        ),
    )
    return run_id, delivery, chapters, (cover, cover_bytes)


def test_book_delivery_materializes_valid_epub_docx_and_markdown_idempotently(
    tmp_path: Path,
) -> None:
    run_id, delivery, chapters, cover_asset = _delivery_fixture(tmp_path)
    exports = ExportStore(tmp_path / "exports")

    first = exports.materialize_book_delivery(
        run_id,
        delivery,
        chapters,
        cover_asset=cover_asset,
    )
    second = exports.materialize_book_delivery(
        run_id,
        delivery,
        chapters,
        cover_asset=cover_asset,
    )

    assert [record.format for record in first] == ["epub", "docx", "markdown"]
    assert first == second
    assert all(record.chapter_refs == ("section-1", "section-2") for record in first)
    assert all(record.cover_asset_ref == cover_asset[0].asset_id for record in first)
    expected_manifest = (
        {
            "ordinal": 1,
            "chapter_ref": "section-1",
            "version_ref": chapters[0].artifact_ref,
            "title": "失踪页",
            "unit_kind": "chapter",
            "volume_ref": "",
            "character_count": len("雨水沿着档案盒的折痕落下。她找到第一枚签章。"),
        },
        {
            "ordinal": 2,
            "chapter_ref": "section-2",
            "version_ref": chapters[1].artifact_ref,
            "title": "公开记录",
            "unit_kind": "chapter",
            "volume_ref": "",
            "character_count": len("听证厅安静下来。原始记录终于被投上大屏。"),
        },
    )
    assert all(
        tuple(row.model_dump() for row in record.chapter_manifest) == expected_manifest
        for record in first
    )

    markdown_record = next(record for record in first if record.format == "markdown")
    _, markdown = exports.book_delivery_content(run_id, markdown_record.export_id)
    decoded_markdown = markdown.decode("utf-8")
    assert "data:image/png;base64," in decoded_markdown
    assert decoded_markdown.index("第 1 章 失踪页") < decoded_markdown.index("第 2 章 公开记录")

    epub_record = next(record for record in first if record.format == "epub")
    _, epub = exports.book_delivery_content(run_id, epub_record.export_id)
    with zipfile.ZipFile(io.BytesIO(epub)) as archive:
        assert archive.namelist()[0] == "mimetype"
        assert archive.read("mimetype") == b"application/epub+zip"
        assert archive.read("OEBPS/cover.png") == cover_asset[1]
        for name in (
            "META-INF/container.xml",
            "OEBPS/cover.xhtml",
            "OEBPS/chapter-0001.xhtml",
            "OEBPS/chapter-0002.xhtml",
            "OEBPS/nav.xhtml",
            "OEBPS/content.opf",
        ):
            ElementTree.fromstring(archive.read(name))
        assert "失踪页" in archive.read("OEBPS/chapter-0001.xhtml").decode("utf-8")

    docx_record = next(record for record in first if record.format == "docx")
    _, docx = exports.book_delivery_content(run_id, docx_record.export_id)
    with zipfile.ZipFile(io.BytesIO(docx)) as archive:
        assert archive.read("word/media/cover.png") == cover_asset[1]
        for name in (
            "[Content_Types].xml",
            "_rels/.rels",
            "docProps/core.xml",
            "docProps/app.xml",
            "word/document.xml",
            "word/styles.xml",
            "word/_rels/document.xml.rels",
        ):
            ElementTree.fromstring(archive.read(name))
        document = archive.read("word/document.xml").decode("utf-8")
        assert document.index("第 1 章 失踪页") < document.index("第 2 章 公开记录")


def test_book_delivery_rejects_wrong_versions_and_detects_damage(tmp_path: Path) -> None:
    run_id, delivery, chapters, cover_asset = _delivery_fixture(tmp_path)
    exports = ExportStore(tmp_path / "exports")

    with pytest.raises(ValueError, match="missing or out of frozen order"):
        exports.materialize_book_delivery(
            run_id,
            delivery,
            list(reversed(chapters)),
            cover_asset=cover_asset,
        )

    records = exports.materialize_book_delivery(
        run_id,
        delivery,
        chapters,
        cover_asset=cover_asset,
    )
    record = records[0]
    content_path = exports.root / run_id / "book-files" / f"{record.export_id}.bin"
    content_path.write_bytes(b"damaged")
    with pytest.raises(ValueError, match="immutable receipt"):
        exports.read_book_delivery(run_id, record.export_id)


def test_short_novel_delivery_api_lists_and_downloads_materialized_file(
    tmp_path: Path,
) -> None:
    client, run_id = _app(tmp_path)
    result = client.post(f"/api/runs/{run_id}/start").json()

    while result["run"]["read_model"]["status"] != "completed":
        decision = result["decision"]
        command = {
            "decision_id": decision["decision_id"],
            "action": "accept",
            "domain_revision": decision["domain_revision"],
        }
        if decision["stage_id"] == "cover":
            current = client.get(
                f"/api/runs/{run_id}/stages/cover/artifacts/current"
            ).json()
            payload = dict(current["payload"])
            payload["selected_asset_ref"] = payload["candidates"][0]["asset_ref"]
            saved = client.put(
                f"/api/runs/{run_id}/stage-drafts/{decision['decision_id']}",
                json={
                    "domain_revision": decision["domain_revision"],
                    "source_artifact_ref": current["artifact_ref"],
                    "payload": payload,
                },
            )
            assert saved.status_code == 200
            command["draft_ref"] = saved.json()["draft"]["draft_ref"]
        response = client.post(f"/api/runs/{run_id}/decisions", json=command)
        assert response.status_code == 200, response.text
        result = response.json()

    listed = client.get(f"/api/runs/{run_id}/exports")
    assert listed.status_code == 200
    payload = listed.json()
    assert payload["artifact_type"] == "book_delivery"
    assert payload["dependency_status"] == "ready"
    assert payload["deferred_reason"] == ""
    assert payload["source_artifact_refs"]
    assert payload["artifact_ref"] == result["run"]["read_model"]["artifact_refs"]["export"]["artifact_ref"]
    assert [item["format"] for item in payload["items"]] == [
        result["run"]["definition"]["export_profile"]
    ]

    record = payload["items"][0]
    downloaded = client.get(f"/api/runs/{run_id}/exports/{record['export_id']}")
    assert downloaded.status_code == 200
    assert downloaded.content.startswith(b"PK")
    assert downloaded.headers["x-content-sha256"] == record["sha256"]
    assert "filename*=UTF-8''" in downloaded.headers["content-disposition"]

    missing = client.get(f"/api/runs/{run_id}/exports/missing-export")
    assert missing.status_code == 404
