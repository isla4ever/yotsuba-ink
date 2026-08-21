from __future__ import annotations

import hashlib
import json

from novel_workflow.output_contracts.artifacts_vnext import ContextManifest
from novel_workflow.runtime.graph.provider_prompt_compiler import (
    render_structured_prompt,
    render_text_prompt,
)
from tests.phase27_bindings import provider_binding


def _context() -> dict[str, object]:
    return {
        "target": "cast",
        "material": {
            "story_spine": {"turns": [{"id": "turn-1"}]},
            "scale_plan": {
                "chapter_target": 40,
                "cast_recommended_range": [3, 7],
                "cast_hard_max": 11,
            },
        },
        "output_budget": {
            "kind": "role_demand",
            "expected_items": 12,
            "item_cap": 12,
            "field_char_cap": 300,
            "max_tokens": 5000,
        },
    }


def test_role_demand_prompt_uses_dynamic_capacity_without_padding_the_cast() -> None:
    prompt = render_structured_prompt(
        provider_binding("cast"),
        "role_demand.proposal",
        _context(),
        {"type": "object"},
    )

    assert "requires at least 3 distinct dramatic subjects" in prompt
    assert "There is no target character count" not in prompt
    assert "irreducible present agencies and indispensable historical subjects" in prompt
    assert "role_demand_target" not in prompt
    assert "role_demand_range" not in prompt
    assert "return only semantically required items" in prompt
    assert "is not a character demand and must be omitted" in prompt
    assert "Never convert such an institution into a named" in prompt
    assert "Every returned function must describe a human actor or an indispensable historical subject" in prompt
    assert "Set subject_mode to actor" in prompt
    assert "historical_record only" in prompt
    assert "never invent present action" in prompt
    assert "closed decision table" in prompt
    assert "不得把历史主体放进 present actor demand" in prompt
    assert "apply a removal test to every demand" in prompt


def test_spine_prompt_requires_first_response_structural_self_check() -> None:
    prompt = render_structured_prompt(
        provider_binding("spine"),
        "spine",
        {
            "target": "spine",
            "material": {
                "scale_plan": {
                    "turn_target": 27,
                    "milestone_positions": {
                        "inciting": 1,
                        "commitment": 7,
                        "midpoint_reversal": 14,
                        "crisis": 19,
                        "climax": 26,
                        "aftermath": 27,
                    },
                }
            },
            "output_budget": {
                "kind": "spine",
                "expected_items": 27,
                "item_cap": 27,
                "field_char_cap": 180,
                "max_tokens": 8_000,
            },
        },
        {"type": "object"},
    )

    assert "silently verify the exact count, every anchor" in prompt
    assert "Every three-turn window must contain at least one relationship, external, or internal change" in prompt
    assert "do not defer structural defects to revision" in prompt


def test_spine_review_distinguishes_liability_collateral_harm_and_institutional_agency() -> None:
    prompt = render_structured_prompt(
        provider_binding("spine"),
        "spine_review.proposal",
        {
            "target": "spine.semantic_review",
            "material": {"story_brief": {}, "story_spine": {}},
            "output_budget": {
                "kind": "spine_review",
                "expected_items": 5,
                "item_cap": 5,
                "field_char_cap": 420,
                "max_tokens": 3_000,
            },
        },
        {"type": "object"},
    )

    assert "sanctions must arise from the sanctioned person's own action" in prompt
    assert "Collateral grief, illness, estrangement" in prompt
    assert "does not require the injured person to have chosen or deserved it" in prompt
    assert "stable functional label such as the supervisor or project lead is enough" in prompt
    assert "never demand a personal name" in prompt
    assert "do not invent a legal or procedural rule" in prompt
    assert "direct physical-state contradictions for the same subject" in prompt
    assert "at most four highest-leverage root findings" in prompt
    assert "within the schema's 800-character maximum" in prompt
    assert "smallest contiguous turn window" in prompt


def test_auxiliary_structured_prompts_do_not_inherit_stage_artifact_templates() -> None:
    cases = (
        ("cast", "role_demand.proposal"),
        ("cast", "role_demand_review.proposal"),
        ("cast", "cast_review.proposal"),
        ("cast", "cast_relation.proposal"),
        ("volumes", "volume_boundary.proposal"),
        ("detail", "detail_layout.proposal"),
        ("text", "text.review"),
        ("text", "text.evidence"),
    )

    for stage_id, task_name in cases:
        prompt = render_structured_prompt(
            provider_binding(stage_id),
            task_name,
            _context(),
            {"type": "object"},
        )

        assert f"Phase 27 {stage_id} prompt" not in prompt
        assert "ignore stage-output instructions above" not in prompt


