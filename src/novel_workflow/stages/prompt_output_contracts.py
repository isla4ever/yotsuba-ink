from __future__ import annotations

from typing import Any

from novel_workflow.workflows.schemas import WorkflowNode


def compact_contract_for_node(node: WorkflowNode) -> dict[str, Any]:
    contracts: dict[str, dict[str, Any]] = {
        "info_recommend": {
            "selected_title": "string",
            "title_candidates": ["string"],
            "synopsis": "string",
            "worldbuilding_detail": "string",
            "characters": [{
                "name": "string", "identity": "string", "background": "string", "motivation": "string",
                "relations": "string", "tier": "protagonist|major|supporting",
                "faction": "string", "faction_stance": "protagonist_side|antagonist_side|neutral|hidden",
                "growth_direction": "string",
            }],
            "relationships": [{
                "source": "string", "target": "string", "relation": "string",
                "kind": "kinship|romance|ally|rival|superior|trade|secret|other",
                "polarity": "positive|negative|complex|neutral", "strength": 0.5,
            }],
            "tags": ["string"],
            "downstream_constraints": ["string"],
            "risk_notes": ["string"],
            "voice_spec": {
                "narration": "string", "rhythm": "string", "banned_words": ["string"],
                "cliche_slots": ["string"],
                "per_character": [{
                    "character": "string", "habits": "string", "catchphrase": "string",
                    "speech_register": "string", "never_says": "string",
                }],
            },
        },
        "summary": {
            "one_liner": "string", "full_synopsis": "string",
            "act_structure": [{"title": "string", "goal": "string", "turn": "string"}],
            "core_conflict": "string",
            "character_arcs": [{"name": "string", "arc": "string", "pressure": "string", "next": "string"}],
            "key_turns": [{"label": "string", "detail": "string"}],
            "ending_resolution": "string", "consistency_checks": ["string"],
        },
        "outline": {
            "volumes": [{
                "title": "string", "chapter_range": "string", "volume_goal": "string",
                "rhythm": "string", "opening": "string", "development": "string",
                "midpoint": "string", "climax": "string", "resolution": "string",
                "new_characters": [{
                    "name": "string", "role": "string", "faction": "string",
                    "tier": "supporting", "faction_stance": "string",
                    "stance": "string", "relation_to_protagonist": "string",
                }],
                "character_progression": [{
                    "character": "string", "related_to": "string", "relation": "string",
                    "kind": "kinship|romance|ally|rival|superior|trade|secret|other",
                    "polarity": "positive|negative|complex|neutral", "strength": 0.6,
                    "pressure": "string", "change": "string", "impact": "string",
                }],
                "world_reveal": [{"anchor": "string", "reveal": "string", "rule": "string", "impact": "string"}],
                "foreshadow_plan": [{"name": "string", "status": "投放|推进|回收|延后", "chapter_range": "string", "note": "string"}],
            }],
        },
        "detail_outline": {
            "chapters": [{
                "chapter": "string", "pov": "string", "scene": "string", "goal": "string",
                "entry_state": "string", "conflict": "string", "stakes": "string",
                "fact_reveals": [{"anchor": "string", "fact": "string", "impact": "string"}],
                "foreshadow": [{"name": "string", "status": "投放|推进|回收|延后", "note": "string"}],
                "character_shift": {
                    "character": "string", "related_to": "string", "relation": "string",
                    "kind": "kinship|romance|ally|rival|superior|trade|secret|other",
                    "polarity": "positive|negative|complex|neutral", "strength": 0.6,
                    "pressure": "string",
                    "motivation": "string", "change": "string", "impact": "string",
                },
                "hook": "string", "continuity_notes": "string",
                "wiki_candidates": [{"title": "string", "fact": "string", "source_anchor": "string", "claim_key": "string"}],
                "new_npcs": [{"name": "string", "role": "string", "faction": "string", "note": "string"}],
            }],
        },
        "chapter_text": {
            "chapter_title": "string", "content": "string", "summary": "string",
            "wiki_writebacks": [{"target": "string", "fact": "string", "claim_key": "string", "source_chapter": "string"}],
            "character_shift": "string",
            "foreshadow_updates": [{"name": "string", "status": "string"}],
        },
        "cover_image": {
            "brief": "string", "visual_keywords": ["string"], "composition": "string",
            "copy_suggestions": ["string"], "prompt": "string",
            "candidates": [{
                "id": "string", "composition": "string",
                "palette": "string", "quality_summary": "string",
            }],
            "selected_candidate_id": "string",
        },
        "export_artifact": {
            "manifest": [{"name": "string", "format": "string", "status": "string"}],
            "formats": ["string"],
            "chapters": [{"id": "string", "title": "string", "words": 0, "status": "string", "content": "string"}],
            "metadata": {},
            "cover_asset": {
                "candidate_id": "string", "asset_id": "string", "sha256": "string",
                "mime_type": "string", "width": 0, "height": 0, "size_bytes": 0,
                "image_url": "string",
            },
            "validation": {},
            "package_status": {"kind": "string", "name": "string", "ready": True},
        },
    }
    return contracts.get(node.type, node.output_schema or {})


