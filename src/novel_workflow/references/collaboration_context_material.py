from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from novel_workflow.output_contracts.author_collaboration import (
    CollaborationMessage,
    ContextSourceReceipt,
)


@dataclass
class ContextMaterialBuilder:
    sources: list[ContextSourceReceipt] = field(default_factory=list)
    material: dict[str, str] = field(default_factory=dict)

    @property
    def used_chars(self) -> int:
        return sum(len(value) for value in self.material.values())

    def add(
        self,
        *,
        category: str,
        source_ref: str,
        scope_ref: str,
        version: str,
        reason: str,
        label: str,
        content: str,
        disposition: str,
        material_key: str,
    ) -> None:
        cleaned = content.strip()
        if not cleaned:
            return
        self.material[material_key] = cleaned
        self.sources.append(
            ContextSourceReceipt(
                category=category,
                source_ref=source_ref,
                scope_ref=scope_ref,
                source_version=version,
                reason=reason,
                char_count=len(cleaned),
                token_estimate=token_estimate(len(cleaned)),
                disposition=disposition,
                label=label,
            )
        )

    def omit(
        self,
        *,
        category: str,
        source_ref: str,
        scope_ref: str,
        version: str,
        reason: str,
        label: str,
    ) -> None:
        self.sources.append(
            ContextSourceReceipt(
                category=category,
                source_ref=source_ref,
                scope_ref=scope_ref,
                source_version=version,
                reason=reason,
                char_count=0,
                token_estimate=0,
                disposition="omitted",
                label=label,
            )
        )

    def add_history(self, message: CollaborationMessage, index: int) -> None:
        self.add(
            category="history",
            source_ref=message.message_id,
            scope_ref=message.turn_id,
            version=digest(message.content),
            reason="当前线程的有界最近对话",
            label="作者" if message.role == "user" else "协作助手",
            content=bounded_text(message.content, 2_400),
            disposition="optional",
            material_key=f"history_{index:02d}_{message.role}",
        )


def bounded_json(value: Any, limit: int) -> str:
    return bounded_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        limit,
    )


def bounded_text(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    head = max(1, int(limit * 0.72))
    tail = max(1, limit - head - 28)
    return f"{value[:head]}\n...[有界截取]...\n{value[-tail:]}"


def digest(value: Any) -> str:
    encoded = (
        value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stage_label(stage_id: str) -> str:
    return {
        "brief": "创作立项",
        "spine": "故事脊柱",
        "cast": "人物编排",
        "volumes": "分卷架构",
        "detail": "章节施工图",
        "text": "正文",
    }.get(stage_id, stage_id)


def token_estimate(char_count: int) -> int:
    return int(math.ceil(char_count / 2.4))


__all__ = [
    "ContextMaterialBuilder",
    "bounded_json",
    "bounded_text",
    "digest",
    "now_iso",
    "stage_label",
    "token_estimate",
]
