from __future__ import annotations

from math import ceil, floor
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


BOOK_SCALE_CONTRACT_VERSION = "book-scale-plan-v1"
DEFAULT_CHAPTER_TARGET_CHARS = 2_000
MIN_TOTAL_CHARS = 3_000
MAX_TOTAL_CHARS = 5_000_000
MIN_TOTAL_CHAPTERS = 1
MAX_TOTAL_CHAPTERS = 2_500
PREFERRED_CHAPTERS_PER_VOLUME = 12
MIN_CHAPTERS_PER_VOLUME = 8
MAX_CHAPTERS_PER_VOLUME = 16
CHAPTER_NATURAL_VARIATION_RATIO = 0.10
CHAPTER_NATURAL_VARIATION_MAX_CHARS = 300
BOOK_NATURAL_VARIATION_RATIO = 0.20
TERMINAL_CHAPTER_CLOSURE_TOLERANCE_RATIO = 0.05
TERMINAL_CHAPTER_CLOSURE_TOLERANCE_MAX_CHARS = 180

BookScaleTargetMode = Literal["total_chars", "total_chapters"]
StageBudgetScope = Literal["per_book", "per_volume", "per_chapter", "per_plan"]


class BookScaleTarget(BaseModel):
    target_mode: BookScaleTargetMode
    target_value: int = Field(gt=0, strict=True)


class StageContentBudget(BaseModel):
    scope: StageBudgetScope
    target_chars: int = Field(gt=0)
    min_chars: int = Field(gt=0)
    max_chars: int = Field(gt=0)
    max_tokens: int = Field(gt=0)
    description: str

    @model_validator(mode="after")
    def validate_range(self) -> "StageContentBudget":
        if not self.min_chars <= self.target_chars <= self.max_chars:
            raise ValueError("阶段目标字符数必须位于合理范围内")
        return self


class VolumeScalePlan(BaseModel):
    volume_index: int = Field(gt=0)
    chapter_start: int = Field(gt=0)
    chapter_end: int = Field(gt=0)
    chapter_count: int = Field(gt=0)
    target_chars: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_chapter_range(self) -> "VolumeScalePlan":
        if self.chapter_end < self.chapter_start:
            raise ValueError("分卷章节终点不能早于起点")
        if self.chapter_count != self.chapter_end - self.chapter_start + 1:
            raise ValueError("分卷章节数量与章节范围不一致")
        return self


class StoryScopeBudget(BaseModel):
    character_min: int = Field(gt=0)
    character_max: int = Field(gt=0)
    relationship_min: int = Field(ge=0)
    relationship_max: int = Field(gt=0)

    @model_validator(mode="after")
    def validate_ranges(self) -> "StoryScopeBudget":
        if self.character_max < self.character_min:
            raise ValueError("人物配额上限不能低于下限")
        if self.relationship_max < self.relationship_min:
            raise ValueError("关系配额上限不能低于下限")
        return self


class NarrativeCapacityPolicy(BaseModel):
    primary_shifts_per_chapter: int = 1
    default_scenes_per_chapter: int = 1
    max_scenes_per_chapter: int = 2
    exceptional_scenes_per_chapter: int = 3
    max_independent_reveals_per_chapter: int = 1
    split_rule: str = (
        "一个章节只承担一个主要叙事位移；独立选择、重大揭示、关系反转或时空视角转换同时出现时，"
        "优先在选择与代价、结果与应对之间拆成相邻章节，并通过 continuity_handoff 交接。"
    )