def test_cast_prompt_requires_all_five_performable_dossier_dimensions_on_first_draft() -> None:
    prompt = render_structured_prompt(
        provider_binding("cast"),
        "cast",
        _context(),
        {"type": "object"},
    )

    assert "Resolve those five dimensions in the first response" in prompt
    assert "conflict_history merely repeats function" in prompt
    assert "person-level identity, workplace, position" in prompt
    assert "腐败势力的代理人" in prompt
    assert "do not invent a personal identity" in prompt
    assert "never write '不适用'" in prompt
    assert "record's wording, omissions" in prompt


def test_cast_planning_reviews_warn_about_padding_and_ambiguous_dossiers() -> None:
    role_review = render_structured_prompt(
        provider_binding("cast"),
        "role_demand_review.proposal",
        _context(),
        {"type": "object"},
    )
    cast_review = render_structured_prompt(
        provider_binding("cast"),
        "cast_review.proposal",
        _context(),
        {"type": "object"},
    )

    assert "capacity rather than permission to invent duties" in role_review
    assert "require an upstream Spine repair rather than fabricated characters" in role_review
    assert "Each finding may cite at most 8 unique turn refs" in role_review
    assert "smallest contiguous evidence window" in role_review
    assert "before the current Cast dossier group enters the visible" in cast_review
    assert "do not by themselves block or trigger regeneration" in cast_review
    assert "specific loss owned by that subject" in cast_review
    assert "repeatable behavior that Text can perform" in cast_review


def test_detail_layout_prompt_requires_dynamic_surplus_to_be_dramatized() -> None:
    context = {
        "target": "detail",
        "material": {
            "story_spine": {"turns": [{"id": f"turn-{index}"} for index in range(1, 26)]},
            "volume_contracts": [{"id": "volume-2", "turn_refs": [f"turn-{index}" for index in range(8, 23)]}],
            "selected_dossiers": [],
            "chapter_slots": [{"slot_index": index} for index in range(1, 24)],
            "scale_plan": {
                "book_chapter_target": 37,
                "book_chapter_range": [34, 37],
                "allocated_chapters": 9,
                "remaining_volume_range": [3, 5],
                "chapter_target": 23,
                "chapter_range": [18, 25],
                "turn_count": 15,
                "minimum_chapter_surplus_over_turns": 3,
                "target_chapter_surplus_over_turns": 8,
            },
        },
        "output_budget": {
            "kind": "detail_layout",
            "expected_items": 23,
            "item_cap": 200,
            "field_char_cap": 85,
            "max_tokens": 4_346,
        },
    }

    prompt = render_structured_prompt(
        provider_binding("detail"),
        "detail_layout.proposal",
        context,
        {"type": "object"},
    )

    assert "positive surplus means a one-turn-per-chapter plan is invalid" in prompt
    assert "return exactly one volume layout" in prompt
    assert "allocated_chapters" in prompt
    assert "remaining_volume_range" in prompt
    assert "Detail owns these derived chapter-level actions" in prompt
    assert "local dramatic invention that only bridges the frozen endpoints" in prompt
    assert "return exactly one chapter proposal for every supplied slot" in prompt
    assert "return status=insufficient instead of shortening the array" in prompt
    assert "runtime has already selected the current turn window's exact chapter-slot count" in prompt
    assert "completed_dramatic_jobs list is a hard exclusion set" in prompt
    assert "near-paraphrase" in prompt
    assert "range is diagnostic context, not permission for the Provider" in prompt
    assert "Choose each current volume's chapter-slot count" not in prompt
    assert "never invent a new clue, decision, actor, procedure result" not in prompt
    assert "repeat suitable turn_refs across adjacent chapters" in prompt
    assert "Do not traverse the Spine slice more than once" in prompt
    assert "first referenced turn position never decreases" in prompt
    assert "attempt and counteraction" in prompt
    assert "return status=insufficient instead of a numerically invalid" in prompt


