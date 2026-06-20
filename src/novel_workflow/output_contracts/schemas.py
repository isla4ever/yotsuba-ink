from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


StageContractName = Literal["story_brief", "summary", "outline", "detail_outline", "chapter_text", "cover", "export"]


class StoryBriefContract(BaseModel):
    positioning: str = ""
    selling_points: list[str] = Field(default_factory=list)
    world_seeds: list[str] = Field(default_factory=list)
    character_seeds: list[dict[str, str]] = Field(default_factory=list)
    foreshadows: list[str] = Field(default_factory=list)
    ending_direction: str = ""
    risk_notes: list[str] = Field(default_factory=list)


class SummaryContract(BaseModel):
    mainline: str = ""
    conflict_escalation: list[str] = Field(default_factory=list)
    character_arcs: list[str] = Field(default_factory=list)
    foreshadow_ledger: list[str] = Field(default_factory=list)
    finale_promise: str = ""


class OutlineContract(BaseModel):
    recommended_volume_count: int = 0
    volumes: list[dict[str, str]] = Field(default_factory=list)


class DetailOutlineContract(BaseModel):
    chapters: list[dict[str, str]] = Field(default_factory=list)


class ChapterTextContract(BaseModel):
    chapter_title: str = ""
    content: str = ""
    key_events: list[str] = Field(default_factory=list)


class StageOutputContract(BaseModel):
    name: StageContractName
    description: str
    schema_name: str


CONTRACTS: dict[str, StageOutputContract] = {
    "info_recommend": StageOutputContract(name="story_brief", description="创作立项定稿必须沉淀可人工确认的 Story Brief JSON。", schema_name="StoryBriefContract"),
    "summary": StageOutputContract(name="summary", description="梗概阶段应输出全书主线、角色弧、伏笔总账和结局承诺。", schema_name="SummaryContract"),
    "outline": StageOutputContract(name="outline", description="分卷阶段应输出卷结构、卷目标和伏笔分布。", schema_name="OutlineContract"),
    "detail_outline": StageOutputContract(name="detail_outline", description="细纲阶段应覆盖全部目标章节。", schema_name="DetailOutlineContract"),
    "chapter_text": StageOutputContract(name="chapter_text", description="正文阶段应输出正文和关键事件摘要。", schema_name="ChapterTextContract"),
}


def contract_for_stage(stage_type: str) -> StageOutputContract | None:
    return CONTRACTS.get(stage_type)
