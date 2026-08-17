from __future__ import annotations

import math
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StageId = Literal[
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
    "export",
]

STAGE_ORDER: tuple[StageId, ...] = (
    "brief",
    "spine",
    "cast",
    "volumes",
    "detail",
    "text",
    "cover",
    "export",
)

STAGE_LABELS: dict[StageId, str] = {
    "brief": "创作立项",
    "spine": "故事脊柱",
    "cast": "人物编排",
    "volumes": "分卷架构",
    "detail": "章节施工图",
    "text": "正文",
    "cover": "封面",
    "export": "导出",
}


def stage_pointer(stage_id: StageId) -> dict[str, str]:
    return {"id": stage_id, "label": STAGE_LABELS[stage_id], "type": stage_id}


class StrictArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


_NUMBERED_TITLE_PREFIX = re.compile(
    r"^(?:(?:第?[0-9一二三四五六七八九十百千万零〇两]+[卷章节部篇])|(?:chapter\s*[0-9]+))",
    re.IGNORECASE,
)

_NON_NAME_MARKERS = (
    "的母亲",
    "的父亲",
    "的同事",
    "的上级",
    "前任档案员",
    "主角",
    "反派",
    "配角",
    "匿名",
    "未命名",
    "某人",
    "机构代表",
)
_RUNTIME_META_MARKERS = (
    "prompt",
    "provider",
    "langgraph",
    "spine",
    "detail",
    "api",
    "run",
    "模型提示",
    "提示词",
    "上游",
    "下游",
)
_VAGUE_CHARACTER_VALUES = {
    "复杂",
    "神秘",
    "性格复杂",
    "性格鲜明",
    "不详",
    "未知",
    "待补充",
    "暂无",
}
_UNRESOLVED_CHARACTER_PREFIXES = (
    "待补充",
    "暂无",
    "不详",
    "未知",
    "未明确",
    "尚未确定",
)
_AMBIGUOUS_CHARACTER_MARKERS = (
    "复杂的过去",
    "神秘的过去",
    "神秘背景",
    "背景不明",
    "背景不详",
    "身份不明",
    "身份不详",
    "来历不明",
    "来历成谜",
    "性格复杂",
    "性格鲜明",
    "难以捉摸",
    "语言风格独特",
    "说话方式独特",
    "表达方式独特",
    "可能失去一切",
    "将付出代价",
    "面临严重后果",
)
_VAGUE_IRREDUCIBILITY_VALUES = {
    "不能合并到其他角色",
    "不可合并到其他角色",
    "该角色不可替代",
    "剧情需要这个角色",
    "故事需要这个角色",
    "为了丰富剧情",
    "为了增加真实感",
}

_VAGUE_ROLE_TEXT_VALUES = {
    "角色功能",
    "承担职责",
    "推动剧情",
    "推动变化",
    "承担后果",
    "剧情需要",
    "故事需要",
}

_AMBIGUOUS_RELATION_MARKERS = (
    "关系复杂",
    "可能",
    "或许",
    "也许",
    "潜在",
    "说不清",
    "尚不明确",
)

_PURE_COGNITIVE_PREFIXES = (
    "意识到",
    "明白",
    "理解",
    "想到",
    "记起",
    "回想起",
)


def _creative_character_name(value: str) -> str:
    cleaned = value.strip()
    folded = cleaned.casefold()
    if any(marker in cleaned or marker in folded for marker in _NON_NAME_MARKERS):
        raise ValueError("Character name must be a stable personal name, not a relationship or role label")
    if not cleaned or len(cleaned) > 120:
        raise ValueError("Character name must be non-empty and concise")
    return cleaned


def _character_text(value: str, *, label: str) -> str:
    cleaned = value.strip()
    folded = cleaned.casefold()
    if any(marker in folded for marker in _RUNTIME_META_MARKERS):
        raise ValueError(f"{label} must describe the story world, not runtime instructions")
    normalized = re.sub(r"[\W_]+", "", folded)
    if normalized in _VAGUE_CHARACTER_VALUES or folded.startswith(
        _UNRESOLVED_CHARACTER_PREFIXES
    ) or any(marker in normalized for marker in _AMBIGUOUS_CHARACTER_MARKERS):
        raise ValueError(f"{label} must be concrete enough to perform in prose")
    return cleaned


def _character_limits(values: list[str]) -> list[str]:
    cleaned = [_character_text(value, label="limits") for value in values]
    normalized = [re.sub(r"[\W_]+", "", value.casefold()) for value in cleaned]
    if len(normalized) != len(set(normalized)):
        raise ValueError("Character limits must be distinct")
    if any(value in {"无", "没有限制", "暂无限制", "无特殊限制"} for value in normalized):
        raise ValueError("Character limits must state a concrete narrative boundary")
    return cleaned


def _brief_text(value: str, *, label: str) -> str:
    """Reject planning placeholders without banning story-level uncertainty."""

    cleaned = value.strip()
    if re.search(
        r"(?:待补充|待完善|尚未确定|暂未明确|"
        r"(?:(?:这个|该|具体|相关)?(?:内容|细节|信息|设定|方案|部分|事项)).{0,6}"
        r"后续(?:再)?(?:补充|决定|确定)|需要(?:后续|进一步)(?:补充|决定|确定))",
        cleaned,
    ):
        raise ValueError(f"{label} must be resolved at Brief stage, not deferred as a placeholder")
    return cleaned


def _resolved_planning_text(value: str, *, label: str) -> str:
    """Keep planning artifacts concrete before they reach a downstream stage."""

    cleaned = _brief_text(value, label=label)
    folded = cleaned.casefold()
    if any(marker in folded for marker in _RUNTIME_META_MARKERS):
        raise ValueError(f"{label} must describe the story, not runtime instructions")
    normalized = re.sub(r"[\W_]+", "", folded)
    if normalized in _VAGUE_ROLE_TEXT_VALUES:
        raise ValueError(f"{label} must state a concrete dramatic responsibility")
    return cleaned


def _visible_scene_action(value: str, *, label: str) -> str:
    cleaned = _resolved_planning_text(value, label=label)
    if cleaned.startswith(_PURE_COGNITIVE_PREFIXES):
        raise ValueError(f"{label} must describe a visible action or state change")
    return cleaned


