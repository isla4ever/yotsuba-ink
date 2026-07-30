"""Quality L2 model review (Phase 10.4a).

Turns each node's `quality_policy.checks` into a scored rubric, asks the
configured text provider for a structured review of a committed-candidate
chapter, and returns a `ModelReviewReport`. Provider failures degrade to an
`unavailable` report — scores are never fabricated and the chapter commit is
never blocked by review availability.

Billing: every call goes through `execute_text_provider_call` with the
dedicated `model_review` budget kind (registered in `usage/budget_scope.py`),
so reviews are individually metered and idempotent per chapter version.
"""
from __future__ import annotations

import hashlib
from typing import Any, Literal

from pydantic import BaseModel, Field, ValidationError

from novel_workflow.orchestration.provider_execution import execute_text_provider_call
from novel_workflow.providers.base import PROMPT_SYSTEM_SPLIT

DEFAULT_RUBRIC = ["连续性", "人物一致性", "伏笔推进", "语言质感", "模板味"]

REVIEW_OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "dimensions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dimension": {"type": "string"},
                    "score": {"type": "number", "minimum": 0, "maximum": 10},
                    "evidence": {"type": "string"},
                    "revision_instruction": {"type": "string"},
                },
                "required": ["dimension", "score"],
            },
        },
        "overall_score": {"type": "number", "minimum": 0, "maximum": 10},
        "tension": {
            "type": "object",
            "properties": {"score": {"type": "number", "minimum": 0, "maximum": 10}, "basis": {"type": "string"}},
            "required": ["score", "basis"],
        },
        "voice": {
            "type": "object",
            "properties": {"drift": {"type": "boolean"}, "notes": {"type": "string"}},
        },
    },
    "required": ["dimensions", "overall_score", "tension"],
}


class ModelReviewDimension(BaseModel):
    dimension: str
    score: float = Field(ge=0, le=10)
    evidence: str = ""
    revision_instruction: str = ""


class ModelReviewTension(BaseModel):
    score: float = Field(default=0.0, ge=0, le=10)
    basis: str = ""


class ModelReviewVoice(BaseModel):
    drift: bool = False
    notes: str = ""


class ModelReviewOutput(BaseModel):
    """Strict provider output contract — unparsable output degrades to unavailable."""

    dimensions: list[ModelReviewDimension] = Field(min_length=1)
    overall_score: float = Field(ge=0, le=10)
    tension: ModelReviewTension
    voice: ModelReviewVoice = Field(default_factory=ModelReviewVoice)


class ModelReviewReport(BaseModel):
    status: Literal["completed", "unavailable"] = "completed"
    chapter: str = ""
    chapter_version: int = 0
    content_signature: str = ""
    dimensions: list[ModelReviewDimension] = Field(default_factory=list)
    overall_score: float = Field(default=0.0, ge=0, le=10)
    tension: ModelReviewTension = Field(default_factory=ModelReviewTension)
    voice: ModelReviewVoice = Field(default_factory=ModelReviewVoice)
    error: str = ""
    source: str = "model_review"


def review_content_signature(node_id: str, chapter: str, version: int, content: str) -> str:
    payload = f"{node_id}:{chapter}:v{version}:{content}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


async def run_model_review(
    providers: Any,
    node: Any,
    state: Any,
    *,
    chapter: str,
    content: str,
    run_store: Any,
    chapter_version: int = 0,
) -> ModelReviewReport:
    signature = review_content_signature(node.id, chapter, chapter_version, content)
    prompt = build_review_prompt(node, state, chapter=chapter, content=content)
    inputs = state.inputs if isinstance(state.inputs, dict) else {}
    try:
        result = await execute_text_provider_call(
            providers,
            node,
            state,
            prompt=prompt,
            task_name="model_review",
            context={**inputs, "chapter": chapter, "review_signature": signature},
            schema=REVIEW_OUTPUT_SCHEMA,
            kind="model_review",
            chapter=chapter,
            idempotency_root=f"model-review:{node.id}:{chapter}:{signature}",
            run_store=run_store,
        )
        output = ModelReviewOutput.model_validate(result if isinstance(result, dict) else {})
    except (Exception, ValidationError) as exc:  # noqa: BLE001 — review must degrade, never block the chapter
        return ModelReviewReport(
            status="unavailable",
            chapter=chapter,
            chapter_version=chapter_version,
            content_signature=signature,
            error=str(exc) or exc.__class__.__name__,
        )
    return ModelReviewReport(
        status="completed",
        chapter=chapter,
        chapter_version=chapter_version,
        content_signature=signature,
        dimensions=output.dimensions,
        overall_score=output.overall_score,
        tension=output.tension,
        voice=output.voice,
    )


