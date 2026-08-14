from __future__ import annotations

import json
import struct
import zlib
from typing import Any

from novel_workflow.providers.base import GeneratedImage
from novel_workflow.runtime.graph.provider_gateway import (
    ChapterEvidenceRequest,
    ChapterEvidenceResult,
    ChapterGenerationRequest,
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
            "chapter_target_soft": 2,
        },
    }


def fake_spine_payload() -> dict[str, Any]:
    return {
        "turns": [
            {"cause": "母带被删除", "change": "主角决定调查"},
            {"cause": "恢复到异常脉冲", "change": "调查转入旧潮道"},
        ],
        "ending": "公开母带并承担记忆损失",
        "open_questions": ["谁签署了删除令？"],
        "progress_types": ["information", "external", "internal"],
    }


class FakeNarrativeProvider:
    """Offline NarrativeProviderGateway double returning contract-valid payloads."""

    def __init__(self, *, subject_count: int = 2) -> None:
        self.subject_count = subject_count
        self.stage_requests: list[StageGenerationRequest] = []
        self.proposal_requests: list[ProposalGenerationRequest] = []
        self.chapter_requests: list[ChapterGenerationRequest] = []
        self.review_requests: list[ChapterReviewRequest] = []
        self.evidence_requests: list[ChapterEvidenceRequest] = []
        self.cover_requests: list[CoverImageRequest] = []

    async def generate_stage(self, request: StageGenerationRequest) -> StructuredProviderResult:
        self.stage_requests.append(request)
        if request.stage_id == "brief":
            payload = fake_brief_payload()
        elif request.stage_id == "spine":
            payload = fake_spine_payload()
        elif request.stage_id == "cast":
            refs = request.context["material"]["subject_refs"]
            payload = {
                "subjects": [
                    {
                        "name": f"角色{int(ref['id'].split('-')[-1])}",
                        "kind": "protagonist" if ref["id"] == "subject-1" else "major",
                        "function": f"承担需求 {ref['demand_key']}",
                        "drive": "推动母带真相公开",
                        "change": "从回避风险转向承担证言责任",
                        "debut": "chapter:1",
                        "limits": ["不得代替主角完成最终选择"],
                        "demand_refs": [ref["demand_key"]],
                    }
                    for ref in refs
                ],
            }
        elif request.stage_id == "volumes":
            boundaries = request.context["material"]["volume_boundaries"]["proposals"]
            cast_ids = [
                item["id"]
                for item in request.context["material"]["character_bible_refs"]
            ]
            payload = {
                "volumes": [
                    {
                        "title": f"雾港{boundary['boundary_key'].split('-')[-1]}卷",
                        "promise": "找到母带来源",
                        "conflict": "档案系统持续删除证据",
                        "climax": "主角公开母带",
                        "closure": "旧案真相公开但记忆受损",
                        "cast_ids": cast_ids,
                        "thread_ids": [],
                        "length_hint": "short",
                    }
                    for boundary in boundaries
                ]
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
        if request.proposal_type == "role_demand":
            payload = {
                "proposals": [
                    {
                        "demand_key": f"demand-role-{index}",
                        "function": f"承担第 {index} 个叙事职责",
                        "required_change": "从回避风险转为承担后果",
                        "active_turn_refs": [f"turn-{1 + (index - 1) % 2}"],
                    }
                    for index in range(1, self.subject_count + 1)
                ]
            }
        elif request.proposal_type == "cast_relation":
            payload = {"relations": [
                {"a": "subject-1", "b": "subject-2", "type": "互相利用的搭档", "pressure": "违规会连累双方"}
            ]}
        else:
            payload = {"proposals": [{"boundary_key": "boundary-1", "turn_refs": ["turn-1", "turn-2"], "reason": "两个转折共同闭合一卷"}]}
        return StructuredProviderResult(payload=payload, usage={"total_tokens": 2})

    async def generate_chapter(self, request: ChapterGenerationRequest) -> PlainTextProviderResult:
        self.chapter_requests.append(request)
        target = _chapter_character_target(request.context)
        prefix = f"{request.chapter_id}正文"
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
        if snippet["purpose"] != "chapter_length_contract":
            continue
        contract = json.loads(snippet["text"])
        return int(contract["target_characters"])
    return None
