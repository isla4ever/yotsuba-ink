"""
Build SFT jsonl from normalized text teacher pairs.

Input line:
{"request": {...}, "response": {...}, "meta": {...}}

Output line:
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple


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


def _sanitize_text(text: str) -> str:
    return str(text or "").replace("\ufffd", "").strip()


def _extract_pair(obj: Dict[str, Any]) -> Tuple[str, str]:
    meta = obj.get("meta")
    if isinstance(meta, dict) and meta.get("status") not in (None, "ok"):
        return "", ""

    req = obj.get("request")
    resp = obj.get("response")
    if not isinstance(req, dict) or not isinstance(resp, dict):
        return "", ""

    messages = req.get("messages")
    if not isinstance(messages, list):
        return "", ""
    user = ""
    for m in messages:
        if isinstance(m, dict) and str(m.get("role", "")) == "user":
            user = str(m.get("content", "") or "")
            break
    if not user:
        return "", ""

    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", ""
    first = choices[0]
    if not isinstance(first, dict):
        return "", ""
    msg = first.get("message")
    if not isinstance(msg, dict):
        return "", ""
    assistant = str(msg.get("content", "") or "")
    return _sanitize_text(user), _sanitize_text(assistant)


def _quality_score(text: str) -> float:
    s = str(text or "").strip()
    if not s:
        return -1e9
    length = len(s)
    punct = len(re.findall(r"[，。！？；：、“”‘’]", s))
    dialogue = s.count("“") + s.count("”")
    # Penalize obvious template leakage.
    penalty = 0
    for bad in ("#### 角色", "#### 输入", "#### 输出", "输出要求", "只输出正文"):
        penalty += s.count(bad) * 30
    for bad in ("上一章承接摘要", "上一章的结尾片段", "上一章的结尾", "当前章细纲", "请根据以上信息"):
        penalty += s.count(bad) * 25
    for bad in ("本章", "上一章", "下一章", "本节", "这一章"):
        penalty += s.count(bad) * 5
    for bad in ("第一轮交锋", "第二轮交锋", "第三轮交锋", "备用方案", "风险边界", "行动优先级", "责任归属"):
        penalty += s.count(bad) * 18
    for bad in ("章末，钩子", "章末钩子", "当前章需要承接并推进", "###", "####", "- 场景：", "- 事件：", "- 对话要点："):
        penalty += s.count(bad) * 25
    if s.startswith("?"):
        penalty += 300
    return length * 1.0 + punct * 1.5 + dialogue * 1.2 - penalty


def main() -> None:
    parser = argparse.ArgumentParser(description="Build text SFT dataset from normalized teacher pairs")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", default="")
    parser.add_argument("--target-count", type=int, default=500)
    parser.add_argument("--min-assistant-chars", type=int, default=1000)
    parser.add_argument("--max-assistant-chars", type=int, default=3200)
    parser.add_argument("--drop-duplicate-user", action="store_true")
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []
    seen_user = set()
    seen_first_sentence = set()
    total = 0
    bad = 0
    short = 0
    for obj in _iter_jsonl(in_path):
        total += 1
        user, assistant = _extract_pair(obj)
        if not user or not assistant:
            bad += 1
            continue
        if len(assistant) < args.min_assistant_chars:
            short += 1
            continue
        if len(assistant) > args.max_assistant_chars:
            assistant = assistant[: args.max_assistant_chars].rstrip()
        first_sentence = re.split(r"(?<=[。！？!?；;])\s*", assistant, maxsplit=1)[0][:120]
        if first_sentence in seen_first_sentence:
            continue
        if first_sentence:
            seen_first_sentence.add(first_sentence)
        if args.drop_duplicate_user:
            key = user[:300]
            if key in seen_user:
                continue
            seen_user.add(key)
        rows.append(
            {
                "messages": [
                    {"role": "user", "content": user},
                    {"role": "assistant", "content": assistant},
                ],
                "_score": _quality_score(assistant),
                "_len": len(assistant),
            }
        )

    rows.sort(key=lambda x: x["_score"], reverse=True)
    if args.target_count > 0:
        rows = rows[: args.target_count]

    with out_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n")

    lengths = [x["_len"] for x in rows]
    report = {
        "input_total": total,
        "output_count": len(rows),
        "bad_format": bad,
        "too_short": short,
        "target_count": args.target_count,
        "avg_len": round(sum(lengths) / len(lengths), 2) if lengths else 0,
        "min_len": min(lengths) if lengths else 0,
        "max_len": max(lengths) if lengths else 0,
        "output": str(out_path),
    }
    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
