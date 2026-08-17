from __future__ import annotations

import json
import struct
import zlib
from typing import Any

from novel_workflow.providers.base import GeneratedImage
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ChapterSceneGenerationRequest,
    ChapterReviewRequest,
    ChapterReviewResult,
    CoverImageRequest,
    PlainTextProviderResult,
    ProposalGenerationRequest,
    StageGenerationRequest,
    StructuredProviderResult,
)


def fake_png_bytes(width: int = 256, height: int = 384, *, seed: int = 0) -> bytes:
    pixel = bytes((0x31, 0x53, (0x72 + seed) % 256, 0xFF))
    raw = b"".join(b"\x00" + pixel * width for _ in range(height))
    signature = b"\x89PNG\r\n\x1a\n"
    return (
        signature
        + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0))
        + _png_chunk(b"IDAT", zlib.compress(raw))
        + _png_chunk(b"IEND", b"")
    )


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)


def fake_brief_payload() -> dict[str, Any]:
    return {
        "title": "雾港旧声",
        "premise": "修复师追查一段被删除的母带。",
        "promise": "每次取证都会改变她对母亲失踪的理解。",
        "world_rules": ["公开广播会覆盖个人记忆"],
        "theme": "真相的代价",
        "ending_promise": "真相会被公开。",
        "voice": "克制、贴近感官、第三人称有限视角",
        "length_envelope": {
            "word_target_soft": 12000,
        },
    }


def fake_spine_payload(turn_count: int) -> dict[str, Any]:
    progress_types = ("information", "external", "relationship", "information", "internal")
    return {
        "turns": [
            {
                "cause": f"第 {index} 个压力承接上一局面",
                "change": f"第 {index} 个不可逆调查结果形成",
                "progress_type": progress_types[(index - 1) % len(progress_types)],
            }
            for index in range(1, turn_count + 1)
        ],
        "ending": "公开母带并承担记忆损失",
        "open_questions": ["谁签署了删除令？"],
    }