class BookScalePlan(BaseModel):
    contract_version: Literal["book-scale-plan-v1"] = BOOK_SCALE_CONTRACT_VERSION
    target_mode: BookScaleTargetMode
    target_value: int = Field(gt=0)
    counting_standard: Literal["cjk-visible-chars-v1"] = "cjk-visible-chars-v1"
    total_chars: int = Field(gt=0)
    total_chapters: int = Field(gt=0)
    volume_count: int = Field(gt=0)
    chapters_per_volume: list[int] = Field(min_length=1)
    chapter_target_chars: int = Field(gt=0)
    chapter_soft_min_chars: int = Field(gt=0)
    chapter_soft_max_chars: int = Field(gt=0)
    chapter_hard_min_chars: int = Field(gt=0)
    chapter_hard_max_chars: int = Field(gt=0)
    book_soft_min_chars: int = Field(gt=0)
    book_soft_max_chars: int = Field(gt=0)
    stage_budgets: dict[str, StageContentBudget]
    story_scope: StoryScopeBudget
    capacity_policy: NarrativeCapacityPolicy = Field(default_factory=NarrativeCapacityPolicy)
    volumes: list[VolumeScalePlan] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_plan_closure(self) -> "BookScalePlan":
        if self.volume_count != len(self.chapters_per_volume):
            raise ValueError("卷数与各卷章节分布不一致")
        if self.volume_count != len(self.volumes):
            raise ValueError("卷数与分卷计划不一致")
        if sum(self.chapters_per_volume) != self.total_chapters:
            raise ValueError("各卷章节数之和必须等于全书章节数")
        if sum(volume.chapter_count for volume in self.volumes) != self.total_chapters:
            raise ValueError("分卷计划没有闭合全书章节数")
        if sum(volume.target_chars for volume in self.volumes) != self.total_chars:
            raise ValueError("分卷目标字符数没有闭合全书目标")
        if not (
            self.chapter_hard_min_chars
            <= self.chapter_soft_min_chars
            <= self.chapter_target_chars
            <= self.chapter_soft_max_chars
            <= self.chapter_hard_max_chars
        ):
            raise ValueError("单章字符预算层级不一致")
        if self.book_soft_max_chars < self.book_soft_min_chars:
            raise ValueError("全书字符范围不一致")
        return self

    def budget_for_stage(self, stage_id: str) -> StageContentBudget:
        try:
            return self.stage_budgets[stage_id]
        except KeyError as exc:
            raise ValueError(f"BookScalePlan 缺少 {stage_id} 阶段预算") from exc


def build_book_scale_plan(
    *,
    target_mode: BookScaleTargetMode,
    target_value: int,
) -> BookScalePlan:
    value = _positive_int(target_value, "创作目标")
    if target_mode == "total_chars":
        if not MIN_TOTAL_CHARS <= value <= MAX_TOTAL_CHARS:
            raise ValueError(
                f"目标总字数必须在 {MIN_TOTAL_CHARS}-{MAX_TOTAL_CHARS} 个中文字符之间"
            )
        total_chars = value
        total_chapters = max(
            1,
            _round_half_up(total_chars / DEFAULT_CHAPTER_TARGET_CHARS),
        )
        total_chapters = min(MAX_TOTAL_CHAPTERS, total_chapters)
        chapter_target = _round_half_up(total_chars / total_chapters)
    elif target_mode == "total_chapters":
        if not MIN_TOTAL_CHAPTERS <= value <= MAX_TOTAL_CHAPTERS:
            raise ValueError(
                f"目标总章数必须在 {MIN_TOTAL_CHAPTERS}-{MAX_TOTAL_CHAPTERS} 章之间"
            )
        total_chapters = value
        chapter_target = DEFAULT_CHAPTER_TARGET_CHARS
        total_chars = total_chapters * chapter_target
    else:
        raise ValueError("创作目标只能选择总字数或总章数")

    distribution = distribute_chapters(total_chapters)
    volume_targets = _distribute_total(total_chars, distribution)
    volumes: list[VolumeScalePlan] = []
    chapter_start = 1
    for index, (chapter_total, volume_chars) in enumerate(
        zip(distribution, volume_targets, strict=True),
        start=1,
    ):
        chapter_end = chapter_start + chapter_total - 1
        volumes.append(
            VolumeScalePlan(
                volume_index=index,
                chapter_start=chapter_start,
                chapter_end=chapter_end,
                chapter_count=chapter_total,
                target_chars=volume_chars,
            )
        )
        chapter_start = chapter_end + 1

    soft_min = max(700, floor(chapter_target * 0.80))
    soft_max = max(soft_min, ceil(chapter_target * 1.20))
    hard_min = max(500, floor(chapter_target * 0.65))
    hard_max = max(soft_max, ceil(chapter_target * 1.50))
    if target_mode == "total_chars":
        book_soft_min = floor(total_chars * 0.95)
        book_soft_max = ceil(total_chars * 1.05)
    else:
        book_soft_min = soft_min * total_chapters
        book_soft_max = soft_max * total_chapters

    return BookScalePlan(
        target_mode=target_mode,
        target_value=value,
        total_chars=total_chars,
        total_chapters=total_chapters,
        volume_count=len(distribution),
        chapters_per_volume=distribution,
        chapter_target_chars=chapter_target,
        chapter_soft_min_chars=soft_min,
        chapter_soft_max_chars=soft_max,
        chapter_hard_min_chars=hard_min,
        chapter_hard_max_chars=hard_max,
        book_soft_min_chars=book_soft_min,
        book_soft_max_chars=book_soft_max,
        stage_budgets=_stage_budgets(
            total_chars=total_chars,
            total_chapters=total_chapters,
            volume_count=len(distribution),
            chapter_target=chapter_target,
            chapter_soft_min=soft_min,
            chapter_soft_max=soft_max,
        ),
        story_scope=_story_scope(total_chapters),
        volumes=volumes,
    )


