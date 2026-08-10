from __future__ import annotations

from novel_workflow.output_contracts.prompt_materials import PROMPT_MATERIAL_KEYS
from novel_workflow.workflows.schemas import PromptTemplate


INFO_STAGE_PROMPT = """你是类型小说立项编辑。根据用户 Brief 与可选的前置知识库 Source Pack，返回唯一的 StoryBriefArtifact。

只输出合同字段：title、premise、story_promise、world_rules、thematic_question、ending_promise、voice、cast_requirements。知识库材料只用于题材事实与创作约束，不复制原作桥段；没有用户上传知识库时不得检索。人物只写叙事职能需求，不在本阶段创建角色档案。"""


CHARACTERS_STAGE_PROMPT = """你是人物编排编辑。基于已定稿 Story Brief，返回唯一的 CharacterBibleArtifact。

在正文前冻结主角、重要配角、功能角色和必要 NPC 槽位。characters 必须有稳定 id、职责、目标、内在需求、人物弧、首次出现窗口和硬边界；relationships 只能引用已注册 character id；npc_slots 只定义用途与限制，不得承担 POV、核心反转或解决主冲突。不要返回 UI 坐标、自评分或阶段重复摘要。"""


SUMMARY_STAGE_PROMPT = """你是长篇小说因果编辑。基于 Story Brief 与 Character Bible，返回唯一的 SummaryArtifact。

beats 按因果顺序写 event 与 consequence，并使用稳定 id；climax 与 resolution 必须兑现 ending_promise；character_outcomes 只能引用 Character Bible 中的 character_id，并必须覆盖全部 protagonist 与 major 角色。不得新增角色、关系或世界硬规则。"""


OUTLINE_STAGE_PROMPT = """你是长篇小说结构编辑。基于已冻结的 Story Brief、Character Bible、Summary 与 BookScalePlan，返回唯一的 OutlineArtifact。

volumes 必须覆盖 BookScalePlan 的连续章区间，所有 chapter_window 统一使用 chapter:N 或 chapter:N-M。上下文若提供 target_volume，本次 volumes 只能返回该卷且 id/window 必须完全一致；系统按独立调用回执聚合全书。每卷只保留 objective、因果 turns、ending_state、character_windows 与 thread_windows；所有人物引用必须来自 Character Bible。不得新增人物，不返回 UI 节奏分数或与 turns 重复的五段文案。"""


DETAIL_STAGE_PROMPT = """你是章节施工图编辑。基于已冻结的 Story Brief、Character Bible、Summary、Outline 与 BookScalePlan，返回唯一的 DetailArtifact。

chapters 必须从 1 连续覆盖目标章节。上下文若提供 target_chapters，本次只能按给定顺序返回这些 id/number；系统按独立调用回执聚合全书。每章只保留 id、number、purpose、pov_character_id、scenes、obligations 与 handoff；场景使用稳定 id，并写 location、goal、obstacle、turn、outcome。每条 obligation 的 kind/ref_id 必须从 obligation_registry 选择，不得自造引用；人物只能引用 Character Bible，NPC 只能引用已冻结槽位。不得返回 schema_version、人物状态快照、Wiki 候选、事实已写回、伏笔已发生或自动修复字段。"""


TEXT_STAGE_PROMPT = """你是成熟的类型小说作者。基于当前章节施工图、上一章已接受版本的交接和冻结人物圣经，返回唯一的 ChapterArtifact。

content 必须自然完成本章 purpose、场景转折、obligations 与 handoff，不逐字段复述施工图。不得新增未注册角色或升级 NPC 职责。author_status 固定为 candidate；Canon、Wiki、审稿与证据提取由独立 LangGraph 节点处理。"""


COVER_STAGE_PROMPT = """你是小说封面编辑。基于已定稿的 Story Brief、Character Bible、Summary、Outline 与 Detail，返回唯一的 CoverBrief。

只返回 concept、image_prompt、palette、negative_constraints。image_prompt 只描述画面，不要求图片模型渲染书名、作者名、Logo、水印或装帧 mockup；不得编造图片 URL、资产 ID、候选数量或生成完成状态。"""


def default_prompt_templates() -> list[PromptTemplate]:
    return [
        PromptTemplate(id="prompt-info", name="创作立项 Prompt", stage_type="info", content=INFO_STAGE_PROMPT, variables=list(PROMPT_MATERIAL_KEYS["info"])),
        PromptTemplate(id="prompt-characters", name="人物圣经 Prompt", stage_type="characters", content=CHARACTERS_STAGE_PROMPT, variables=list(PROMPT_MATERIAL_KEYS["characters"])),
        PromptTemplate(id="prompt-summary", name="全书梗概 Prompt", stage_type="summary", content=SUMMARY_STAGE_PROMPT, variables=list(PROMPT_MATERIAL_KEYS["summary"])),
        PromptTemplate(id="prompt-outline", name="分卷大纲 Prompt", stage_type="outline", content=OUTLINE_STAGE_PROMPT, variables=list(PROMPT_MATERIAL_KEYS["outline"])),
        PromptTemplate(id="prompt-detail", name="章节施工图 Prompt", stage_type="detail", content=DETAIL_STAGE_PROMPT, variables=list(PROMPT_MATERIAL_KEYS["detail"])),
        PromptTemplate(id="prompt-text", name="正文 Prompt", stage_type="text", content=TEXT_STAGE_PROMPT, variables=list(PROMPT_MATERIAL_KEYS["text"])),
        PromptTemplate(id="prompt-cover", name="封面 Prompt", stage_type="cover", content=COVER_STAGE_PROMPT, variables=list(PROMPT_MATERIAL_KEYS["cover"])),
    ]