def _resolved_relation_text(value: str, *, label: str) -> str:
    cleaned = _resolved_planning_text(value, label=label)
    normalized = re.sub(r"[\W_]+", "", cleaned.casefold())
    if any(marker in normalized for marker in _AMBIGUOUS_RELATION_MARKERS):
        raise ValueError(
            f"{label} must state an established, concrete relationship pressure"
        )
    return cleaned


def _require_distinct_character_dimensions(subject: Any) -> None:
    fields = (
        "background",
        "conflict_history",
        "present_stakes",
        "temperament",
        "speech_style",
    )
    normalized = {
        field: re.sub(r"[\W_]+", "", str(getattr(subject, field)).casefold())
        for field in fields
    }
    duplicates = sorted(
        {
            left
            for index, left in enumerate(fields)
            for right in fields[index + 1 :]
            if normalized[left] == normalized[right]
        }
    )
    if duplicates:
        raise ValueError(
            "Character background, conflict history, present stakes, temperament, "
            "and speech style must carry distinct performable information"
        )


def _require_milestone_window(
    position: int,
    turn_count: int,
    start_ratio: float,
    end_ratio: float,
    label: str,
) -> None:
    minimum = max(1, math.ceil(turn_count * start_ratio))
    maximum = max(minimum, math.floor(turn_count * end_ratio))
    if not minimum <= position <= maximum:
        raise ValueError(
            f"Spine {label} milestone must land at turn {minimum}-{maximum} "
            f"for a {turn_count}-turn structure"
        )


def _creative_title(value: str, *, label: str) -> str:
    if _NUMBERED_TITLE_PREFIX.match(value):
        raise ValueError(f"{label} must be a creative title, not a numbered placeholder")
    return value


def _require_unique_titles(titles: list[str], *, label: str) -> None:
    normalized = [title.casefold() for title in titles]
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{label} titles must be unique across the whole artifact")


def _non_whitespace_characters(value: str) -> int:
    return len(re.sub(r"\s+", "", value))


# The Run's frozen scale projection owns the actual scene interval. This is
# only a structural guard so the artifact schema does not reintroduce a fixed
# product rule such as "2-4 scenes" before that projection is available.
_DETAIL_STRUCTURAL_SCENE_MAX = 12


def _detail_script_length_max(scene_count: int) -> int:
    if scene_count < 1 or scene_count > _DETAIL_STRUCTURAL_SCENE_MAX:
        raise ValueError(
            "Detail chapters must contain at least one scene and stay within the structural limit"
        )
    return 700 + max(0, scene_count - 2) * 250


def _validate_detail_script_length(
    *,
    purpose: str,
    scenes: list[DetailScene],
    handoff: str,
) -> None:
    script = " ".join(
        [
            purpose,
            *(
                field
                for scene in scenes
                for field in (
                    scene.place,
                    scene.objective,
                    scene.conflict,
                    scene.turn,
                    scene.result,
                )
            ),
            handoff,
        ]
    )
    actual = _non_whitespace_characters(script)
    maximum = _detail_script_length_max(len(scenes))
    if actual > maximum:
        raise ValueError(
            f"Detail chapter script must not exceed {maximum} characters "
            f"for {len(scenes)} scenes; got {actual}. target_characters is prose budget metadata only"
        )


def validate_detail_scene_quality(scenes: list[DetailScene]) -> None:
    """Reject repeated scene beats that would make a chapter pad itself."""

    for field, label in (
        ("objective", "objective"),
        ("turn", "turn"),
        ("result", "result"),
    ):
        values = [
            re.sub(r"[\W_]+", "", str(getattr(scene, field)).casefold())
            for scene in scenes
        ]
        if len(values) != len(set(values)):
            raise ValueError(
                f"Detail scene {label}s must be distinct; repeated scene work cannot pad a chapter"
            )


class LengthEnvelope(StrictArtifact):
    word_target_soft: int = Field(ge=1, le=10_000_000)


