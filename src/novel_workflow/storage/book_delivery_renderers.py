"""Deterministic Markdown, EPUB and DOCX renderers for Phase 32 books."""

from __future__ import annotations

import base64
import hashlib
import html
import io
import zipfile
from collections.abc import Sequence
from typing import Literal

from novel_workflow.output_contracts.phase32_delivery_artifacts import (
    BookDeliveryArtifact,
    ChapterArtifact,
    ShortProseUnitArtifact,
)
from novel_workflow.storage.cover_asset_store import CoverAssetRecord
from novel_workflow.storage.script_delivery_renderers import safe_delivery_filename


BookDeliveryFormat = Literal["epub", "docx", "markdown"]
BookTextArtifact = ShortProseUnitArtifact | ChapterArtifact


def render_book_delivery(
    artifact: BookDeliveryArtifact,
    chapters: Sequence[BookTextArtifact],
    cover_asset: tuple[CoverAssetRecord, bytes],
    delivery_format: BookDeliveryFormat,
) -> tuple[bytes, str, str]:
    stem = safe_delivery_filename(artifact.title)
    if delivery_format == "markdown":
        return (
            _render_markdown(artifact, chapters, cover_asset),
            f"{stem}.md",
            "text/markdown; charset=utf-8",
        )
    if delivery_format == "epub":
        return _render_epub(artifact, chapters, cover_asset), f"{stem}.epub", "application/epub+zip"
    if delivery_format == "docx":
        return (
            _render_docx(artifact, chapters, cover_asset),
            f"{stem}.docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    raise ValueError(f"Unsupported book delivery format: {delivery_format}")


def _render_markdown(
    artifact: BookDeliveryArtifact,
    chapters: Sequence[BookTextArtifact],
    cover_asset: tuple[CoverAssetRecord, bytes],
) -> bytes:
    cover, cover_bytes = cover_asset
    encoded = base64.b64encode(cover_bytes).decode("ascii")
    sections = [
        f"# {artifact.title}",
        f"![{artifact.title} 封面](data:{cover.mime_type};base64,{encoded})",
    ]
    if artifact.author:
        sections.append(f"**作者：** {artifact.author}")
    if artifact.version_note:
        sections.append(f"**版本：** {artifact.version_note}")
    for ordinal, chapter in enumerate(chapters, start=1):
        sections.append(f"## 第 {ordinal} 章 {chapter.title}\n\n{chapter.content.strip()}")
    return ("\n\n---\n\n".join(sections).rstrip() + "\n").encode("utf-8")


def _render_epub(
    artifact: BookDeliveryArtifact,
    chapters: Sequence[BookTextArtifact],
    cover_asset: tuple[CoverAssetRecord, bytes],
) -> bytes:
    cover, cover_bytes = cover_asset
    identifier = hashlib.sha256(
        (artifact.title + "\0" + "\0".join(artifact.chapter_version_refs)).encode("utf-8")
    ).hexdigest()
    chapter_names = [f"chapter-{ordinal:04d}.xhtml" for ordinal in range(1, len(chapters) + 1)]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED) as archive:
        _write_zip_member(archive, "mimetype", b"application/epub+zip")
        _write_zip_member(
            archive,
            "META-INF/container.xml",
            _xml(
                '<?xml version="1.0" encoding="UTF-8"?>'
                '<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">'
                '<rootfiles><rootfile full-path="OEBPS/content.opf" '
                'media-type="application/oebps-package+xml"/></rootfiles></container>'
            ),
        )
        _write_zip_member(archive, "OEBPS/styles.css", _epub_styles())
        _write_zip_member(
            archive,
            f"OEBPS/cover.{cover.extension}",
            cover_bytes,
        )
        _write_zip_member(
            archive,
            "OEBPS/cover.xhtml",
            _xhtml(
                artifact.title,
                f'<section class="cover"><img src="cover.{cover.extension}" alt="{html.escape(artifact.title)} 封面"/></section>',
            ),
        )
        for name, chapter in zip(chapter_names, chapters, strict=True):
            paragraphs = "".join(
                f"<p>{html.escape(paragraph)}</p>"
                for paragraph in _paragraphs(chapter.content)
            )
            body = f"<h1>{html.escape(chapter.title)}</h1>{paragraphs}"
            _write_zip_member(archive, f"OEBPS/{name}", _xhtml(chapter.title, body))
        _write_zip_member(
            archive,
            "OEBPS/nav.xhtml",
            _epub_navigation(artifact, chapters, chapter_names),
        )
        _write_zip_member(
            archive,
            "OEBPS/content.opf",
            _epub_package(artifact, identifier, cover, chapter_names),
        )
    return buffer.getvalue()


