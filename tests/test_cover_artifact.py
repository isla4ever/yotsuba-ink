from __future__ import annotations

import pytest
from pydantic import ValidationError

from novel_workflow.output_contracts.schemas import CoverContract


def _cover_artifact() -> dict:
    return {
        "brief": "旧港雾夜与声纹磁带形成悬疑封面气质。",
        "visual_keywords": ["旧港", "磁带", "雾钟"],
        "composition": "2:3 竖版，人物背影面对雾钟。",
        "copy_suggestions": ["雾港旧声"],
        "prompt": "cinematic mist harbor, suspense novel cover",
        "candidates": [
            {
                "id": "cover-1",
                "image_url": "",
                "composition": "背影与雾钟",
                "palette": "冷灰蓝",
                "quality_summary": "标题留白充足",
            },
            {
                "id": "cover-2",
                "image_url": "/assets/cover-2.png",
                "composition": "磁带与波形",
                "palette": "黑金",
                "quality_summary": "题材识别明确",
            },
        ],
        "selected_candidate_id": "cover-2",
    }


def test_cover_contract_accepts_a_selection_that_references_a_candidate() -> None:
    artifact = CoverContract.model_validate(_cover_artifact())

    assert artifact.selected_candidate_id == "cover-2"


def test_cover_contract_rejects_duplicate_candidate_ids() -> None:
    value = _cover_artifact()
    value["candidates"][1]["id"] = "cover-1"

    with pytest.raises(ValidationError, match="ids must be unique"):
        CoverContract.model_validate(value)


def test_cover_contract_rejects_an_unknown_selected_candidate() -> None:
    value = _cover_artifact()
    value["selected_candidate_id"] = "cover-missing"

    with pytest.raises(ValidationError, match="must reference a candidate"):
        CoverContract.model_validate(value)
