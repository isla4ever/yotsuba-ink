from __future__ import annotations

import html
import re
from pathlib import Path


TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".html", ".htm", ".epub"}
STRUCTURED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".xlsx"}


def parse_document_bytes(content: bytes, filename: str, content_type: str = "") -> tuple[str, str, str]:
    """Return text, parser name, and a capability note.

    Docling is the intended production parser for rich formats. The local demo
    path keeps text-like uploads working without forcing heavyweight optional
    dependencies into every development install.
    """

    suffix = Path(filename).suffix.lower()
    if suffix in TEXT_EXTENSIONS or content_type.startswith("text/"):
        raw = content.decode("utf-8", errors="ignore")
        if suffix in {".html", ".htm"} or "html" in content_type:
            raw = html_to_text(raw)
        return raw.strip(), "plain-text", ""

    if suffix in STRUCTURED_EXTENSIONS:
        parsed = try_docling_parse(content, filename)
        if parsed:
            return parsed, "docling", ""
        note = "当前环境未安装 Docling，PDF/DOCX/PPTX/XLSX 将等待增强解析；TXT/MD/HTML 可直接入库。"
        fallback = content.decode("utf-8", errors="ignore").strip()
        return fallback, "plain-text-fallback", note

    fallback = content.decode("utf-8", errors="ignore").strip()
    return fallback, "plain-text", ""


def html_to_text(raw: str) -> str:
    text = re.sub(r"(?is)<(script|style).*?>.*?</\1>", " ", raw)
    text = re.sub(r"(?is)<br\s*/?>", "\n", text)
    text = re.sub(r"(?is)</(p|div|h[1-6]|li)>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    return html.unescape(re.sub(r"[ \t]+", " ", text))


def try_docling_parse(content: bytes, filename: str) -> str:
    try:
        from docling.document_converter import DocumentConverter  # type: ignore
    except Exception:
        return ""

    # Keep optional Docling support isolated. Some versions require filesystem
    # paths, so this branch can be expanded without touching the API contract.
    try:
        import tempfile

        suffix = Path(filename).suffix or ".bin"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=True) as tmp:
            tmp.write(content)
            tmp.flush()
            result = DocumentConverter().convert(tmp.name)
            document = getattr(result, "document", None)
            if document and hasattr(document, "export_to_markdown"):
                return str(document.export_to_markdown()).strip()
    except Exception:
        return ""
    return ""