def _epub_package(
    artifact: BookDeliveryArtifact,
    identifier: str,
    cover: CoverAssetRecord,
    chapter_names: Sequence[str],
) -> bytes:
    chapter_manifest = "".join(
        f'<item id="chapter-{index}" href="{name}" media-type="application/xhtml+xml"/>'
        for index, name in enumerate(chapter_names, start=1)
    )
    chapter_spine = "".join(
        f'<itemref idref="chapter-{index}"/>'
        for index in range(1, len(chapter_names) + 1)
    )
    author = html.escape(artifact.author or "Yotsuba Ink")
    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="book-id">'
        '<metadata xmlns:dc="http://purl.org/dc/elements/1.1/">'
        f'<dc:identifier id="book-id">urn:sha256:{identifier}</dc:identifier>'
        f'<dc:title>{html.escape(artifact.title)}</dc:title><dc:language>zh-CN</dc:language>'
        f'<dc:creator>{author}</dc:creator><meta property="dcterms:modified">1980-01-01T00:00:00Z</meta>'
        '</metadata><manifest><item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>'
        '<item id="style" href="styles.css" media-type="text/css"/>'
        '<item id="cover-page" href="cover.xhtml" media-type="application/xhtml+xml"/>'
        f'<item id="cover-image" href="cover.{cover.extension}" media-type="{cover.mime_type}" properties="cover-image"/>'
        f'{chapter_manifest}</manifest><spine><itemref idref="cover-page"/>{chapter_spine}</spine></package>'
    )


def _epub_navigation(
    artifact: BookDeliveryArtifact,
    chapters: Sequence[BookTextArtifact],
    chapter_names: Sequence[str],
) -> bytes:
    items = ['<li><a href="cover.xhtml">封面</a></li>']
    items.extend(
        f'<li><a href="{name}">{html.escape(chapter.title)}</a></li>'
        for name, chapter in zip(chapter_names, chapters, strict=True)
    )
    return _xhtml(
        f"{artifact.title} - 目录",
        '<nav epub:type="toc" xmlns:epub="http://www.idpf.org/2007/ops"><h1>目录</h1><ol>'
        + "".join(items)
        + "</ol></nav>",
    )


def _xhtml(title: str, body: str) -> bytes:
    return _xml(
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<html xmlns="http://www.w3.org/1999/xhtml" lang="zh-CN"><head>'
        f'<title>{html.escape(title)}</title><link rel="stylesheet" type="text/css" href="styles.css"/>'
        f'</head><body>{body}</body></html>'
    )


def _epub_styles() -> bytes:
    return (
        "body{font-family:serif;line-height:1.75;margin:6%;}"
        "h1{text-align:center;font-size:1.45em;margin:1.5em 0;}"
        "p{text-indent:2em;margin:.55em 0;}"
        ".cover{display:flex;align-items:center;justify-content:center;height:90vh;}"
        ".cover img{display:block;max-width:100%;max-height:88vh;margin:auto;}"
    ).encode("utf-8")


def _render_docx(
    artifact: BookDeliveryArtifact,
    chapters: Sequence[BookTextArtifact],
    cover_asset: tuple[CoverAssetRecord, bytes],
) -> bytes:
    cover, cover_bytes = cover_asset
    image_width = 4_114_800
    image_height = int(image_width * cover.height / cover.width)
    max_height = 6_400_800
    if image_height > max_height:
        image_width = int(image_width * max_height / image_height)
        image_height = max_height
    body = [_docx_image_paragraph(image_width, image_height), _docx_title(artifact)]
    for index, chapter in enumerate(chapters, start=1):
        body.append(_docx_page_break())
        body.append(_docx_heading(f"第 {index} 章 {chapter.title}"))
        body.extend(_docx_paragraph(paragraph) for paragraph in _paragraphs(chapter.content))
    document = _xml(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
        'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        f'<w:body>{"".join(body)}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
        '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440"/></w:sectPr></w:body></w:document>'
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_STORED) as archive:
        members = {
            "[Content_Types].xml": _docx_content_types(cover.extension, cover.mime_type),
            "_rels/.rels": _xml(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
                '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
                '</Relationships>'
            ),
            "docProps/core.xml": _docx_core(artifact),
            "docProps/app.xml": _docx_app(),
            "word/document.xml": document,
            "word/styles.xml": _docx_styles(),
            "word/_rels/document.xml.rels": _xml(
                '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                f'<Relationship Id="rIdCover" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/cover.{cover.extension}"/>'
                '</Relationships>'
            ),
            f"word/media/cover.{cover.extension}": cover_bytes,
        }
        for name, content in members.items():
            _write_zip_member(archive, name, content)
    return buffer.getvalue()


