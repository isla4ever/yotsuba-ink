"""
Normalize text teacher pairs (first/non-first chapter).

Input line format:
{"request": {...}, "response": {...}, "meta": {...}}

Output line format:
same structure, with response.choices[0].message.content normalized.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple


_SPECIAL_TOKENS = ("<|im_end|>", "<|im_start|>", "<|endoftext|>", "</s>")
_DROP_PHRASES = (
    "第一轮交锋",
    "第二轮交锋",
    "第三轮交锋",
    "责任归属",
    "行动优先级",
    "风险边界",
    "章末，钩子",
    "章末钩子",
    "当前章需要承接并推进",
    "请根据以上信息",
)


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            try:
                obj = json.loads(s)
            except Exception:
                continue
            if isinstance(obj, dict):
                yield obj


def _sanitize_content(text: str) -> str:
    s = str(text or "")
    s = s.replace("\r", "\n")
    s = s.replace("\ufffd", "")
    s = s.replace("\\n", "\n").replace("\\r", "\n").replace("\\t", " ")
    s = s.replace("\\", "")
    for tok in _SPECIAL_TOKENS:
        s = s.replace(tok, "")
    s = re.sub(r"<think>[\s\S]*?</think>\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\s*```[a-zA-Z0-9_-]*\s*", "", s)
    s = re.sub(r"\s*```\s*$", "", s)
    # Remove obvious role/prompt leakage headers.
    s = re.sub(r"(?m)^\s*(####\s*角色|####\s*输入|####\s*输出|输出要求)\s*[:：]?.*$", "", s)
    s = re.sub(r"(?m)^\s*\*\*(小说标题|分类|小说简介|本卷梗概|主要人物和行为|小说章节信息|上一章的结尾|第\d+章细纲|第1章细纲)\*\*\s*[:：]?.*$", "", s)
    s = re.sub(r"(?m)^\s*(上一章承接摘要|上一章的结尾片段|上一章的结尾|当前章细纲|第\d+章细纲)\s*[:：].*$", "", s)
    s = re.sub(r"(?m)^\s*[-–—]?\s*第\d+章[:：]?.*$", "", s)
    s = re.sub(r"(?m)^\s*[-–—]?\s*(场景|事件|对话要点|情感变化)\s*[:：].*$", "", s)
    s = re.sub(r"(?m)^\s*#+\s*[一二三四五六七八九十]+\s*$", "", s)
    s = re.sub(r"(?m)^\s*#+\s*.*$", "", s)
    s = re.sub(r"(?m)^\s*(第一轮交锋|第二轮交锋|第三轮交锋)[^\n]*$", "", s)
    s = re.sub(r"(?m)^\s*章末[，,：:].*$", "", s)
    # Collapse blank lines.
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    return s


def _too_dirty(text: str) -> bool:
    s = str(text or "").strip()
    if not s:
        return True
    if s.startswith("?"):
        return True
    bad_hits = sum(s.count(x) for x in _DROP_PHRASES)
    if bad_hits >= 2:
        return True
    if "上一章" in s or "当前章" in s or "本章" in s:
        return True
    if "- 场景：" in s or "- 事件：" in s or "- 对话要点：" in s:
        return True
    if "请根据以上信息" in s:
        return True
    return False


def _extract_content(obj: Dict[str, Any]) -> Tuple[str, bool]:
    resp = obj.get("response")
    if not isinstance(resp, dict):
        return "", False
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", False
    first = choices[0]
    if not isinstance(first, dict):
        return "", False
    msg = first.get("message")
    if not isinstance(msg, dict):
        return "", False
    return str(msg.get("content", "") or ""), True


def _set_content(obj: Dict[str, Any], content: str) -> bool:
    resp = obj.get("response")
    if not isinstance(resp, dict):
        return False
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return False
    first = choices[0]
    if not isinstance(first, dict):
        return False
    msg = first.get("message")
    if not isinstance(msg, dict):
        return False
    msg["content"] = content
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize first/non-first text teacher pairs")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--min-chars", type=int, default=1000)
    parser.add_argument("--max-chars", type=int, default=3200)
    parser.add_argument("--drop-too-short", action="store_true")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    kept = 0
    dropped = 0
    bad_format = 0
    too_short = 0
    dirty = 0
    replacement_char_rows = 0
    replacement_char_count = 0
    lengths = []

    with out_path.open("w", encoding="utf-8") as fout:
        for obj in _iter_jsonl(in_path):
            total += 1
            raw, ok = _extract_content(obj)
            if not ok:
                bad_format += 1
                dropped += 1
                continue

            replacement_char_rows += int("\ufffd" in raw)
            replacement_char_count += raw.count("\ufffd")
            cleaned = _sanitize_content(raw)
            if len(cleaned) > args.max_chars:
                cleaned = cleaned[: args.max_chars].rstrip()
            if _too_dirty(cleaned):
                dirty += 1
                dropped += 1
                continue
            if len(cleaned) < args.min_chars:
                too_short += 1
                if args.drop_too_short:
                    dropped += 1
                    continue

            if not _set_content(obj, cleaned):
                bad_format += 1
                dropped += 1
                continue

            fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
            kept += 1
            lengths.append(len(cleaned))

    report = {
        "input_total": total,
        "kept": kept,
        "dropped": dropped,
        "bad_format": bad_format,
        "too_short": too_short,
        "dirty": dirty,
        "replacement_char_rows": replacement_char_rows,
        "replacement_char_count": replacement_char_count,
        "min_chars_cfg": args.min_chars,
        "max_chars_cfg": args.max_chars,
        "avg_chars": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "min_chars_actual": min(lengths) if lengths else 0,
        "max_chars_actual": max(lengths) if lengths else 0,
        "output": str(out_path),
    }
    if args.report:
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
