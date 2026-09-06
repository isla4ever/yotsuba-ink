"""Dormant screenplay, prose, cover and delivery Artifact contracts."""

from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from novel_workflow.output_contracts.phase32_artifact_base import (
    NonEmptyText,
    Phase32Artifact,
    Ref,
    ScreenplayBlockKind,
    ShortText,
)


class ScreenplayBlock(Phase32Artifact):
    kind: ScreenplayBlockKind = Field(
        description=(
            "块类型，只能是 scene_heading、action、dialogue、parenthetical 或 transition。"
        )
    )
    text: NonEmptyText = Field(
        description=(
            "该块唯一的可见文本字段；对白也使用 text，禁止使用 dialogue_text、content 或其它别名。"
        )
    )
    speaker_ref: Ref | None = Field(
        default=None,
        description=(
            "仅 dialogue 或 parenthetical 块填写冻结 Cast 的 subject_ref；"
            "scene_heading、action、transition 必须省略此字段，禁止使用空字符串。"
        ),
    )

    @model_validator(mode="after")
    def validate_speaker_binding(self) -> Self:
        if self.kind == "dialogue" and self.speaker_ref is None:
            raise ValueError("Dialogue block requires a speaker ref")
        if self.kind not in {"dialogue", "parenthetical"} and self.speaker_ref is not None:
            raise ValueError("Only dialogue and parenthetical blocks may bind a speaker")
        return self


class ScreenplayDraftArtifact(Phase32Artifact):
    scene_ref: Ref
    blocks: tuple[ScreenplayBlock, ...] = Field(min_length=2, max_length=500)

    @model_validator(mode="after")
    def validate_scene_script(self) -> Self:
        heading_count = sum(block.kind == "scene_heading" for block in self.blocks)
        if heading_count != 1:
            raise ValueError(
                "Screenplay draft must contain exactly one frozen Scene heading "
                "(scene heading)"
            )
        if self.blocks[0].kind != "scene_heading":
            raise ValueError("Screenplay draft must start with a scene heading")
        if not any(block.kind in {"action", "dialogue"} for block in self.blocks[1:]):
            raise ValueError("Screenplay draft requires visible action or dialogue")
        return self


class ShortProseUnitArtifact(Phase32Artifact):
    unit_ref: Ref
    unit_kind: Literal["section", "chapter"]
    title: ShortText
    pov_subject_ref: Ref
    content: Annotated[str, Field(min_length=1, max_length=250_000)]


class ChapterArtifact(Phase32Artifact):
    chapter_ref: Ref
    volume_ref: Ref
    title: ShortText
    pov_subject_ref: Ref
    content: Annotated[str, Field(min_length=1, max_length=250_000)]


class CoverBrief(Phase32Artifact):
    concept: NonEmptyText
    image_prompt: Annotated[str, Field(min_length=1, max_length=3_000)]
    palette: tuple[ShortText, ...] = Field(min_length=1, max_length=8)
    negative_constraints: tuple[ShortText, ...] = Field(default=(), max_length=24)


class CoverCandidate(Phase32Artifact):
    asset_ref: Ref
    alt_text: ShortText
    visual_notes: NonEmptyText


class CoverCandidateProposal(Phase32Artifact):
    """Provider-authored direction before code binds immutable image bytes."""

    alt_text: ShortText
    visual_notes: NonEmptyText
    image_prompt: Annotated[str, Field(min_length=1, max_length=3_000)]


class CoverProposal(Phase32Artifact):
    """Internal Provider contract; never persisted as the stage authority."""

    brief: CoverBrief
    candidates: tuple[CoverCandidateProposal, ...] = Field(min_length=1, max_length=4)


class CoverArtifact(Phase32Artifact):
    brief: CoverBrief
    # Canonical novel routes currently stop after the text CoverBrief. Image
    # candidates are introduced only by the later image-acceptance wave.
    candidates: tuple[CoverCandidate, ...] = Field(default=(), max_length=12)
    selected_asset_ref: Ref | None = None
    image_acceptance_status: Literal["image_deferred", "ready"] = "ready"

    @model_validator(mode="after")
    def validate_selected_asset(self) -> Self:
        refs = tuple(candidate.asset_ref for candidate in self.candidates)
        if len(set(refs)) != len(refs):
            raise ValueError("Cover candidate asset refs must be unique")
        if self.selected_asset_ref is not None and self.selected_asset_ref not in set(refs):
            raise ValueError("Selected cover asset must be one of the candidates")
        if self.image_acceptance_status == "image_deferred":
            if self.candidates or self.selected_asset_ref is not None:
                raise ValueError(
                    "Image-deferred CoverArtifact cannot contain image candidates"
                )
        elif not self.candidates:
            raise ValueError("Ready CoverArtifact requires at least one candidate")
        return self


class ScriptDeliveryArtifact(Phase32Artifact):
    title: ShortText
    author: Annotated[str, Field(max_length=160)]
    version_note: Annotated[str, Field(max_length=500)]
    formats: tuple[Literal["fountain", "pdf", "markdown"], ...] = Field(
        min_length=1,
        max_length=3,
    )
    scene_refs: tuple[Ref, ...] = Field(min_length=1, max_length=120)
    scene_version_refs: tuple[
        Annotated[
            str,
            Field(pattern=r"^p32-script-committed-[a-f0-9]{64}$"),
        ],
        ...,
    ] = Field(min_length=1, max_length=120)

    @model_validator(mode="after")
    def validate_scene_refs(self) -> Self:
        if len(set(self.scene_refs)) != len(self.scene_refs):
            raise ValueError("Script delivery scene refs must be unique")
        if len(self.scene_refs) != len(self.scene_version_refs):
            raise ValueError("Script delivery must bind one accepted version per scene")
        if len(set(self.scene_version_refs)) != len(self.scene_version_refs):
            raise ValueError("Script delivery scene version refs must be unique")
        return self


class BookDeliveryArtifact(Phase32Artifact):
    title: ShortText
    author: Annotated[str, Field(max_length=160)]
    version_note: Annotated[str, Field(max_length=500)]
    formats: tuple[Literal["epub", "docx", "markdown"], ...] = Field(
        min_length=1,
        max_length=3,
    )
    chapter_refs: tuple[Ref, ...] = Field(min_length=1, max_length=4000)
    chapter_version_refs: tuple[
        Annotated[
            str,
            Field(pattern=r"^p32-text-committed-[a-f0-9]{64}$"),
        ],
        ...,
    ] = Field(min_length=1, max_length=4000)
    volume_refs: tuple[Ref, ...] = Field(default=(), max_length=24)
    cover_asset_ref: Ref

    @model_validator(mode="after")
    def validate_delivery_refs(self) -> Self:
        if len(set(self.chapter_refs)) != len(self.chapter_refs):
            raise ValueError("Book delivery chapter refs must be unique")
        if len(self.chapter_refs) != len(self.chapter_version_refs):
            raise ValueError("Book delivery must bind one accepted version per chapter")
        if len(set(self.chapter_version_refs)) != len(self.chapter_version_refs):
            raise ValueError("Book delivery chapter version refs must be unique")
        if len(set(self.volume_refs)) != len(self.volume_refs):
            raise ValueError("Book delivery volume refs must be unique")
        return self


__all__ = [
    "BookDeliveryArtifact",
    "ChapterArtifact",
    "CoverArtifact",
    "CoverBrief",
    "CoverCandidate",
    "CoverCandidateProposal",
    "CoverProposal",
    "ScreenplayBlock",
    "ScreenplayDraftArtifact",
    "ScriptDeliveryArtifact",
    "ShortProseUnitArtifact",
]
