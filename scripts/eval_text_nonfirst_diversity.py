from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def _iter_jsonl(path: Path) -> Iterable[dict]:
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


def _extract_assistant(obj: dict) -> str:
    if isinstance(obj.get("messages"), list):
        for msg in obj["messages"]:
            if isinstance(msg, dict) and msg.get("role") == "assistant":
                return str(msg.get("content", "") or "").strip()
    resp = obj.get("response")
    if isinstance(resp, dict):
        choices = resp.get("choices")
        if isinstance(choices, list) and choices:
            msg = choices[0].get("message")
            if isinstance(msg, dict):
                return str(msg.get("content", "") or "").strip()
    return ""


def _first_sentence(text: str) -> str:
    parts = re.split(r"(?<=[。！？!?])", text.strip(), maxsplit=1)
    return parts[0].strip()[:80] if parts else ""


def _char_ngrams(text: str, n: int = 4) -> List[str]:
    s = re.sub(r"\s+", "", text)
    if len(s) < n:
        return []
    return [s[i : i + n] for i in range(len(s) - n + 1)]


def main() -> None:
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    parser = argparse.ArgumentParser(description="Evaluate non-first chapter dataset diversity")
    parser.add_argument("--input", required=True)
    parser.add_argument("--report", default="")
    args = parser.parse_args()

    rows: List[str] = []
    for obj in _iter_jsonl(Path(args.input)):
        text = _extract_assistant(obj)
        if text:
            rows.append(text)

    first_sent_counter = Counter()
    line_counter = Counter()
    ngram_counter = Counter()
    meta_hits = Counter()
    template_terms = ("本章", "上一章", "下一章", "这一章", "请根据以上信息", "当前章细纲")

    for text in rows:
        first = _first_sentence(text)
        if first:
            first_sent_counter[first] += 1
        for line in [x.strip() for x in text.splitlines() if len(x.strip()) >= 10]:
            line_counter[line[:120]] += 1
        for gram in _char_ngrams(text, n=4):
            ngram_counter[gram] += 1
        for term in template_terms:
            if term in text:
                meta_hits[term] += 1

    report: Dict[str, object] = {
        "sample_count": len(rows),
        "avg_chars": round(sum(len(x) for x in rows) / len(rows), 2) if rows else 0,
        "duplicate_first_sentence_top10": first_sent_counter.most_common(10),
        "duplicate_line_top10": line_counter.most_common(10),
        "high_freq_4gram_top20": [(k, v) for k, v in ngram_counter.most_common(20) if v >= 3],
        "meta_phrase_hits": dict(meta_hits),
    }

    if args.report:
        rp = Path(args.report)
        rp.parent.mkdir(parents=True, exist_ok=True)
        rp.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
