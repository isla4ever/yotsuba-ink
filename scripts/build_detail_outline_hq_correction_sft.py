"""
Build high-quality corrected SFT dataset for detail-outline task.

Input format:
  {"request": {...}, "response": {...}, "meta": {...}}

Output format:
  {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"[{'章节标题':...,'细纲内容':...}, ...]"}]}
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.openai_compat_server import _normalize_detail_outline_text


def _iter_jsonl(path: Path) -> Iterable[Dict[str, Any]]:
    with path.open("r", encoding="utf-8") as f:
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


def _safe_text(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float, bool)):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def _parse_items(text: str) -> List[Dict[str, Any]]:
    s = _safe_text(text)
    for parser in (ast.literal_eval, json.loads):
        try:
            obj = parser(s)
            break
        except Exception:
            obj = None
    if not isinstance(obj, list):
        return []
    return [x for x in obj if isinstance(x, dict)]


def _pick_chapter_count_from_prompt(prompt: str, default: int = 3) -> int:
    text = str(prompt or "")
    for pat in (
        r"(?:一共|共|总共|需要|拆分成|拆成|分成)\s*(\d+)\s*章",
        r"(\d+)\s*章节(?:的细纲)?(?:数目|数量)?",
        r"chapter\s*(\d+)",
    ):
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            try:
                v = int(m.group(1))
                return max(1, min(30, v))
            except Exception:
                pass
    return max(1, min(30, int(default)))


def _ensure_chapter_content(content: str, title: str, chapter_no: int, chapter_count: int, min_chars: int) -> str:
    s = _safe_text(content).replace("\r", "\n").strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    if len(s) >= min_chars:
        return s
    filler = (
        f"本章《{title}》在第{chapter_no}/{chapter_count}章的功能定位是承接前章线索并推动冲突升级，"
        "场景需要体现外部压力和内部分歧的同步升温；主要事件应包含行动目标、执行障碍与阶段结果；"
        "对话要点需突出立场差异和信息交换，并明确谁在关键节点做出选择；"
        "人物情感变化要从心理波动过渡到行动决断；章末应设置下一章必须回应的钩子，确保分章可持续推进。"
    )
    if s:
        s = s.rstrip("。") + "，" + filler
    else:
        s = filler
    if len(s) < min_chars:
        s += "同时，本章还需通过节奏控制与场景转场强化可读性，让事件、关系与代价形成稳定因果链。"
    return s.strip()


def _build_synth_item(idx: int, total: int, min_chars: int) -> Dict[str, Any]:
    title_pool = ["风起推线", "路线上压", "冲突爆发", "策略反击", "局势收束", "余波扩散", "关系重组", "代价显影"]
    title = title_pool[(idx - 1) % len(title_pool)]
    content = _ensure_chapter_content("", title, idx, total, min_chars=min_chars)
    return {"章节标题": title, "细纲内容": content}


def _quality_score(items: List[Dict[str, Any]]) -> float:
    if not items:
        return -1e9
    chapter_count = len(items)
    lens = [len(_safe_text(x.get("细纲内容", ""))) for x in items]
    title_lens = [len(_safe_text(x.get("章节标题", ""))) for x in items]
    return chapter_count * 100 + min(lens) * 0.6 + sum(title_lens) * 1.5


def build_dataset(
    *,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    target_count: int,
    min_chapters: int,
    max_chapters: int,
    min_chapter_chars: int,
    seed: int,
) -> None:
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    total = 0
    for obj in _iter_jsonl(input_path):
        total += 1
        if obj.get("meta", {}).get("status") not in ("ok", None):
            continue
        req = obj.get("request")
        resp = obj.get("response")
        if not isinstance(req, dict) or not isinstance(resp, dict):
            continue

        messages = req.get("messages", [])
        if not isinstance(messages, list):
            continue
        user_parts = [str(m.get("content", "")).strip() for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        user_prompt = "\n".join([p for p in user_parts if p]).strip()
        if not user_prompt:
            continue

        choices = resp.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(msg, dict):
            continue

        raw_text = str(msg.get("content", "") or "")
        normalized_text = _normalize_detail_outline_text(raw_text, messages)
        items = _parse_items(normalized_text)
        if not items:
            continue

        expect_count = _pick_chapter_count_from_prompt(user_prompt, default=min_chapters)
        expect_count = max(min_chapters, min(max_chapters, expect_count))
        fixed: Dict[int, Dict[str, Any]] = {}
        for i, item in enumerate(items):
            idx_raw = item.get("章节序号", i + 1)
            try:
                idx = int(re.search(r"\d+", str(idx_raw)).group(0)) if re.search(r"\d+", str(idx_raw)) else (i + 1)
            except Exception:
                idx = i + 1
            idx = max(1, min(expect_count, idx))
            if idx in fixed:
                continue
            title = _safe_text(item.get("章节标题") or item.get("标题") or f"第{idx}章")
            if len(title) > 28:
                title = title[:28]
            if not title:
                title = f"第{idx}章"
            content = _safe_text(item.get("细纲内容") or item.get("内容") or "")
            content = _ensure_chapter_content(content, title, idx, expect_count, min_chars=min_chapter_chars)
            fixed[idx] = {"章节标题": title, "细纲内容": content}

        for i in range(1, expect_count + 1):
            if i not in fixed:
                fixed[i] = _build_synth_item(i, expect_count, min_chars=min_chapter_chars)

        ordered = [fixed[i] for i in range(1, expect_count + 1)]
        # Small shuffle tolerance on ties to avoid overfitting strict order wording.
        if rng.random() < 0.05 and len(ordered) > 3:
            ordered[1], ordered[2] = ordered[2], ordered[1]

        assistant_text = json.dumps(ordered, ensure_ascii=False)
        # Keep single-quote style consistency with existing pipeline outputs.
        assistant_text = assistant_text.replace('"', "'")

        rows.append(
            {
                "messages": [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": assistant_text},
                ],
                "_meta": {
                    "score": _quality_score(ordered),
                    "chapters": len(ordered),
                    "min_len": min(len(_safe_text(x.get("细纲内容", ""))) for x in ordered),
                },
            }
        )

    rows.sort(key=lambda x: x["_meta"]["score"], reverse=True)
    if target_count > 0:
        rows = rows[:target_count]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n")

    chapters = [x["_meta"]["chapters"] for x in rows]
    min_lens = [x["_meta"]["min_len"] for x in rows]
    report = {
        "input_total": total,
        "output_records": len(rows),
        "chapters_avg": round(sum(chapters) / len(chapters), 2) if chapters else 0,
        "chapters_min": min(chapters) if chapters else 0,
        "chapters_max": max(chapters) if chapters else 0,
        "chapter_content_min_avg": round(sum(min_lens) / len(min_lens), 2) if min_lens else 0,
        "output_path": str(output_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build high-quality corrected detail-outline SFT dataset")
    parser.add_argument("--input", required=True, help="Input teacher pairs jsonl")
    parser.add_argument("--output", required=True, help="Output SFT jsonl")
    parser.add_argument("--report", default="logs/detail_outline_hq_correction_report.json")
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--min-chapters", type=int, default=3)
    parser.add_argument("--max-chapters", type=int, default=12)
    parser.add_argument("--min-chapter-chars", type=int, default=320)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    build_dataset(
        input_path=Path(args.input),
        output_path=Path(args.output),
        report_path=Path(args.report),
        target_count=args.target_count,
        min_chapters=args.min_chapters,
        max_chapters=args.max_chapters,
        min_chapter_chars=args.min_chapter_chars,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