class StoryBriefArtifact(StrictArtifact):
    title: str = Field(min_length=2, max_length=30)
    premise: str = Field(min_length=1, max_length=2000)
    promise: str = Field(min_length=1, max_length=1000)
    world_rules: list[str] = Field(min_length=1, max_length=24)
    theme: str = Field(min_length=1, max_length=600)
    ending_promise: str = Field(min_length=1, max_length=1000)
    voice: str = Field(min_length=1, max_length=600)
    length_envelope: LengthEnvelope

    @field_validator("title")
    @classmethod
    def generated_title(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2 or cleaned.casefold() in {
            "待定",
            "待定书名",
            "未命名",
            "未命名作品",
            "未命名小说",
            "untitled",
            "tbd",
        }:
            raise ValueError("Story Brief must generate a real book title")
        return cleaned

    @field_validator(
        "premise",
        "promise",
        "theme",
        "ending_promise",
        "voice",
    )
    @classmethod
    def resolved_planning_text(cls, value: str, info: Any) -> str:
        return _brief_text(value, label=info.field_name)

    @field_validator("world_rules")
    @classmethod
    def resolved_world_rules(cls, value: list[str]) -> list[str]:
        return [_brief_text(item, label="world_rules") for item in value]


SpineMilestone = Literal[
    "inciting",
    "commitment",
    "midpoint_reversal",
    "crisis",
    "climax",
    "aftermath",
]


class SpineTurn(StrictArtifact):
    id: str = Field(pattern=r"^turn-[1-9][0-9]*$")
    cause: str = Field(min_length=1, max_length=1200)
    change: str = Field(min_length=1, max_length=1200)
    progress_type: Literal["information", "relationship", "external", "internal"]
    milestones: list[SpineMilestone] = Field(max_length=6)

    _cause_validator = field_validator("cause")(
        lambda value: _resolved_planning_text(value, label="cause")
    )
    _change_validator = field_validator("change")(
        lambda value: _resolved_planning_text(value, label="change")
    )


class SpineTurnDraft(StrictArtifact):
    cause: str = Field(min_length=1, max_length=1200)
    change: str = Field(min_length=1, max_length=1200)
    progress_type: Literal["information", "relationship", "external", "internal"]

    _cause_validator = field_validator("cause")(
        lambda value: _resolved_planning_text(value, label="cause")
    )
    _change_validator = field_validator("change")(
        lambda value: _resolved_planning_text(value, label="change")
    )


class StorySpineArtifact(StrictArtifact):
    turns: list[SpineTurn] = Field(min_length=1, max_length=120)
    ending: str = Field(min_length=1, max_length=1600)
    open_questions: list[str] = Field(max_length=16)
    progress_types: list[Literal["information", "relationship", "external", "internal"]] = Field(
        min_length=1, max_length=4
    )

    @model_validator(mode="after")
    def unique_turns(self) -> "StorySpineArtifact":
        ids = [turn.id for turn in self.turns]
        if ids != [f"turn-{index}" for index in range(1, len(ids) + 1)]:
            raise ValueError("Spine turn ids must be deterministic and contiguous")
        causes = [turn.cause.casefold() for turn in self.turns]
        changes = [turn.change.casefold() for turn in self.turns]
        if len(causes) != len(set(causes)):
            raise ValueError("Spine turns must not repeat the same cause")
        if len(changes) != len(set(changes)):
            raise ValueError("Spine turns must not repeat the same change")
        if any(cause == change for cause, change in zip(causes, changes, strict=True)):
            raise ValueError("A Spine turn cause and change must describe different states")
        progress_types = list(dict.fromkeys(turn.progress_type for turn in self.turns))
        if self.progress_types != progress_types:
            raise ValueError("Spine progress_types must be the ordered projection of turn progress_type")
        if len(self.turns) >= 6:
            if "relationship" not in progress_types:
                raise ValueError("A long Spine must contain at least one relationship turn")
            if "external" not in progress_types:
                raise ValueError("A long Spine must contain at least one external-pressure turn")
        milestone_positions: dict[SpineMilestone, list[int]] = {
            milestone: []
            for milestone in (
                "inciting",
                "commitment",
                "midpoint_reversal",
                "crisis",
                "climax",
                "aftermath",
            )
        }
        for index, turn in enumerate(self.turns, start=1):
            if len(turn.milestones) != len(set(turn.milestones)):
                raise ValueError("One Spine turn cannot repeat a structural milestone")
            for milestone in turn.milestones:
                milestone_positions[milestone].append(index)
        for milestone, positions in milestone_positions.items():
            if len(positions) != 1:
                raise ValueError(f"Spine must bind exactly one {milestone} milestone")
        count = len(self.turns)
        positions = {key: value[0] for key, value in milestone_positions.items()}
        if positions["inciting"] != 1:
            raise ValueError("Spine inciting milestone must bind to the first turn")
        if count >= 6 and positions["climax"] != count - 1:
            raise ValueError("A long Spine climax milestone must bind to the penultimate turn")
        if count < 6 and positions["climax"] not in {max(1, count - 1), count}:
            raise ValueError("A short Spine climax must bind to its final two turns")
        if positions["aftermath"] != count:
            raise ValueError("Spine aftermath milestone must bind to the final turn")
        ordered = [
            positions["inciting"],
            positions["commitment"],
            positions["midpoint_reversal"],
            positions["crisis"],
            positions["climax"],
            positions["aftermath"],
        ]
        if ordered != sorted(ordered):
            raise ValueError("Spine structural milestones must stay in causal order")
        if count >= 6:
            _require_milestone_window(positions["commitment"], count, 0.20, 0.30, "commitment")
            _require_milestone_window(
                positions["midpoint_reversal"], count, 0.40, 0.60, "midpoint_reversal"
            )
            _require_milestone_window(positions["crisis"], count, 0.65, 0.80, "crisis")
        return self


class StorySpineDraftArtifact(StrictArtifact):
    turns: list[SpineTurnDraft] = Field(min_length=1, max_length=120)
    ending: str = Field(min_length=1, max_length=1600)
    open_questions: list[str] = Field(max_length=16)


class RoleDemandProposal(StrictArtifact):
    demand_key: str = Field(pattern=r"^demand-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    subject_mode: Literal["actor", "historical_record"]
    narrative_role: Literal["protagonist", "opposition", "relationship", "functional", "historical_record"]
    function: str = Field(min_length=1, max_length=400)
    required_change: str = Field(min_length=1, max_length=600)
    irreducibility: str = Field(min_length=8, max_length=500)
    # A principal role can legitimately stay active across every spine turn,
    # so this cap must track StorySpineArtifact.turns (max 120), not a fixed dozen.
    active_turn_refs: list[str] = Field(min_length=1, max_length=120)

    @field_validator("irreducibility", mode="before")
    @classmethod
    def validate_irreducibility(cls, value: Any) -> Any:
        if not isinstance(value, str):
            return value
        cleaned = value.strip()
        cleaned = _resolved_planning_text(cleaned, label="irreducibility")
        if cleaned.casefold() in _VAGUE_IRREDUCIBILITY_VALUES:
            raise ValueError(
                "Role demand irreducibility must name a concrete choice, pressure, or consequence"
            )
        return cleaned

    _function_validator = field_validator("function")(
        lambda value: _resolved_planning_text(value, label="function")
    )
    _required_change_validator = field_validator("required_change")(
        lambda value: _resolved_planning_text(value, label="required_change")
    )

    @field_validator("active_turn_refs")
    @classmethod
    def validate_active_turn_refs(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Role demand active turn refs must be unique")
        if any(re.fullmatch(r"turn-[1-9][0-9]*", item) is None for item in value):
            raise ValueError("Role demand active turn refs must use turn-N ids")
        order = [int(item.removeprefix("turn-")) for item in value]
        if order != sorted(order):
            raise ValueError("Role demand active turn refs must follow Spine order")
        return value

    @model_validator(mode="after")
    def validate_role_mode(self) -> "RoleDemandProposal":
        if self.narrative_role == "historical_record" and self.subject_mode != "historical_record":
            raise ValueError("A historical role demand must use historical_record mode")
        if self.narrative_role != "historical_record" and self.subject_mode != "actor":
            raise ValueError("A present role demand must use actor mode")
        return self


class CastDemand(StrictArtifact):
    """Rebuildable pressure diagnostic, never a character-count authority."""

    subject_id: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    pressure: int = Field(ge=0, le=200)
    signals: list[str] = Field(max_length=12)
    recommendation: Literal["keep", "split", "merge", "review"]


class VolumeBoundaryProposal(StrictArtifact):
    boundary_key: str = Field(pattern=r"^boundary-[1-9][0-9]*$")
    # One volume may absorb most of a long spine; keep in step with the 120-turn ceiling.
    turn_refs: list[str] = Field(min_length=1, max_length=120)
    reason: str = Field(min_length=1, max_length=1000)


class RoleDemandProposalBatch(StrictArtifact):
    proposals: list[RoleDemandProposal] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_distinct_demands(self) -> "RoleDemandProposalBatch":
        if sum(item.narrative_role == "protagonist" for item in self.proposals) != 1:
            raise ValueError("Role demand proposal must contain exactly one protagonist")
        demand_keys = [item.demand_key for item in self.proposals]
        if len(demand_keys) != len(set(demand_keys)):
            raise ValueError("Role demand proposal keys must be unique")
        functions = [item.function.strip().casefold() for item in self.proposals]
        if len(functions) != len(set(functions)):
            raise ValueError(
                "Role demand proposal contains duplicate functions; merge the duplicated subject duties"
            )
        changes = [item.required_change.strip().casefold() for item in self.proposals]
        if len(changes) != len(set(changes)):
            raise ValueError(
                "Role demand proposal contains duplicate required changes; give each subject a distinct dramatic arc"
            )
        return self


class VolumeBoundaryProposalBatch(StrictArtifact):
    proposals: list[VolumeBoundaryProposal] = Field(min_length=1, max_length=24)


class DetailLayoutChapterProposal(StrictArtifact):
    """One creative chapter boundary proposed before scene-card expansion."""

    turn_refs: list[str] = Field(min_length=1, max_length=24)
    dramatic_job: str = Field(min_length=1, max_length=400)
    length_hint: Literal["compact", "standard", "expansive"]

    _dramatic_job_validator = field_validator("dramatic_job")(
        lambda value: _resolved_planning_text(value, label="dramatic_job")
    )


class DetailLayoutVolumeProposal(StrictArtifact):
    volume_ref: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    chapters: list[DetailLayoutChapterProposal] = Field(min_length=1, max_length=200)


class DetailLayoutProposalBatch(StrictArtifact):
    """Narrow creative sidecar that decides chapter boundaries before Detail."""

    status: Literal["sufficient", "insufficient"]
    diagnosis: str = Field(max_length=1000)
    volumes: list[DetailLayoutVolumeProposal] = Field(max_length=24)

    @model_validator(mode="after")
    def validate_capacity_state(self) -> "DetailLayoutProposalBatch":
        if self.status == "sufficient":
            if not self.volumes:
                raise ValueError("A sufficient Detail layout must contain volume plans")
            if self.diagnosis.strip():
                raise ValueError("A sufficient Detail layout must keep diagnosis empty")
        else:
            if self.volumes:
                raise ValueError("An insufficient Detail layout must not fabricate chapter plans")
            if not self.diagnosis.strip():
                raise ValueError("An insufficient Detail layout requires a capacity diagnosis")
        return self


class ContextSnippet(StrictArtifact):
    ref: str = Field(min_length=1, max_length=160)
    purpose: str = Field(min_length=1, max_length=160)
    text: str = Field(min_length=1, max_length=12_000)
    source_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class ContextBudget(StrictArtifact):
    input_chars: int = Field(ge=1, le=500_000)
    output_tokens: int = Field(ge=1, le=1_000_000)


class ContextManifest(StrictArtifact):
    task: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    required: list[str] = Field(min_length=1, max_length=8)
    optional: list[str] = Field(max_length=12)
    forbidden: list[str] = Field(min_length=1, max_length=12)
    snippets: list[ContextSnippet] = Field(max_length=16)
    budget: ContextBudget
    manifest_hash: str = Field(pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def validate_integrity(self) -> "ContextManifest":
        required = self.required
        optional = self.optional
        if len(required) != len(set(required)) or len(optional) != len(set(optional)):
            raise ValueError("Context Manifest refs must be unique")
        if set(required) & set(optional):
            raise ValueError("Context Manifest required and optional refs must be disjoint")
        snippet_refs = [snippet.ref for snippet in self.snippets]
        if len(snippet_refs) != len(set(snippet_refs)):
            raise ValueError("Context Manifest snippet refs must be unique")
        if set(snippet_refs) != set(required) | set(optional):
            raise ValueError("Context Manifest refs must match its snippets exactly")
        if any(_content_hash(snippet.text) != snippet.source_hash for snippet in self.snippets):
            raise ValueError("Context Manifest source hash does not match snippet text")
        if self.budget.input_chars != sum(len(snippet.text) for snippet in self.snippets):
            raise ValueError("Context Manifest input character budget does not match snippets")
        payload = self.model_dump(mode="json", exclude={"manifest_hash"})
        if _content_hash(_canonical_json(payload)) != self.manifest_hash:
            raise ValueError("Context Manifest hash does not match its signed payload")
        return self


CharacterKind = Literal["protagonist", "major", "functional", "npc", "historical_record"]


class CharacterSubject(StrictArtifact):
    id: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    name: str = Field(min_length=1, max_length=120)
    kind: CharacterKind
    function: str = Field(min_length=1, max_length=500)
    background: str = Field(
        min_length=12,
        max_length=600,
        description="故事开始前已成立的身份、经历与可调用能力，不写当前剧情动作。",
    )
    conflict_history: str = Field(
        min_length=12,
        max_length=600,
        description="此人与核心冲突在故事开始前已经发生的具体联系、责任或损失。",
    )
    present_stakes: str = Field(
        min_length=8,
        max_length=400,
        description="当前失败将失去的具体人、关系、资格、位置、信誉或信念。",
    )
    temperament: str = Field(
        min_length=8,
        max_length=400,
        description="压力下可重复演绎的判断顺序、行动倾向与防御方式。",
    )
    speech_style: str = Field(
        min_length=6,
        max_length=400,
        description="可直接写入对白的句式、措辞、节奏、停顿或沉默习惯。",
    )
    drive: str = Field(min_length=1, max_length=600)
    change: str = Field(min_length=1, max_length=600)
    debut: str = Field(pattern=r"^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$")
    limits: list[str] = Field(min_length=1, max_length=16)
    demand_refs: list[str] = Field(min_length=1, max_length=8)

    _name_validator = field_validator("name")(_creative_character_name)

    @field_validator(
        "function",
        "background",
        "conflict_history",
        "present_stakes",
        "temperament",
        "speech_style",
        "drive",
        "change",
    )
    @classmethod
    def validate_narrative_text(cls, value: str, info: Any) -> str:
        return _character_text(value, label=info.field_name)

    _limits_validator = field_validator("limits")(_character_limits)

    @model_validator(mode="after")
    def distinct_performance_dimensions(self) -> "CharacterSubject":
        _require_distinct_character_dimensions(self)
        return self


class CharacterDossier(StrictArtifact):
    """Provider-authored dossier; the runtime binds its preallocated subject id."""

    name: str = Field(min_length=1, max_length=120)
    kind: CharacterKind
    function: str = Field(min_length=1, max_length=500)
    background: str = Field(
        min_length=12,
        max_length=600,
        description="故事开始前已成立的身份、经历与可调用能力，不写当前剧情动作。",
    )
    conflict_history: str = Field(
        min_length=12,
        max_length=600,
        description="此人与核心冲突在故事开始前已经发生的具体联系、责任或损失。",
    )
    present_stakes: str = Field(
        min_length=8,
        max_length=400,
        description="当前失败将失去的具体人、关系、资格、位置、信誉或信念。",
    )
    temperament: str = Field(
        min_length=8,
        max_length=400,
        description="压力下可重复演绎的判断顺序、行动倾向与防御方式。",
    )
    speech_style: str = Field(
        min_length=6,
        max_length=400,
        description="可直接写入对白的句式、措辞、节奏、停顿或沉默习惯。",
    )
    drive: str = Field(min_length=1, max_length=600)
    change: str = Field(min_length=1, max_length=600)
    debut: str = Field(pattern=r"^chapter:[1-9][0-9]*(?:-[1-9][0-9]*)?$")
    limits: list[str] = Field(min_length=1, max_length=16)
    demand_refs: list[str] = Field(min_length=1, max_length=8)

    _name_validator = field_validator("name")(_creative_character_name)

    @field_validator(
        "function",
        "background",
        "conflict_history",
        "present_stakes",
        "temperament",
        "speech_style",
        "drive",
        "change",
    )
    @classmethod
    def validate_narrative_text(cls, value: str, info: Any) -> str:
        return _character_text(value, label=info.field_name)

    _limits_validator = field_validator("limits")(_character_limits)

    @model_validator(mode="after")
    def distinct_performance_dimensions(self) -> "CharacterDossier":
        _require_distinct_character_dimensions(self)
        return self


class CharacterDossierBatch(StrictArtifact):
    subjects: list[CharacterDossier] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def distinct_subject_dimensions(self) -> "CharacterDossierBatch":
        if len(self.subjects) < 2:
            return self
        for field in (
            "background",
            "conflict_history",
            "present_stakes",
            "temperament",
            "speech_style",
        ):
            normalized = [
                re.sub(r"[\W_]+", "", getattr(subject, field).casefold())
                for subject in self.subjects
            ]
            if len(normalized) != len(set(normalized)):
                raise ValueError(
                    f"Character dossiers must give each subject distinct {field} information"
                )
        return self


def validate_character_dossier_modes(
    dossiers: CharacterDossierBatch,
    subject_refs: list[dict[str, Any]],
) -> None:
    """Bind each dossier to one frozen actor or historical-subject demand."""

    modes: dict[str, str] = {}
    roles: dict[str, str] = {}
    for subject_ref in subject_refs:
        demand_key = str(subject_ref.get("demand_key") or "")
        subject_mode = str(subject_ref.get("subject_mode") or "")
        narrative_role = str(subject_ref.get("narrative_role") or "")
        if not demand_key or subject_mode not in {"actor", "historical_record"}:
            raise ValueError("Cast subject refs require a frozen demand_key and subject_mode")
        if narrative_role not in {
            "protagonist",
            "opposition",
            "relationship",
            "functional",
            "historical_record",
        }:
            raise ValueError("Cast subject refs require a frozen narrative_role")
        if narrative_role == "historical_record" and subject_mode != "historical_record":
            raise ValueError("A historical_record narrative role must use historical_record mode")
        if narrative_role != "historical_record" and subject_mode != "actor":
            raise ValueError("Present narrative roles must use actor mode")
        if demand_key in modes:
            raise ValueError(f"Cast subject refs repeat role demand {demand_key}")
        modes[demand_key] = subject_mode
        roles[demand_key] = narrative_role

    coverage = {demand_key: 0 for demand_key in modes}
    for dossier in dossiers.subjects:
        referenced_modes: set[str] = set()
        for demand_ref in dossier.demand_refs:
            subject_mode = modes.get(demand_ref)
            if subject_mode is None:
                raise ValueError(
                    f"Character dossier references unknown role demand: {demand_ref}"
                )
            coverage[demand_ref] += 1
            referenced_modes.add(subject_mode)
        if len(referenced_modes) != 1:
            raise ValueError("One character dossier cannot combine actor and historical demands")
        subject_mode = referenced_modes.pop()
        if subject_mode == "historical_record" and dossier.kind != "historical_record":
            raise ValueError(
                "A historical_record demand must produce a historical_record dossier"
            )
        if subject_mode == "actor" and dossier.kind == "historical_record":
            raise ValueError("An actor demand cannot produce a historical_record dossier")
        dossier_roles = {roles[demand_ref] for demand_ref in dossier.demand_refs}
        if "protagonist" in dossier_roles and dossier.kind != "protagonist":
            raise ValueError("The protagonist demand must produce a protagonist dossier")
        if dossier.kind == "protagonist" and "protagonist" not in dossier_roles:
            raise ValueError("Only the frozen protagonist demand may produce a protagonist dossier")
        if "historical_record" in dossier_roles and dossier.kind != "historical_record":
            raise ValueError("The historical_record demand must produce a historical_record dossier")

    invalid_coverage = sorted(
        demand_key for demand_key, count in coverage.items() if count != 1
    )
    if invalid_coverage:
        raise ValueError(
            "Each frozen role demand must be covered by exactly one dossier: "
            f"{invalid_coverage}"
        )


class CharacterRelation(StrictArtifact):
    a: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    b: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    type: str = Field(min_length=1, max_length=160)
    pressure: str = Field(min_length=1, max_length=500)

    @field_validator("type", "pressure")
    @classmethod
    def validate_relation_text(cls, value: str, info: Any) -> str:
        return _resolved_relation_text(value, label=info.field_name)


class CharacterRelationBatch(StrictArtifact):
    relations: list[CharacterRelation] = Field(max_length=360)


class CharacterBibleArtifact(StrictArtifact):
    subjects: list[CharacterSubject] = Field(min_length=1, max_length=120)
    relations: list[CharacterRelation] = Field(max_length=360)

    @model_validator(mode="after")
    def validate_registry(self) -> "CharacterBibleArtifact":
        ids = [subject.id for subject in self.subjects]
        if len(ids) != len(set(ids)):
            raise ValueError("Character subject ids must be unique")
        names = [subject.name.casefold() for subject in self.subjects]
        if len(names) != len(set(names)):
            raise ValueError("Character subject names must be unique")
        if sum(subject.kind == "protagonist" for subject in self.subjects) != 1:
            raise ValueError("Character Bible must register exactly one protagonist")
        known = set(ids)
        for relation in self.relations:
            if relation.a == relation.b or relation.a not in known or relation.b not in known:
                raise ValueError("Character relations must reference two registered subjects")
        return self


class VolumeContract(StrictArtifact):
    id: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    title: str = Field(min_length=2, max_length=12)
    promise: str = Field(min_length=1, max_length=1000)
    conflict: str = Field(min_length=1, max_length=1000)
    climax: str = Field(min_length=1, max_length=1200)
    climax_turn_ref: str = Field(pattern=r"^turn-[1-9][0-9]*$")
    closure: str = Field(min_length=1, max_length=1200)
    # Keep in step with the 120-turn spine ceiling: one volume may own most turns.
    turn_refs: list[str] = Field(min_length=1, max_length=120)
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    length_hint: Literal["short", "medium", "long"]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _creative_title(value, label="Volume")

    @model_validator(mode="after")
    def validate_climax_position(self) -> "VolumeContract":
        if self.climax_turn_ref not in self.turn_refs:
            raise ValueError("Volume climax must bind to a turn owned by the volume")
        climax_index = self.turn_refs.index(self.climax_turn_ref)
        if climax_index + 1 < max(1, math.ceil(len(self.turn_refs) * 0.6)):
            raise ValueError("Volume climax must land in the final 40 percent of its owned turns")
        return self


class VolumeContractDraft(StrictArtifact):
    title: str = Field(min_length=2, max_length=12)
    promise: str = Field(min_length=1, max_length=1000)
    conflict: str = Field(min_length=1, max_length=1000)
    climax: str = Field(min_length=1, max_length=1200)
    climax_turn_ref: str = Field(pattern=r"^turn-[1-9][0-9]*$")
    closure: str = Field(min_length=1, max_length=1200)
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    length_hint: Literal["short", "medium", "long"]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _creative_title(value, label="Volume")


class VolumeArchitectureDraftArtifact(StrictArtifact):
    volumes: list[VolumeContractDraft] = Field(min_length=1, max_length=24)


class VolumeArchitectureUnitArtifact(StrictArtifact):
    volumes: list[VolumeContractDraft] = Field(min_length=1, max_length=1)


class VolumeArchitectureArtifact(StrictArtifact):
    volumes: list[VolumeContract] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def unique_and_contiguous(self) -> "VolumeArchitectureArtifact":
        ids = [volume.id for volume in self.volumes]
        if ids != [f"volume-{index}" for index in range(1, len(ids) + 1)]:
            raise ValueError("Volume ids must be deterministic and contiguous")
        _require_unique_titles(
            [volume.title for volume in self.volumes],
            label="Volume",
        )
        return self


class DetailScene(StrictArtifact):
    place: str = Field(min_length=1, max_length=300)
    objective: str = Field(min_length=1, max_length=700)
    conflict: str = Field(min_length=1, max_length=700)
    turn: str = Field(min_length=1, max_length=700)
    result: str = Field(min_length=1, max_length=700)

    _objective_validator = field_validator("objective")(
        lambda value: _resolved_planning_text(value, label="objective")
    )
    _conflict_validator = field_validator("conflict")(
        lambda value: _resolved_planning_text(value, label="conflict")
    )
    _turn_validator = field_validator("turn")(
        lambda value: _visible_scene_action(value, label="turn")
    )
    _result_validator = field_validator("result")(
        lambda value: _visible_scene_action(value, label="result")
    )


class DetailChapter(StrictArtifact):
    ref: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    volume_ref: str = Field(pattern=r"^volume-[1-9][0-9]*$")
    title: str = Field(min_length=2, max_length=12)
    # Prose-length metadata owned by the runtime; it is never a Detail script
    # content target or a requirement to expand the chapter card.
    target_characters: Optional[int] = Field(default=None, ge=1)
    # Frozen by the runtime from the chapter beat slots. Editors may revise the
    # script, but they may not move a chapter onto a different causal turn.
    turn_refs: list[str] = Field(min_length=1, max_length=24)
    purpose: str = Field(min_length=1, max_length=1000)
    pov: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    scenes: list[DetailScene] = Field(min_length=1, max_length=_DETAIL_STRUCTURAL_SCENE_MAX)
    handoff: str = Field(min_length=1, max_length=800)

    @model_validator(mode="after")
    def validate_cast(self) -> "DetailChapter":
        _validate_chapter_cast(self.pov, self.cast_ids)
        _validate_detail_script_length(
            purpose=self.purpose,
            scenes=self.scenes,
            handoff=self.handoff,
        )
        return self

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _creative_title(value, label="Chapter")


class DetailArtifact(StrictArtifact):
    chapters: list[DetailChapter] = Field(min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_chapters(self) -> "DetailArtifact":
        refs = [chapter.ref for chapter in self.chapters]
        if refs != [f"chapter-{index}" for index in range(1, len(refs) + 1)]:
            raise ValueError("Detail chapter refs must be deterministic and contiguous")
        targets = [
            chapter.target_characters
            for chapter in self.chapters
            if chapter.target_characters is not None
        ]
        if targets and len(targets) != len(self.chapters):
            raise ValueError("Detail character targets must be present for every chapter or none")
        if targets:
            average_target = sum(targets) / len(targets)
            if any(
                abs(target - average_target) > average_target * 0.1 + 1
                for target in targets
            ):
                raise ValueError("Detail chapter targets must stay within 10% of the book average")
            if any(
                abs(left - right) > average_target * 0.15 + 1
                for left, right in zip(targets, targets[1:])
            ):
                raise ValueError("Adjacent Detail chapter targets must stay within the rhythm band")
        return self


class DetailSegmentChapter(StrictArtifact):
    title: str = Field(min_length=2, max_length=12)
    purpose: str = Field(min_length=1, max_length=1000)
    pov: str = Field(pattern=r"^subject-[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
    cast_ids: list[str] = Field(min_length=1, max_length=80)
    scenes: list[DetailScene] = Field(min_length=1, max_length=_DETAIL_STRUCTURAL_SCENE_MAX)
    handoff: str = Field(min_length=1, max_length=800)

    @model_validator(mode="after")
    def validate_cast(self) -> "DetailSegmentChapter":
        _validate_chapter_cast(self.pov, self.cast_ids)
        _validate_detail_script_length(
            purpose=self.purpose,
            scenes=self.scenes,
            handoff=self.handoff,
        )
        return self

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _creative_title(value, label="Chapter")


class DetailSegmentArtifact(StrictArtifact):
    chapters: list[DetailSegmentChapter] = Field(min_length=1, max_length=200)


class ChapterArtifact(StrictArtifact):
    chapter_id: str = Field(pattern=r"^chapter-[1-9][0-9]*$")
    version_id: str = Field(min_length=1, max_length=160)
    title: str = Field(min_length=2, max_length=12)
    content: str = Field(min_length=1)
    author_status: Literal["candidate", "accepted", "edited", "branched"]

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _creative_title(value, label="Chapter")


class CoverBrief(StrictArtifact):
    concept: str = Field(min_length=1, max_length=1000)
    image_prompt: str = Field(min_length=1, max_length=3000)
    palette: list[str] = Field(min_length=1, max_length=6)
    negative_constraints: list[str] = Field(max_length=16)


class CoverArtifact(StrictArtifact):
    brief: CoverBrief
    selected_asset_id: str = Field(max_length=200)


class ExportMetadata(StrictArtifact):
    title: str = Field(min_length=1, max_length=200)
    author: str = Field(max_length=160)
    version_note: str = Field(max_length=500)


class ExportVolume(StrictArtifact):
    """Volume grouping for delivery rendering: consecutive chapters per volume."""

    title: str = Field(min_length=2, max_length=12)
    chapter_count: int = Field(ge=1)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        return _creative_title(value, label="Volume")


class ExportArtifact(StrictArtifact):
    format: Literal["md", "json", "zip"]
    chapter_version_ids: list[str] = Field(min_length=1)
    cover_asset_id: str = Field(max_length=200)
    metadata: ExportMetadata
    volumes: list[ExportVolume] = Field(min_length=1, max_length=24)

    @model_validator(mode="after")
    def validate_volume_grouping(self) -> "ExportArtifact":
        counted = sum(volume.chapter_count for volume in self.volumes)
        if counted != len(self.chapter_version_ids):
            raise ValueError("Export volume grouping must cover every chapter exactly once")
        _require_unique_titles(
            [volume.title for volume in self.volumes],
            label="Export volume",
        )
        return self


ARTIFACT_MODELS: dict[StageId, type[StrictArtifact]] = {
    "brief": StoryBriefArtifact,
    "spine": StorySpineArtifact,
    "cast": CharacterBibleArtifact,
    "volumes": VolumeArchitectureArtifact,
    "detail": DetailArtifact,
    "text": ChapterArtifact,
    "cover": CoverArtifact,
    "export": ExportArtifact,
}


def validate_artifact_vnext(
    stage_id: StageId,
    payload: Any,
    *,
    subject_ids: set[str] | None = None,
    chapter_refs: set[str] | None = None,
    chapter_target: int | None = None,
    chapter_turn_refs: dict[str, list[str]] | None = None,
    demand_keys: set[str] | None = None,
    turn_ids: set[str] | None = None,
    volume_cast_ids: dict[str, set[str]] | None = None,
    historical_subject_ids: set[str] | None = None,
    cover_asset_ids: set[str] | None = None,
    chapter_version_ids: list[str] | None = None,
    export_title: str | None = None,
    **_: Any,
) -> StrictArtifact:
    artifact = ARTIFACT_MODELS[stage_id].model_validate(payload)
    known_subjects = subject_ids or set()
    if isinstance(artifact, CharacterBibleArtifact):
        known = {item.id for item in artifact.subjects}
        if demand_keys is not None:
            referenced_demands = {
                demand_ref for item in artifact.subjects for demand_ref in item.demand_refs
            }
            unknown_demands = referenced_demands - demand_keys
            if unknown_demands:
                raise ValueError(f"Character Bible references unknown role demands: {sorted(unknown_demands)}")
            missing_demands = demand_keys - referenced_demands
            if missing_demands:
                raise ValueError(f"Character Bible does not cover role demands: {sorted(missing_demands)}")
        frozen_chapter_count = chapter_target or (
            len(chapter_refs) if chapter_refs is not None else None
        )
        if frozen_chapter_count is not None and any(
            _chapter_end(item.debut) > frozen_chapter_count for item in artifact.subjects
        ):
            raise ValueError("Character debut windows exceed the frozen detail range")
        if known_subjects and known != known_subjects:
            raise ValueError("Character Bible subject registry must match the frozen registry")
    if isinstance(artifact, VolumeArchitectureArtifact):
        if turn_ids is not None:
            unknown_turns = {
                turn_ref
                for volume in artifact.volumes
                for turn_ref in volume.turn_refs
                if turn_ref not in turn_ids
            }
            if unknown_turns:
                raise ValueError(f"Volume references unknown spine turns: {sorted(unknown_turns)}")
        if known_subjects:
            unknown = {
                subject_id
                for volume in artifact.volumes
                for subject_id in volume.cast_ids
                if subject_id not in known_subjects
            }
            if unknown:
                raise ValueError(f"Volume references unknown subjects: {sorted(unknown)}")
    if isinstance(artifact, DetailArtifact):
        if known_subjects:
            unknown = {
                subject_id
                for item in artifact.chapters
                for subject_id in item.cast_ids
            } - known_subjects
            if unknown:
                raise ValueError(f"Detail references unknown subjects: {sorted(unknown)}")
        if historical_subject_ids:
            present_historical = {
                subject_id
                for item in artifact.chapters
                for subject_id in item.cast_ids
                if subject_id in historical_subject_ids
            }
            if present_historical:
                raise ValueError(
                    "Detail present-action cast_ids reference historical subjects: "
                    f"{sorted(present_historical)}"
                )
        if volume_cast_ids is not None:
            for item in artifact.chapters:
                allowed = volume_cast_ids.get(item.volume_ref)
                if allowed is None:
                    raise ValueError(f"Detail references unknown volume: {item.volume_ref}")
                outside_volume = set(item.cast_ids) - allowed
                if outside_volume:
                    raise ValueError(
                        f"Detail chapter references subjects outside {item.volume_ref}: {sorted(outside_volume)}"
                    )
        if chapter_refs is not None and {item.ref for item in artifact.chapters} != chapter_refs:
            raise ValueError("Detail chapters must match the frozen chapter refs")
        if chapter_turn_refs is not None:
            actual = {item.ref: item.turn_refs for item in artifact.chapters}
            expected = {
                str(chapter_ref): [str(turn_ref) for turn_ref in turn_refs]
                for chapter_ref, turn_refs in chapter_turn_refs.items()
            }
            if actual != expected:
                raise ValueError(
                    "Detail chapter turn bindings must match the frozen chapter beat slots"
                )
    if isinstance(artifact, CoverArtifact) and artifact.selected_asset_id:
        if cover_asset_ids is not None and artifact.selected_asset_id not in cover_asset_ids:
            raise ValueError("Cover selects an asset outside the immutable candidate set")
    if isinstance(artifact, ExportArtifact):
        if chapter_version_ids is not None and artifact.chapter_version_ids != chapter_version_ids:
            raise ValueError("Export chapter versions must match the accepted manuscript")
        if (
            cover_asset_ids is not None
            and artifact.cover_asset_id
            and artifact.cover_asset_id not in cover_asset_ids
        ):
            raise ValueError("Export references an unknown cover asset")
        if export_title is not None and artifact.metadata.title != export_title:
            raise ValueError("Export title must match the committed brief")
    return artifact


def validate_detail_writeback_identity(
    source: DetailArtifact,
    candidate: DetailArtifact,
) -> None:
    source_identity = [
        (chapter.ref, chapter.volume_ref, chapter.target_characters, tuple(chapter.turn_refs))
        for chapter in source.chapters
    ]
    candidate_identity = [
        (chapter.ref, chapter.volume_ref, chapter.target_characters, tuple(chapter.turn_refs))
        for chapter in candidate.chapters
    ]
    if candidate_identity != source_identity:
        raise ValueError(
            "Detail chapter ids, volume allocation, and character budgets are code-owned"
        )


def _chapter_end(window: str) -> int:
    bounds = window.removeprefix("chapter:").split("-", maxsplit=1)
    return int(bounds[-1])


def _validate_chapter_cast(pov: str, cast_ids: list[str]) -> None:
    if len(cast_ids) != len(set(cast_ids)):
        raise ValueError("Detail chapter cast ids must be unique")
    if pov not in cast_ids:
        raise ValueError("Detail chapter cast ids must include its POV")


def _canonical_json(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def required_cast_subject_ids(artifact: CharacterBibleArtifact) -> set[str]:
    return {subject.id for subject in artifact.subjects}


__all__ = [
    "ARTIFACT_MODELS",
    "CharacterBibleArtifact",
    "CastDemand",
    "CharacterDossier",
    "CharacterDossierBatch",
    "ContextBudget",
    "CharacterRelation",
    "CharacterRelationBatch",
    "CharacterSubject",
    "ChapterArtifact",
    "DetailArtifact",
    "DetailChapter",
    "DetailLayoutChapterProposal",
    "DetailLayoutProposalBatch",
    "DetailLayoutVolumeProposal",
    "DetailScene",
    "DetailSegmentChapter",
    "DetailSegmentArtifact",
    "ExportArtifact",
    "ExportMetadata",
    "CoverArtifact",
    "CoverBrief",
    "ContextManifest",
    "ContextSnippet",
    "LengthEnvelope",
    "RoleDemandProposal",
    "RoleDemandProposalBatch",
    "SpineMilestone",
    "SpineTurn",
    "SpineTurnDraft",
    "StageId",
    "STAGE_LABELS",
    "STAGE_ORDER",
    "StoryBriefArtifact",
    "StorySpineArtifact",
    "StorySpineDraftArtifact",
    "StrictArtifact",
    "VolumeArchitectureArtifact",
    "VolumeArchitectureDraftArtifact",
    "VolumeArchitectureUnitArtifact",
    "VolumeBoundaryProposal",
    "VolumeBoundaryProposalBatch",
    "VolumeContract",
    "VolumeContractDraft",
    "required_cast_subject_ids",
    "stage_pointer",
    "validate_artifact_vnext",
    "validate_character_dossier_modes",
    "validate_detail_writeback_identity",
]
