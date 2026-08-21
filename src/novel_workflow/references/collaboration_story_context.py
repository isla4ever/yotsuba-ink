from __future__ import annotations

from typing import Any

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationContextPolicy,
    CollaborationThread,
)
from novel_workflow.references.collaboration_context_material import (
    ContextMaterialBuilder,
    bounded_json,
    digest,
)


def add_story_sources(
    stores: Any,
    thread: CollaborationThread,
    policy: CollaborationContextPolicy,
    builder: ContextMaterialBuilder,
    *,
    subject_ids: set[str],
    chapter_number: int | None,
) -> None:
    if thread.stage_id not in {"detail", "text"}:
        return
    if thread.stage_id == "text":
        state = stores.canon.resolved_state(
            thread.run_id,
            as_of_chapter=chapter_number,
            subject_ids=subject_ids or None,
        )
        state_payload = state.model_dump(mode="json")
        if state.entries or state.conflicts:
            builder.add(
                category="continuity",
                source_ref="resolved-story-state",
                scope_ref=thread.scope.unit_ref,
                version=digest(state_payload),
                reason="正文局部范围在当前章节位置的确定性连续性状态",
                label="连续性状态",
                content=bounded_json(state_payload, 3_600),
                disposition="required",
                material_key="continuity_state",
            )
        else:
            builder.omit(
                category="continuity",
                source_ref="resolved-story-state",
                scope_ref=thread.scope.unit_ref,
                version=digest(state_payload),
                reason="当前章节位置尚无可注入的已确认连续性事实",
                label="连续性状态",
            )

    _add_story_bible_section(
        stores,
        thread,
        builder,
        enabled=policy.include_canon_wiki,
        policy=policy,
        section="facts",
        category="canon_wiki",
        source_ref="story-bible:facts",
        label="相关 Canon / Wiki",
        present_reason="当前局部范围可追溯到 Evidence 的 Canon / Wiki 事实",
        empty_reason="当前局部范围暂无已确认的 Canon / Wiki 事实",
        disabled_reason="本轮上下文策略未启用 Canon / Wiki",
        material_key="canon_wiki",
        item_limit=24,
        char_limit=4_800,
        subject_ids=subject_ids,
        chapter_number=chapter_number,
    )
    _add_story_bible_section(
        stores,
        thread,
        builder,
        enabled=policy.include_foreshadow,
        policy=policy,
        section="foreshadow",
        category="foreshadow",
        source_ref="story-bible:foreshadow",
        label="当前范围伏笔",
        present_reason="当前章节窗口内仍可追溯的伏笔与兑现状态",
        empty_reason="当前章节窗口暂无可追溯伏笔",
        disabled_reason="本轮上下文策略未启用伏笔投影",
        material_key="foreshadow",
        item_limit=20,
        char_limit=3_600,
        subject_ids=subject_ids,
        chapter_number=chapter_number,
    )


def _add_story_bible_section(
    stores: Any,
    thread: CollaborationThread,
    builder: ContextMaterialBuilder,
    *,
    enabled: bool,
    policy: CollaborationContextPolicy,
    section: str,
    category: str,
    source_ref: str,
    label: str,
    present_reason: str,
    empty_reason: str,
    disabled_reason: str,
    material_key: str,
    item_limit: int,
    char_limit: int,
    subject_ids: set[str],
    chapter_number: int | None,
) -> None:
    if not enabled:
        builder.omit(
            category=category,
            source_ref=f"policy:{policy.policy_id}",
            scope_ref=thread.scope.unit_ref,
            version=str(policy.version),
            reason=disabled_reason,
            label=label,
        )
        return
    page = stores.story_bible.page(thread.run_id, section=section, limit=100)
    items = [
        item.model_dump(mode="json")
        for item in page.items
        if _story_item_in_scope(
            item,
            subject_ids=subject_ids,
            chapter_number=chapter_number,
        )
    ][:item_limit]
    if items:
        builder.add(
            category=category,
            source_ref=source_ref,
            scope_ref=thread.scope.unit_ref,
            version=digest(items),
            reason=present_reason,
            label=label,
            content=bounded_json(items, char_limit),
            disposition="optional",
            material_key=material_key,
        )
        return
    builder.omit(
        category=category,
        source_ref=source_ref,
        scope_ref=thread.scope.unit_ref,
        version="empty",
        reason=empty_reason,
        label=label,
    )


def _story_item_in_scope(
    item: Any,
    *,
    subject_ids: set[str],
    chapter_number: int | None,
) -> bool:
    subject_id = str(getattr(item, "subject_id", "") or "")
    if subject_id and subject_ids and subject_id not in subject_ids and subject_id != "story":
        return False
    effective_from = getattr(item, "effective_from_chapter", None)
    effective_to = getattr(item, "effective_to_chapter", None)
    if chapter_number is not None:
        if isinstance(effective_from, int) and effective_from > chapter_number:
            return False
        if isinstance(effective_to, int) and effective_to < chapter_number:
            return False
    return True


__all__ = ["add_story_sources"]