def chapter_acceptance_maximum(
    book_plan: BookScalePlan,
    *,
    chapter_index: int,
    completed_chapter_chars: int,
) -> int:
    """Return the active chapter ceiling for the selected creation target.

    Chapter-count runs treat the chapter count as the only hard book target, so
    their derived total character count remains pacing guidance. Character-count
    runs must also reserve the remaining whole-book capacity for future chapters.
    """
    current_index = min(
        book_plan.total_chapters,
        max(1, int(chapter_index or 1)),
    )
    natural_allowance = min(
        CHAPTER_NATURAL_VARIATION_MAX_CHARS,
        ceil(
            book_plan.chapter_hard_max_chars
            * CHAPTER_NATURAL_VARIATION_RATIO
        ),
    )
    closure_allowance = (
        min(
            TERMINAL_CHAPTER_CLOSURE_TOLERANCE_MAX_CHARS,
            ceil(
                book_plan.chapter_hard_max_chars
                * TERMINAL_CHAPTER_CLOSURE_TOLERANCE_RATIO
            ),
        )
        if (
            book_plan.target_mode == "total_chapters"
            and book_plan.total_chapters > 1
            and current_index == book_plan.total_chapters
        )
        else 0
    )
    local_maximum = (
        book_plan.chapter_hard_max_chars
        + natural_allowance
        + closure_allowance
    )
    if book_plan.target_mode == "total_chapters":
        return local_maximum

    future_chapters = book_plan.total_chapters - current_index
    book_residual_maximum = (
        book_acceptance_maximum(book_plan)
        + closure_allowance
        - max(0, int(completed_chapter_chars))
        - future_chapters * book_plan.chapter_hard_min_chars
    )
    return max(0, min(local_maximum, book_residual_maximum))


def book_acceptance_maximum(book_plan: BookScalePlan) -> int:
    """Return a bounded whole-book ceiling above the planning soft target.

    The soft maximum guides pacing; it is not an exact deletion target. Short
    works may naturally vary by 20% plus one bounded chapter-level tail, while
    long works can still borrow at most one chapter's hard capacity. This keeps
    the tolerance meaningful at both scales without allowing unbounded drift.
    """
    natural_allowance = min(
        ceil(book_plan.book_soft_max_chars * BOOK_NATURAL_VARIATION_RATIO)
        + min(
            CHAPTER_NATURAL_VARIATION_MAX_CHARS,
            ceil(
                book_plan.chapter_hard_max_chars
                * CHAPTER_NATURAL_VARIATION_RATIO
            ),
        ),
        book_plan.chapter_hard_max_chars,
    )
    return book_plan.book_soft_max_chars + natural_allowance


def distribute_chapters(total_chapters: int) -> list[int]:
    chapters = _positive_int(total_chapters, "全书章节数")
    if chapters <= MAX_CHAPTERS_PER_VOLUME:
        return [chapters]
    preferred = _round_half_up(chapters / PREFERRED_CHAPTERS_PER_VOLUME)
    minimum_volumes = ceil(chapters / MAX_CHAPTERS_PER_VOLUME)
    maximum_volumes = max(1, floor(chapters / MIN_CHAPTERS_PER_VOLUME))
    volume_count = min(maximum_volumes, max(minimum_volumes, preferred))
    base, remainder = divmod(chapters, volume_count)
    return [base + (1 if index < remainder else 0) for index in range(volume_count)]


def book_scale_plan_from_inputs(inputs: dict[str, Any]) -> BookScalePlan:
    raw = inputs.get("book_scale_plan") if isinstance(inputs, dict) else None
    if raw is None:
        raise ValueError("运行输入缺少 BookScalePlan")
    return BookScalePlan.model_validate(raw)


def freeze_book_scale_inputs(inputs: dict[str, object]) -> dict[str, object]:
    frozen = dict(inputs)
    if "book_scale_plan" in frozen:
        raise ValueError("启动请求不得提交派生 BookScalePlan，请只提交成书目标")
    raw_target = frozen.pop("book_scale_target", None)
    if raw_target is None:
        raise ValueError("启动请求缺少成书目标，无法确定全书体量")
    target = BookScaleTarget.model_validate(raw_target)
    plan = build_book_scale_plan(
        target_mode=target.target_mode,
        target_value=target.target_value,
    )
    frozen["book_scale_plan"] = plan.model_dump(mode="json")
    return frozen