class FakeNarrativeProvider:
    """Offline NarrativeProviderGateway double returning contract-valid payloads."""

    def __init__(self, *, subject_count: int = 3) -> None:
        self.subject_count = subject_count
        self.stage_requests: list[StageGenerationRequest] = []
        self.proposal_requests: list[ProposalGenerationRequest] = []
        self.chapter_requests: list[ChapterSceneGenerationRequest] = []
        self.review_requests: list[ChapterReviewRequest] = []
        self.evidence_requests: list[ChapterEvidenceRequest] = []
        self.cover_requests: list[CoverImageRequest] = []

    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        self.stage_requests.append(request)
        if request.stage_id == "brief":
            payload = fake_brief_payload()
        elif request.stage_id == "spine":
            scale = request.context["material"]["scale_plan"]
            payload = fake_spine_payload(int(scale["turn_target"]))
        elif request.stage_id == "cast":
            refs = request.context["material"]["subject_refs"]
            names = ("林岚", "周屿", "苏禾", "陈砚", "顾遥", "沈闻")
            payload = {
                "subjects": [
                    {
                        "name": names[(int(ref["id"].split("-")[-1]) - 1) % len(names)],
                        "kind": (
                            "protagonist"
                            if ref["narrative_role"] == "protagonist"
                            else "historical_record"
                            if ref["narrative_role"] == "historical_record"
                            else "major"
                        ),
                        "function": f"承担需求 {ref['demand_key']}",
                        "background": f"长期从事公共档案修复，曾在旧港事故留下的职业争议中负责第 {index} 类记录。",
                        "conflict_history": f"曾参与旧港事故档案的第 {index} 次修复，签名记录与现存母带相互矛盾。",
                        "present_stakes": f"若第 {index} 类证言失效，将失去职业资格并让旧案的一段记录永久封存。",
                        "temperament": f"受压时先核对第 {index} 类证据，再用克制的坚持逼迫对方表态。",
                        "speech_style": f"句子短，常先复述第 {index} 类可验证事实；没有把握时保持沉默。",
                        "drive": "推动母带真相公开",
                        "change": "从回避风险转向承担证言责任",
                        "debut": "chapter:1",
                        "limits": ["不得代替主角完成最终选择"],
                        "demand_refs": [ref["demand_key"]],
                    }
                    for ref in refs
                    for index in [int(ref["id"].split("-")[-1])]
                ],
            }
        elif request.stage_id == "volumes":
            boundary = request.context["material"]["volume_boundary"]
            cast_ids = [
                item["id"]
                for item in request.context["material"]["character_bible_refs"]
            ]
            payload = {
                "volumes": [{
                    "title": f"雾港{boundary['boundary_key'].split('-')[-1]}卷",
                    "promise": "找到母带来源",
                    "conflict": "档案系统持续删除证据",
                    "climax": "主角公开母带",
                    "climax_turn_ref": next(
                        (
                            turn["id"]
                            for turn in request.context["material"]["volume_spine_turns"]
                            if "climax" in turn.get("milestones", [])
                        ),
                        boundary["turn_refs"][
                            max(0, (len(boundary["turn_refs"]) * 3 + 4) // 5 - 1)
                        ],
                    ),
                    "closure": "旧案真相公开但记忆受损",
                    "cast_ids": cast_ids,
                    "length_hint": "short",
                }]
            }
        elif request.stage_id == "detail":
            scale = request.context["material"]["scale_projection"]
            start = int(scale["chapter_number_start"])
            count = int(scale["chapter_target"])
            cast_ids = [
                item["id"]
                for item in request.context["material"]["selected_dossiers"]
            ]
            payload = {
                "chapters": [
                    {
                        "title": f"母带残响{start + offset}",
                        "purpose": "取得母带副本" if offset == 0 else "公开母带",
                        "pov": cast_ids[0],
                        "cast_ids": cast_ids,
                        "scenes": [
                            {
                                "place": "档案室" if scene == 0 else "旧潮道",
                                "objective": "取得登记簿" if scene == 0 else "核对母带",
                                "conflict": "管理员拒绝" if scene == 0 else "广播系统拦截",
                                "turn": "发现删除签名" if scene == 0 else "同伴承认沉默",
                                "result": "拿到副本" if scene == 0 else "确认播放路径",
                            }
                            for scene in range(2)
                        ],
                        "handoff": "追查签名来源" if offset == 0 else "承担记忆损失",
                    }
                    for offset in range(count)
                ]
            }
        elif request.stage_id == "cover":
            payload = {"concept": "雾港中的旧录音", "image_prompt": "雾港、旧录音带、克制悬疑", "palette": ["深蓝", "锈红"], "negative_constraints": ["无文字"]}
        else:
            raise AssertionError(request.stage_id)
        return StructuredProviderResult(payload=payload, usage={"total_tokens": 3})

    async def generate_proposal(self, request: ProposalGenerationRequest) -> StructuredProviderResult:
        self.proposal_requests.append(request)
        if request.proposal_type == "spine_review":
            payload = {"verdict": "pass", "findings": []}
        elif request.proposal_type in {"role_demand_review", "cast_review"}:
            payload = {"verdict": "pass", "findings": []}
        elif request.proposal_type == "role_demand":
            spine_turns = request.context["material"]["story_spine"]["turns"]
            turn_refs = [str(turn["id"]) for turn in spine_turns]
            scale_plan = request.context["material"].get("scale_plan") or {}
            recommended = scale_plan.get("cast_recommended_range") or [1, 1]
            hard_max = int(scale_plan.get("cast_hard_max") or recommended[-1])
            desired_count = min(
                hard_max,
                max(int(recommended[0]), self.subject_count),
            )
            relationship_refs = [
                str(turn["id"])
                for turn in spine_turns
                if turn.get("progress_type") == "relationship"
            ] or [turn_refs[0]]
            payload = {
                "proposals": [
                    {
                        "demand_key": f"demand-role-{index}",
                        "subject_mode": "actor",
                        "narrative_role": (
                            "protagonist"
                            if index == 1
                            else "opposition"
                            if index == 2
                            else "relationship"
                        ),
                        "function": f"承担第 {index} 个叙事职责",
                        "required_change": f"从第 {index} 类回避风险转为承担第 {index} 类后果",
                        "irreducibility": "必须独立作出不可逆选择，不能由现有主体或机构程序代替。",
                        "active_turn_refs": (
                            [turn_refs[0], turn_refs[-1]]
                            if index == 1 and len(turn_refs) > 1
                            else [turn_refs[0]]
                            if index == 1
                            else sorted(
                                set(
                                    [turn_refs[(index - 1) % len(turn_refs)], *relationship_refs]
                                    if index == 2
                                    else [
                                        turn_refs[(index - 1) % len(turn_refs)],
                                        relationship_refs[-1],
                                    ]
                                ),
                                key=turn_refs.index,
                            )
                        ),
                    }
                    for index in range(1, desired_count + 1)
                ]
            }
        elif request.proposal_type == "cast_relation":
            subject_ids = [
                str(item["id"])
                for item in request.context["material"].get("subjects", [])
            ]
            payload = {
                "relations": [
                    {
                        "a": "subject-1",
                        "b": subject_id,
                        "type": "互相利用的搭档",
                        "pressure": "违规会连累双方",
                    }
                    for subject_id in subject_ids
                    if subject_id != "subject-1"
                ]
            }
        elif request.proposal_type == "volume_boundary":
            turn_refs = [
                item["id"]
                for item in request.context["material"]["story_spine"]["turns"]
            ]
            volume_target = int(
                request.context["material"]["scale_plan"]["volume_target"]
            )
            chunk_size, remainder = divmod(len(turn_refs), volume_target)
            offset = 0
            proposals = []
            for index in range(1, volume_target + 1):
                size = chunk_size + (1 if index <= remainder else 0)
                proposals.append(
                    {
                        "boundary_key": f"boundary-{index}",
                        "turn_refs": turn_refs[offset : offset + size],
                        "reason": f"第 {index} 个连续转折单元形成局部闭合",
                    }
                )
                offset += size
            payload = {
                "proposals": proposals
            }
        elif request.proposal_type == "detail_layout":
            material = request.context["material"]
            volume = material["volume_contracts"][0]
            payload = {
                "status": "sufficient",
                "diagnosis": "",
                "volumes": [{
                    "volume_ref": volume["id"],
                    "chapters": [
                        {
                            "turn_refs": turn_refs,
                            "dramatic_job": f"完成{volume['id']}的第{index}个独立变化",
                            "length_hint": "standard",
                        }
                        for index, turn_refs in enumerate(
                            _fake_layout_turn_refs(
                                list(volume["turn_refs"]),
                                int(material["scale_plan"]["chapter_target"]),
                            ),
                            start=1,
                        )
                    ],
                }],
            }
        else:
            raise AssertionError(request.proposal_type)
        return StructuredProviderResult(payload=payload, usage={"total_tokens": 2})

    async def generate_chapter_scene(
        self,
        request: ChapterSceneGenerationRequest,
    ) -> PlainTextProviderResult:
        self.chapter_requests.append(request)
        target = _chapter_character_target(request.context)
        prefix = f"{request.chapter_id}场景{request.scene_index}正文"
        content = prefix + "文" * max(0, target - len(prefix)) if target else f"{prefix}。"
        return PlainTextProviderResult(content=content, usage={"total_tokens": 4})

    async def review_chapter(self, request: ChapterReviewRequest) -> StructuredProviderResult:
        self.review_requests.append(request)
        return StructuredProviderResult(payload=ChapterReviewResult(role=request.role).model_dump(mode="json"), usage={"total_tokens": 1})

    async def extract_chapter_evidence(self, request: ChapterEvidenceRequest) -> StructuredProviderResult:
        self.evidence_requests.append(request)
        return StructuredProviderResult(payload=ChapterEvidenceResult(claims=[{"kind": "fact", "claim": "本章完成施工图目标", "span_ids": ["span-0001"]}]).model_dump(mode="json"), usage={"total_tokens": 1})

    async def generate_cover_image(self, request: CoverImageRequest) -> GeneratedImage:
        self.cover_requests.append(request)
        return GeneratedImage(content=fake_png_bytes(seed=request.candidate_index), mime_type="image/png", provider_asset_id=f"asset-{request.candidate_index}", usage={"total_tokens": 1})


def _chapter_character_target(context: dict[str, Any]) -> int | None:
    manifest = context["material"]["chapter_context_manifest"]
    for snippet in manifest["snippets"]:
        if snippet["purpose"] != "rolling_scene_length_contract":
            continue
        contract = json.loads(snippet["text"])
        return int(contract["target_characters"])
    return None


def _fake_layout_turn_refs(turn_refs: list[str], chapter_count: int) -> list[list[str]]:
    if chapter_count <= len(turn_refs):
        base, remainder = divmod(len(turn_refs), chapter_count)
        result: list[list[str]] = []
        offset = 0
        for index in range(chapter_count):
            size = base + (1 if index < remainder else 0)
            result.append(turn_refs[offset : offset + size])
            offset += size
        return result
    return [
        [turn_refs[min(len(turn_refs) - 1, index * len(turn_refs) // chapter_count)]]
        for index in range(chapter_count)
    ]