def test_stage_artifact_prompt_keeps_its_frozen_stage_template() -> None:
    prompt = render_structured_prompt(
        provider_binding("detail"),
        "detail",
        _context(),
        {"type": "object"},
    )

    assert prompt.startswith("Phase 27 detail prompt")


def test_cast_relation_prompt_rejects_speculative_complete_graphs() -> None:
    prompt = render_structured_prompt(
        provider_binding("cast"),
        "cast_relation.proposal",
        _context(),
        {"type": "object"},
    )

    assert "Omit speculative" in prompt
    assert "do not connect every subject" in prompt
    assert "must describe an already established relationship" in prompt
    assert "visible agency signal" in prompt
    assert "双方形成对抗" in prompt
    assert "主体 A 已经做了具体动作 X" in prompt
    assert "能否" in prompt
    assert "推动公开" in prompt
    assert "omit the edge" in prompt
    assert "权衡是否继续" in prompt
    assert "调查发现某人的职位" in prompt
    assert "迫使 B 转向媒体公开" in prompt
    assert "A 已深夜潜入取证" in prompt
    assert "可能的报复" in prompt
    assert "do not optimize global graph connectivity" in prompt
    assert "An empty relations array is valid" in prompt
    assert "vague, possible, potential" in prompt
    assert "item_cap is a ceiling, not a target" in prompt


def test_cast_revision_prompt_keeps_stage_feedback_inside_the_current_dossier_batch() -> None:
    context = {
        "target": "cast",
        "material": {
            "subject_refs": [{"id": "subject-6", "demand_key": "demand-archivist", "subject_mode": "actor"}],
            "role_demand_proposals": [
                {
                    "demand_key": "demand-archivist",
                    "subject_mode": "actor",
                    "function": "档案员",
                    "required_change": "失忆后证词失效",
                    "active_turn_refs": ["turn-9"],
                }
            ],
            "revision_request": {
                "direction": "林泽延后登台，林父保持历史主体，档案员保持功能角色。"
            },
        },
        "output_budget": {
            "kind": "cast_dossier",
            "expected_items": 1,
            "item_cap": 5,
            "field_char_cap": 760,
            "max_tokens": 7_500,
        },
    }

    prompt = render_structured_prompt(
        provider_binding("cast"),
        "cast",
        context,
        {"type": "object"},
    )

    assert "current subject_refs and matching role_demand_proposals dossier batch" in prompt
    assert "Requirements about sibling units are context constraints" in prompt
    assert "never create, return, or rewrite a sibling unit" in prompt
    assert "Filter it through the current frozen unit boundary" in prompt
    assert "apply every requirement" not in prompt


def test_volume_boundary_prompt_freezes_count_but_leaves_boundary_positions_creative() -> None:
    context = {
        "target": "volumes",
        "material": {
            "story_spine": {"turns": [{"id": "turn-1"}, {"id": "turn-2"}]},
            "scale_plan": {
                "chapter_target": 45,
                "chapter_range": [34, 50],
                "volume_target": 3,
                "volume_range": [2, 5],
                "volume_candidate_cap": 12,
            },
        },
        "output_budget": {
            "kind": "volume_boundary",
            "expected_items": 2,
            "item_cap": 12,
            "field_char_cap": 240,
            "max_tokens": 2_000,
        },
    }

    prompt = render_structured_prompt(
        provider_binding("volumes"),
        "volume_boundary.proposal",
        context,
        {"type": "object"},
    )

    assert "already derived material.scale_plan.volume_target" in prompt
    assert "Return exactly volume_target consecutive boundaries" in prompt
    assert "where those boundaries fall, not how many exist" in prompt
    assert "Never add, drop, or merge volumes" in prompt


