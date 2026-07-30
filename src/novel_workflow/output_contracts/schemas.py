from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from novel_workflow.output_contracts.cover import CoverContract


StageContractName = Literal["story_brief", "summary", "outline", "detail_outline", "chapter_text", "cover", "export"]
RequiredText = Annotated[str, Field(min_length=1)]


class StrictArtifactModel(BaseModel):
    model_config = ConfigDict(extra="ignore")


class StoryCharacter(StrictArtifactModel):
    name: RequiredText
    identity: RequiredText
    motivation: RequiredText
    relations: RequiredText
    tier: str = ""
    faction: str = ""
    faction_stance: str = ""
    growth_direction: str = ""
    background: str = ""


class StoryRelationship(StrictArtifactModel):
    source: RequiredText
    target: RequiredText
    relation: RequiredText
    kind: str = ""
    polarity: str = ""
    strength: float = Field(default=0.5, ge=0, le=1)


class VoiceCharacterSheet(StrictArtifactModel):
    character: RequiredText
    habits: str = ""
    catchphrase: str = ""
    speech_register: str = ""
    never_says: str = ""


class VoiceSpec(StrictArtifactModel):
    narration: str = ""
    rhythm: str = ""
    banned_words: list[str] = Field(default_factory=list)
    cliche_slots: list[str] = Field(default_factory=list)
    per_character: list[VoiceCharacterSheet] = Field(default_factory=list)


class StoryBriefContract(BaseModel):
    selected_title: RequiredText
    title_candidates: list[RequiredText] = Field(min_length=1)
    synopsis: RequiredText
    worldbuilding_detail: RequiredText
    characters: list[StoryCharacter] = Field(min_length=1)
    relationships: list[StoryRelationship] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    downstream_constraints: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    voice_spec: VoiceSpec | None = None

    @model_validator(mode="after")
    def validate_character_relationships(self) -> "StoryBriefContract":
        names = [character.name.strip() for character in self.characters]
        if len(set(names)) != len(names):
            raise ValueError("characters: names must be unique")
        known_names = set(names)
        seen_edges: set[tuple[str, str]] = set()
        for relationship in self.relationships:
            source = relationship.source.strip()
            target = relationship.target.strip()
            if source == target:
                raise ValueError("relationships: source and target must differ")
            if source not in known_names or target not in known_names:
                raise ValueError("relationships: source and target must reference characters")
            edge = (source, target)
            if edge in seen_edges:
                raise ValueError("relationships: duplicate directed edge")
            seen_edges.add(edge)
        return self


class SummaryAct(StrictArtifactModel):
    title: RequiredText
    goal: RequiredText
    turn: RequiredText


class CharacterArc(StrictArtifactModel):
    name: RequiredText
    arc: RequiredText
    pressure: RequiredText
    next: RequiredText


class KeyTurn(StrictArtifactModel):
    label: RequiredText
    detail: RequiredText


class SummaryContract(BaseModel):
    one_liner: RequiredText
    full_synopsis: RequiredText
    act_structure: list[SummaryAct] = Field(min_length=1)
    core_conflict: RequiredText
    character_arcs: list[CharacterArc] = Field(min_length=1)
    key_turns: list[KeyTurn] = Field(min_length=1)
    ending_resolution: RequiredText
    consistency_checks: list[RequiredText] = Field(min_length=1)


class OutlineCharacterProgression(StrictArtifactModel):
    character: RequiredText
    related_to: RequiredText
    relation: RequiredText
    kind: str = ""
    polarity: str = ""
    strength: float | None = Field(default=None, ge=0, le=1)
    pressure: RequiredText
    change: RequiredText
    impact: RequiredText


class OutlineWorldReveal(StrictArtifactModel):
    anchor: RequiredText
    reveal: RequiredText
    rule: RequiredText
    impact: RequiredText


class OutlineForeshadow(StrictArtifactModel):
    name: RequiredText
    status: Literal["投放", "推进", "回收", "延后"]
    chapter_range: RequiredText
    note: RequiredText


class OutlineNewCharacter(StrictArtifactModel):
    name: RequiredText
    role: RequiredText
    tier: str = ""
    faction: str = ""
    faction_stance: str = ""
    stance: str = ""
    relation_to_protagonist: str = ""


