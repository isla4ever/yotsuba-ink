from __future__ import annotations

import hashlib
import re

from novel_workflow.knowledge.schemas import KnowledgeChunk


def chunk_document(
    *,
    doc_id: str,
    project_id: str,
    title: str,
    text: str,
    chunk_tokens: int = 800,
    overlap_tokens: int = 120,
) -> list[KnowledgeChunk]:
    sections = split_sections(text)
    chunks: list[KnowledgeChunk] = []
    chunk_index = 0
    max_chars = chunk_tokens * 2
    overlap_chars = overlap_tokens * 2
    for section_title, section_text in sections:
        for piece in recursive_chunks(section_text, max_chars=max_chars, overlap_chars=overlap_chars):
            clean = piece.strip()
            if not clean:
                continue
            chunk_index += 1
            chunk_hash = hashlib.sha1(clean.encode("utf-8")).hexdigest()[:16]
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{doc_id}-c{chunk_index}",
                    doc_id=doc_id,
                    project_id=project_id,
                    title=title,
                    section=section_title,
                    text=clean,
                    index=chunk_index,
                    hash=chunk_hash,
                    tokens_estimate=max(1, len(clean) // 2),
                    keywords=keywords(clean),
                    embedding=hash_embedding(clean),
                )
            )
    return chunks


def split_sections(text: str) -> list[tuple[str, str]]:
    normalized = text.replace("\r\n", "\n")
    headings = list(re.finditer(r"(?m)^(#{1,6}\s+.+|第[一二三四五六七八九十百\d]+[章节卷].*)$", normalized))
    if not headings:
        return [("全文", normalized)]

    sections: list[tuple[str, str]] = []
    for index, heading in enumerate(headings):
        start = heading.end()
        end = headings[index + 1].start() if index + 1 < len(headings) else len(normalized)
        title = heading.group(1).lstrip("#").strip()
        body = normalized[start:end].strip()
        sections.append((title, body or title))
    prefix = normalized[: headings[0].start()].strip()
    if prefix:
        sections.insert(0, ("前言", prefix))
    return sections


def recursive_chunks(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    compact = re.sub(r"\n{3,}", "\n\n", text).strip()
    if len(compact) <= max_chars:
        return [compact]

    separators = ["\n\n", "\n", "。", "；", "，", " "]
    return _split_with_separators(compact, separators, max_chars=max_chars, overlap_chars=overlap_chars)


def _split_with_separators(text: str, separators: list[str], *, max_chars: int, overlap_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    if not separators:
        return sliding_chunks(text, max_chars=max_chars, overlap_chars=overlap_chars)

    separator = separators[0]
    parts = text.split(separator)
    if len(parts) == 1:
        return _split_with_separators(text, separators[1:], max_chars=max_chars, overlap_chars=overlap_chars)

    chunks: list[str] = []
    current = ""
    for part in parts:
        candidate = part if not current else f"{current}{separator}{part}"
        if len(candidate) <= max_chars:
            current = candidate
            continue
        if current:
            chunks.append(current)
        current = part
        if len(current) > max_chars:
            chunks.extend(_split_with_separators(current, separators[1:], max_chars=max_chars, overlap_chars=overlap_chars))
            current = ""
    if current:
        chunks.append(current)
    return add_overlap(chunks, overlap_chars)


def sliding_chunks(text: str, *, max_chars: int, overlap_chars: int) -> list[str]:
    step = max(1, max_chars - overlap_chars)
    return [text[index : index + max_chars] for index in range(0, len(text), step)]


def add_overlap(chunks: list[str], overlap_chars: int) -> list[str]:
    if overlap_chars <= 0 or len(chunks) <= 1:
        return chunks
    result = [chunks[0]]
    for index in range(1, len(chunks)):
        prefix = chunks[index - 1][-overlap_chars:]
        result.append(f"{prefix}\n{chunks[index]}")
    return result


def keywords(text: str) -> list[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_-]{2,}", text)
    seen: dict[str, int] = {}
    for token in tokens:
        seen[token] = seen.get(token, 0) + 1
    ranked = sorted(seen.items(), key=lambda item: (-item[1], item[0]))
    return [token for token, _ in ranked[:24]]


def hash_embedding(text: str, dims: int = 64) -> list[float]:
    vector = [0.0] * dims
    for token in keywords(text) or [text[:24]]:
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        for index, byte in enumerate(digest):
            vector[index % dims] += (byte / 255.0) - 0.5
    norm = sum(value * value for value in vector) ** 0.5 or 1.0
    return [round(value / norm, 6) for value in vector]
