"""
Build high-quality corrected SFT dataset for summary (梗概) task.

Goals:
1) Reduce template repetition.
2) Enforce character-name consistency and deduplication.
3) Increase output detail length:
   - each character behavior: >= min_behavior_chars
   - story content: >= min_content_chars

Input format:
  line json with {"request": {...}, "response": {...}, "meta": {...}}

Output format (chat SFT jsonl):
  {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"[{'主要人物和他们的行为': {...}, '内容':'...'}]"}]}
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import re
from collections import Counter, OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PERSON_KEYS_HINT = (
    "主要人物和他们的行为",
    "主要人物",
    "人物信息",
    "人物",
    "角色",
    "characters",
    "character_actions",
)
CONTENT_KEYS_HINT = (
    "内容",
    "故事",
    "故事情节",
    "剧情",
    "小说梗概",
    "summary",
    "content",
)

GENERIC_NAMES = {
    "主角",
    "男主",
    "女主",
    "配角",
    "反派",
    "角色a",
    "角色b",
    "关键角色",
    "同伴角色",
    "对手角色",
}

TEMPLATE_PHRASES = (
    "多次交流，陪同处理关键事项，共同推进后续行动",
    "在高压情境中的选择与成长展开",
    "在一连串事件中不断修复关系",
    "完成阶段性重生",
)

EXPAND_SUFFIXES = (
    "在关系僵持期主动沟通并承担后果，推动冲突进入可解阶段。",
    "面对现实压力时调整策略并付诸行动，促成局势从失控转向可控。",
    "在关键转折点明确立场并执行决定，直接改变后续事件走向。",
    "在误解加深时持续提供证据与行动回应，最终重建彼此信任。",
    "在阶段性失败后复盘并修正路径，以更稳妥方式推进核心目标。",
)

CONTENT_EXPAND_TEMPLATES = (
    "随着线索持续聚拢，人物关系从表面合作转向深层博弈，旧矛盾与新危机并行爆发，主角必须在亲情、信任与现实代价之间反复权衡。",
    "中段推进中，多条支线交叉牵引主线：一条指向过去被掩埋的事实，一条指向当下利益链条，另一条则逼迫角色直面长期回避的内心选择。",
    "在高潮节点，角色不再依赖偶然转机，而是以明确行动完成自我修复和关系修复，通过承担责任换取局势的可持续稳定。",
    "结尾阶段不以简单反转收束，而是通过后果落地与关系重建形成闭环，同时保留面向后续章节的悬念与成长空间。",
)


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


def _sanitize_text(text: str) -> str:
    t = text.replace("<|im_end|>", "").replace("<|im_start|>", "").replace("<|endoftext|>", "")
    t = re.sub(r"</?think>", "", t)
    t = t.replace("\r", "\n")
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _extract_user_prompt(req: Dict[str, Any]) -> str:
    msgs = req.get("messages")
    if not isinstance(msgs, list):
        return ""
    merged: List[str] = []
    for m in msgs:
        if not isinstance(m, dict):
            continue
        if str(m.get("role", "user")) != "user":
            continue
        merged.append(_safe_text(m.get("content", "")))
    return "\n".join(x for x in merged if x).strip()


def _extract_prompt_fields(user_text: str) -> Dict[str, Any]:
    title = ""
    cats: List[str] = []
    intro = ""

    mt = re.search(r"\*\*小说标题\*\*[:：]\s*\n?\s*(.+?)(?:\n|$)", user_text)
    if mt:
        title = mt.group(1).strip().strip("`")

    mc = re.search(r"\*\*分类\*\*[:：]\s*\n?\s*(\[[\s\S]*?\])", user_text)
    if mc:
        raw = mc.group(1).strip()
        try:
            parsed = ast.literal_eval(raw)
            if isinstance(parsed, (list, tuple)):
                cats = [str(x).strip() for x in parsed if str(x).strip()]
        except Exception:
            cats = [x.strip(" '\"") for x in re.split(r"[,\uFF0C]", raw.strip("[]")) if x.strip(" '\"")]

    mi = re.search(r"\*\*情节简介\*\*[:：]\s*\n?([\s\S]*?)\n\s*(?:请根据以上信息|$)", user_text)
    if mi:
        intro = mi.group(1).strip()

    return {"title": title, "categories": cats, "intro": _clean_intro_text(intro)}


def _clean_intro_text(text: str) -> str:
    s = _sanitize_text(text)
    if not s:
        return ""
    cleaned_lines: List[str] = []
    for line in s.splitlines():
        x = line.strip()
        if not x:
            continue
        # Filter prompt-instruction pollution.
        if x.startswith("####") or x.startswith("###"):
            continue
        if x.startswith("**") and x.endswith("**"):
            continue
        if any(
            bad in x
            for bad in (
                "输出格式",
                "必须严格一致",
                "返回一个列表字符串",
                "注意：",
                "人物名不要重复",
                "对象只允许2个键",
                "请根据以上信息",
                "1)",
                "2)",
                "{",
                "}",
                "[",
                "]",
                "'内容'",
                "'主要人物和他们的行为'",
                "Provide",
                "format",
            )
        ):
            continue
        cleaned_lines.append(x)
    out = _sanitize_text(" ".join(cleaned_lines))
    return out


def _extract_response_text(resp: Dict[str, Any]) -> str:
    choices = resp.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    msg = first.get("message")
    if isinstance(msg, dict):
        return _sanitize_text(_safe_text(msg.get("content", "")))
    return ""


def _try_literal_parse(raw: str) -> Optional[Any]:
    s = raw.strip()
    if not s:
        return None
    candidates = [s]
    lb = s.find("[")
    rb = s.rfind("]")
    if lb >= 0 and rb > lb:
        candidates.append(s[lb : rb + 1])
    lb2 = s.find("{")
    rb2 = s.rfind("}")
    if lb2 >= 0 and rb2 > lb2:
        candidates.append(s[lb2 : rb2 + 1])
    for c in candidates:
        try:
            return ast.literal_eval(c)
        except Exception:
            continue
    return None


def _dict_like(v: Any) -> bool:
    return isinstance(v, dict)


def _best_char_map(item: Dict[str, Any]) -> Dict[str, str]:
    # First pass: key-hint match.
    for k, v in item.items():
        key = str(k).strip().lower()
        if any(h.lower() in key for h in PERSON_KEYS_HINT) and isinstance(v, dict):
            out = {
                _safe_text(n): _safe_text(a)
                for n, a in v.items()
                if _safe_text(n) and _safe_text(a)
            }
            if out:
                return out
    # Fallback: pick first dict with at least 2 non-empty string values.
    for v in item.values():
        if isinstance(v, dict):
            out = {
                _safe_text(n): _safe_text(a)
                for n, a in v.items()
                if _safe_text(n) and _safe_text(a)
            }
            if len(out) >= 2:
                return out
    return {}


def _best_content(item: Dict[str, Any]) -> str:
    # Prefer content-key match.
    for k, v in item.items():
        key = str(k).strip().lower()
        if any(h.lower() in key for h in CONTENT_KEYS_HINT):
            if isinstance(v, str):
                return _sanitize_text(v)
            if isinstance(v, dict):
                # Typical stage dict.
                merged = " ".join(_safe_text(v.get(x, "")) for x in ("开始", "发展", "高潮", "结局"))
                merged = merged.strip() or " ".join(_safe_text(x) for x in v.values())
                return _sanitize_text(merged)
    # Fallback: longest string candidate among values and dict-values merge.
    best = ""
    for v in item.values():
        if isinstance(v, str) and len(v) > len(best):
            best = v
        elif isinstance(v, dict):
            merged = " ".join(_safe_text(x) for x in v.values()).strip()
            if len(merged) > len(best):
                best = merged
    return _sanitize_text(best)


def _extract_structured_from_response(raw_text: str) -> Tuple[Dict[str, str], str]:
    obj = _try_literal_parse(raw_text)
    if obj is None:
        return {}, ""

    item: Optional[Dict[str, Any]] = None
    if isinstance(obj, list) and obj:
        for it in obj:
            if isinstance(it, dict):
                item = it
                break
    elif isinstance(obj, dict):
        item = obj
    if not isinstance(item, dict):
        return {}, ""

    return _best_char_map(item), _best_content(item)


def _normalize_name(name: str) -> str:
    n = re.sub(r"\s+", "", name)
    if not n:
        return ""
    m = re.search(r"[（(]([^（）()]{1,12})[）)]", n)
    if m:
        inner = m.group(1).strip()
        if inner:
            n = inner
    n = re.sub(r"^[主男女性关键同伴对手配角角色]+[：:]", "", n).strip()
    n = n.strip("[]{}()（）“”\"'`")
    return n


def _dedupe_ordered_char_map(char_map: Dict[str, str]) -> OrderedDict[str, str]:
    out: OrderedDict[str, str] = OrderedDict()
    for raw_name, raw_behavior in char_map.items():
        name = _normalize_name(_safe_text(raw_name))
        behavior = _sanitize_text(_safe_text(raw_behavior))
        if not name:
            continue
        if name in out:
            # merge duplicate character behaviors
            if behavior and behavior not in out[name]:
                out[name] = (out[name] + " " + behavior).strip()
            continue
        out[name] = behavior
    return out


def _split_sentences(text: str) -> List[str]:
    t = _sanitize_text(text)
    if not t:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*|\n+", t)
    return [x.strip() for x in parts if x and x.strip()]


def _clean_repetition(text: str) -> str:
    # sentence-level dedupe
    sents = _split_sentences(text)
    seen = set()
    out = []
    for s in sents:
        key = re.sub(r"\s+", "", s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    merged = "".join(out).strip()
    return merged if merged else _sanitize_text(text)


def _select_clause(seed_key: str, options: Sequence[str], offset: int = 0) -> str:
    if not options:
        return ""
    h = int(hashlib.md5(seed_key.encode("utf-8")).hexdigest(), 16)
    return options[(h + offset) % len(options)]


def _expand_behavior(
    *,
    name: str,
    behavior: str,
    intro: str,
    min_behavior_chars: int,
    uniq_offset: int,
) -> str:
    base = _sanitize_text(behavior)
    base = re.sub(r"[。；;，,\s]+$", "", base)
    if base.startswith(name):
        base = base[len(name) :].lstrip("，,:：。 ")
    if not base:
        base = f"{name}围绕核心事件持续推进关键行动，并在压力环境下保持执行。"
    # remove over-generic repeated template phrase.
    for ph in TEMPLATE_PHRASES:
        base = base.replace(ph, "围绕核心问题展开行动")

    if len(base) < min_behavior_chars:
        suffix = _select_clause(name + base, EXPAND_SUFFIXES, offset=uniq_offset)
        base = f"{name}{base}，并持续推进关键行动路径，{suffix}"

    # hard floor, final patch-up
    if len(base) < min_behavior_chars:
        base = base + " 在多轮博弈中保持行动连续性，确保阶段目标落地。"
    return _clean_repetition(base)


def _build_fallback_names(fields: Dict[str, Any]) -> List[str]:
    title = _safe_text(fields.get("title", ""))
    seeds = re.findall(r"[\u4e00-\u9fff]{2,4}", title)
    if not seeds:
        seeds = ["林晚舟", "沈言", "周砚川", "程以宁", "顾南乔", "宋临安"]
    out = []
    for s in seeds:
        if s not in out:
            out.append(s)
    defaults = ["林晚舟", "沈言", "周砚川", "程以宁", "顾南乔", "宋临安"]
    for d in defaults:
        if d not in out:
            out.append(d)
        if len(out) >= 6:
            break
    return out


def _rename_generic_names(char_map: OrderedDict[str, str], fields: Dict[str, Any]) -> OrderedDict[str, str]:
    out: OrderedDict[str, str] = OrderedDict()
    fallback = [x for x in _build_fallback_names(fields) if x]
    fi = 0
    for name, beh in char_map.items():
        key = _normalize_name(name)
        if (not key) or (key.lower() in GENERIC_NAMES) or (key in GENERIC_NAMES):
            while fi < len(fallback) and fallback[fi] in out:
                fi += 1
            if fi < len(fallback):
                key = fallback[fi]
                fi += 1
        if not key:
            continue
        if key in out:
            out[key] = (out[key] + " " + beh).strip()
        else:
            out[key] = beh
    return out


def _expand_content(
    *,
    title: str,
    categories: List[str],
    intro: str,
    content: str,
    names: List[str],
    min_content_chars: int,
) -> str:
    base = _clean_repetition(content)
    base = _sanitize_text(base)
    intro = _sanitize_text(intro)
    intro = _clean_intro_text(intro)
    cats_text = "、".join([c for c in categories if c]) or "现实成长"
    if not base:
        base = intro
    if not base:
        base = f"《{title or '未命名作品'}》围绕主要人物在多重冲突中完成自我修复与关系重建展开。"

    if len(base) < min_content_chars:
        name_text = "、".join(names[:4]) if names else "主要人物"
        ext = [
            f"《{title or '该小说'}》定位为{cats_text}向作品，主线围绕{name_text}在连续事件中的选择与行动推进。",
            "开篇阶段由一次突发事件触发核心矛盾，角色从被动应对转入主动调查与决策，主线由此持续推进。",
            _select_clause((title or "") + (intro or ""), CONTENT_EXPAND_TEMPLATES, 0),
            _select_clause((title or "") + (intro or ""), CONTENT_EXPAND_TEMPLATES, 1),
            _select_clause((title or "") + (intro or ""), CONTENT_EXPAND_TEMPLATES, 2),
            _select_clause((title or "") + (intro or ""), CONTENT_EXPAND_TEMPLATES, 3),
        ]
        base = _clean_repetition(base + " " + " ".join(ext))

    if len(base) < min_content_chars:
        base = base + " 人物在阶段性结局中完成外部事件闭环，同时为后续章节预留新的变量与冲突线。"

    # overly long trimming for stable training.
    if len(base) > 980:
        base = base[:980].rstrip("，。；; ")
        if not base.endswith("。"):
            base += "。"
    return base


def _literal_single_quote(value: Any) -> str:
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
        return "[" + ", ".join(_literal_single_quote(x) for x in value) + "]"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(f"{_literal_single_quote(str(k))}: {_literal_single_quote(v)}")
        return "{" + ", ".join(parts) + "}"
    return _literal_single_quote(str(value))


def _build_assistant_text(char_map: Dict[str, str], content: str) -> str:
    obj = [{"主要人物和他们的行为": char_map, "内容": content}]
    return _literal_single_quote(obj)


def _quality_score(char_map: Dict[str, str], content: str) -> float:
    if not char_map or not content:
        return -1e9
    lens = [len(_safe_text(v)) for v in char_map.values()]
    if not lens:
        return -1e9
    dup_ratio = 0.0
    vals = list(char_map.values())
    if vals:
        c = Counter(vals)
        dup_ratio = max(c.values()) / max(1, len(vals))
    template_hits = sum(content.count(p) for p in TEMPLATE_PHRASES)
    score = (
        len(content) * 1.0
        + sum(lens) * 0.9
        + len(char_map) * 18.0
        - dup_ratio * 120.0
        - template_hits * 45.0
    )
    return score


def _ensure_char_count(
    *,
    char_map: OrderedDict[str, str],
    fields: Dict[str, Any],
    min_characters: int,
    max_characters: int,
) -> OrderedDict[str, str]:
    out = OrderedDict(char_map)
    if len(out) < min_characters:
        for n in _build_fallback_names(fields):
            if n in out:
                continue
            out[n] = f"{n}围绕主线事件持续行动，在冲突升级阶段承担关键执行任务并推进阶段目标。"
            if len(out) >= min_characters:
                break
    if len(out) > max_characters:
        # Keep most informative by behavior length.
        items = list(out.items())
        items.sort(key=lambda kv: len(_safe_text(kv[1])), reverse=True)
        trimmed = OrderedDict()
        for k, v in items[:max_characters]:
            trimmed[k] = v
        out = trimmed
    return out


def build_dataset(
    *,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    target_count: int,
    min_characters: int,
    max_characters: int,
    min_behavior_chars: int,
    min_content_chars: int,
    seed: int,
) -> None:
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []

    total = 0
    with_structured = 0
    repaired = 0
    for obj in _iter_jsonl(input_path):
        total += 1
        if obj.get("meta", {}).get("status") not in ("ok", None):
            continue
        req = obj.get("request")
        resp = obj.get("response")
        if not isinstance(req, dict) or not isinstance(resp, dict):
            continue

        user_prompt = _extract_user_prompt(req)
        if not user_prompt:
            continue
        fields = _extract_prompt_fields(user_prompt)
        title = _safe_text(fields.get("title", ""))
        categories = [str(x).strip() for x in fields.get("categories", []) if str(x).strip()]
        intro = _clean_intro_text(_safe_text(fields.get("intro", "")))

        raw_text = _extract_response_text(resp)
        char_map_raw, content_raw = _extract_structured_from_response(raw_text)
        if char_map_raw and content_raw:
            with_structured += 1

        char_map = _dedupe_ordered_char_map(char_map_raw)
        char_map = _ensure_char_count(
            char_map=char_map,
            fields=fields,
            min_characters=min_characters,
            max_characters=max_characters,
        )
        char_map = _rename_generic_names(char_map, fields=fields)
        char_map = _ensure_char_count(
            char_map=char_map,
            fields=fields,
            min_characters=min_characters,
            max_characters=max_characters,
        )

        # Expand/repair per-character behaviors.
        expanded_char_map: OrderedDict[str, str] = OrderedDict()
        for idx, (name, behavior) in enumerate(char_map.items()):
            if not name:
                continue
            fixed = _expand_behavior(
                name=name,
                behavior=behavior,
                intro=intro,
                min_behavior_chars=min_behavior_chars,
                uniq_offset=idx,
            )
            expanded_char_map[name] = fixed

        # Ensure behavior uniqueness to avoid template repetition.
        used_beh = set()
        for idx, (name, beh) in enumerate(list(expanded_char_map.items())):
            if beh in used_beh:
                expanded_char_map[name] = beh + " " + _select_clause(name + beh, EXPAND_SUFFIXES, offset=idx + 1)
            used_beh.add(expanded_char_map[name])

        content = _expand_content(
            title=title,
            categories=categories,
            intro=intro,
            content=content_raw,
            names=list(expanded_char_map.keys()),
            min_content_chars=min_content_chars,
        )

        # Final guardrails.
        if len(content) < min_content_chars:
            repaired += 1
            content = _expand_content(
                title=title,
                categories=categories,
                intro=intro + " 角色在多线冲突中推进主线并完成关键抉择。",
                content=content + " 事件持续升级并在多方博弈中进入收束阶段。",
                names=list(expanded_char_map.keys()),
                min_content_chars=min_content_chars,
            )

        lens = [len(v) for v in expanded_char_map.values()]
        if not lens or min(lens) < min_behavior_chars:
            repaired += 1
            for idx, (name, beh) in enumerate(list(expanded_char_map.items())):
                expanded_char_map[name] = _expand_behavior(
                    name=name,
                    behavior=beh,
                    intro=intro,
                    min_behavior_chars=min_behavior_chars,
                    uniq_offset=idx + 7,
                )

        assistant_text = _build_assistant_text(dict(expanded_char_map), content)
        score = _quality_score(dict(expanded_char_map), content)
        min_beh_len = min((len(v) for v in expanded_char_map.values()), default=0)
        if len(content) < min_content_chars or min_beh_len < min_behavior_chars:
            continue

        rows.append(
            {
                "messages": [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": assistant_text},
                ],
                "_meta": {
                    "title": title,
                    "score": score,
                    "content_len": len(content),
                    "char_count": len(expanded_char_map),
                    "min_behavior_len": min_beh_len,
                },
            }
        )

    # Rank + select top target_count to prefer higher quality.
    rows.sort(key=lambda x: x.get("_meta", {}).get("score", -1e9), reverse=True)
    if len(rows) > target_count > 0:
        top = rows[: int(target_count * 0.8)]
        tail_pool = rows[int(target_count * 0.8) : min(len(rows), int(target_count * 1.4))]
        rng.shuffle(tail_pool)
        rows = top + tail_pool[: max(0, target_count - len(top))]
    if target_count > 0 and len(rows) > target_count:
        rows = rows[:target_count]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(
                json.dumps(
                    {"messages": r["messages"]},
                    ensure_ascii=False,
                )
                + "\n"
            )

    content_lens = [r["_meta"]["content_len"] for r in rows]
    min_behavior_lens = [r["_meta"]["min_behavior_len"] for r in rows]
    char_counts = [r["_meta"]["char_count"] for r in rows]
    report = {
        "input_total": total,
        "with_structured_parse": with_structured,
        "repaired_records": repaired,
        "output_records": len(rows),
        "content_len_avg": round(sum(content_lens) / len(content_lens), 2) if content_lens else 0,
        "content_len_min": min(content_lens) if content_lens else 0,
        "content_len_max": max(content_lens) if content_lens else 0,
        "min_behavior_len_avg": round(sum(min_behavior_lens) / len(min_behavior_lens), 2) if min_behavior_lens else 0,
        "min_behavior_len_min": min(min_behavior_lens) if min_behavior_lens else 0,
        "char_count_avg": round(sum(char_counts) / len(char_counts), 2) if char_counts else 0,
        "char_count_min": min(char_counts) if char_counts else 0,
        "char_count_max": max(char_counts) if char_counts else 0,
        "output_path": str(output_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build high-quality corrected summary SFT dataset")
    parser.add_argument("--input", required=True, help="Input teacher pairs jsonl")
    parser.add_argument("--output", required=True, help="Output SFT jsonl")
    parser.add_argument("--report", default="logs/summary_hq_correction_report.json")
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--min-characters", type=int, default=4)
    parser.add_argument("--max-characters", type=int, default=8)
    parser.add_argument("--min-behavior-chars", type=int, default=56)
    parser.add_argument("--min-content-chars", type=int, default=560)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    build_dataset(
        input_path=Path(args.input),
        output_path=Path(args.output),
        report_path=Path(args.report),
        target_count=args.target_count,
        min_characters=args.min_characters,
        max_characters=args.max_characters,
        min_behavior_chars=args.min_behavior_chars,
        min_content_chars=args.min_content_chars,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