class OutlineVolume(StrictArtifactModel):
    title: RequiredText
    chapter_range: RequiredText
    volume_goal: RequiredText
    rhythm: RequiredText
    opening: RequiredText
    development: RequiredText
    midpoint: RequiredText
    climax: RequiredText
    resolution: RequiredText
    new_characters: list[OutlineNewCharacter] = Field(default_factory=list, max_length=4)
    character_progression: list[OutlineCharacterProgression] = Field(min_length=1)
    world_reveal: list[OutlineWorldReveal] = Field(min_length=1)
    foreshadow_plan: list[OutlineForeshadow] = Field(min_length=1)


class OutlineContract(BaseModel):
    volumes: list[OutlineVolume] = Field(min_length=1)


class DetailArtifactModel(StrictArtifactModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)


class DetailNewNpc(DetailArtifactModel):
    name: RequiredText
    role: RequiredText
    faction: str = ""
    note: str = ""


class DetailCharacterShift(DetailArtifactModel):
    character: RequiredText
    related_to: str = ""
    relation: str = ""
    kind: str = ""
    polarity: str = ""
    strength: float | None = Field(default=None, ge=0, le=1)
    pressure: RequiredText
    motivation: RequiredText
    change: RequiredText
    impact: RequiredText

    @model_validator(mode="after")
    def validate_relation_pair(self) -> "DetailCharacterShift":
        if bool(self.related_to) != bool(self.relation):
            raise ValueError("related_to and relation must be provided together")
        if self.related_to and self.related_to == self.character:
            raise ValueError("related_to must reference a different character")
        return self


class DetailFactReveal(DetailArtifactModel):
    anchor: RequiredText
    fact: RequiredText
    impact: RequiredText


class DetailWikiCandidate(DetailArtifactModel):
    title: RequiredText
    fact: RequiredText
    source_anchor: RequiredText
    claim_key: str = ""


class DetailForeshadow(DetailArtifactModel):
    name: RequiredText
    status: Literal["投放", "推进", "回收", "延后"]
    note: RequiredText


class DetailChapter(DetailArtifactModel):
    chapter: RequiredText
    pov: RequiredText
    scene: RequiredText
    goal: RequiredText
    entry_state: RequiredText
    conflict: RequiredText
    stakes: RequiredText
    fact_reveals: list[DetailFactReveal] = Field(min_length=1)
    foreshadow: list[DetailForeshadow] = Field(min_length=1)
    character_shift: DetailCharacterShift
    hook: RequiredText
    continuity_notes: RequiredText
    wiki_candidates: list[DetailWikiCandidate] = Field(min_length=1)
    new_npcs: list[DetailNewNpc] = Field(default_factory=list, max_length=2)

    @field_validator("fact_reveals")
    @classmethod
    def validate_fact_uniqueness(cls, value: list[DetailFactReveal]) -> list[DetailFactReveal]:
        if not _unique_text([item.fact for item in value]):
            raise ValueError("fact_reveals: facts must be unique within a chapter")
        return value

    @field_validator("wiki_candidates")
    @classmethod
    def validate_wiki_uniqueness(cls, value: list[DetailWikiCandidate]) -> list[DetailWikiCandidate]:
        if not _unique_text([item.title for item in value]):
            raise ValueError("wiki_candidates: titles must be unique within a chapter")
        return value

    @field_validator("foreshadow")
    @classmethod
    def validate_foreshadow_uniqueness(cls, value: list[DetailForeshadow]) -> list[DetailForeshadow]:
        if not _unique_text([item.name for item in value]):
            raise ValueError("foreshadow: names must be unique within a chapter")
        return value


class DetailOutlineContract(BaseModel):
    chapters: list[DetailChapter] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_chapter_names(self) -> "DetailOutlineContract":
        if not _unique_text([chapter.chapter for chapter in self.chapters]):
            raise ValueError("chapters: chapter names must be unique")
        return self


def _unique_text(values: list[str]) -> bool:
    normalized = [value.strip() for value in values]
    return len(normalized) == len(set(normalized))


class ChapterItem(StrictArtifactModel):
    id: RequiredText
    title: RequiredText
    generated_title: str = ""
    content: RequiredText
    words: int = Field(ge=1)
    status: Literal["drafting", "committing", "completed"]
    version: int = Field(default=1, ge=0)
    commit_signature: str = ""
    summary: RequiredText
    summary_dirty: Literal[False] = False
    context_packet: "ChapterContextContract"
    wiki_writebacks: list[dict[str, Any]] = Field(default_factory=list)
    character_shift: Any = ""
    foreshadow_updates: list[dict[str, Any]] = Field(default_factory=list)
    quality_report: dict[str, Any] = Field(default_factory=dict)
    quality_recheck: dict[str, Any] = Field(default_factory=dict)
    model_review: dict[str, Any] = Field(default_factory=dict)
    writeback_proposal: dict[str, Any] = Field(default_factory=dict)
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    version_history: list[dict[str, Any]] = Field(default_factory=list)


