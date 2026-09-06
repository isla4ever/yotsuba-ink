"""Long-novel Story Bible entry builders."""

from __future__ import annotations

from novel_workflow.output_contracts.phase32_route_artifacts import (
    BookArchitectureArtifact,
    DetailPlanIndexArtifact,
    VolumeArchitectureArtifact,
)
from novel_workflow.storage.phase32_story_bible_entries import append_promises, entry


def project_long_novel(sections, architecture_record, volume_record, detail_record) -> None:
    promise_sources: dict[str, list[str]] = {}
    if architecture_record is not None:
        artifact = BookArchitectureArtifact.model_validate(architecture_record.payload)
        for index, part in enumerate(artifact.parts, start=1):
            sections["structure"].append(
                entry(
                    architecture_record,
                    source_path=f"book_architecture.parts[{index - 1}]",
                    entry_ref=part.part_ref,
                    kind="part",
                    title=f"Part {part.ordinal:02d}",
                    body=part.dramatic_question,
                    detail=f"进入：{part.entry_state}\n退出：{part.exit_state}",
                    status="committed",
                    ordinal=part.ordinal,
                    promise_refs=part.promise_refs,
                    tags=("Book Part",),
                )
            )
            for promise_ref in part.promise_refs:
                promise_sources.setdefault(promise_ref, []).append(part.part_ref)
            for obligation_index, obligation in enumerate(
                part.unresolved_obligations,
                start=1,
            ):
                sections["continuity"].append(
                    entry(
                        architecture_record,
                        source_path=(
                            f"book_architecture.parts[{index - 1}]"
                            f".unresolved_obligations[{obligation_index - 1}]"
                        ),
                        entry_ref=f"obligation:{part.part_ref}:{obligation_index}",
                        kind="open_question",
                        title=f"{part.part_ref} · 未闭合义务",
                        body=obligation,
                        status="open",
                        parent_ref=part.part_ref,
                    )
                )
        for index, condition in enumerate(artifact.ending_conditions, start=1):
            sections["continuity"].append(
                entry(
                    architecture_record,
                    source_path=f"book_architecture.ending_conditions[{index - 1}]",
                    entry_ref=f"ending-condition-{index}",
                    kind="ending_condition",
                    title=f"终局条件 {index:02d}",
                    body=condition,
                    status="planned",
                    ordinal=index,
                )
            )
    if volume_record is not None:
        artifact = VolumeArchitectureArtifact.model_validate(volume_record.payload)
        for index, volume in enumerate(artifact.volumes, start=1):
            sections["structure"].append(
                entry(
                    volume_record,
                    source_path=f"volumes.volumes[{index - 1}]",
                    entry_ref=volume.volume_ref,
                    kind="volume",
                    title=f"第 {volume.ordinal} 卷",
                    body=volume.promise,
                    detail=f"冲突：{volume.conflict}\n高潮：{volume.climax}",
                    status="committed",
                    ordinal=volume.ordinal,
                    parent_ref=volume.part_ref,
                    subject_refs=volume.cast_subject_refs,
                    tags=(f"{volume.length_hint:,} 字符",),
                )
            )
            sections["continuity"].append(
                entry(
                    volume_record,
                    source_path=f"volumes.volumes[{index - 1}].closure",
                    entry_ref=f"closure:{volume.volume_ref}",
                    kind="ending_condition",
                    title=f"第 {volume.ordinal} 卷闭合",
                    body=volume.closure,
                    status="planned",
                    ordinal=volume.ordinal,
                    parent_ref=volume.part_ref,
                )
            )
    if detail_record is not None:
        artifact = DetailPlanIndexArtifact.model_validate(detail_record.payload)
        for window_index, window in enumerate(artifact.windows, start=1):
            sections["structure"].append(
                entry(
                    detail_record,
                    source_path=f"rolling_detail.windows[{window_index - 1}]",
                    entry_ref=window.window_ref,
                    kind="detail_window",
                    title=f"施工窗口 {window.ordinal:02d}",
                    body=window.entry_state,
                    detail=window.next_window_entry_state,
                    status="committed",
                    ordinal=window.ordinal,
                    tags=window.volume_refs,
                )
            )
            sections["continuity"].append(
                entry(
                    detail_record,
                    source_path=f"rolling_detail.windows[{window_index - 1}].handoff",
                    entry_ref=f"handoff:{window.window_ref}",
                    kind="handoff",
                    title=f"窗口 {window.ordinal:02d} · 交接",
                    body=window.handoff,
                    detail=window.next_window_entry_state,
                    status="planned",
                    ordinal=window.ordinal,
                )
            )
            for chapter_index, chapter in enumerate(window.chapters, start=1):
                sections["structure"].append(
                    entry(
                        detail_record,
                        source_path=(
                            f"rolling_detail.windows[{window_index - 1}]"
                            f".chapters[{chapter_index - 1}]"
                        ),
                        entry_ref=chapter.chapter_ref,
                        kind="chapter_plan",
                        title=chapter.title,
                        body=chapter.dramatic_job,
                        detail=f"冲突：{chapter.conflict}\n出口：{chapter.exit_state}",
                        status="committed",
                        ordinal=chapter.ordinal,
                        parent_ref=window.window_ref,
                        subject_refs=chapter.cast_subject_refs,
                        tags=(chapter.volume_ref, f"{chapter.length_hint:,} 字符"),
                    )
                )
                sections["continuity"].append(
                    entry(
                        detail_record,
                        source_path=(
                            f"rolling_detail.windows[{window_index - 1}]"
                            f".chapters[{chapter_index - 1}].handoff"
                        ),
                        entry_ref=f"handoff:{chapter.chapter_ref}",
                        kind="handoff",
                        title=f"{chapter.title} · 交接",
                        body=chapter.handoff,
                        detail=f"进入：{chapter.entry_state}\n退出：{chapter.exit_state}",
                        status="planned",
                        ordinal=chapter.ordinal,
                        parent_ref=window.window_ref,
                        subject_refs=chapter.cast_subject_refs,
                    )
                )
    append_promises(
        sections["continuity"],
        architecture_record,
        promise_sources,
    )


__all__ = ["project_long_novel"]
