from __future__ import annotations

import re

from novel_workflow.output_contracts.artifacts_vnext import ContextManifest


_QUANTIFIED_FACT = re.compile(
    r"百分之(?:[零〇一二两三四五六七八九十百千万]+|\d+(?:\.\d+)?)"
    r"|第[零〇一二两三四五六七八九十百千万\d]+(?:章|卷|场|幕|枚|批|号|条|项|份|组|层|级)"
    r"|\d+(?:\.\d+)?(?:%|％|年|月|日|时|分|秒|枚|次|号|条|项|份|组|层|级|厘米|毫米|米|公斤|克|元|块)?"
)

_FACT_AUTHORITY_REFS = {
    "detail.chapter",
    "cast.subjects",
    "brief.world_rules",
    "previous.handoff",
    "previous.ending_excerpt",
    "previous.staged_beats",
    "canon.established_facts",
    "current_chapter.previous_scene",
    "scene.execution",
}


def introduced_quantified_fact_tokens(
    content: str,
    manifest: ContextManifest,
) -> tuple[str, ...]:
    """Return quantified claims that are absent from frozen story context."""

    allowed_text = "\n".join(
        snippet.text
        for snippet in manifest.snippets
        if snippet.ref in _FACT_AUTHORITY_REFS
    )
    allowed = set(_QUANTIFIED_FACT.findall(allowed_text))
    return tuple(
        dict.fromkeys(
            token for token in _QUANTIFIED_FACT.findall(content) if token not in allowed
        )
    )


__all__ = ["introduced_quantified_fact_tokens"]
