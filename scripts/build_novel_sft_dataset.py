"""
Build SFT JSONL from teacher request/response logs.

Input line formats supported:
1) {"request": {...}, "response": {...}}
2) {"request_body": "{...json...}", "response_body": "{...json...}"}
3) {"request": {...}, "stream_response": "data: {...}\\n\\ndata: [DONE]"}
4) {"request": {...}, "stream_response_lines": ["data: {...}", "data: [DONE]"]}

Output line format:
{"messages": [{"role":"user","content":"..."}, ..., {"role":"assistant","content":"..."}]}
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


def _parse_json_maybe(value):
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return None
    return None


def _normalize_content(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        out = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                out.append(str(item.get("text", "")))
            else:
                out.append(_normalize_content(item))
        return "".join(out)
    if isinstance(content, dict):
        for key in ("text", "value", "content"):
            if key in content:
                return _normalize_content(content[key])
        return json.dumps(content, ensure_ascii=False)
    return str(content)


def _get_request_obj(entry: Dict) -> Optional[Dict]:
    for key in ("request", "request_obj", "request_json", "payload", "req", "request_body"):
        if key not in entry:
            continue
        obj = _parse_json_maybe(entry[key])
        if isinstance(obj, dict):
            return obj
    return None


def _extract_assistant_from_non_stream(resp_obj: Dict) -> str:
    try:
        choices = resp_obj.get("choices", [])
        if not choices:
            return ""
        msg = choices[0].get("message", {})
        content = _normalize_content(msg.get("content", ""))
        return content.replace("<|im_end|>", "").strip()
    except Exception:
        return ""


def _iter_sse_data_lines(raw_text: str) -> Iterable[str]:
    for line in raw_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("data:"):
            yield s[5:].strip()
        elif s.startswith("{") and s.endswith("}"):
            # tolerate raw JSON line without "data:" prefix
            yield s


def _extract_assistant_from_stream_text(raw_text: str) -> str:
    chunks: List[str] = []
    for data in _iter_sse_data_lines(raw_text):
        if data == "[DONE]":
            continue
        try:
            obj = json.loads(data)
        except json.JSONDecodeError:
            continue

        choices = obj.get("choices", [])
        if not choices:
            continue
        first = choices[0]
        delta = first.get("delta")
        if isinstance(delta, dict):
            piece = _normalize_content(delta.get("content", ""))
            if piece:
                chunks.append(piece)
            continue
        msg = first.get("message")
        if isinstance(msg, dict):
            piece = _normalize_content(msg.get("content", ""))
            if piece:
                chunks.append(piece)

    return "".join(chunks).replace("<|im_end|>", "").strip()


def _extract_assistant(entry: Dict) -> str:
    # First try structured response object.
    for key in ("response", "response_obj", "response_json", "resp", "response_body"):
        if key in entry:
            obj = _parse_json_maybe(entry[key])
            if isinstance(obj, dict):
                text = _extract_assistant_from_non_stream(obj)
                if text:
                    return text

    # Then try stream text blocks.
    for key in ("stream_response", "stream_text", "sse", "response_stream"):
        raw = entry.get(key)
        if isinstance(raw, str):
            text = _extract_assistant_from_stream_text(raw)
            if text:
                return text

    # Or list of stream lines.
    for key in ("stream_response_lines", "sse_lines"):
        value = entry.get(key)
        if isinstance(value, list):
            lines = [str(x) for x in value]
            text = _extract_assistant_from_stream_text("\n".join(lines))
            if text:
                return text

    return ""


def _normalize_messages(request_obj: Dict) -> List[Dict[str, str]]:
    raw_messages = request_obj.get("messages", [])
    out: List[Dict[str, str]] = []
    if not isinstance(raw_messages, list):
        return out
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))
        content = _normalize_content(item.get("content", ""))
        out.append({"role": role, "content": content})
    return out


def _convert_entry(entry: Dict) -> Optional[Dict]:
    req = _get_request_obj(entry)
    if not isinstance(req, dict):
        return None
    messages = _normalize_messages(req)
    if not messages:
        return None
    assistant = _extract_assistant(entry)
    if not assistant:
        return None
    return {"messages": [*messages, {"role": "assistant", "content": assistant}]}


def _iter_input_lines(paths: List[Path]) -> Iterable[Tuple[Path, int, Dict]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line_no, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield path, line_no, obj


def main() -> None:
    parser = argparse.ArgumentParser(description="Build SFT JSONL from request/response pairs")
    parser.add_argument("--input", type=str, nargs="+", required=True, help="Input JSONL files")
    parser.add_argument("--output", type=str, required=True, help="Output JSONL path")
    parser.add_argument("--min-assistant-chars", type=int, default=1)
    parser.add_argument("--dedupe", action="store_true", help="Dedupe by full message JSON")
    args = parser.parse_args()

    input_paths = [Path(x) for x in args.input]
    for path in input_paths:
        if not path.exists():
            raise FileNotFoundError(f"Input file not found: {path}")

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    converted = 0
    dropped = 0
    seen = set()

    with output_path.open("w", encoding="utf-8") as out_f:
        for _, _, entry in _iter_input_lines(input_paths):
            total += 1
            item = _convert_entry(entry)
            if item is None:
                dropped += 1
                continue
            assistant = item["messages"][-1]["content"]
            if len(assistant) < args.min_assistant_chars:
                dropped += 1
                continue

            if args.dedupe:
                key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                if key in seen:
                    dropped += 1
                    continue
                seen.add(key)

            out_f.write(json.dumps(item, ensure_ascii=False) + "\n")
            converted += 1

    print(f"input_examples={total}")
    print(f"converted_examples={converted}")
    print(f"dropped_examples={dropped}")
    print(f"output={output_path}")


if __name__ == "__main__":
    main()
