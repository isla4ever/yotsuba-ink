from __future__ import annotations

import pytest

from novel_workflow.providers.base import GeneratedImage
from novel_workflow.storage.cover_asset_store import CoverAssetStore
from tests.fakes import fake_png_bytes


def test_cover_asset_store_persists_verified_content_and_attempt_projection(tmp_path) -> None:
    store = CoverAssetStore(tmp_path / "covers")
    record = store.save(
        "run-cover",
        operation_key="run-cover:cover:image:2:candidate:1",
        candidate_index=1,
        generation_attempt=2,
        image=GeneratedImage(
            content=fake_png_bytes(),
            mime_type="image/png",
            provider_asset_id="provider-asset-1",
        ),
        expected_ratio=2 / 3,
    )

    loaded, content = store.content("run-cover", record.asset_id)
    assert loaded == record
    assert content == fake_png_bytes()
    assert store.list("run-cover", generation_attempt=1) == []
    assert store.list("run-cover", generation_attempt=2) == [record]


def test_cover_asset_store_rejects_invalid_bytes_and_wrong_ratio(tmp_path) -> None:
    store = CoverAssetStore(tmp_path / "covers")
    with pytest.raises(ValueError, match="PNG、JPEG 或 WebP"):
        store.save(
            "run-cover",
            operation_key="run-cover:cover:image:1:candidate:1",
            candidate_index=1,
            generation_attempt=1,
            image=GeneratedImage(content=b"not-an-image", mime_type="image/png"),
        )
    with pytest.raises(ValueError, match="aspect ratio"):
        store.save(
            "run-cover",
            operation_key="run-cover:cover:image:1:candidate:2",
            candidate_index=2,
            generation_attempt=1,
            image=GeneratedImage(content=fake_png_bytes(), mime_type="image/png"),
            expected_ratio=1,
        )