def build_review_prompt(node: Any, state: Any, *, chapter: str, content: str) -> str:
    rubric = [str(item).strip() for item in getattr(node.quality_policy, "checks", []) if str(item).strip()] or DEFAULT_RUBRIC
    system = "\n".join(
        [
            "你是长篇小说的资深评审编辑，负责对单章正文做结构化质量评审。",
            "评分维度（rubric）：" + "、".join(rubric) + "。",
            "对每个维度输出 dimension、score（0-10）、evidence（引用正文证据）、revision_instruction（可直接执行的修订指令，可为空）。",
            "连续性必须评审真实因果承接：默认应从上一章结果推进到本章进入状态；视角、场景、时间转换或倒叙必须有清晰锚点和叙事目的，不能靠机械出现‘上一章’字样判定通过。",
            "另输出 overall_score（0-10）、tension（本章张力 score 0-10 + basis 依据）、voice（drift 是否文风漂移 + notes）。",
            "只输出符合以上字段的 JSON 对象，不输出其他文字；证据必须来自正文，不得虚构。",
        ]
    )
    packet = next((item for item in state.chapter_context_packets if item.chapter == chapter), None)
    user_lines = [f"## 待评审章节：{chapter}", "", "## 正文", content.strip()]
    if packet is not None:
        if packet.chapter_outline:
            user_lines.extend(["", "## 本章细纲", packet.chapter_outline])
        if packet.previous_chapter_summary:
            user_lines.extend(["", "## 上一章摘要", packet.previous_chapter_summary])
        if packet.previous_volume_ending:
            user_lines.extend(["", "## 上一卷结尾", packet.previous_volume_ending])
        if packet.transition_directive:
            user_lines.extend(["", "## 本章衔接合同", packet.transition_directive])
    voice_summary = _voice_spec_summary(state)
    if voice_summary:
        user_lines.extend(["", "## Voice Spec 摘要", voice_summary])
    return f"{system}{PROMPT_SYSTEM_SPLIT}" + "\n".join(user_lines)


def primary_revision_instruction(review: dict[str, Any] | None) -> str:
    """Lowest-scoring dimension with an actionable instruction drives balanced auto-revision."""
    if not isinstance(review, dict) or review.get("status") != "completed":
        return ""
    dimensions = [item for item in review.get("dimensions", []) if isinstance(item, dict)]
    scored = sorted(dimensions, key=lambda item: float(item.get("score") or 0))
    for item in scored:
        instruction = str(item.get("revision_instruction") or "").strip()
        if instruction:
            return instruction
    return ""


def upsert_tension_entry(story_bible: Any, *, chapter: str, score: float, basis: str) -> dict[str, Any]:
    """Idempotent per-chapter upsert into story_bible.tension_track."""
    entry = {"chapter": chapter, "score": round(float(score), 1), "basis": basis, "source": "model_review"}
    story_bible.tension_track = [item for item in story_bible.tension_track if item.get("chapter") != chapter]
    story_bible.tension_track.append(entry)
    return entry


def _voice_spec_summary(state: Any) -> str:
    artifacts = getattr(state, "artifacts", None)
    brief = artifacts.get("info_recommend") if isinstance(artifacts, dict) else None
    spec = brief.get("voice_spec") if isinstance(brief, dict) else None
    if not isinstance(spec, dict):
        return ""
    lines: list[str] = []
    if spec.get("narration"):
        lines.append(f"叙事：{spec['narration']}")
    if spec.get("rhythm"):
        lines.append(f"节奏：{spec['rhythm']}")
    banned = [str(item) for item in spec.get("banned_words", []) if str(item).strip()]
    if banned:
        lines.append(f"禁用词：{'、'.join(banned[:20])}")
    cliches = [str(item) for item in spec.get("cliche_slots", []) if str(item).strip()]
    if cliches:
        lines.append(f"陈词槽：{'、'.join(cliches[:10])}")
    return "\n".join(lines)
