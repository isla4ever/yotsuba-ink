"""Runtime policy for the novel generation service.

The core server is intentionally conservative here: model output should be the
source of truth. Deterministic builders are only allowed for hard failures such
as an empty model response, unless an operator explicitly opts into the old
template-first behavior.
"""

from __future__ import annotations

import os
from typing import Dict


LIGHT_TASK_TOKEN_CAPS: Dict[str, int] = {
    "info_recommend": 1800,
    "summary": 1200,
    "outline": 1600,
    "detail_outline": 1800,
}

LIGHT_TASK_TOKEN_FLOORS: Dict[str, int] = {
    "info_recommend": 1000,
    "summary": 700,
    "outline": 900,
    "detail_outline": 1000,
}

TEXT_TASK_TOKEN_CAPS: Dict[str, int] = {
    "text": 1500,
    "text_first_chapter": 1600,
    "text_non_first_chapter": 1600,
}

TEXT_TASK_TOKEN_FLOORS: Dict[str, int] = {
    "text": 900,
    "text_first_chapter": 950,
    "text_non_first_chapter": 950,
}


def env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def allow_deterministic_fallback(reason: str = "empty") -> bool:
    """Return whether prompt-based deterministic fallback may be used.

    Modes:
    - ``empty_only`` (default): allow only empty/hard-failure fallbacks.
    - ``never``: never use deterministic fallback.
    - ``always``: restore old aggressive fallback behavior for debugging.
    """

    mode = str(os.environ.get("NOVEL_DETERMINISTIC_FALLBACK_MODE", "empty_only") or "empty_only").strip().lower()
    if mode in {"always", "all", "1", "true", "yes", "on"}:
        return True
    if mode in {"never", "none", "0", "false", "no", "off"}:
        return False
    return reason in {"empty", "empty_model_output", "hard_failure"}


def allow_direct_structured_resolution(task_name: str) -> bool:
    """Gate the legacy direct structured path.

    The old ``NOVEL_FAST_STRUCTURED_TASKS`` switch skipped real model decoding
    for outline/detail tasks and returned prompt-derived templates. That is
    useful for emergency smoke tests, but it should not be enabled for product
    generation by accident.
    """

    if task_name not in {"outline", "detail_outline"}:
        return False
    legacy_enabled = env_flag("NOVEL_FAST_STRUCTURED_TASKS", False)
    explicit_enabled = env_flag("NOVEL_ALLOW_DIRECT_STRUCTURED_FALLBACK", False)
    return legacy_enabled and explicit_enabled
