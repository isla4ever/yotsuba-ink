from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Literal

from novel_workflow.workflows.book_scale_plan import BookScalePlan


ChapterCapacityStatus = Literal[
    "hard_underflow",
    "soft_underflow",
    "within_soft",
    "soft_overflow",
    "hard_overflow",
]


@dataclass(frozen=True, slots=True)
class ChapterCapacityDiagnostic:
    counting_standard: str
    visible_chars: int
    target_chars: int
    soft_min_chars: int
    soft_max_chars: int
    hard_min_chars: int
    hard_max_chars: int
    status: ChapterCapacityStatus

    def as_dict(self) -> dict[str, str | int]:
        return asdict(self)

    def blocking_finding(self) -> dict[str, str] | None:
        if self.status == "hard_underflow":
            return {
                "code": "chapter.capacity.hard_min",
                "severity": "blocking",
                "claim": "Chapter content is below the frozen hard capacity floor.",
                "evidence": (
                    f"{self.counting_standard}: {self.visible_chars} visible chars; "
                    f"hard minimum: {self.hard_min_chars}."
                ),
            }
        if self.status == "hard_overflow":
            return {
                "code": "chapter.capacity.hard_max",
                "severity": "blocking",
                "claim": "Chapter content exceeds the frozen hard capacity ceiling.",
                "evidence": (
                    f"{self.counting_standard}: {self.visible_chars} visible chars; "
                    f"hard maximum: {self.hard_max_chars}."
                ),
            }
        return None


def evaluate_chapter_capacity(
    content: str,
    plan: BookScalePlan,
) -> ChapterCapacityDiagnostic:
    visible_chars = sum(1 for char in content if not char.isspace())
    if visible_chars < plan.chapter_hard_min_chars:
        status: ChapterCapacityStatus = "hard_underflow"
    elif visible_chars < plan.chapter_soft_min_chars:
        status = "soft_underflow"
    elif visible_chars <= plan.chapter_soft_max_chars:
        status = "within_soft"
    elif visible_chars <= plan.chapter_hard_max_chars:
        status = "soft_overflow"
    else:
        status = "hard_overflow"
    return ChapterCapacityDiagnostic(
        counting_standard=plan.counting_standard,
        visible_chars=visible_chars,
        target_chars=plan.chapter_target_chars,
        soft_min_chars=plan.chapter_soft_min_chars,
        soft_max_chars=plan.chapter_soft_max_chars,
        hard_min_chars=plan.chapter_hard_min_chars,
        hard_max_chars=plan.chapter_hard_max_chars,
        status=status,
    )


__all__ = [
    "ChapterCapacityDiagnostic",
    "ChapterCapacityStatus",
    "evaluate_chapter_capacity",
]
