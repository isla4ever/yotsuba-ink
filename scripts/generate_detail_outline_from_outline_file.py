"""
Generate detail outlines for each volume from an existing outline content file.

Input outline file should contain content like:
[{'主要人物和他们的行为': {...}, '故事情节': {'开始':..., '发展':..., '高潮':..., '结局':...}}, ...]
"""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any, Dict, List

import requests


def _parse_outline_items(text: str) -> List[Dict[str, Any]]:
    s = str(text or "").strip()
    for parser in (ast.literal_eval, json.loads):
        try:
            obj = parser(s)
            break
        except Exception:
            obj = None
    if not isinstance(obj, list):
        return []
    return [x for x in obj if isinstance(x, dict)]


def _single_quote_literal(value: Any) -> str:
    if isinstance(value, str):
        s = (
            value.replace("\\", "\\\\")
            .replace("'", "\\'")
            .replace("\r", "\\r")
            .replace("\n", "\\n")
            .replace("\t", "\\t")
        )
        return f"'{s}'"
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_single_quote_literal(x) for x in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_single_quote_literal(str(k))}: {_single_quote_literal(v)}" for k, v in value.items()) + "}"
    return _single_quote_literal(str(value))


def _story_to_summary(story: Any) -> str:
    if isinstance(story, dict):
        parts = [str(story.get(k, "")).strip() for k in ("开始", "发展", "高潮", "结局")]
        return " ".join([p for p in parts if p]).strip()
    return str(story or "").strip()


def _build_prompt(
    *,
    novel_title: str,
    char_map: Dict[str, str],
    volume_summary: str,
    novel_intro: str,
    chapter_count: int,
) -> str:
    char_literal = _single_quote_literal(char_map)
    return (
        "\n#### 角色：\n"
        "你是一位资深小说章节策划助手。请把给定分卷梗概细化为可直接写作的章节细纲。\n\n"
        "#### 输出格式（必须严格遵守）：\n"
        "只输出一个列表字符串，列表每项为：\n"
        "{'章节标题': str, '细纲内容': str}\n"
        f"共输出 {chapter_count} 项，按列表顺序表示章节先后。\n\n"
        f"**小说标题**：\n{novel_title}\n\n"
        f"**人物信息**：\n{char_literal}\n\n"
        f"**小说部分内容的梗概**：\n{volume_summary}\n\n"
        f"**小说简介**：\n{novel_intro}\n\n"
        f"**章节划分**：\n一共 {chapter_count} 章\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate detail outlines for each volume from outline file")
    parser.add_argument("--url", default="http://127.0.0.1:54862/v1/chat/completions")
    parser.add_argument("--model", default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--outline-content-file", required=True)
    parser.add_argument("--novel-title", default="未命名小说")
    parser.add_argument("--novel-intro", default="")
    parser.add_argument("--chapter-counts", default="3,3,3,3", help="Comma-separated chapter counts per volume")
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--output", default="logs/_detail_outline_from_outline_all_volumes.json")
    args = parser.parse_args()

    outline_path = Path(args.outline_content_file)
    raw = outline_path.read_text(encoding="utf-8")
    volumes = _parse_outline_items(raw)
    if not volumes:
        raise SystemExit(f"cannot parse outline items from: {outline_path}")

    count_tokens = [x.strip() for x in args.chapter_counts.split(",") if x.strip()]
    chapter_counts: List[int] = []
    for tok in count_tokens:
        try:
            chapter_counts.append(max(1, min(30, int(tok))))
        except Exception:
            chapter_counts.append(3)
    if not chapter_counts:
        chapter_counts = [3]

    out_rows = []
    for i, vol in enumerate(volumes):
        char_map = vol.get("主要人物和他们的行为") if isinstance(vol.get("主要人物和他们的行为"), dict) else {}
        if not char_map:
            char_map = vol.get("主要人物") if isinstance(vol.get("主要人物"), dict) else {}
        volume_summary = _story_to_summary(vol.get("故事情节") or vol.get("故事") or vol.get("内容"))
        chapter_count = chapter_counts[i] if i < len(chapter_counts) else chapter_counts[-1]
        prompt = _build_prompt(
            novel_title=args.novel_title,
            char_map=char_map,
            volume_summary=volume_summary,
            novel_intro=args.novel_intro or volume_summary,
            chapter_count=chapter_count,
        )
        payload = {
            "model": args.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "max_tokens": 2600,
            "temperature": 0.72,
            "top_p": 0.88,
        }
        resp = requests.post(args.url, json=payload, timeout=args.timeout)
        resp.raise_for_status()
        obj = resp.json()
        content = str(obj.get("choices", [{}])[0].get("message", {}).get("content", ""))
        out_rows.append(
            {
                "volume_index": i + 1,
                "chapter_count": chapter_count,
                "request": payload,
                "response": obj,
                "content": content,
            }
        )
        print(f"[volume {i + 1}] status={resp.status_code} content_len={len(content)}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()
