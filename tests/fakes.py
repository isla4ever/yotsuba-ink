from __future__ import annotations

import struct
import zlib
from typing import Any

from novel_workflow.providers.base import GeneratedImage, ImageProvider, TextProvider


class FakeTextProvider(TextProvider):
    name = "test-fake-text"

    async def generate_text(self, prompt: str, *, task_name: str, context: dict[str, Any]) -> str:
        return "测试文本输出"

    async def generate_structured(self, prompt: str, *, task_name: str, context: dict[str, Any], schema: dict[str, Any] | None = None) -> Any:
        if task_name == "info_recommend":
            return {
                "selected_title": "雾港旧声",
                "title_candidates": ["雾港旧声", "雾钟回声", "蓝潮证词", "旧案母带", "港雾未眠"],
                "synopsis": "旧港声纹修复师在旧磁带中听见十年前求救声，追查后发现证词被实验改写。",
                "worldbuilding_detail": "旧港雾钟系统记录声纹证词，蓝潮实验曾筛选并改写关键证词，档案馆、码头和实验区构成核心场域。",
                "characters": [
                    {"name": "林澈", "identity": "声纹修复师", "motivation": "查清父亲与旧案关系", "relations": "与许望舒合作", "growth_direction": "从回避到公开证据"},
                    {"name": "许望舒", "identity": "调查记者", "motivation": "证明旧案存在", "relations": "与林澈合作", "growth_direction": "从追逐报道到保护证人"},
                ],
                "relationships": [{"source": "林澈", "target": "许望舒", "relation": "调查同盟", "strength": 0.7}],
                "tags": ["悬疑", "旧港", "记忆实验"],
                "downstream_constraints": ["雾钟是技术装置", "关系变化由证据推进"],
                "risk_notes": ["避免万能记忆解释"],
            }
        if task_name == "summary":
            return {
                "one_liner": "旧磁带让林澈发现旧港失踪案背后的蓝潮实验仍在运作。",
                "full_synopsis": "林澈修复 7A-13 母带时听见十年前求救声。许望舒带来删改日志，周泊言承认幸存者身份。三人追查雾钟码头和蓝潮实验区，确认证词被技术性筛选。结尾他们公开第一批声纹档案，同时留下父亲签章和备用电源两条后续长线。",
                "act_structure": [{"title": "磁带入局", "goal": "建立旧案入口", "turn": "求救声喊出林澈名字"}],
                "core_conflict": "私人记忆与公共档案互相冲突，公开真相会触动港务利益链。",
                "character_arcs": [{"name": "林澈", "arc": "从回避旧案到公开档案", "pressure": "父亲可能参与实验", "next": "判断亲情和证据边界"}],
                "key_turns": [{"label": "7A-13 母带", "detail": "求救声与私人记忆重叠"}],
                "ending_resolution": "公开第一层真相，并保留父亲签章作为后续追问。",
                "consistency_checks": ["雾钟机制符合硬设定"],
            }
        if task_name == "outline":
            return {
                "volumes": [{
                    "title": "第一卷：7A-13 母带",
                    "chapter_range": "第1-3章",
                    "volume_goal": "完成旧案入口、三人结盟和第一层真相揭示。",
                    "rhythm": "悬念递进",
                    "opening": "林澈修复磁带。",
                    "development": "许望舒带来删改日志。",
                    "midpoint": "周泊言暴露幸存者身份。",
                    "climax": "雾钟无人操作响起。",
                    "resolution": "三人公开第一批档案。",
                    "character_progression": [{"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "证据公开节奏产生分歧", "change": "主动追查", "impact": "下一卷需要重新确认信任边界"}],
                    "world_reveal": [{"anchor": "雾钟", "reveal": "声纹证词装置", "rule": "雾钟只能记录和筛选既有声纹", "impact": "细纲必须保留技术证据链"}],
                    "foreshadow_plan": [{"name": "父亲签章", "status": "投放", "chapter_range": "第3章", "note": "卷尾露出"}],
                }]
            }
        if task_name == "detail_outline":
            return {
                "chapters": [
                    {
                        "chapter": f"第{index}章",
                        "pov": "林澈",
                        "scene": "旧港档案馆",
                        "goal": "推进旧案调查",
                        "entry_state": "承接上一章线索",
                        "conflict": "证据被封存",
                        "stakes": "母带链路可能消失",
                        "fact_reveals": [{"anchor": "雾钟", "fact": "7A-13 母带真实存在", "impact": "旧案获得可验证入口"}],
                        "foreshadow": [{"name": "父亲签章", "status": "投放", "note": "保留签章来源疑问"}],
                        "character_shift": {"character": "林澈", "related_to": "许望舒", "relation": "调查同盟", "pressure": "证据随时可能被封存", "motivation": "保住旧案物证", "change": "从回避转为主动保留证据", "impact": "下一章继续追查母带来源"},
                        "hook": "雾钟再次响起",
                        "continuity_notes": "保持雾钟技术设定",
                        "wiki_candidates": [{"title": "7A-13 母带", "fact": "保存十年前声纹证词", "source_anchor": "雾钟"}],
                    }
                    for index in range(1, 4)
                ]
            }
        if task_name == "chapter_text":
            return {
                "chapter_title": "第1章 7A-13 母带",
                "content": "林澈把 7A-13 母带推进修复机时，旧港档案馆的灯暗了一下。底噪里有人叫出他的名字，像隔着十年的雾钟传来。他没有交出母带，而是复制了证据，也复制了自己的犹豫。",
                "summary": "林澈发现母带异常并保留证据。",
                "wiki_writebacks": [{"target": "7A-13 母带", "fact": "含有十年前求救声", "source_chapter": "第1章"}],
                "character_shift": "林澈开始主动追查。",
                "foreshadow_updates": [{"name": "父亲签章", "status": "投放"}],
            }
        if task_name == "chapter_selection_revision":
            return {"replacement": "林澈压低呼吸，把母带藏进档案袋，决定先保住这条唯一的声纹证据。"}
        if task_name == "model_review":
            return fake_model_review_output()
        if task_name == "cover_image":
            return {
                "brief": "旧港雾夜、声纹磁带和档案馆构成悬疑气质。",
                "visual_keywords": ["旧港", "磁带", "雾钟", "档案馆"],
                "composition": "竖版 2:3，主角背影面对雾钟，前景为磁带波形。",
                "copy_suggestions": ["雾港旧声", "每段回声都在改写证词"],
                "prompt": "cinematic mist harbor, cassette tape waveform, archive room, suspense novel cover",
                "candidates": [{"id": "cover-1", "image_url": "/assets/test-cover-1.png", "composition": "背影+雾钟", "palette": "冷灰蓝", "quality_summary": "主题明确，标题留白充足"}],
                "selected_candidate_id": "cover-1",
            }
        raise AssertionError(f"unexpected task: {task_name}")


def fake_model_review_output() -> dict[str, Any]:
    return {
        "dimensions": [
            {"dimension": "连续性", "score": 8.2, "evidence": "承接上一章母带线索与雾钟设定。", "revision_instruction": ""},
            {"dimension": "语言质感", "score": 6.4, "evidence": "中段描写出现重复句式。", "revision_instruction": "压缩中段重复描写，补充具体感官细节，保持事件顺序不变。"},
        ],
        "overall_score": 7.6,
        "tension": {"score": 6.5, "basis": "章末钩子有效，但中段推进平缓。"},
        "voice": {"drift": False, "notes": "叙事人称与语域保持稳定。"},
    }


class FakeImageProvider(ImageProvider):
    name = "test-fake-image"

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def generate_cover(self, prompt: str, *, context: dict[str, Any]) -> GeneratedImage:
        self.calls.append({"prompt": prompt, "context": context})
        return GeneratedImage(content=fake_png_bytes(), mime_type="image/png", provider_asset_id=f"fake-{len(self.calls)}")


def fake_png_bytes(width: int = 256, height: int = 384) -> bytes:
    raw = b"".join(b"\x00" + b"\x31\x53\x72\xff" * width for _ in range(height))
    signature = b"\x89PNG\r\n\x1a\n"
    return signature + _png_chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + _png_chunk(b"IDAT", zlib.compress(raw)) + _png_chunk(b"IEND", b"")


def _png_chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
