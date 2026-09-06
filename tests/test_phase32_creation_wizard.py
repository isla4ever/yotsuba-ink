from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from novel_workflow.workflows.phase32_creation_wizard import (
    CreationIntent,
    WorkflowCatalogEntry,
    WorkflowSelection,
    official_workflow_catalog,
    recommend_workflows,
    resolve_workflow_selection,
)
from novel_workflow.workflows.route_specs import (
    LONG_NOVEL_ROUTE,
    SCREENPLAY_SAMPLE_ROUTE,
    SHORT_NOVEL_ROUTE,
)


def test_step_one_infers_screenplay_route_without_novel_length() -> None:
    intent = CreationIntent(
        creative_intent="一份 12 分钟的悬疑剧本样片，核心是被篡改的城市档案。",
        creation_kind="screenplay",
        requested_target=12,
    )

    assert intent.creation_route_id == "screenplay_sample"
    assert intent.creation_language == "zh-CN"
    assert intent.scale_profile().unit == "minutes"
    assert intent.scale_profile().target == 12


@pytest.mark.parametrize("length_class", ["short_novel", "long_novel"])
def test_step_one_requires_novel_length_class_and_maps_it_to_route(length_class: str) -> None:
    intent = CreationIntent(
        creative_intent="围绕城市记忆展开一条完整小说主线。",
        creation_kind="novel",
        novel_length_class=length_class,  # type: ignore[arg-type]
    )

    assert intent.creation_route_id == length_class
    assert intent.scale_profile().unit == "characters"


def test_step_one_rejects_ambiguous_or_cross_kind_scale_inputs() -> None:
    with pytest.raises(ValidationError, match="requires short_novel or long_novel"):
        CreationIntent(
            creative_intent="还没有决定写哪种小说。",
            creation_kind="novel",
        )
    with pytest.raises(ValidationError, match="cannot define a novel length"):
        CreationIntent(
            creative_intent="剧本不应该携带小说长度分类。",
            creation_kind="screenplay",
            novel_length_class="short_novel",
        )
    with pytest.raises(ValidationError, match="target must be between"):
        CreationIntent(
            creative_intent="短中篇目标不能超出 P0 包络。",
            creation_kind="novel",
            novel_length_class="short_novel",
            requested_target=200_000,
        )
    with pytest.raises(ValidationError, match="zh-CN"):
        CreationIntent(
            creative_intent="当前产品不应创建没有受支持语言合同的 Run。",
            creation_language="en-US",  # type: ignore[arg-type]
            creation_kind="screenplay",
        )


def test_step_two_official_catalog_is_filtered_to_inferred_route() -> None:
    catalog = official_workflow_catalog()
    intent = CreationIntent(
        creative_intent="做一个长篇连载项目。",
        creation_kind="novel",
        novel_length_class="long_novel",
    )
    recommendations = recommend_workflows(intent, catalog)

    assert len(recommendations) == 1
    assert recommendations[0].workflow.route_id == "long_novel"
    assert recommendations[0].workflow.source == "official"
    assert recommendations[0].recommended is True


def test_step_two_rejects_the_unreleased_new_workflow_path() -> None:
    intent = CreationIntent(
        creative_intent="先做一份可持续修订的剧本样片流水线。",
        creation_kind="screenplay",
    )

    with pytest.raises(ValidationError, match="existing"):
        WorkflowSelection.model_validate({"intent": intent, "mode": "new"})


def test_step_two_rejects_a_custom_workflow_identity() -> None:
    intent = CreationIntent(
        creative_intent="写一个短中篇调查故事。",
        creation_kind="novel",
        novel_length_class="short_novel",
    )
    selection = WorkflowSelection(
        intent=intent,
        mode="existing",
        workflow_id="custom.short-investigation",
    )

    with pytest.raises(ValueError, match="unavailable or missing"):
        resolve_workflow_selection(selection, official_workflow_catalog())


def test_step_two_rejects_unavailable_or_wrong_route_workflows() -> None:
    intent = CreationIntent(
        creative_intent="选择短中篇流水线。",
        creation_kind="novel",
        novel_length_class="short_novel",
    )
    wrong_route = official_workflow_catalog()[0]
    selection = WorkflowSelection(
        intent=intent,
        mode="existing",
        workflow_id=wrong_route.workflow_id,
    )
    with pytest.raises(ValueError, match="does not match"):
        resolve_workflow_selection(selection, (wrong_route,))

    unavailable = WorkflowCatalogEntry(
        workflow_id="official.short_novel",
        route_id="short_novel",
        label="已下线流水线",
        source="official",
        revision="r1",
        workflow_digest="a" * 64,
        available=False,
    )
    with pytest.raises(ValueError, match="unavailable or missing"):
        resolve_workflow_selection(
            WorkflowSelection(
                intent=intent,
                mode="existing",
                workflow_id=unavailable.workflow_id,
            ),
            (unavailable,),
        )


def test_creation_wizard_source_has_no_legacy_modes_or_runtime_imports() -> None:
    source = Path(
        Path(__file__).resolve().parents[1]
        / "src/novel_workflow/workflows/phase32_creation_wizard.py"
    ).read_text(encoding="utf-8")
    assert "quality_mode" not in source
    assert "fast" not in source
    assert "balanced" not in source
    assert "deep" not in source
    assert "novel_workflow.runtime" not in source


def test_route_specs_used_by_official_catalog_are_stable() -> None:
    catalog = official_workflow_catalog()
    assert tuple(item.route_id for item in catalog) == (
        SCREENPLAY_SAMPLE_ROUTE.route_id,
        SHORT_NOVEL_ROUTE.route_id,
        LONG_NOVEL_ROUTE.route_id,
    )