def _stage_budgets(
    *,
    total_chars: int,
    total_chapters: int,
    volume_count: int,
    chapter_target: int,
    chapter_soft_min: int,
    chapter_soft_max: int,
) -> dict[str, StageContentBudget]:
    if total_chars <= 20_000:
        info_target, info_min, info_max = 1_600, 1_100, 2_400
    elif total_chars <= 150_000:
        info_target, info_min, info_max = 2_200, 1_400, 3_200
    elif total_chars <= 600_000:
        info_target, info_min, info_max = 2_800, 1_800, 4_000
    else:
        info_target, info_min, info_max = 3_200, 2_000, 4_600

    summary_target = min(4_200, max(1_200, 1_100 + volume_count * 140))
    summary_min = max(900, floor(summary_target * 0.72))
    summary_max = ceil(summary_target * 1.45)
    outline_target = 1_000
    detail_target = min(2_200, max(1_400, 1_250 + total_chapters // 80 * 100))
    return {
        "info": _budget("per_book", info_target, info_min, info_max, "立项 Story DNA，按全书体量配置人物与关系基线。"),
        "summary": _budget("per_book", summary_target, summary_min, summary_max, "完整因果梗概；篇幅随分卷复杂度增长，但不重放逐章剧情。"),
        "outline": _budget("per_volume", outline_target, 650, 1_600, "单卷 Volume Program；长篇按卷分批生成并连续合并。"),
        "detail": _budget("per_chapter", detail_target, 1_000, 3_200, "单章结构化剧本；每章一个主要叙事位移，超载内容顺延到相邻章节。"),
        "text": StageContentBudget(
            scope="per_chapter",
            target_chars=chapter_target,
            min_chars=chapter_soft_min,
            max_chars=chapter_soft_max,
            max_tokens=max(1_200, ceil(chapter_soft_max * 1.25)),
            description="单章正文软预算；转场章可略短，高潮章可略长，全书目标负责最终闭合。",
        ),
        "cover": _budget("per_plan", 700, 450, 1_200, "封面 brief、构图和图像提示词，不随正文章数线性增长。"),
    }


def _budget(
    scope: StageBudgetScope,
    target: int,
    minimum: int,
    maximum: int,
    description: str,
) -> StageContentBudget:
    return StageContentBudget(
        scope=scope,
        target_chars=target,
        min_chars=minimum,
        max_chars=maximum,
        max_tokens=max(1_200, ceil(maximum * 1.45)),
        description=description,
    )


def _story_scope(total_chapters: int) -> StoryScopeBudget:
    if total_chapters <= 5:
        return StoryScopeBudget(
            character_min=3,
            character_max=5,
            relationship_min=3,
            relationship_max=8,
        )
    if total_chapters <= 50:
        return StoryScopeBudget(
            character_min=5,
            character_max=8,
            relationship_min=7,
            relationship_max=16,
        )
    return StoryScopeBudget(
        character_min=7,
        character_max=11,
        relationship_min=10,
        relationship_max=26,
    )


def _distribute_total(total: int, weights: list[int]) -> list[int]:
    base = [total * weight // sum(weights) for weight in weights]
    remainder = total - sum(base)
    for index in range(remainder):
        base[index % len(base)] += 1
    return base


def _round_half_up(value: float) -> int:
    return floor(value + 0.5)


def _positive_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or isinstance(value, float) and not value.is_integer():
        raise ValueError(f"{label}必须是正整数")
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label}必须是正整数") from exc
    if parsed <= 0:
        raise ValueError(f"{label}必须是正整数")
    return parsed


__all__ = [
    "BOOK_SCALE_CONTRACT_VERSION",
    "BOOK_NATURAL_VARIATION_RATIO",
    "BookScalePlan",
    "BookScaleTarget",
    "BookScaleTargetMode",
    "CHAPTER_NATURAL_VARIATION_MAX_CHARS",
    "CHAPTER_NATURAL_VARIATION_RATIO",
    "NarrativeCapacityPolicy",
    "StageContentBudget",
    "StoryScopeBudget",
    "VolumeScalePlan",
    "book_scale_plan_from_inputs",
    "book_acceptance_maximum",
    "build_book_scale_plan",
    "chapter_acceptance_maximum",
    "distribute_chapters",
    "freeze_book_scale_inputs",
]