def _docx_content_types(extension: str, mime_type: str) -> bytes:
    return _xml(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        f'<Default Extension="{extension}" ContentType="{mime_type}"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '</Types>'
    )


def _docx_core(artifact: BookDeliveryArtifact) -> bytes:
    return _xml(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
        f'<dc:title>{html.escape(artifact.title)}</dc:title><dc:creator>{html.escape(artifact.author or "Yotsuba Ink")}</dc:creator>'
        '<dcterms:created xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:created>'
        '<dcterms:modified xsi:type="dcterms:W3CDTF">1980-01-01T00:00:00Z</dcterms:modified>'
        '</cp:coreProperties>'
    )


def _docx_app() -> bytes:
    return _xml(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties" '
        'xmlns:vt="http://schemas.openxmlformats.org/officeDocument/2006/docPropsVTypes">'
        '<Application>Yotsuba Ink</Application></Properties>'
    )


def _docx_styles() -> bytes:
    return _xml(
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/>'
        '<w:rPr><w:rFonts w:ascii="Songti SC" w:eastAsia="宋体"/><w:sz w:val="24"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Title"><w:name w:val="Title"/>'
        '<w:pPr><w:jc w:val="center"/><w:spacing w:before="360" w:after="240"/></w:pPr>'
        '<w:rPr><w:b/><w:sz w:val="40"/></w:rPr></w:style>'
        '<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/>'
        '<w:pPr><w:spacing w:after="240"/></w:pPr><w:rPr><w:b/><w:sz w:val="32"/></w:rPr></w:style>'
        '</w:styles>'
    )


def _docx_image_paragraph(width: int, height: int) -> str:
    return (
        '<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing><wp:inline>'
        f'<wp:extent cx="{width}" cy="{height}"/><wp:docPr id="1" name="Cover"/>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
        '<pic:pic><pic:nvPicPr><pic:cNvPr id="0" name="Cover"/><pic:cNvPicPr/></pic:nvPicPr>'
        '<pic:blipFill><a:blip r:embed="rIdCover"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
        '<pic:spPr><a:xfrm><a:off x="0" y="0"/>'
        f'<a:ext cx="{width}" cy="{height}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>'
        '</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'
    )


def _docx_title(artifact: BookDeliveryArtifact) -> str:
    lines = [f'<w:p><w:pPr><w:pStyle w:val="Title"/></w:pPr><w:r><w:t>{html.escape(artifact.title)}</w:t></w:r></w:p>']
    if artifact.author:
        lines.append(_docx_centered(f"作者：{artifact.author}"))
    if artifact.version_note:
        lines.append(_docx_centered(artifact.version_note))
    return "".join(lines)


def _docx_centered(value: str) -> str:
    return f'<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>{html.escape(value)}</w:t></w:r></w:p>'


def _docx_page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def _docx_heading(value: str) -> str:
    return f'<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>{html.escape(value)}</w:t></w:r></w:p>'


def _docx_paragraph(value: str) -> str:
    escaped = html.escape(value)
    return (
        '<w:p><w:pPr><w:ind w:firstLineChars="200"/><w:spacing w:line="420" w:lineRule="auto"/></w:pPr>'
        f'<w:r><w:t xml:space="preserve">{escaped}</w:t></w:r></w:p>'
    )


def _paragraphs(content: str) -> list[str]:
    values = [value.strip() for value in content.replace("\r\n", "\n").split("\n\n")]
    return [value.replace("\n", " ") for value in values if value] or [""]


def _xml(value: str) -> bytes:
    return value.encode("utf-8")


def _write_zip_member(archive: zipfile.ZipFile, name: str, content: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_STORED
    info.external_attr = 0o100644 << 16
    archive.writestr(info, content)


__all__ = ["BookDeliveryFormat", "render_book_delivery"]
