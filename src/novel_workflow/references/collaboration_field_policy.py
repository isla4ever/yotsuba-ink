from __future__ import annotations

import re


_EDITABLE_FIELD_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "spine": (
        re.compile(r"ending"),
        re.compile(r"open_questions\.[0-9]+"),
        re.compile(r"turns\.[0-9]+\.(?:cause|change)"),
    ),
    "cast": (
        re.compile(
            r"subjects\.[0-9]+\."
            r"(?:function|background|conflict_history|present_stakes|"
            r"temperament|speech_style|drive|change)"
        ),
        re.compile(r"relations\.[0-9]+\.(?:type|pressure)"),
    ),
    "volumes": (
        re.compile(
            r"volumes\.[0-9]+\."
            r"(?:title|promise|conflict|climax|closure|length_hint)"
        ),
    ),
    "detail": (
        re.compile(r"chapters\.[0-9]+\.(?:purpose|handoff)"),
        re.compile(
            r"chapters\.[0-9]+\.scenes\.[0-9]+\."
            r"(?:place|objective|conflict|turn|result)"
        ),
    ),
    "text": (re.compile(r"content"),),
}


def collaboration_field_is_editable(stage_id: str, field_path: str) -> bool:
    return any(
        pattern.fullmatch(field_path)
        for pattern in _EDITABLE_FIELD_PATTERNS.get(stage_id, ())
    )


__all__ = ["collaboration_field_is_editable"]
