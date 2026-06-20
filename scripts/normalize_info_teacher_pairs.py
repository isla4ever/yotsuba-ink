"""
Normalize info_recommend teacher pairs to fixed content schema.

Input line format:
{"request": {...}, "response": {...}, ...}

Output line format:
same object, with response.choices[0].message.content normalized to:
**人物信息** / **故事背景** / **简介** + <|im_end|>
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.openai_compat_server import _normalize_info_recommend_text


def _normalize_line(obj: Dict) -> Dict:
    req = obj.get("request")
    resp = obj.get("response")
    if not isinstance(req, dict) or not isinstance(resp, dict):
        return obj

    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return obj
    first = choices[0]
    if not isinstance(first, dict):
        return obj
    msg = first.get("message")
    if not isinstance(msg, dict):
        return obj

    raw = str(msg.get("content", "") or "")
    normalized = _normalize_info_recommend_text(raw, req.get("messages", []))
    normalized = re.sub(r"\n[ \t]{8,}", "\n", normalized).strip()
    msg["content"] = normalized
    return obj


def main() -> None:
    parser = argparse.ArgumentParser(description="Normalize info_recommend teacher pair responses")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    normalized = 0
    with in_path.open("r", encoding="utf-8") as fin, out_path.open("w", encoding="utf-8") as fout:
        for line in fin:
            s = line.strip()
            if not s:
                continue
            total += 1
            try:
                obj = json.loads(s)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                before = json.dumps(obj, ensure_ascii=False, sort_keys=True)
                obj = _normalize_line(obj)
                after = json.dumps(obj, ensure_ascii=False, sort_keys=True)
                if before != after:
                    normalized += 1
                fout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    print(f"total={total}")
    print(f"normalized={normalized}")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()
