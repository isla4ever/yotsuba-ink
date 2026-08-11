from __future__ import annotations

from dataclasses import dataclass


_SENTENCE_ENDINGS = frozenset("。！？!?")
_TRAILING_CLOSERS = frozenset("”’」』】）)")


@dataclass(frozen=True, slots=True)
class ChapterEvidenceCandidate:
    span_id: str
    start: int
    end: int
    quote: str

    def prompt_payload(self) -> dict[str, str]:
        return {"span_id": self.span_id, "quote": self.quote}


def build_chapter_evidence_candidates(
    content: str,
) -> tuple[ChapterEvidenceCandidate, ...]:
    candidates: list[ChapterEvidenceCandidate] = []
    start: int | None = None
    index = 0
    length = len(content)

    while index < length:
        char = content[index]
        if start is None:
            if char.isspace():
                index += 1
                continue
            start = index

        if char in _SENTENCE_ENDINGS:
            end = index + 1
            while end < length and (
                content[end] in _SENTENCE_ENDINGS
                or content[end] in _TRAILING_CLOSERS
            ):
                end += 1
            _append_candidate(candidates, content, start, end)
            start = None
            index = end
            continue

        if char == "\n":
            _append_candidate(candidates, content, start, index)
            start = None

        index += 1

    if start is not None:
        _append_candidate(candidates, content, start, length)

    if not candidates:
        raise ValueError("Accepted chapter does not contain evidence candidates")
    return tuple(candidates)


def _append_candidate(
    candidates: list[ChapterEvidenceCandidate],
    content: str,
    start: int,
    end: int,
) -> None:
    while end > start and content[end - 1].isspace():
        end -= 1
    if end <= start:
        return
    candidates.append(
        ChapterEvidenceCandidate(
            span_id=f"span-{len(candidates) + 1:04d}",
            start=start,
            end=end,
            quote=content[start:end],
        )
    )


__all__ = ["ChapterEvidenceCandidate", "build_chapter_evidence_candidates"]
