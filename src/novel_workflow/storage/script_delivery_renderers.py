"""Deterministic screenplay delivery renderers for Phase 32."""

from __future__ import annotations

import io
from collections.abc import Sequence
from typing import Literal

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    ScreenplayBlock,
    ScreenplayDraftArtifact,
    ScriptDeliveryArtifact,
)


ScriptDeliveryFormat = Literal["fountain", "pdf", "markdown"]


def render_script_delivery(
    artifact: ScriptDeliveryArtifact,
    scenes: Sequence[ScreenplayDraftArtifact],
    delivery_format: ScriptDeliveryFormat,
) -> tuple[bytes, str, str]:
    stem = safe_delivery_filename(artifact.title)
    if delivery_format == "fountain":
        return (
            _render_fountain(artifact, scenes),
            f"{stem}.fountain",
            "text/plain; charset=utf-8",
        )
    if delivery_format == "markdown":
        return (
            _render_markdown(artifact, scenes),
            f"{stem}.md",
            "text/markdown; charset=utf-8",
        )
    if delivery_format == "pdf":
        return _render_pdf(artifact, scenes), f"{stem}.pdf", "application/pdf"
    raise ValueError(f"Unsupported script delivery format: {delivery_format}")


def safe_delivery_filename(title: str) -> str:
    forbidden = '\\/:*?"<>|'
    value = "".join("-" if character in forbidden or ord(character) < 32 else character for character in title)
    value = value.strip(" .-")
    return value[:120] or "yotsuba-ink-screenplay"


def _render_fountain(
    artifact: ScriptDeliveryArtifact,
    scenes: Sequence[ScreenplayDraftArtifact],
) -> bytes:
    title_page = [f"Title: {artifact.title}"]
    if artifact.author:
        title_page.extend(("Credit: Written by", f"Author: {artifact.author}"))
    if artifact.version_note:
        title_page.append(f"Draft date: {artifact.version_note}")
    sections = ["\n".join(title_page)]
    for scene in scenes:
        sections.append("\n\n".join(_fountain_block(block) for block in scene.blocks))
    return ("\n\n\n".join(sections).rstrip() + "\n").encode("utf-8")


def _fountain_block(block: ScreenplayBlock) -> str:
    if block.kind == "scene_heading":
        return f".{block.text.upper()}"
    if block.kind == "dialogue":
        return f"{_speaker_label(block)}\n{block.text}"
    if block.kind == "parenthetical":
        text = block.text.strip("()")
        return f"({text})"
    if block.kind == "transition":
        text = block.text.upper()
        return text if text.endswith("TO:") else f"> {text}"
    return block.text


def _render_markdown(
    artifact: ScriptDeliveryArtifact,
    scenes: Sequence[ScreenplayDraftArtifact],
) -> bytes:
    sections = [f"# {artifact.title}"]
    if artifact.author:
        sections.append(f"**编剧：** {artifact.author}")
    if artifact.version_note:
        sections.append(f"**版本：** {artifact.version_note}")
    for scene in scenes:
        blocks: list[str] = []
        for block in scene.blocks:
            if block.kind == "scene_heading":
                blocks.append(f"## {block.text}")
            elif block.kind == "dialogue":
                blocks.append(f"**{_speaker_label(block)}**\n\n{block.text}")
            elif block.kind == "parenthetical":
                blocks.append(f"*（{block.text.strip('()')}）*")
            elif block.kind == "transition":
                blocks.append(f"**{block.text.upper()}**")
            else:
                blocks.append(block.text)
        sections.append("\n\n".join(blocks))
    return ("\n\n---\n\n".join(sections).rstrip() + "\n").encode("utf-8")