def test_detail_prompt_treats_turns_handoffs_and_character_limits_as_hard_boundaries() -> None:
    context = {
        "target": "detail",
        "material": {
            "volume_contract": {"id": "volume-1", "title": "潮痕卷"},
            "volume_spine_turns": [{"id": "turn-2", "cause": "cause", "change": "change"}],
            "scale_projection": {
                "chapter_target": 2,
                "scenes_per_chapter_min": 2,
                "scenes_per_chapter_max": 4,
                "chapter_beats": [
                    {
                        "chapter_offset": 1,
                        "turn_refs": ["turn-2"],
                        "dramatic_job": "把授权缺口变成公开职业风险",
                        "length_hint": "compact",
                    },
                    {
                        "chapter_offset": 2,
                        "turn_refs": ["turn-2"],
                        "dramatic_job": "迫使主角用实名索引承担后果",
                        "length_hint": "expansive",
                    },
                ],
            },
            "selected_dossiers": [{"id": "subject-1", "limits": ["must hold"]}],
            "previous_segment_handoff": {
                "previous_ref": "chapter-2",
                "completed_turn_refs": ["turn-1"],
                "established_chapters": [
                    {
                        "chapter_ref": "chapter-2",
                        "title": "潮前校验",
                        "turn_refs": ["turn-1"],
                        "purpose": "固定异常哈希",
                        "final_result": "异常记录已进入保全链",
                    }
                ],
                "unresolved": ["下一步核对实名索引"],
                "next_ref": "volume-1.segment-2",
            },
        },
        "output_budget": {
            "kind": "detail",
            "expected_items": 2,
            "item_cap": 2,
            "field_char_cap": 900,
            "max_tokens": 4478,
            "scene_cap": 4,
        },
    }

    prompt = render_structured_prompt(
        provider_binding("detail"),
        "detail",
        context,
        {"type": "object"},
    )

    assert "exclusive executable story boundary" in prompt
    assert "never enact an event" in prompt
    assert "runtime execution projection" in prompt
    assert "future climax" not in prompt
    assert "future closure" not in prompt
    assert "established_chapters are already planned canon" in prompt
    assert "cumulative across the whole book" in prompt
    assert "scale_projection.chapter_beats" in prompt
    assert "without returning or reassigning those metadata fields" in prompt
    assert "dramatic_job" in prompt
    assert "repeating a procedural submission" in prompt
    assert "selected_dossiers[].limits is a hard invariant" in prompt
    assert "historical_record may never act" in prompt
    assert "cast_ids contains only subjects physically present" in prompt
    assert "compare every proposed title against reserved_titles" in prompt
    assert "compact executable scene card" in prompt
    assert "scale_projection.scenes_per_chapter_min" in prompt
    assert "exactly two effective scenes per chapter" not in prompt
    assert "no chapter may contain more than 4 scenes" in prompt
    assert "future prose budget" in prompt
    assert "Do not write dialogue, atmosphere, inner monologue" in prompt