def compact_output_budget(node: WorkflowNode, stage_config: dict[str, Any]) -> str:
    budget = _configured_budget(node, stage_config)
    prefix = (
        "## 输出长度配置\n"
        f"- 目标中文字符数: {budget['target_chars']}\n"
        f"- 合理范围: {budget['min_chars']}-{budget['max_chars']} 中文字符\n"
        f"- 本节点 max_tokens: {budget['max_tokens']}\n"
        f"- 配置说明: {budget['description']}\n"
        "必须严格按上述长度规划内容；不要为了凑字重复解释，也不要短到缺失剧情、人物或结构信息。\n"
    )
    stage_budgets = {
        "info_recommend": (
            "输出预算：title_candidates 恰好 5 个；synopsis 80-140 字；worldbuilding_detail 180-320 字（硬设定不超过 12 条）；"
            "characters 5-8 个（tier 必填，每个字段 12-45 字）；relationships 8-16 条（kind/polarity 必填）；"
            "tags/downstream_constraints/risk_notes 各 3-5 条；voice_spec 给出叙事、节奏、禁用词和主要人物语声表；"
            "整个 JSON 内容控制在 3200 个中文字符以内。"
        ),
        "summary": (
            "输出预算：one_liner 40-70 字；full_synopsis 450-700 字；act_structure 3-5 项；"
            "character_arcs 2-4 项；key_turns 3-5 项；ending_resolution 80-160 字；整个 JSON 内容控制在 2400 个中文字符以内。"
        ),
        "outline": (
            "输出预算：volumes 1-3 项；每卷 opening/development/midpoint/climax/resolution 各 35-90 字；"
            "character_progression/world_reveal/foreshadow_plan 各 1-4 条结构对象；new_characters 0-4 条（仅在该卷确有结构职责时新增）。"
        ),
        "detail_outline": (
            "输出预算：chapters 按目标章节数返回；每章 goal/conflict/stakes/hook/continuity_notes 各 20-70 字；"
            "fact_reveals/foreshadow/wiki_candidates 各 1-3 条；new_npcs 0-2 条（仅登场需要时新增，不承担关键剧情）。"
        ),
        "chapter_text": (
            "输出预算：content 1500-2200 字；summary 50-120 字；wiki_writebacks/foreshadow_updates 各 0-3 条。"
            "每条 wiki_writeback 必须给出稳定的 claim_key，用于 Canon 事实冲突判断。"
        ),
        "cover_image": "输出预算：brief 80-160 字；visual_keywords 4-8 个；copy_suggestions 2-4 条；candidates 2-3 个。",
    }
    return prefix + stage_budgets.get(node.type, "输出预算：字段完整但保持紧凑，不要扩写解释性段落。")


def _configured_budget(node: WorkflowNode, stage_config: dict[str, Any]) -> dict[str, Any]:
    raw = stage_config.get("generation_budget") if isinstance(stage_config, dict) else None
    if isinstance(raw, dict):
        target = int(raw.get("target_chars") or raw.get("target_words") or 0)
        minimum = int(raw.get("min_chars") or raw.get("min_words") or 0)
        maximum = int(raw.get("max_chars") or raw.get("max_words") or 0)
        max_tokens = int(raw.get("max_tokens") or node.model_settings.max_tokens)
        if target and minimum and maximum:
            return {
                "target_chars": target, "min_chars": minimum, "max_chars": maximum,
                "max_tokens": max_tokens,
                "description": str(raw.get("description") or "用户配置的阶段输出长度。"),
            }
    if node.generation_budget is not None:
        return node.generation_budget.model_dump()
    defaults = {
        "info_recommend": {"target_chars": 2200, "min_chars": 1400, "max_chars": 3200, "max_tokens": 4600, "description": "立项 Story Brief（含人物基线与风格规格）。"},
        "summary": {"target_chars": 1800, "min_chars": 1200, "max_chars": 2800, "max_tokens": 3600, "description": "完整 synopsis。"},
        "outline": {"target_chars": 2200, "min_chars": 1400, "max_chars": 3600, "max_tokens": 4200, "description": "分卷 beat board。"},
        "detail_outline": {"target_chars": 3000, "min_chars": 1800, "max_chars": 4800, "max_tokens": 5200, "description": "章节施工细纲。"},
        "chapter_text": {"target_chars": 2200, "min_chars": 1500, "max_chars": 3200, "max_tokens": 4200, "description": "单章正文。"},
        "cover_image": {"target_chars": 900, "min_chars": 500, "max_chars": 1400, "max_tokens": 2200, "description": "封面 brief 与视觉候选。"},
    }
    return defaults.get(node.type, {
        "target_chars": 900, "min_chars": 500, "max_chars": 1600,
        "max_tokens": node.model_settings.max_tokens, "description": "默认紧凑输出。",
    })
