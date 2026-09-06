"""Shared entry builders for the Phase 32 Story Bible projection."""

from __future__ import annotations

import re
from typing import Literal

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ChapterArtifact,
    ScreenplayDraftArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.output_contracts.phase32_route_artifacts import (
    CharacterBibleArtifact,
    NovelBriefArtifact,
    ScreenplayBriefArtifact,
)
from novel_workflow.storage.phase32_artifact_store import Phase32ArtifactRecord
from novel_workflow.storage.phase32_story_bible_projection import (
    Phase32StoryBibleEntry,
    Phase32StoryBibleSource,
    StoryBibleEntryKind,
    StoryBibleEntryStatus,
)


def project_brief(
    target: list[Phase32StoryBibleEntry],
    record: Phase32ArtifactRecord,
) -> None:
    if record.creation_route_id == "screenplay_sample":
        artifact = ScreenplayBriefArtifact.model_validate(record.payload)
        fields = (
            ("premise", "故事前提", artifact.premise),
            ("audience_promise", "观众承诺", artifact.audience_promise),
            ("visible_conflict", "可见冲突", artifact.visible_conflict),
            ("ending_effect", "结尾效果", artifact.ending_effect),
            ("tone", "视听语气", artifact.tone),
            ("target_minutes", "目标时长", f"{artifact.target_minutes} 分钟"),
        )
    else:
        artifact = NovelBriefArtifact.model_validate(record.payload)
        fields = (
            ("premise", "故事前提", artifact.premise),
            ("audience_promise", "读者承诺", artifact.audience_promise),
            ("theme_question", "主题问题", artifact.theme_question),
            ("ending_direction", "结局方向", artifact.ending_direction),
            ("narrative_voice", "叙事声音", artifact.narrative_voice),
            ("target_characters", "目标篇幅", f"{artifact.target_characters:,} 字符"),
        )
        for index, rule in enumerate(artifact.world_rules, start=1):
            target.append(
                entry(
                    record,
                    source_path=f"brief.world_rules[{index - 1}]",
                    entry_ref=f"world-rule-{index}",
                    kind="world_rule",
                    title=f"世界规则 {index:02d}",
                    body=rule,
                    status="committed",
                    ordinal=index,
                    tags=("世界规则",),
                )
            )
    for index, (field, label, value) in enumerate(fields, start=1):
        target.append(
            entry(
                record,
                source_path=f"brief.{field}",
                entry_ref=f"brief-{field}",
                kind="brief_field",
                title=label,
                body=str(value),
                status="committed",
                ordinal=index,
            )
        )


def project_cast(
    target: list[Phase32StoryBibleEntry],
    record: Phase32ArtifactRecord,
) -> None:
    artifact = CharacterBibleArtifact.model_validate(record.payload)
    for index, character in enumerate(artifact.characters, start=1):
        target.append(
            entry(
                record,
                source_path=f"cast.characters[{index - 1}]",
                entry_ref=character.subject_ref,
                kind="character",
                title=character.display_name,
                body=character.role,
                detail=character.desire,
                status="committed",
                ordinal=index,
                subject_refs=(character.subject_ref,),
                tags=("人物", character.arc_scope),
            )
        )
    for index, relation in enumerate(artifact.relationships, start=1):
        target.append(
            entry(
                record,
                source_path=f"cast.relationships[{index - 1}]",
                entry_ref=f"relation:{relation.from_subject_ref}:{relation.to_subject_ref}",
                kind="relationship",
                title="关系压力",
                body=relation.pressure,
                detail=relation.change_trigger,
                status="committed",
                ordinal=index,
                subject_refs=(relation.from_subject_ref, relation.to_subject_ref),
                tags=("关系",),
            )
        )


def append_promises(
    target: list[Phase32StoryBibleEntry],
    record: Phase32ArtifactRecord | None,
    promise_sources: dict[str, list[str]],
) -> None:
    if record is None:
        return
    for index, (promise_ref, refs) in enumerate(sorted(promise_sources.items()), start=1):
        target.append(
            entry(
                record,
                source_path=f"projection.promise_refs.{promise_ref}",
                entry_ref=f"promise:{promise_ref}",
                kind="promise",
                title=promise_ref,
                body="、".join(refs),
                detail=f"在 {len(refs)} 个已提交规划单元中被引用；正文兑现尚未自动判定。",
                status="tracked",
                ordinal=index,
                promise_refs=(promise_ref,),
                tags=("规划引用",),
            )
        )


def accepted_unit(
    record: Phase32ArtifactRecord,
    unit_ref: str,
) -> Phase32StoryBibleEntry:
    if record.creation_route_id == "screenplay_sample":
        artifact = ScreenplayDraftArtifact.model_validate(record.payload)
        body = " ".join(block.text for block in artifact.blocks)
        title = artifact.scene_ref
        subject_refs = tuple(
            dict.fromkeys(
                block.speaker_ref
                for block in artifact.blocks
                if block.speaker_ref is not None
            )
        )
        tags = (f"{len(artifact.blocks)} 个规范块",)
    elif record.creation_route_id == "short_novel":
        artifact = ShortProseUnitArtifact.model_validate(record.payload)
        body = artifact.content
        title = artifact.title
        subject_refs = (artifact.pov_subject_ref,)
        tags = (artifact.unit_kind,)
    else:
        artifact = ChapterArtifact.model_validate(record.payload)
        body = artifact.content
        title = artifact.title
        subject_refs = (artifact.pov_subject_ref,)
        tags = (artifact.volume_ref,)
    normalized = re.sub(r"\s+", " ", body).strip()
    excerpt = normalized[:360] + ("…" if len(normalized) > 360 else "")
    return entry(
        record,
        source_path=f"{record.stage_id}.accepted_units.{unit_ref}",
        entry_ref=unit_ref,
        kind="accepted_unit",
        title=title,
        body=excerpt,
        detail=f"已接受版本 · {len(normalized):,} 字符",
        status="accepted",
        unit_ref=unit_ref,
        subject_refs=subject_refs,
        tags=tags,
        authority="accepted_unit",
    )


def entry(
    record: Phase32ArtifactRecord,
    *,
    source_path: str,
    entry_ref: str,
    kind: StoryBibleEntryKind,
    title: str,
    status: StoryBibleEntryStatus,
    body: str = "",
    detail: str = "",
    ordinal: int | None = None,
    parent_ref: str = "",
    unit_ref: str = "",
    subject_refs: tuple[str, ...] = (),
    promise_refs: tuple[str, ...] = (),
    tags: tuple[str, ...] = (),
    authority: Literal["committed_artifact", "accepted_unit"] = "committed_artifact",
) -> Phase32StoryBibleEntry:
    return Phase32StoryBibleEntry(
        entry_ref=entry_ref,
        kind=kind,
        title=title,
        body=body,
        detail=detail,
        status=status,
        ordinal=ordinal,
        parent_ref=parent_ref,
        unit_ref=unit_ref,
        subject_refs=tuple(subject_refs),
        promise_refs=tuple(promise_refs),
        tags=tuple(tags[:24]),
        authority=authority,
        source=Phase32StoryBibleSource(
            stage_id=record.stage_id,
            artifact_kind=record.artifact_kind,
            artifact_ref=record.artifact_ref,
            payload_digest=record.payload_digest,
            source_path=source_path,
            committed_at=record.created_at,
        ),
    )


__all__ = ["accepted_unit", "append_promises", "entry", "project_brief", "project_cast"]