def test_text_prompt_turns_character_contract_into_scene_level_drafting_instruction() -> None:
    text = '{"accepted_prior_characters":911,"chapter_max_characters":2800,"chapter_min_characters":2200,"chapter_target_characters":2500,"max_characters":1889,"min_characters":1289,"remaining_scene_count":0,"scene_count":2,"scene_index":2,"target_characters":1589}'
    required_values = {
        "detail.chapter": "chapter script",
        "cast.subjects": "cast",
        "volume.contract": "volume",
        "brief.world_rules": "rules",
        "scene.execution": "beats",
    }
    snippets = [
        {
            "ref": ref,
            "purpose": ref,
            "text": value,
            "source_hash": hashlib.sha256(value.encode()).hexdigest(),
        }
        for ref, value in required_values.items()
    ]
    snippets.append(
        {
            "ref": "scale.scene_length",
            "purpose": "rolling_scene_length_contract",
            "text": text,
            "source_hash": hashlib.sha256(text.encode()).hexdigest(),
        }
    )
    body = {
        "task": "chapter-1",
        "required": list(required_values),
        "optional": ["scale.scene_length"],
        "forbidden": ["full_canon"],
        "snippets": snippets,
        "budget": {
            "input_chars": sum(len(item["text"]) for item in snippets),
            "output_tokens": 2400,
        },
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest = ContextManifest.model_validate(
        {**body, "manifest_hash": hashlib.sha256(canonical.encode()).hexdigest()}
    )
    prompt = render_text_prompt(
        provider_binding("text"),
        {"material": {"chapter_context_manifest": manifest.model_dump(mode="json")}},
    )

    assert "rolling scene envelope, not an equal-share chapter split" in prompt
    assert "whole chapter must finish near 2500 and inside 2200-2800" in prompt
    assert "accepted earlier scenes currently total 911" in prompt
    assert "Draft toward 1589 non-whitespace characters" in prompt
    assert "at least 1289 and no more than 1889 characters" in prompt
    assert "Count Chinese characters and punctuation, not model tokens" in prompt
    assert "executes one scene, not a whole chapter" in prompt
    assert "brief.world_rules is the only world and professional rule source" in prompt
    assert "Creative freedom applies to dramatization, not canon" in prompt
    assert "ordinal labels" in prompt
    assert "numeric facts or percentages" in prompt
    assert "professional behavior already entailed by the script" in prompt
    assert "Do not add any named or unnamed present actor" in prompt
    assert "recorded speech may dramatize only information directly stated" in prompt
    assert "newly named workflow, permission, document" in prompt
    assert "hard execution boundary" in prompt
    assert "Do not restart the same approach" in prompt
    assert "write an alternate version of the previous scene" in prompt


def test_text_revision_prompt_rewrites_from_the_signed_source_draft() -> None:
    source = '{"scope":"scene","measured_non_whitespace_characters":900,"content":"未接受短稿"}'
    direction = "逐场扩写到长度合同内"
    required_values = {
        "detail.chapter": "冻结施工图",
        "cast.subjects": "cast",
        "volume.contract": "volume",
        "brief.world_rules": "rules",
        "scene.execution": "beats",
    }
    snippets = [
        {
            "ref": ref,
            "purpose": ref,
            "text": value,
            "source_hash": hashlib.sha256(value.encode()).hexdigest(),
        }
        for ref, value in required_values.items()
    ] + [
        {
            "ref": "revision.source_draft",
            "purpose": "unaccepted_draft_to_replace",
            "text": source,
            "source_hash": hashlib.sha256(source.encode()).hexdigest(),
        },
        {
            "ref": "revision.request",
            "purpose": "controlling_revision_direction",
            "text": direction,
            "source_hash": hashlib.sha256(direction.encode()).hexdigest(),
        },
    ]
    body = {
        "task": "chapter-1",
        "required": list(required_values),
        "optional": ["revision.source_draft", "revision.request"],
        "forbidden": ["full_previous_chapter"],
        "snippets": snippets,
        "budget": {
            "input_chars": sum(len(item["text"]) for item in snippets),
            "output_tokens": 6000,
        },
    }
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    manifest = ContextManifest.model_validate(
        {**body, "manifest_hash": hashlib.sha256(canonical.encode()).hexdigest()}
    )

    prompt = render_text_prompt(
        provider_binding("text"),
        {"material": {"chapter_context_manifest": manifest.model_dump(mode="json")}},
    )

    assert "returns a full scene replacement, not a continuation" in prompt
    assert "Use revision.source_draft as the unaccepted scene" in prompt
    assert "For a net-expansion revision" in prompt
    assert "do not summarize" in prompt
    assert "return one complete replacement scene" in prompt


def test_continuity_review_prompt_blocks_durable_inventions_without_policing_dramatization() -> None:
    context = {
        "target": "text.review",
        "material": {
            "review_role": "continuity",
            "chapter": {
                "chapter_id": "chapter-1",
                "version_id": "chapter-1-v1",
                "content": (
                    "她翻开入行便签，想起监修员上月处分。"
                    "盐液按手册流程漫过晶片。"
                    "从小到大只有林泽这样称呼她。"
                ),
            },
            "opening_chapter": True,
            "current_detail_chapter": {"ref": "chapter-1", "title": "异常哈希"},
            "world_rules": ["修复必须留痕"],
            "character_bible": [{"id": "subject-1", "name": "林澈"}],
        },
        "output_budget": {
            "kind": "review",
            "expected_items": 4,
            "item_cap": 8,
            "field_char_cap": 2_000,
            "max_tokens": 2_000,
        },
    }

    prompt = render_structured_prompt(
        provider_binding("text"),
        "text.review",
        context,
        {"type": "object"},
    )

    assert "complete durable-fact authority" in prompt
    assert "invented_durable_fact blocking finding" in prompt
    assert "repair process" in prompt
    assert "unregistered monitor and punishment" in prompt
    assert "onboarding note that invents career history" in prompt
    assert "childhood relationship claim" in prompt
    assert "ordinary momentary action" in prompt
    assert "generic temporary object" in prompt
    assert "internal scene boundary" in prompt
    assert "replays an earlier scene's completed entry" in prompt
    assert "remain in the state produced by the preceding scene" in prompt
