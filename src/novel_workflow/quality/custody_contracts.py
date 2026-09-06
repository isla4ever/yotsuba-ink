from __future__ import annotations

import re


CUSTODY_PLACE_MARKERS = ("拘留所", "拘留室", "看守所", "羁押室")
CUSTODY_STATE_MARKERS = (
    "在拘留期间",
    "被拘留后",
    "在拘留中",
    "拘留期间",
    "拘留后",
    "仍被拘留",
    "被拘留",
    "被羁押",
    "被关押",
)
CUSTODY_ENTRY_MARKERS = (
    "再次被拘留",
    "重新被拘留",
    "被警方拘留",
    "被逮捕",
    "被捕",
    "向警方自首",
    "主动自首",
    "投案自首",
)
CUSTODY_RELEASE_MARKERS = ("获释", "被释放", "释放后", "保释")


def text_assumes_custody(text: str) -> bool:
    """Return whether text treats a subject as already being in custody."""

    return any(
        marker in text
        for marker in (*CUSTODY_PLACE_MARKERS, *CUSTODY_STATE_MARKERS)
    )


def text_executes_custody_entry(text: str) -> bool:
    return any(marker in text for marker in CUSTODY_ENTRY_MARKERS)


def text_executes_custody_release(text: str) -> bool:
    return any(marker in text for marker in CUSTODY_RELEASE_MARKERS)


def project_custody_safe_dramatic_task(text: str) -> str:
    """Remove an invalid custody assumption while retaining the chapter's task."""

    projected = text
    for marker in sorted(
        (*CUSTODY_PLACE_MARKERS, *CUSTODY_STATE_MARKERS, *CUSTODY_ENTRY_MARKERS),
        key=len,
        reverse=True,
    ):
        projected = projected.replace(marker, "")
    projected = re.sub(r"\s+", " ", projected)
    projected = re.sub(r"[，；。]{2,}", "，", projected)
    projected = re.sub(r"后(?=(?:通过|获得|接收|核验|发现))", "", projected)
    projected = re.sub(
        r"^([^，；。]{1,16})，(?=(?:通过|获得|接收|核验|发现))",
        r"\1",
        projected,
    )
    projected = projected.strip(" ，；。")
    return projected or "完成自由到拘留的台面状态迁移"


def project_superseded_custody_history_text(text: str) -> str:
    """Remove obsolete custody clauses while retaining unrelated past facts."""

    if not (
        text_assumes_custody(text)
        or text_executes_custody_entry(text)
        or text_executes_custody_release(text)
    ):
        return text
    retained: list[str] = []
    for clause in re.split(r"[，,；;。]", text):
        clause = clause.strip()
        if not clause or (
            text_assumes_custody(clause)
            or text_executes_custody_entry(clause)
            or text_executes_custody_release(clause)
        ):
            continue
        clause = re.sub(r"^(?:但|而|并且|同时|随后|之后)", "", clause).strip()
        if clause:
            retained.append(clause)
    return "，".join(retained)


__all__ = [
    "CUSTODY_ENTRY_MARKERS",
    "CUSTODY_PLACE_MARKERS",
    "CUSTODY_RELEASE_MARKERS",
    "CUSTODY_STATE_MARKERS",
    "project_custody_safe_dramatic_task",
    "project_superseded_custody_history_text",
    "text_assumes_custody",
    "text_executes_custody_entry",
    "text_executes_custody_release",
]