def _render_pdf(
    artifact: ScriptDeliveryArtifact,
    scenes: Sequence[ScreenplayDraftArtifact],
) -> bytes:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.cidfonts import UnicodeCIDFont
        from reportlab.pdfgen import canvas
    except ImportError as exc:  # pragma: no cover - dependency gate
        raise RuntimeError("PDF delivery requires the reportlab package") from exc

    font_name = "STSong-Light"
    if font_name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(font_name))

    buffer = io.BytesIO()
    page_width, page_height = letter
    pdf = canvas.Canvas(
        buffer,
        pagesize=letter,
        pageCompression=1,
        invariant=1,
    )
    pdf.setTitle(artifact.title)
    pdf.setAuthor(artifact.author)
    pdf.setSubject(artifact.version_note or "Yotsuba Ink screenplay delivery")

    pdf.setFont(font_name, 26)
    pdf.drawCentredString(page_width / 2, page_height * 0.62, artifact.title)
    if artifact.author:
        pdf.setFont(font_name, 12)
        pdf.drawCentredString(page_width / 2, page_height * 0.50, f"编剧：{artifact.author}")
    if artifact.version_note:
        pdf.setFont(font_name, 9)
        pdf.drawCentredString(page_width / 2, 72, artifact.version_note)
    pdf.showPage()

    cursor_y = page_height - 54
    page_number = 1
    for scene in scenes:
        for block in scene.blocks:
            layout = _pdf_block_layout(block, page_width)
            lines = _wrap_pdf_text(
                layout["text"],
                font_name,
                layout["font_size"],
                layout["width"],
                pdfmetrics.stringWidth,
            )
            required_height = len(lines) * layout["leading"] + layout["after"]
            if cursor_y - required_height < 48:
                _draw_page_number(pdf, font_name, page_width, page_number)
                pdf.showPage()
                page_number += 1
                cursor_y = page_height - 54
            pdf.setFont(font_name, layout["font_size"])
            for line in lines:
                x = layout["x"]
                if layout["align"] == "center":
                    pdf.drawCentredString(x, cursor_y, line)
                elif layout["align"] == "right":
                    pdf.drawRightString(x, cursor_y, line)
                else:
                    pdf.drawString(x, cursor_y, line)
                cursor_y -= layout["leading"]
            cursor_y -= layout["after"]
    _draw_page_number(pdf, font_name, page_width, page_number)
    pdf.save()
    return buffer.getvalue()


def _pdf_block_layout(block: ScreenplayBlock, page_width: float) -> dict[str, float | str]:
    left = 72.0
    content_width = page_width - 144.0
    if block.kind == "scene_heading":
        return _layout(block.text.upper(), left, content_width, 10.5, 14.0, 8.0)
    if block.kind == "dialogue":
        text = f"{_speaker_label(block)}\n{block.text}"
        return _layout(text, 144.0, page_width - 288.0, 10.5, 14.0, 8.0)
    if block.kind == "parenthetical":
        text = f"（{block.text.strip('()')}）"
        return _layout(text, 166.0, page_width - 332.0, 9.5, 13.0, 5.0)
    if block.kind == "transition":
        return {
            **_layout(block.text.upper(), page_width - 72.0, content_width, 10.0, 14.0, 8.0),
            "align": "right",
        }
    return _layout(block.text, left, content_width, 10.5, 15.0, 8.0)


def _layout(
    text: str,
    x: float,
    width: float,
    font_size: float,
    leading: float,
    after: float,
) -> dict[str, float | str]:
    return {
        "text": text,
        "x": x,
        "width": width,
        "font_size": font_size,
        "leading": leading,
        "after": after,
        "align": "left",
    }


def _wrap_pdf_text(
    value: str,
    font_name: str,
    font_size: float,
    max_width: float,
    string_width,
) -> list[str]:
    lines: list[str] = []
    for paragraph in value.splitlines() or [""]:
        if not paragraph:
            lines.append("")
            continue
        current = ""
        current_width = 0.0
        for character in paragraph:
            width = string_width(character, font_name, font_size)
            if current and current_width + width > max_width:
                lines.append(current.rstrip())
                current = character.lstrip()
                current_width = string_width(current, font_name, font_size)
            else:
                current += character
                current_width += width
        lines.append(current.rstrip())
    return lines or [""]


def _draw_page_number(pdf, font_name: str, page_width: float, page_number: int) -> None:
    pdf.setFont(font_name, 8)
    pdf.drawRightString(page_width - 54, 30, str(page_number))


def _speaker_label(block: ScreenplayBlock) -> str:
    return (block.speaker_ref or "角色").replace("_", " ").replace("-", " ").upper()


__all__ = ["ScriptDeliveryFormat", "render_script_delivery", "safe_delivery_filename"]