class ChapterContextContract(StrictArtifactModel):
    chapter: RequiredText
    chapter_index: int = Field(ge=1)
    chapter_kind: Literal["first", "normal", "volume_start", "volume_end", "finale"]
    story_brief: str = ""
    summary: str = ""
    volume_goal: str = ""
    volume_title: str = ""
    volume_chapter_range: str = ""
    next_volume_goal: str = ""
    chapter_outline: RequiredText
    previous_chapter_summary: str = ""
    previous_volume_ending: str = ""
    transition_directive: str = ""
    character_state: dict[str, Any] = Field(default_factory=dict)
    open_foreshadows: list[dict[str, Any]] = Field(default_factory=list)
    world_rules: list[str] = Field(default_factory=list)


class ChapterTextContract(BaseModel):
    schema_version: int = Field(default=1, ge=1)
    status: Literal["running", "completed"] = "completed"
    target_chapters: int = Field(default=1, ge=1)
    context_packet: dict[str, Any] = Field(default_factory=dict)
    context_packets: list[dict[str, Any]] = Field(default_factory=list)
    chapter_deltas: list[dict[str, Any]] = Field(default_factory=list)
    chapters: list[ChapterItem] = Field(min_length=1)
    quality_reports: list[dict[str, Any]] = Field(default_factory=list)
    wiki_writebacks: list[dict[str, Any]] = Field(default_factory=list)
    chapter_summaries: list[dict[str, Any]] = Field(default_factory=list)


class ExportFile(StrictArtifactModel):
    name: RequiredText
    format: RequiredText
    status: RequiredText


class ExportChapter(StrictArtifactModel):
    id: RequiredText
    title: RequiredText
    words: int = 0
    status: RequiredText
    content: str = ""


class ExportCoverAsset(StrictArtifactModel):
    candidate_id: str = ""
    asset_id: str = ""
    sha256: str = ""
    mime_type: str = ""
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    size_bytes: int = Field(default=0, ge=0)
    image_url: str = ""


class ExportContract(BaseModel):
    manifest: list[ExportFile] = Field(min_length=1)
    formats: list[str] = Field(default_factory=list)
    chapters: list[ExportChapter] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    cover_asset: ExportCoverAsset = Field(default_factory=ExportCoverAsset)
    validation: dict[str, Any] = Field(default_factory=dict)
    package_status: dict[str, Any] = Field(default_factory=dict)


class ChapterGenerationContract(BaseModel):
    chapter_title: RequiredText
    content: RequiredText
    summary: str = ""
    wiki_writebacks: list[dict[str, Any]] = Field(default_factory=list)
    character_shift: str = ""
    foreshadow_updates: list[dict[str, Any]] = Field(default_factory=list)


class StageOutputContract(BaseModel):
    name: StageContractName
    description: str
    schema_name: str


CONTRACTS: dict[str, StageOutputContract] = {
    "info_recommend": StageOutputContract(name="story_brief", description="创作立项定稿必须沉淀可人工确认的结构化 Story Brief。", schema_name="StoryBriefContract"),
    "summary": StageOutputContract(name="summary", description="梗概阶段应输出完整梗概、结构节拍、角色弧、关键转折和结局承诺。", schema_name="SummaryContract"),
    "outline": StageOutputContract(name="outline", description="分卷阶段应输出分卷结构、卷目标、卷节拍和承接写回对象。", schema_name="OutlineContract"),
    "detail_outline": StageOutputContract(name="detail_outline", description="细纲阶段应覆盖全部目标章节与 Wiki / 伏笔 / 关系写回对象。", schema_name="DetailOutlineContract"),
    "chapter_text": StageOutputContract(name="chapter_text", description="正文阶段应输出上下文包、正文增量、质量结果和写回记录。", schema_name="ChapterTextContract"),
    "cover_image": StageOutputContract(name="cover", description="AI 封面阶段应输出封面 brief、提示词、候选与最终选择。", schema_name="CoverContract"),
    "export_artifact": StageOutputContract(name="export", description="导出阶段应输出导出清单、校验结果和包状态。", schema_name="ExportContract"),
}


def contract_for_stage(stage_type: str) -> Union[StageOutputContract, None]:
    return CONTRACTS.get(stage_type)
