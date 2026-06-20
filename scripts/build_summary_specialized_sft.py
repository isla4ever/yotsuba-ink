"""
Build a summary-specialized SFT dataset with strict output schema.

Target assistant format (string literal, single quotes):
[
  {
    '主要人物和他们的行为': {'角色A': '行为描述', ...},
    '故事': {'开始': '...', '发展': '...', '高潮': '...', '结局': '...'}
  },
  ...
]

Input can be mixed structured records. Only summary-like records are used.
Output is chat SFT JSONL:
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
from pathlib import Path
from textwrap import dedent
from typing import Any, Dict, Iterable, List, Optional, Sequence


SUMMARY_ALIASES = {
    "summary",
    "synopsis",
    "梗概",
    "分卷梗概",
}

PERSON_KEYS = (
    "主要人物和他们的行为",
    "主要人物",
    "人物",
    "人物信息",
    "角色",
    "character_actions",
    "characters",
)
STORY_KEYS = (
    "故事",
    "故事情节",
    "情节",
    "剧情",
    "story",
)

START_KEYS = ("开始", "开端", "起始", "起")
DEVELOP_KEYS = ("发展", "经过", "推进", "中段")
CLIMAX_KEYS = ("高潮", "转折", "高点", "爆发")
END_KEYS = ("结局", "结尾", "收束", "尾声")

GENERIC_ROLE_POOL = ("主角", "关键配角", "对手角色", "同伴角色")


def _iter_jsonl(paths: Sequence[Path]) -> Iterable[Dict[str, Any]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, (int, float, bool)):
        return str(value)
    return json.dumps(value, ensure_ascii=False)


def _to_mapping(value: Any) -> Dict[str, str]:
    if isinstance(value, dict):
        out: Dict[str, str] = {}
        for k, v in value.items():
            k_text = _as_text(k)
            v_text = _as_text(v)
            if k_text:
                out[k_text] = v_text
        return out
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
        except Exception:
            return {}
        if isinstance(obj, dict):
            return {str(k): _as_text(v) for k, v in obj.items() if _as_text(k)}
    return {}


def _to_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, tuple):
        return [str(x).strip() for x in value if str(x).strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        try:
            obj = json.loads(s)
            if isinstance(obj, list):
                return [str(x).strip() for x in obj if str(x).strip()]
        except Exception:
            pass
        parts = re.split(r"[,\uFF0C;/\|]", s)
        return [p.strip() for p in parts if p.strip()]
    return [str(value).strip()]


def _candidate_sources(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    out = [record]
    for key in ("input", "fields", "data", "payload", "task_input"):
        value = record.get(key)
        if isinstance(value, dict):
            out.append(value)
    return out


def _pick_value(record: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    for src in _candidate_sources(record):
        for key in keys:
            if key in src and src[key] not in (None, ""):
                return src[key]
    return default


def _normalize_task(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    key = str(raw).strip().lower()
    if key in {x.lower() for x in SUMMARY_ALIASES}:
        return "summary"
    return None


def _infer_is_summary(record: Dict[str, Any]) -> bool:
    explicit = _normalize_task(_pick_value(record, ("task", "task_type", "scene", "业务类型")))
    if explicit == "summary":
        return True

    if _pick_value(record, ("characters", "人物信息")) and _pick_value(record, ("background", "故事背景")):
        return True

    request_obj = _pick_value(record, ("request", "request_obj", "request_body"))
    if isinstance(request_obj, dict):
        msgs = request_obj.get("messages")
        if isinstance(msgs, list):
            merged = "\n".join(_as_text(x.get("content")) for x in msgs if isinstance(x, dict))
            if "梗概" in merged:
                return True
    if isinstance(request_obj, str) and "梗概" in request_obj:
        return True
    return False


def _extract_assistant_from_non_stream(resp_obj: Dict[str, Any]) -> str:
    choices = resp_obj.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message")
    if isinstance(msg, dict):
        return _as_text(msg.get("content", "")).replace("<|im_end|>", "").strip()
    return ""


def _iter_sse_data_lines(raw_text: str) -> Iterable[str]:
    for line in raw_text.splitlines():
        s = line.strip()
        if not s:
            continue
        if s.startswith("data:"):
            yield s[5:].strip()
        elif s.startswith("{") and s.endswith("}"):
            yield s


def _extract_assistant_from_stream_text(raw_text: str) -> str:
    pieces: List[str] = []
    for data in _iter_sse_data_lines(raw_text):
        if data == "[DONE]":
            continue
        try:
            obj = json.loads(data)
        except Exception:
            continue
        choices = obj.get("choices", [])
        if not choices:
            continue
        first = choices[0]
        if not isinstance(first, dict):
            continue
        delta = first.get("delta")
        if isinstance(delta, dict):
            part = _as_text(delta.get("content", ""))
            if part:
                pieces.append(part)
            continue
        msg = first.get("message")
        if isinstance(msg, dict):
            part = _as_text(msg.get("content", ""))
            if part:
                pieces.append(part)
    return "".join(pieces).replace("<|im_end|>", "").strip()


def _extract_assistant(record: Dict[str, Any]) -> str:
    for key in (
        "assistant",
        "assistant_text",
        "output",
        "output_text",
        "target",
        "target_text",
        "answer",
        "completion",
    ):
        value = _pick_value(record, (key,))
        text = _as_text(value)
        if text:
            return text

    for key in ("response", "response_obj", "response_json", "resp", "response_body"):
        value = _pick_value(record, (key,))
        if isinstance(value, dict):
            text = _extract_assistant_from_non_stream(value)
            if text:
                return text
        if isinstance(value, str):
            s = value.strip()
            if s.startswith("{") and s.endswith("}"):
                try:
                    obj = json.loads(s)
                except Exception:
                    obj = None
                if isinstance(obj, dict):
                    text = _extract_assistant_from_non_stream(obj)
                    if text:
                        return text

    for key in ("stream_response", "stream_text", "response_stream", "sse"):
        raw = _pick_value(record, (key,))
        if isinstance(raw, str):
            text = _extract_assistant_from_stream_text(raw)
            if text:
                return text
    return ""


def _strip_fences_and_tokens(text: str) -> str:
    s = text.strip()
    s = s.replace("<|im_end|>", "").replace("<|im_start|>", "")
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _first_non_empty(*values: str) -> str:
    for value in values:
        if value and value.strip():
            return value.strip()
    return ""


def _split_sentences(text: str) -> List[str]:
    s = _as_text(text)
    if not s:
        return []
    parts = re.split(r"(?<=[。！？!?])", s)
    out = [x.strip() for x in parts if x.strip()]
    if not out and s:
        out = [s]
    return out


def _pick_story_value(raw: Dict[str, Any], keys: Sequence[str]) -> str:
    for k in keys:
        if k in raw and _as_text(raw[k]):
            return _as_text(raw[k])
    return ""


def _coerce_char_map(value: Any, fallback_chars: Dict[str, str]) -> Dict[str, str]:
    if isinstance(value, dict):
        out = {k: _as_text(v) for k, v in value.items() if _as_text(k)}
        if out:
            return out
    if isinstance(value, list):
        out = {str(x).strip(): "在冲突推进中承担关键行动" for x in value if str(x).strip()}
        if out:
            return out
    if isinstance(value, str):
        names = _to_list(value)
        if names:
            return {name: "在冲突推进中承担关键行动" for name in names}
    if fallback_chars:
        return dict(fallback_chars)
    return {
        "主角": "卷入核心事件并推动主线发展",
        "关键配角": "提供转折线索并影响主角决策",
        "对手角色": "制造阻碍并放大叙事冲突",
    }


def _coerce_story_map(value: Any, fallback_story: Dict[str, str]) -> Dict[str, str]:
    if isinstance(value, dict):
        start = _pick_story_value(value, START_KEYS)
        develop = _pick_story_value(value, DEVELOP_KEYS)
        climax = _pick_story_value(value, CLIMAX_KEYS)
        ending = _pick_story_value(value, END_KEYS)
        out = {
            "开始": _first_non_empty(start, fallback_story["开始"]),
            "发展": _first_non_empty(develop, fallback_story["发展"]),
            "高潮": _first_non_empty(climax, fallback_story["高潮"]),
            "结局": _first_non_empty(ending, fallback_story["结局"]),
        }
        return out
    if isinstance(value, str) and value.strip():
        parts = _split_sentences(value)
        out = {
            "开始": parts[0] if len(parts) > 0 else fallback_story["开始"],
            "发展": " ".join(parts[1:3]).strip() if len(parts) > 1 else fallback_story["发展"],
            "高潮": parts[3] if len(parts) > 3 else fallback_story["高潮"],
            "结局": parts[4] if len(parts) > 4 else fallback_story["结局"],
        }
        out["发展"] = _first_non_empty(out["发展"], fallback_story["发展"])
        return out
    return dict(fallback_story)


def _normalize_item(item: Dict[str, Any], fallback_chars: Dict[str, str], fallback_story: Dict[str, str]) -> Dict[str, Any]:
    person_raw: Any = None
    story_raw: Any = None
    for k in PERSON_KEYS:
        if k in item:
            person_raw = item[k]
            break
    for k in STORY_KEYS:
        if k in item:
            story_raw = item[k]
            break
    return {
        "主要人物和他们的行为": _coerce_char_map(person_raw, fallback_chars),
        "故事": _coerce_story_map(story_raw, fallback_story),
    }


def _build_fallback_story(record: Dict[str, Any]) -> Dict[str, str]:
    background = _as_text(_pick_value(record, ("background", "story_background", "故事背景"), ""))
    intro = _as_text(_pick_value(record, ("intro", "introduction", "简介"), ""))
    sentence_pool = _split_sentences(f"{background} {intro}".strip())
    if not sentence_pool:
        sentence_pool = ["主角被卷入核心事件并被迫做出选择。"]

    def pick(idx: int, default_text: str) -> str:
        if idx < len(sentence_pool):
            return sentence_pool[idx]
        return default_text

    return {
        "开始": pick(0, "主角被卷入核心事件并与主要人物发生交集。"),
        "发展": _first_non_empty(" ".join(sentence_pool[1:3]).strip(), pick(1, "多方矛盾逐步升级，主角开始主动应对。")),
        "高潮": pick(3, "关键秘密揭开，冲突在高压下集中爆发。"),
        "结局": pick(4, "阶段性冲突收束，同时为后续情节埋下伏笔。"),
    }


def _build_fallback_char_map(record: Dict[str, Any]) -> Dict[str, str]:
    raw = _pick_value(record, ("characters", "character_info", "人物信息"), {})
    mapping = _to_mapping(raw)
    if mapping:
        return mapping
    names = _to_list(raw)
    if names:
        return {name: "在冲突推进中承担关键行动" for name in names}
    return {}


def _extract_items_from_parsed_obj(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if "小说梗概" in obj and isinstance(obj["小说梗概"], list):
            return [x for x in obj["小说梗概"] if isinstance(x, dict)]
        if any(k in obj for k in PERSON_KEYS) or any(k in obj for k in STORY_KEYS):
            return [obj]
    return []


def _try_parse_assistant_object(raw_text: str) -> Optional[Any]:
    if not raw_text:
        return None
    s = _strip_fences_and_tokens(raw_text)

    for parser in (ast.literal_eval, json.loads):
        try:
            obj = parser(s)
            return obj
        except Exception:
            pass
    return None


def _expand_to_min_items(items: List[Dict[str, Any]], min_items: int) -> List[Dict[str, Any]]:
    if min_items <= 0:
        return items
    if not items:
        return items
    out = list(items)
    while len(out) < min_items:
        seed = json.loads(json.dumps(out[-1], ensure_ascii=False))
        if "关键配角" not in seed["主要人物和他们的行为"]:
            seed["主要人物和他们的行为"]["关键配角"] = "在关键节点促成信息交换并放大冲突"
        seed["故事"]["发展"] = _first_non_empty(seed["故事"].get("发展", ""), "主线持续推进，人物关系逐步重组。")
        if not seed["故事"]["发展"].endswith("。"):
            seed["故事"]["发展"] += "。"
        seed["故事"]["发展"] += " 人物关系进一步变化，冲突层级持续上升。"
        out.append(seed)
    return out


def _normalize_summary_items(record: Dict[str, Any], raw_assistant: str, min_items: int) -> List[Dict[str, Any]]:
    fallback_chars = _build_fallback_char_map(record)
    fallback_story = _build_fallback_story(record)

    parsed = _try_parse_assistant_object(raw_assistant)
    raw_items = _extract_items_from_parsed_obj(parsed) if parsed is not None else []

    normalized: List[Dict[str, Any]] = []
    for item in raw_items:
        normalized.append(_normalize_item(item, fallback_chars, fallback_story))

    if not normalized:
        normalized = [
            {
                "主要人物和他们的行为": _coerce_char_map(None, fallback_chars),
                "故事": _coerce_story_map(None, fallback_story),
            }
        ]

    return _expand_to_min_items(normalized, min_items)


def _escape_single_quote(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _to_single_quote_literal(value: Any) -> str:
    if isinstance(value, str):
        return "'" + _escape_single_quote(value) + "'"
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_to_single_quote_literal(x) for x in value) + "]"
    if isinstance(value, dict):
        parts: List[str] = []
        for k, v in value.items():
            parts.append(f"{_to_single_quote_literal(str(k))}: {_to_single_quote_literal(v)}")
        return "{" + ", ".join(parts) + "}"
    return _to_single_quote_literal(str(value))


def _short_text(text: str, max_chars: int) -> str:
    s = _as_text(text)
    if max_chars <= 0:
        return s
    if len(s) <= max_chars:
        return s
    return s[:max_chars].rstrip() + "…"


def _compact_items(
    items: List[Dict[str, Any]],
    max_items: int,
    max_roles: int,
    max_value_chars: int,
) -> List[Dict[str, Any]]:
    compacted: List[Dict[str, Any]] = []
    for item in items[: max(1, max_items)]:
        char_map = item.get("主要人物和他们的行为", {})
        story_map = item.get("故事", {})

        role_out: Dict[str, str] = {}
        if isinstance(char_map, dict):
            for idx, (k, v) in enumerate(char_map.items()):
                if idx >= max(1, max_roles):
                    break
                role_out[_short_text(str(k), 8)] = _short_text(_as_text(v), max_value_chars)
        if not role_out:
            role_out = {"主角": "推进主线", "配角": "触发转折", "对手": "制造冲突"}

        compact_story = {
            "开始": _short_text(_as_text(story_map.get("开始", "")), max_value_chars),
            "发展": _short_text(_as_text(story_map.get("发展", "")), max_value_chars),
            "高潮": _short_text(_as_text(story_map.get("高潮", "")), max_value_chars),
            "结局": _short_text(_as_text(story_map.get("结局", "")), max_value_chars),
        }
        for key in ("开始", "发展", "高潮", "结局"):
            if not compact_story[key]:
                compact_story[key] = {
                    "开始": "主角卷入事件",
                    "发展": "冲突持续升级",
                    "高潮": "真相触发反转",
                    "结局": "阶段收束留伏笔",
                }[key]

        compacted.append({"主要人物和他们的行为": role_out, "故事": compact_story})
    return compacted


def _build_strict_summary_content(
    record: Dict[str, Any],
    raw_assistant: str,
    min_items: int,
    compact: bool,
    compact_max_items: int,
    compact_max_roles: int,
    compact_max_value_chars: int,
) -> str:
    items = _normalize_summary_items(record, raw_assistant, min_items=min_items)
    if compact:
        items = _compact_items(
            items=items,
            max_items=compact_max_items,
            max_roles=compact_max_roles,
            max_value_chars=compact_max_value_chars,
        )
    return _to_single_quote_literal(items)


def _format_list_literal(items: Sequence[str]) -> str:
    return _to_single_quote_literal(list(items))


def _build_summary_prompts(record: Dict[str, Any], compact: bool) -> List[str]:
    title = _as_text(_pick_value(record, ("title", "novel_title", "小说标题"), "未命名小说"))
    categories = _to_list(_pick_value(record, ("categories", "tags", "分类"), []))
    categories_text = _format_list_literal(categories)
    characters = _pick_value(record, ("characters", "character_info", "人物信息"), {})
    characters_map = _to_mapping(characters)
    characters_text = _to_single_quote_literal(characters_map) if characters_map else _format_list_literal(_to_list(characters))
    background = _as_text(_pick_value(record, ("background", "story_background", "故事背景"), ""))
    intro = _as_text(_pick_value(record, ("intro", "introduction", "简介"), ""))

    if compact:
        s1 = (
            "按固定结构输出梗概："
            "[{'主要人物和他们的行为':{...},'故事':{'开始':'...','发展':'...','高潮':'...','结局':'...'}}]"
        )
        s2 = f"人物:{characters_text}\n背景:{_short_text(background, 32)}\n简介:{_short_text(intro, 32)}"
        s3 = "只返回列表字符串，不要代码块。"
        return [f"{s1}\n{s2}\n{s3}", f"{s1}\n标题:{title}\n{s2}\n{s3}"]

    p1 = dedent(
        f"""
        #### 角色:
        你是一位才华横溢的小说作家助手，擅长将小说的主要人物、故事背景和简介转换为详细的梗概。
        你的任务是根据提供的基本信息，生成多个详细的梗概。

        #### 输入:
        1. **主要人物**：{characters_text}
        2. **故事背景**：{background}
        3. **简介**：{intro}

        #### 输出:
        输出必须是列表字符串，严格使用以下结构和键名：
        [{{'主要人物和他们的行为':{{str:str,...}},'故事':{{'开始':str,'发展':str,'高潮':str,'结局':str}}}},...]

        请根据以上信息生成梗概。
        """
    ).strip()

    p2 = dedent(
        f"""
        任务: 生成小说内容梗概。
        小说标题: {title}
        小说分类: {categories_text}
        人物信息: {characters_text}
        故事背景: {background}
        情节简介: {intro}

        输出约束:
        1. 返回值必须是单个列表字符串。
        2. 每个元素只允许两个键: '主要人物和他们的行为' 与 '故事'。
        3. '故事' 必须包含 '开始'、'发展'、'高潮'、'结局' 四个键。
        """
    ).strip()

    p3 = dedent(
        f"""
        你是网文策划编辑。请把“人物+背景+简介”扩展为多版本梗概列表。
        标题: {title}
        分类: {categories_text}
        人物: {characters_text}
        背景: {background}
        简介: {intro}

        必须输出:
        [{{'主要人物和他们的行为':{{...}},'故事':{{'开始':'...','发展':'...','高潮':'...','结局':'...'}}}}, ...]
        """
    ).strip()

    return [p1, p2, p3]


def _select_variants(candidates: List[str], n: int, rng: random.Random) -> List[str]:
    if not candidates:
        return []
    n = max(1, n)
    if len(candidates) == 1:
        return [candidates[0] for _ in range(n)]
    start = rng.randrange(len(candidates))
    return [candidates[(start + i) % len(candidates)] for i in range(n)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build summary-specialized strict-schema SFT dataset")
    parser.add_argument("--input", type=str, nargs="+", required=True, help="Input JSONL files")
    parser.add_argument("--output", type=str, required=True, help="Output SFT JSONL")
    parser.add_argument("--variants-per-record", type=int, default=4, help="Prompt variants per source record")
    parser.add_argument("--min-items", type=int, default=2, help="Minimum number of synopsis objects in assistant list")
    parser.add_argument("--max-records", type=int, default=0, help="Use at most N source records (0 means all)")
    parser.add_argument("--min-assistant-chars", type=int, default=30)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--dedupe", action="store_true")
    parser.add_argument("--compact", action="store_true", help="Build compact targets for low-memory training")
    parser.add_argument("--compact-max-items", type=int, default=1)
    parser.add_argument("--compact-max-roles", type=int, default=3)
    parser.add_argument("--compact-max-value-chars", type=int, default=12)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    input_paths = [Path(x) for x in args.input]
    for path in input_paths:
        if not path.exists():
            raise FileNotFoundError(f"input not found: {path}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    total = 0
    selected_summary = 0
    emitted = 0
    dropped_no_target = 0
    dropped_short = 0
    dropped_dedup = 0
    seen = set()

    with out_path.open("w", encoding="utf-8") as out_f:
        for record in _iter_jsonl(input_paths):
            total += 1
            if args.max_records > 0 and selected_summary >= args.max_records:
                break
            if not _infer_is_summary(record):
                continue

            raw_assistant = _extract_assistant(record)
            strict_assistant = _build_strict_summary_content(
                record=record,
                raw_assistant=raw_assistant,
                min_items=args.min_items,
                compact=args.compact,
                compact_max_items=args.compact_max_items,
                compact_max_roles=args.compact_max_roles,
                compact_max_value_chars=args.compact_max_value_chars,
            )
            if not strict_assistant:
                dropped_no_target += 1
                continue
            if len(strict_assistant) < args.min_assistant_chars:
                dropped_short += 1
                continue

            prompts = _select_variants(_build_summary_prompts(record, compact=args.compact), args.variants_per_record, rng)
            if not prompts:
                continue

            selected_summary += 1
            for prompt in prompts:
                item = {
                    "messages": [
                        {"role": "user", "content": prompt},
                        {"role": "assistant", "content": strict_assistant},
                    ]
                }
                if args.dedupe:
                    key = json.dumps(item, ensure_ascii=False, sort_keys=True)
                    if key in seen:
                        dropped_dedup += 1
                        continue
                    seen.add(key)
                out_f.write(json.dumps(item, ensure_ascii=False) + "\n")
                emitted += 1

    print(f"input_records={total}")
    print(f"selected_summary_records={selected_summary}")
    print(f"output_examples={emitted}")
    print(f"dropped_no_target={dropped_no_target}")
    print(f"dropped_short={dropped_short}")
    print(f"dropped_dedup={dropped_dedup}")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()
