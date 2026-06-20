"""
OpenAI-compatible chat completions server for local Qwen models.

Goals:
1) Keep existing Spring backend logic unchanged as much as possible.
2) Expose /v1/chat/completions with stream/non-stream support.
3) Accept legacy "model" names (for example ChiYong-MoE-Novel-18B-A6B)
   while serving a local base model (for example Qwen3.5-4B) + optional LoRA.

Run:
    python deploy/openai_compat_server.py \
        --model-path D:\\models\\Qwen3.5-4B \
        --served-model-name ChiYong-MoE-Novel-18B-A6B \
        --host 0.0.0.0 --port 54862
"""

from __future__ import annotations

import ast
import argparse
from contextlib import nullcontext
import hashlib
import json
import math
import os
import platform
import re
import sys
import threading
import time
import uuid
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import requests

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _patch_windows_wmi_for_torch() -> None:
    """
    Work around Windows WMI hangs when torch imports platform.machine().
    """
    if os.name != "nt":
        return
    try:
        _ = platform._wmi_query  # type: ignore[attr-defined]
    except Exception:
        return

    def _fast_wmi_query(*_args: object, **_kwargs: object):
        return ("10.0.0", 1, "multiprocessor free", 0, 0)

    platform._wmi_query = _fast_wmi_query  # type: ignore[attr-defined]


from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse
import uvicorn

from novelrag import NovelWikiStore
try:
    from novel_runtime_policy import (
        LIGHT_TASK_TOKEN_CAPS,
        LIGHT_TASK_TOKEN_FLOORS,
        TEXT_TASK_TOKEN_CAPS,
        TEXT_TASK_TOKEN_FLOORS,
        allow_deterministic_fallback,
        allow_direct_structured_resolution,
    )
except ImportError:  # pragma: no cover - supports package-style imports in tests.
    from deploy.novel_runtime_policy import (
        LIGHT_TASK_TOKEN_CAPS,
        LIGHT_TASK_TOKEN_FLOORS,
        TEXT_TASK_TOKEN_CAPS,
        TEXT_TASK_TOKEN_FLOORS,
        allow_deterministic_fallback,
        allow_direct_structured_resolution,
    )


torch = None
PeftModel = None
AutoModelForCausalLM = None
AutoTokenizer = None
TextIteratorStreamer = None


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except Exception:
        return
    for raw_line in lines:
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line[7:].strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


def _load_local_env() -> None:
    _load_dotenv_file(REPO_ROOT / ".env")
    _load_dotenv_file(REPO_ROOT / ".env.local")


_load_local_env()


def _ensure_local_model_dependencies() -> None:
    """Import heavyweight local model dependencies only when local mode is used."""

    global torch, PeftModel, AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
    if torch is not None:
        return
    _patch_windows_wmi_for_torch()
    import torch as _torch
    from peft import PeftModel as _PeftModel
    from transformers import (
        AutoModelForCausalLM as _AutoModelForCausalLM,
        AutoTokenizer as _AutoTokenizer,
        TextIteratorStreamer as _TextIteratorStreamer,
    )

    torch = _torch
    PeftModel = _PeftModel
    AutoModelForCausalLM = _AutoModelForCausalLM
    AutoTokenizer = _AutoTokenizer
    TextIteratorStreamer = _TextIteratorStreamer


SPECIAL_STRIP_TOKENS = (
    "<|im_end|>",
    "<|im_start|>",
    "<|endoftext|>",
    "</s>",
)

SUMMARY_DETECT_KEYWORDS = (
    "梗概",
    "小说梗概",
    "主要人物和他们的行为",
    "情节简介",
)

SUMMARY_PERSON_KEYS = (
    "主要人物和他们的行为",
    "主要人物的行为和他们的行为",
    "主要人物行为",
    "人物行为",
    "主要人物",
    "人物",
    "人物信息",
    "主要角色",
    "characters",
)

SUMMARY_STORY_KEYS = (
    "故事",
    "故事情节",
    "情节",
    "剧情",
    "关键情节",
    "story",
)

SUMMARY_CONTENT_KEYS = (
    "内容",
    "完整故事",
    "故事内容",
    "小说梗概",
    "梗概",
    "content",
    "summary",
    "synopsis",
)

OUTLINE_PERSON_KEYS = (
    "主要人物和他们的行为",
    "主要人物",
    "人物",
    "人物信息",
    "主要角色",
    "characters",
)

OUTLINE_STORY_KEYS = (
    "故事情节",
    "故事",
    "情节",
    "内容",
    "剧情",
    "story",
    "content",
)

INFO_RECOMMEND_DETECT_KEYWORDS = (
    "人物信息",
    "故事背景",
    "简介",
    "小说标题",
    "分类",
)

INFO_RECOMMEND_TASK_NAME = "info_recommend"
SUMMARY_TASK_NAME = "summary"
OUTLINE_TASK_NAME = "outline"
DETAIL_OUTLINE_TASK_NAME = "detail_outline"
TEXT_TASK_NAME = "text"
TEXT_FIRST_CHAPTER_TASK_NAME = "text_first_chapter"
TEXT_NON_FIRST_CHAPTER_TASK_NAME = "text_non_first_chapter"
TEXT_STREAM_TASK_NAMES = {
    TEXT_TASK_NAME,
    TEXT_FIRST_CHAPTER_TASK_NAME,
    TEXT_NON_FIRST_CHAPTER_TASK_NAME,
}

INFO_RECOMMEND_RELATION_GUIDE = (
    "信息推荐任务补充要求：在“人物信息”中，每个人物行除了行为职责外，必须显式写出可用于拓扑图的静态关系锚点。"
    "优先写家族/血缘、师承、阵营、旧识、同乡、婚约、盟友、敌对、背景交集等关系；"
    "每个主要人物至少连接一名已列出人物或一个明确阵营，避免只写“推动主线”“协助调查”等空泛关系。"
    "人物关系网会作为后续梗概、大纲、细纲和正文的稳定设定约束，因此一开始必须清晰、可信、可回显；"
    "不要把后续剧情行为走向误写成静态关系。推荐格式：人物名：身份与行为职责。关系锚点：与A为兄妹/旧识/同门/敌对；隶属某阵营。"
)

# Outline quality guards (favor long-form per-volume planning text).
OUTLINE_MIN_BEHAVIOR_CHARS = 88
OUTLINE_MIN_STORY_SEGMENT_CHARS = 120

# Detail-outline quality guards (favor long-form per-chapter plan text).
DETAIL_OUTLINE_DEFAULT_CHAPTERS = 3
DETAIL_OUTLINE_MIN_CHAPTER_CHARS = 320


def _has_xpu() -> bool:
    if torch is None:
        return False
    try:
        return hasattr(torch, "xpu") and torch.xpu.is_available()
    except Exception:
        return False


def _normalize_content(content: object) -> str:
    """Normalize incoming OpenAI-style content into a plain text string."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, (int, float, bool)):
        return str(content)

    if isinstance(content, list):
        # OpenAI "array of content parts" format
        parts: List[str] = []
        for part in content:
            if isinstance(part, dict) and part.get("type") == "text":
                parts.append(str(part.get("text", "")))
            else:
                parts.append(_normalize_content(part))
        return "".join(parts)

    if isinstance(content, dict):
        for key in ("text", "value", "content"):
            if key in content:
                return _normalize_content(content.get(key))
        return json.dumps(content, ensure_ascii=False)

    return str(content)


def _extract_messages(payload: Dict[str, object]) -> List[Dict[str, str]]:
    raw_messages = payload.get("messages")
    if not isinstance(raw_messages, list) or len(raw_messages) == 0:
        raise HTTPException(status_code=400, detail="`messages` must be a non-empty list.")

    normalized: List[Dict[str, str]] = []
    for item in raw_messages:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role", "user"))
        content = _normalize_content(item.get("content", ""))
        normalized.append({"role": role, "content": content})

    if not normalized:
        raise HTTPException(status_code=400, detail="No valid messages found in `messages`.")
    return normalized


def _sanitize_text(text: str) -> str:
    cleaned = text
    for token in SPECIAL_STRIP_TOKENS:
        cleaned = cleaned.replace(token, "")
    # Hide reasoning traces for compatibility with existing backend expectations.
    cleaned = re.sub(r"<think>[\s\S]*?</think>\s*", "", cleaned)
    return cleaned


def _sanitize_text_keep_think(text: str) -> str:
    cleaned = text
    for token in SPECIAL_STRIP_TOKENS:
        cleaned = cleaned.replace(token, "")
    return cleaned


def _split_reasoning_and_visible(text: str) -> Tuple[str, str]:
    source = str(text or "")
    reasoning_parts: List[str] = []
    visible_parts: List[str] = []
    mode = "visible"
    i = 0
    open_tag = "<think>"
    close_tag = "</think>"
    tag_prefixes = {open_tag[:idx] for idx in range(1, len(open_tag))}
    tag_prefixes.update({close_tag[:idx] for idx in range(1, len(close_tag))})
    while i < len(source):
        remaining = source[i:]
        if remaining.startswith(open_tag):
            mode = "reasoning"
            i += len(open_tag)
            continue
        if remaining.startswith(close_tag):
            mode = "visible"
            i += len(close_tag)
            continue
        if remaining in tag_prefixes:
            break
        if mode == "reasoning":
            reasoning_parts.append(source[i])
        else:
            visible_parts.append(source[i])
        i += 1
    return "".join(reasoning_parts), "".join(visible_parts)


_TRADITIONAL_LITE_MAP = str.maketrans(
    {
        "標": "标", "題": "题", "細": "细", "綱": "纲", "內": "内", "檔": "档", "案": "案",
        "觀": "观", "瀾": "澜", "許": "许", "蘇": "苏", "臨": "临", "淵": "渊", "見": "见",
        "與": "与", "舊": "旧", "啟": "启", "轉": "转", "錄": "录", "證": "证", "據": "据",
        "線": "线", "緒": "绪", "壓": "压", "裡": "里", "裏": "里", "對": "对", "發": "发",
        "現": "现", "關": "关", "係": "系", "衝": "冲", "突": "突", "階": "阶", "段": "段",
        "場": "场", "景": "景", "緒": "绪", "釋": "释", "權": "权", "隱": "隐", "藏": "藏",
        "遙": "遥", "視": "视", "鋪": "铺", "舖": "铺",
        "聽": "听", "點": "点", "兒": "儿", "對": "对", "黙": "默",
        "華": "华", "東": "东", "嵐": "岚", "蘭": "兰",
    }
)


def _to_simplified_lite(text: str) -> str:
    return str(text or "").translate(_TRADITIONAL_LITE_MAP)


def _has_chapter_list_leakage(text: str) -> bool:
    value = _to_simplified_lite(_clean_linebreaks(str(text or "")))
    return bool(
        re.search(r"第[一二三四五六七八九十\d]+章[:：][^。！？\n]{1,24}(?:[/／、，,]\s*第[一二三四五六七八九十\d]+章[:：][^。！？\n]{1,24})+", value)
        or re.search(r"第一章[:：][^。！？\n]{1,24}[/／、，,]\s*第二章[:：]", value)
    )


def _strip_fences(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```[a-zA-Z0-9_-]*\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _split_sentences(text: str) -> List[str]:
    if not text:
        return []
    normalized = str(text).replace("\r", "\n")
    parts = re.split(r"(?<=[。！？!；;])|\n+", normalized)
    out = [x.strip() for x in parts if x and x.strip()]
    if not out and normalized.strip():
        out = [normalized.strip()]
    return out


def _split_clauses(text: str) -> List[str]:
    if not text:
        return []
    normalized = str(text).replace("\r", "\n")
    parts = re.split(r"[。！？!；;，,\n]+", normalized)
    return [x.strip() for x in parts if x and x.strip()]


def _escape_single(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("\r", "\\r")
        .replace("\n", "\\n")
        .replace("\t", "\\t")
    )


def _to_single_quote_literal(value: Any) -> str:
    if isinstance(value, str):
        return "'" + _escape_single(value) + "'"
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_to_single_quote_literal(x) for x in value) + "]"
    if isinstance(value, dict):
        parts = []
        for k, v in value.items():
            parts.append(f"{_to_single_quote_literal(str(k))}: {_to_single_quote_literal(v)}")
        return "{" + ", ".join(parts) + "}"
    return _to_single_quote_literal(str(value))


def _first_non_empty(*values: str) -> str:
    for v in values:
        if isinstance(v, str) and v.strip():
            return v.strip()
    return ""


def _pick_dict_value(raw: Dict[str, Any], keys: Sequence[str]) -> str:
    for k in keys:
        if k in raw and str(raw[k]).strip():
            return str(raw[k]).strip()
    return ""


def _coerce_char_map(raw: Any, fallback: Dict[str, str]) -> Dict[str, str]:
    if isinstance(raw, dict):
        out = {str(k).strip(): str(v).strip() for k, v in raw.items() if str(k).strip()}
        if out:
            return out
    if isinstance(raw, list):
        out = {str(x).strip(): "行为待补充。" for x in raw if str(x).strip()}
        if out:
            return out
    if isinstance(raw, str) and raw.strip():
        dict_like_names = re.findall(r"['\"]([一-鿿A-Za-z0-9_]{2,12})['\"]\s*:", raw)
        dict_like_names = _normalize_person_names(dict_like_names, max_count=8)
        if dict_like_names:
            return {name: "行为待补充。" for name in dict_like_names}
        names = [x.strip() for x in re.split(r"[,，;；/\|、]", raw) if x.strip()]
        if names:
            return {name: "行为待补充。" for name in names}
    if fallback:
        return fallback
    return {
        "主角": "在家人陪伴下逐步恢复并推进行动。",
        "义父": "持续安排日常照护与行程准备。",
        "阿爸": "处理现实事务并协同家庭安排。",
        "阿妈": "整理生活物品并稳定家人情绪。",
    }


def _coerce_story_map(raw: Any, fallback: Dict[str, str]) -> Dict[str, str]:
    k_start = "开始"
    k_dev = "发展"
    k_climax = "高潮"
    k_end = "结局"

    if isinstance(raw, dict):
        start = _pick_dict_value(raw, (k_start, "起因", "开篇", "序章"))
        develop = _pick_dict_value(raw, (k_dev, "过程", "中段", "发展阶段"))
        climax = _pick_dict_value(raw, (k_climax, "转折", "冲突", "高点"))
        ending = _pick_dict_value(raw, (k_end, "结尾", "收束", "落点"))
        return {
            k_start: _first_non_empty(start, fallback.get(k_start, "")),
            k_dev: _first_non_empty(develop, fallback.get(k_dev, "")),
            k_climax: _first_non_empty(climax, fallback.get(k_climax, "")),
            k_end: _first_non_empty(ending, fallback.get(k_end, "")),
        }

    if isinstance(raw, str) and raw.strip():
        segs = _split_sentences(raw)
        return {
            k_start: segs[0] if len(segs) > 0 else fallback.get(k_start, ""),
            k_dev: " ".join(segs[1:3]).strip() if len(segs) > 1 else fallback.get(k_dev, ""),
            k_climax: segs[3] if len(segs) > 3 else fallback.get(k_climax, ""),
            k_end: segs[-1] if len(segs) > 1 else fallback.get(k_end, ""),
        }

    return {
        k_start: fallback.get(k_start, ""),
        k_dev: fallback.get(k_dev, ""),
        k_climax: fallback.get(k_climax, ""),
        k_end: fallback.get(k_end, ""),
    }


def _extract_summary_items_from_obj(obj: Any) -> List[Dict[str, Any]]:
    main_key = "主要人物和他们的行为"
    story_key = "故事"
    content_key = "内容"
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if "小说梗概" in obj:
            inner = obj["小说梗概"]
            if isinstance(inner, dict):
                return [inner]
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
        if main_key in obj or story_key in obj or content_key in obj:
            return [obj]
    return []


def _parse_summary_obj(text: str) -> Optional[Any]:
    s = _strip_fences(text)
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(s)
        except Exception:
            pass
    return None


def _get_last_user_content(messages: List[Dict[str, str]]) -> str:
    for msg in reversed(messages):
        if msg.get("role") == "user":
            return msg.get("content", "")
    return ""


def _extract_section(user_text: str, label: str) -> str:
    pattern = rf"\*\*{re.escape(label)}\*\*\s*[:：]\s*([\s\S]*?)(?=\n\s*\*\*[^*]+\*\*\s*[:：]|\Z)"
    matches = list(re.finditer(pattern, user_text, re.IGNORECASE))
    if matches:
        return matches[-1].group(1).strip()

    marker_pattern = rf"(?m)^\s*{re.escape(label)}\s*[:：]\s*"
    marker_matches = list(re.finditer(marker_pattern, user_text))
    if marker_matches:
        marker_match = marker_matches[-1]
        tail = user_text[marker_match.end():]
        lines = tail.splitlines()
        collected: List[str] = []
        for idx, raw_line in enumerate(lines):
            line = raw_line.rstrip()
            if idx > 0 and re.match(r"^\s*(?:\*\*[^*]+\*\*|[一-鿿A-Za-z0-9_/／（）() \-]{1,50})\s*[:：]\s*", line):
                break
            collected.append(line)
        value = "\n".join(collected).strip()
        if value:
            return value
    return ""


def _extract_section_any(user_text: str, labels: Sequence[str]) -> str:
    for label in labels:
        value = _extract_section(user_text, label)
        if value:
            return value
    return ""


def _parse_categories(text: str) -> List[str]:
    def _clean(items: Sequence[str]) -> List[str]:
        out: List[str] = []
        seen = set()
        for item in items:
            c = str(item or "").strip()
            if not c:
                continue
            # Filter prompt leakage and long noisy fragments.
            if len(c) > 14:
                continue
            if any(x in c for x in ("请根据", "以上信息", "生成", "输出", "输入", "小说标题", "分类")) and len(c) > 6:
                continue
            if re.search(r"[。.!?：:\n\r]", c):
                continue
            if c in seen:
                continue
            seen.add(c)
            out.append(c)
        return out[:3]

    raw = text.strip()
    if not raw:
        return []
    for parser in (ast.literal_eval, json.loads):
        try:
            obj = parser(raw)
            if isinstance(obj, list):
                out = [str(x).strip() for x in obj if str(x).strip()]
                if out:
                    cleaned = _clean(out)
                    if cleaned:
                        return cleaned
        except Exception:
            pass
    cleaned = raw.replace("[", " ").replace("]", " ").replace("'", " ").replace('"', " ")
    parts = re.split(r"[,，;；/|、]", cleaned)
    return _clean([p.strip() for p in parts if p.strip()])


def _extract_summary_prompt_fields(user_text: str) -> Dict[str, Any]:
    title_labels = ("小说标题", "小说名称", "标题", "书名")
    category_labels = ("分类/标签", "分类标签", "题材标签", "分类", "题材", "标签")
    revision_direction_labels = ("换稿方向", "改稿方向", "用户不满意点", "本次换稿要求")
    revision_seed_labels = ("换稿批次", "改稿批次", "生成批次", "随机种子")
    intro_labels = (
        "情节简介",
        "故事简介",
        "小说简介",
        "简介",
        "故事提要",
        "梳概",
        "小说梗概",
    )
    world_labels = ("世界设定", "故事背景", "背景", "世界观")
    char_labels = ("角色名单", "人物信息", "主要人物", "人物")

    title = _extract_section_any(user_text, title_labels)
    categories_raw = _extract_section_any(user_text, category_labels)
    intro = _extract_section_any(user_text, intro_labels)
    world = _extract_section_any(user_text, world_labels)
    characters_raw = _extract_section_any(user_text, char_labels)

    if intro:
        # Cut away prompt-format instructions that often appear after intro block.
        cut_patterns = [
            r"(?m)^\s*####\s*输出.*$",
            r"(?m)^\s*输出\s*[:：].*$",
            r"(?m)^\s*请按固定结构返回.*$",
            r"(?m)^\s*请生成小说梗概.*$",
        ]
        for pat in cut_patterns:
            intro = re.split(pat, intro, maxsplit=1)[0]
        intro = re.sub(r"(?m)^\s*请根据.*$", "", intro).strip()
        intro = re.sub(r"\n{3,}", "\n\n", intro)

    categories = _parse_categories(categories_raw)
    world = _clean_linebreaks(str(world or "")).strip()
    if world and intro:
        intro = _clean_linebreaks(f"{world}\n{intro}")
    elif world and not intro:
        intro = world

    return {
        "title": title,
        "categories": categories,
        "intro": intro,
        "world": world,
        "characters_raw": characters_raw,
    }


def _extract_info_prompt_fields(user_text: str) -> Dict[str, Any]:
    def _parse_info_tags(text: str, max_items: int = 8, max_len: int = 24) -> List[str]:
        raw = str(text or "").strip()
        if not raw:
            return []

        def _clean(items: Sequence[str]) -> List[str]:
            out: List[str] = []
            seen = set()
            for item in items:
                value = str(item or "").strip().strip("'\"[]")
                if not value:
                    continue
                if len(value) > max_len:
                    continue
                if re.search(r"[\n\r]", value):
                    continue
                if value in seen:
                    continue
                seen.add(value)
                out.append(value)
                if len(out) >= max_items:
                    break
            return out

        for parser in (ast.literal_eval, json.loads):
            try:
                obj = parser(raw)
                if isinstance(obj, list):
                    cleaned = _clean([str(x) for x in obj])
                    if cleaned:
                        return cleaned
            except Exception:
                pass

        parts = re.split(r"[,，;；/\|、]+", raw)
        return _clean(parts)

    title_labels = ("小说标题", "小说名称", "标题", "书名")
    category_labels = ("分类/标签", "分类标签", "题材标签", "分类", "题材", "标签")
    revision_direction_labels = ("换稿方向", "改稿方向", "用户不满意点", "本次换稿要求")
    revision_seed_labels = ("换稿批次", "改稿批次", "生成批次", "随机种子")
    previous_draft_labels = (
        "上一版底稿（如果存在，本次需要保留标题与标签约束，但避免复刻人物组合、主舞台、核心冲突表达和简介展开方式）",
        "上一版底稿",
        "上版底稿",
        "上一稿",
        "上版内容",
    )
    tag_groups = {
        "length": ("篇幅", "篇幅定位"),
        "style": ("风格", "文风", "写作风格"),
        "era": ("时代背景", "时代", "时代定位"),
        "world": ("世界设定", "世界观", "背景设定"),
        "genre": ("题材", "分类题材"),
        "creative": ("创作关键词", "关键词", "用户关键词"),
        "tone": ("情绪基调", "基调", "氛围"),
        "scene": ("场景方向", "场景", "场域"),
        "relation": ("人物关系", "关系设定"),
        "driver": ("剧情驱动", "主线驱动", "剧情推进"),
        "elements": ("核心元素", "核心卖点", "关键元素"),
    }

    title = _extract_section_any(user_text, title_labels).strip()
    categories_raw = _extract_section_any(user_text, category_labels).strip()
    categories = _parse_categories(categories_raw)

    tag_map: Dict[str, List[str]] = {}
    for key, labels in tag_groups.items():
        tag_map[key] = _parse_info_tags(_extract_section_any(user_text, labels))

    if not tag_map.get("genre"):
        tag_map["genre"] = list(categories)

    all_tags: List[str] = []
    for values in tag_map.values():
        for value in values:
            if value not in all_tags:
                all_tags.append(value)

    return {
        "title": title,
        "categories": categories,
        "tag_map": tag_map,
        "all_tags": all_tags,
        "revision_direction": _clean_linebreaks(_extract_section_any(user_text, revision_direction_labels))[:180],
        "revision_seed": _clean_linebreaks(_extract_section_any(user_text, revision_seed_labels))[:80],
        "previous_draft": _clean_linebreaks(_extract_section_any(user_text, previous_draft_labels))[:1800],
    }


def _extract_markdown_section(text: str, label: str) -> str:
    if not text:
        return ""
    pattern = rf"\*\*{re.escape(label)}\*\*\s*[:：]\s*([\s\S]*?)(?=\n\s*\*\*[^*]+\*\*\s*[:：]|\Z)"
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return ""
    return m.group(1).strip()


def _clean_linebreaks(text: str) -> str:
    s = str(text or "").strip()
    s = s.replace("\r", "\n")
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _single_quote_list(names: Sequence[str]) -> str:
    cleaned: List[str] = []
    for x in names:
        v = str(x).strip()
        if not v:
            continue
        if v not in cleaned:
            cleaned.append(v)
    if not cleaned:
        cleaned = ["主角", "关键配角A", "关键配角B"]
    return "[" + ", ".join(f"'{_escape_single(x)}'" for x in cleaned) + "]"


COMMON_CHINESE_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褊卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喁柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝鹌安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昅管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉钮龚程嵇邢滑裴陆荣翁荠羊甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璇桑桂濮牛寿通边扈燕冀郏浦尚农温别庄晏柴瞿阎充慕连茹习宦艾鱼容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越头隆师巩厩聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权速盖益桓公"
)
COMMON_TWO_CHAR_SURNAMES = {
    "欧阳", "司马", "上官", "司徒", "诸葛", "东方", "皇甫", "尉迟",
    "公孙", "慕容", "仲孙", "钟离", "长孙", "宇文", "司寇", "南宫",
    "夏侯", "进于", "公羊", "赫连", "澄台", "公冶", "宗政", "濮阳",
    "淮于", "单于", "太史", "申屠", "公仪", "轩辕", "令狐", "钟离",
}
TITLE_FRAGMENT_BAD_TAIL_CHARS = set("里中上下间外内前后边侧处")
NON_PERSON_NAME_PREFIXES = set("和与在把被将对向从为因由让使给")
NON_PERSON_NAME_WORDS = {
    "关系锚",
    "关系锚点",
    "和在立",
    "和是家",
    "和旧社",
    "家族或",
    "边军",
    "内廷",
    "港务",
    "民间",
    "官方",
    "灰色",
    "旧案",
    "真相",
    "证据",
    "线索",
    "资源",
    "阵营",
    "人物",
    "主线",
    "阶段",
    "风险",
    "局势",
    "关系",
    "成员",
    "交集",
    "景交集",
    "关系边",
    "拓扑",
    "节点",
    "边缘",
    "段未解",
    "程师",
    "数据员",
    "工程师",
    "监察员",
    "关键事",
    "曾与梁",
}
NON_PERSON_NAME_FRAGMENTS = (
    "关系锚",
    "关系",
    "关系失",
    "家族或",
    "家族",
    "阵营",
    "立场上",
    "旧案牵",
    "旧社团",
    "共同旧",
    "核心阵",
    "交集",
    "关系边",
    "拓扑",
    "节点",
    "未解",
    "解码",
)


def _has_plausible_person_surname(name: str) -> bool:
    n = str(name or "").strip()
    if not n or not re.fullmatch(r"[一-鿿]{2,4}", n):
        return False
    if len(n) >= 4 and n[:2] not in COMMON_TWO_CHAR_SURNAMES:
        return False
    if n[:2] in COMMON_TWO_CHAR_SURNAMES:
        return True
    return n[0] in COMMON_CHINESE_SURNAMES


def _is_safe_title_lead_name_fragment(name: str, title: str) -> bool:
    n = str(name or "").strip()
    t = str(title or "").strip()
    if not n or not t or not t.startswith(n + "的"):
        return False
    if n[-1] in TITLE_FRAGMENT_BAD_TAIL_CHARS:
        return False
    return _has_plausible_person_surname(n)


def _is_valid_person_name(name: str, title: str = "") -> bool:
    n = str(name or "").strip().strip("'\"")
    if not n:
        return False
    if title and n == str(title).strip():
        return False
    if title and n in str(title).strip() and not _is_safe_title_lead_name_fragment(n, title):
        return False
    if title and str(title).strip().startswith(n + "的") and not _is_safe_title_lead_name_fragment(n, title):
        return False
    if len(n) < 2 or len(n) > 8:
        return False
    if n in NON_PERSON_NAME_WORDS:
        return False
    if n[0] in NON_PERSON_NAME_PREFIXES:
        return False
    if any(fragment in n for fragment in NON_PERSON_NAME_FRAGMENTS):
        return False
    if n in {"主角", "关键配角A", "关键配角B"}:
        return False
    if len(n) == 2 and n[-1] in "师员者队站局港塔":
        return False
    if len(n) >= 3 and re.search(r"(未解|解码|数据|工程|监察|救援|维修)", n):
        return False
    if re.search(r"[,，。！？:：;；\[\]{}()<>《》#@/\\]", n):
        return False
    bad_fragments = (
        "小说",
        "故事",
        "简介",
        "背景",
        "情节",
        "奇遇",
        "之旅",
        "请根据",
        "信息",
        "融合",
        "推进",
        "展开",
    )
    if any(x in n for x in bad_fragments):
        return False
    if re.fullmatch(r"[一-鿿]{2,3}", n) and _has_plausible_person_surname(n):
        return True
    if "·" in n and re.fullmatch(r"[一-鿿·]{2,8}", n):
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z .'-]{1,20}", n):
        return True
    return False


def _normalize_person_names(names: Sequence[str], title: str = "", max_count: int = 8) -> List[str]:
    out: List[str] = []
    for item in names:
        n = str(item or "").strip().strip("'\"")
        if not _is_valid_person_name(n, title=title):
            continue
        if n in out:
            continue
        out.append(n)
        if len(out) >= max_count:
            break
    return out


def _build_default_person_names(title: str, categories: Sequence[str], count: int = 6) -> List[str]:
    title = str(title or "").strip()
    cat_text = "、".join(str(x) for x in categories if isinstance(x, str))
    name_banks = {
        "wuxia": [
            ["谢临川", "顾长晏", "沈知衡", "陆清辞", "裴行舟", "秦昭宁", "苏砚秋", "林疏月"],
            ["萧听雪", "叶问山", "白照野", "宁停云", "温书遥", "段归岚", "顾怀山", "沈行止"],
            ["柳怀真", "裴照川", "秦问舟", "苏停云", "林知遥", "谢砚秋", "顾闻雪", "陆归岚"],
        ],
        "history": [
            ["谢怀瑾", "顾承砚", "沈知衡", "陆清辞", "裴闻策", "秦昭临", "苏砚臣", "林归棠"],
            ["贺长晏", "崔行舟", "温照临", "晏怀远", "柳承安", "顾砚秋", "谢观衡", "沈景辞"],
            ["陆闻川", "裴照临", "苏知策", "林归远", "秦承砚", "崔砚之", "温临川", "柳长宁"],
        ],
        "urban": [
            ["林以宁", "沈南乔", "周临安", "程清屿", "顾见微", "宋知遥", "陈叙南", "苏时安"],
            ["许观澜", "陆意深", "江照棠", "季闻夏", "方知远", "乔清和", "周予安", "程明序"],
            ["沈听岚", "顾言川", "林叙舟", "陈知晗", "宋景澄", "许安禾", "苏见川", "陆星野"],
        ],
        "youth": [
            ["季安然", "江叙白", "林念初", "程知远", "许清禾", "顾晚意", "张予安", "陆晏明"],
            ["周嘉树", "沈星遥", "苏今棠", "陈听夏", "林景初", "程明栀", "许嘉屿", "顾知夏"],
            ["江言澈", "季听澜", "周念禾", "陈叙辰", "陆安可", "沈知暖", "林嘉遥", "程向晚"],
        ],
        "noir": [
            ["沈砚川", "顾既明", "林见深", "周渡川", "许危舟", "程夜澜", "宋观潮", "陈叙白"],
            ["裴临渊", "秦雁回", "陆照野", "苏沉川", "谢闻洲", "乔夜泊", "顾沉砚", "林既白"],
            ["周叙川", "许照临", "陈见舟", "沈夜行", "宋临潮", "裴闻渡", "程雁沉", "秦观野"],
            ["陆危岚", "谢照临", "苏听潮", "顾沉屿", "林见潮", "周闻川", "乔鸣潮", "陈闻砚"],
            ["沈观潮", "顾临舟", "林叙白", "周照野", "许闻川", "程见深", "宋既明", "陈渡临"],
            ["裴见深", "秦夜行", "陆叙川", "苏观岚", "谢沉野", "乔闻野", "顾听潮", "林渡川"],
        ],
        "sci": [
            ["祁星衡", "林序光", "周界川", "程以曜", "顾临穹", "宋折野", "陈观澜", "苏沉轨"],
            ["陆微冕", "秦霁航", "谢昭穹", "裴昼临", "闻澄界", "韩引川", "周序衡", "林曜辰"],
            ["程界衡", "顾观穹", "宋临界", "陈澄野", "苏星河", "陆霁临", "秦序航", "谢引曜"],
        ],
    }

    if any(k in cat_text for k in ("仙侠", "武侠", "玄幻", "历史")):
        bank_groups = name_banks["history"] if "历史" in cat_text else name_banks["wuxia"]
    elif any(k in cat_text for k in ("悬疑", "推理", "刑侦", "惊悚", "恐怖", "志怪", "克苏鲁")):
        bank_groups = name_banks["noir"]
    elif any(k in cat_text for k in ("科幻", "赛博朋克", "星际", "机甲", "未来", "近未来", "未来都市", "星际时代")):
        bank_groups = name_banks["sci"]
    elif any(k in cat_text for k in ("青春", "言情", "校园")):
        bank_groups = name_banks["youth"]
    else:
        bank_groups = name_banks["urban"]

    seed_text = f"{title}|{cat_text}|{count}"
    seed = int(hashlib.md5(seed_text.encode("utf-8")).hexdigest(), 16)
    primary = seed % len(bank_groups)
    secondary = (seed // 17) % len(bank_groups)
    if secondary == primary and len(bank_groups) > 1:
        secondary = (secondary + 1) % len(bank_groups)
    tertiary = (seed // 29) % len(bank_groups)
    while len(bank_groups) > 2 and tertiary in (primary, secondary):
        tertiary = (tertiary + 1) % len(bank_groups)
    primary_pool = list(bank_groups[primary])
    secondary_pool = list(bank_groups[secondary])
    tertiary_pool = list(bank_groups[tertiary]) if len(bank_groups) > 2 else list(bank_groups[primary])
    start_primary = (seed // 7) % len(primary_pool)
    start_secondary = (seed // 13) % len(secondary_pool)
    start_tertiary = (seed // 23) % len(tertiary_pool)
    mixed_pool: List[str] = []
    for idx in range(max(len(primary_pool), len(secondary_pool), len(tertiary_pool))):
        mixed_pool.append(primary_pool[(start_primary + idx) % len(primary_pool)])
        mixed_pool.append(secondary_pool[(start_secondary + idx) % len(secondary_pool)])
        mixed_pool.append(tertiary_pool[(start_tertiary + idx) % len(tertiary_pool)])
    unique_pool = list(dict.fromkeys(mixed_pool))
    ranked_pool = sorted(
        unique_pool,
        key=lambda name: hashlib.md5(f"{seed_text}|{name}".encode("utf-8")).hexdigest(),
    )

    out: List[str] = []
    m = re.search(r"([一-鿿]{2,4})的", title)
    if m:
        n = m.group(1)
        if _is_safe_title_lead_name_fragment(n, title) and _is_valid_person_name(n, title=title):
            out.append(n)

    # Split the ranked pool into title-specific buckets so same-genre titles are less
    # likely to pull the same front-loaded names in the same order.
    bucket_count = max(1, min(count, len(ranked_pool)))
    buckets = [ranked_pool[i::bucket_count] for i in range(bucket_count)]
    for idx, bucket in enumerate(buckets):
        if not bucket:
            continue
        pick_index = int(hashlib.md5(f"{seed_text}|bucket|{idx}".encode("utf-8")).hexdigest(), 16) % len(bucket)
        name = bucket[pick_index]
        if name not in out and _is_valid_person_name(name, title=title):
            out.append(name)
        if len(out) >= count:
            break
    if len(out) < count:
        for name in ranked_pool:
            if name not in out and _is_valid_person_name(name, title=title):
                out.append(name)
            if len(out) >= count:
                break

    return out[:count]


def _parse_character_names(raw: str, title: str = "") -> List[str]:
    text = _clean_linebreaks(raw)
    if not text:
        return []

    candidates: List[str] = []

    # Prefer explicit list-like content.
    list_match = re.search(r"\[[\s\S]*\]", text)
    if list_match:
        list_text = list_match.group(0).strip()
        for parser in (ast.literal_eval, json.loads):
            try:
                obj = parser(list_text)
                if isinstance(obj, list):
                    for item in obj:
                        n = str(item).strip().strip("'\"")
                        if n and n not in candidates:
                            candidates.append(n)
                    filtered = _normalize_person_names(candidates, title=title, max_count=8)
                    if filtered:
                        return filtered
            except Exception:
                pass

    # Try quoted names fallback.
    for q in re.findall(r"['\"]([一-鿿A-Za-z0-9_]{2,12})['\"]", text):
        n = str(q).strip()
        if n and n not in candidates:
            candidates.append(n)
    filtered = _normalize_person_names(candidates, title=title, max_count=8)
    if filtered:
        return filtered

    # Split free text.
    split_parts = re.split(r"[,，、/\|\s]+", text)
    for p in split_parts:
        n = p.strip().strip("'\"[]")
        if not n:
            continue
        if re.fullmatch(r"[一-鿿A-Za-z0-9_]{2,12}", n) and n not in candidates:
            candidates.append(n)
    filtered = _normalize_person_names(candidates, title=title, max_count=8)
    if filtered:
        return filtered

    # Title-based fallback (only "X的..." pattern).
    m = re.search(r"([一-鿿]{2,4})的", title)
    if m and _is_safe_title_lead_name_fragment(m.group(1), title):
        protagonist = m.group(1)
        filtered = _normalize_person_names([protagonist, "沈青禾", "陆临川"], title=title, max_count=8)
        if filtered:
            return filtered

    return []


def _extract_name_candidates(title: str, intro: str, categories: Sequence[str]) -> List[str]:
    candidates: List[str] = []
    cat_set = {x.strip() for x in categories if isinstance(x, str) and x.strip()}
    stop_words = {
        "小说", "故事", "情节", "简介", "标题", "分类", "主角", "人物",
        "家人", "父亲", "母亲", "陌生人", "故乡", "旅程", "新生", "成长",
        "现实", "青春", "文学", "信息", "提供", "根据", "输出", "最终",
        "开始", "发展", "高潮", "结局", "重生",
    }
    bad_tail_chars = set("被在与和向对将把了着过中后前上下里来去")
    bad_name_fragments = (
        "发现",
        "经历",
        "恢复",
        "陪伴",
        "告别",
        "踏上",
        "迎来",
        "努力",
        "带到",
        "相认",
    )

    def _add_name(name: str) -> None:
        n = str(name).strip()
        if not n or n in candidates:
            return
        if not _is_valid_person_name(n, title=title):
            return
        if n in stop_words or n in cat_set:
            return
        if n[-1] in bad_tail_chars:
            return
        if any(frag in n for frag in bad_name_fragments):
            return
        if any(w in n for w in ("小说", "故事", "情节", "简介", "重生", "新生")):
            return
        candidates.append(n)

    m = re.search(r"([一-鿿]{2,4})的", title)
    if m and _is_safe_title_lead_name_fragment(m.group(1), title):
        _add_name(m.group(1))

    name_counts: Dict[str, int] = {}
    for token in re.findall(r"[一-鿿]{2,3}", intro):
        if token in stop_words or token in cat_set:
            continue
        if token[-1] in bad_tail_chars:
            continue
        if any(frag in token for frag in bad_name_fragments):
            continue
        if token[0] not in COMMON_CHINESE_SURNAMES:
            continue
        name_counts[token] = name_counts.get(token, 0) + 1

    for token, freq in sorted(name_counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if freq >= 2:
            _add_name(token)
        if len(candidates) >= 6:
            break

    if any(k in intro for k in ("父亲", "爸爸", "父母", "家人")):
        _add_name("义父")
        _add_name("阿爸")
    if any(k in intro for k in ("母亲", "妈妈", "父母", "家人")):
        _add_name("阿妈")

    if len(candidates) < 3:
        for n in _build_default_person_names(title, categories, count=6):
            if n not in candidates:
                candidates.append(n)
            if len(candidates) >= 6:
                break

    # Avoid role-only candidate lists (e.g. only 义父/阿爸/阿妈).
    role_like = {"义父", "阿爸", "阿妈", "父亲", "母亲", "哥哥", "姐姐", "弟弟", "妹妹"}
    if candidates and not any(name not in role_like for name in candidates):
        enriched: List[str] = []
        for n in _build_default_person_names(title, categories, count=6):
            if n not in enriched:
                enriched.append(n)
        for n in candidates:
            if n not in enriched:
                enriched.append(n)
        candidates = enriched[:6]

    return candidates[:6]


def _clean_behavior_sentence(sentence: str) -> str:
    s = sentence.strip()
    if not s:
        return ""

    s = re.sub(r"《[^》]{1,60}》", "", s)
    s = re.sub(r"\*\*[^*]+\*\*", "", s)
    s = re.sub(r"\s+", "", s)

    s = re.sub(r"^(小说标题|分类|情节简介|故事简介|简介)[:：]?", "", s)
    s = re.sub(r"^(请根据|根据以上信息).*$", "", s)

    banned_role_patterns = [
        r"(作为|身为|担任|负责|承担|扮演)[^。！？；;，,]{0,18}(角色|作用|职责|功能)",
        r"(是|属于)[^。！？；;，,]{0,14}(主角|配角|核心人物|关键人物)",
        r"(主要|核心)?(角色|人物)之一",
    ]
    for pat in banned_role_patterns:
        s = re.sub(pat, "", s)

    replacements = {
        "通过通过": "通过",
        "把把": "把",
        "在在": "在",
        "他他": "他",
        "她她": "她",
    }
    for old, new in replacements.items():
        s = s.replace(old, new)

    s = s.strip("。，！？；,:;!?“”‘’\"'()[]{}【】《》")
    return s


def _looks_like_summary_behavior_pollution(name: str, behavior: str, intro: str) -> bool:
    text = _clean_behavior_sentence(behavior)
    if not text:
        return True
    generic_markers = (
        "故事围绕",
        "以" + name + "为叙事中心",
        "融合",
        "在这一设定中",
        "人物在谜团",
        "主角组",
        "情感折返",
        "阅读体验",
        "长线剧情",
        "阶段性结局",
    )
    if any(marker in text for marker in generic_markers):
        return True
    if len(text) > 110 and _text_similarity(text, intro) >= 0.58:
        return True
    return False


def _dedupe_sentences(sentences: Sequence[str]) -> List[str]:
    out: List[str] = []
    for s in sentences:
        t = s.strip()
        if not t:
            continue
        if any(t == x or t in x for x in out):
            continue
        out = [x for x in out if x not in t]
        out.append(t)
    return out


def _text_similarity(a: str, b: str) -> float:
    left = _clean_behavior_sentence(str(a or ""))
    right = _clean_behavior_sentence(str(b or ""))
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _ensure_period(text: str) -> str:
    s = text.strip()
    if not s:
        return s
    s = re.sub(r"[?？!！]+$", "。", s)
    if s and s[-1] not in "。！？!?":
        s += "。"
    return s


def _extract_clean_clauses(text: str, min_len: int = 6) -> List[str]:
    clauses = [_clean_behavior_sentence(x) for x in _split_clauses(text)]
    clauses = [x for x in clauses if x and len(x) >= min_len]
    return _dedupe_sentences(clauses)


TEXT_SOURCE_NOISE_MARKERS = (
    "主要人物和他们的行为",
    "故事情节",
    "直接输出小说正文",
    "请根据以上信息",
    "输出要求",
    "章节标题",
    "细纲内容",
    "静态关系铁律",
    "章尾要",
    "章末要",
    "尾声要",
    "收束时要",
    "本章要",
    "静态关系不变",
    "角色职能定位",
    "剧情推进逻辑",
    "关系恒定",
    "核心冲突",
    "节奏把控",
    "人物关系拓扑",
    "关系拓扑",
    "关系边偏向",
    "人物关系网应",
    "静态人物关系",
    "static_initial_topology",
    "stage_policy",
    "topology",
    "nodes",
    "edges",
    "source",
    "家族/血缘",
    "不可更改",
    "将抽象",
    "落地为具体",
    "卷名：",
    "核心目标：",
    "人物映射",
    "实际主角",
    "对应：",
    "':{",
    '":{',
    "': {",
    ":{",
    "###",
    "```",
)


def _looks_like_text_source_noise(clause: str) -> bool:
    value = _clean_linebreaks(str(clause or "")).strip()
    if not value:
        return True
    if any(marker in value for marker in TEXT_SOURCE_NOISE_MARKERS):
        return True
    if re.match(r"^\s*\d+\s*[.、:：]", value):
        return True
    if re.search(r"[：:]\s*\d+\s*[.、:：]", value):
        return True
    if re.search(r"(^|\n|\s)\d+\s*[.、:：]\s*(静态关系|关系恒定|角色职能|剧情推进|核心冲突|节奏把控)", value):
        return True
    if any(ch in value for ch in ("{", "}", "[", "]", "`")):
        return True
    if re.search(r"(主要人物|他们的行为|故事情节|细纲内容|章节标题|内容)\s*[:：]", value):
        return True
    return False


def _extract_narrative_source_clauses(text: str, min_len: int = 6) -> List[str]:
    return [clause for clause in _extract_clean_clauses(text, min_len=min_len) if not _looks_like_text_source_noise(clause)]


def _filter_summary_content(content: str, locked_names: Sequence[str], title: str = "") -> str:
    locked_order = [str(name).strip() for name in locked_names if str(name).strip()]
    locked = set(locked_order)
    title_text = str(title or "").strip()
    title_fragments = {
        title_text[-size:]
        for size in (2, 3, 4)
        if len(title_text) > size and title_text[-size:]
    }
    cleaned_content = _normalize_locked_name_variants(str(content or ""), locked_order)
    if locked_order:
        primary = locked_order[0]
        same_surname_relatives = [
            name for name in locked_order[1:] if len(name) >= 2 and len(primary) >= 2 and name[0] == primary[0]
        ]
        kinship_target = same_surname_relatives[0] if same_surname_relatives else ""

        def fix_story_name(match: re.Match[str]) -> str:
            candidate = match.group(0)
            if candidate in locked:
                return candidate
            if len(candidate) != len(primary) or candidate[0] != primary[0]:
                return candidate
            prev = cleaned_content[max(0, match.start() - 8) : match.start()]
            if kinship_target and re.search(r"(父亲|生父|父女|父子|父亲的|父亲在)$", prev):
                return kinship_target
            return primary

        candidates = sorted(
            set(re.findall(rf"{re.escape(primary[0])}[一-鿿]{{{max(1, len(primary) - 1)}}}", cleaned_content)),
            key=len,
            reverse=True,
        )
        non_name_suffix = set("凭正主开意发站险被与因在到将把虽会了的借")
        for candidate in candidates:
            if candidate in locked or len(candidate) != len(primary):
                continue
            if candidate[-1] in non_name_suffix:
                continue
            if len(candidate) >= 2 and candidate[1] in {"家", "氏", "某"}:
                continue
            cleaned_content = re.sub(re.escape(candidate), fix_story_name, cleaned_content)
        for name in locked_order:
            if len(name) >= 2:
                cleaned_content = cleaned_content.replace(f"{name}{name[-1]}", name)
                cleaned_content = re.sub(rf"{re.escape(name)}[澜岚阑栏鸾峦叶](?=[、，。；;\s])", name, cleaned_content)
        if primary:
            cleaned_content = re.sub(rf"{re.escape(primary[0])}[一-鿿]在[澜岚阑栏鸾峦](?=[险，,。；;\s])", primary, cleaned_content)
            if kinship_target:
                cleaned_content = re.sub(rf"{re.escape(primary[0])}[一-鿿]在叶(?=[虽，,。；;\s])", kinship_target, cleaned_content)
        for name in locked_order:
            if len(name) == 2:
                cleaned_content = re.sub(rf"[一-鿿]{re.escape(name[1])}(?=凭|会|悲悯|，|,|。)", name, cleaned_content)
    for fragment in title_fragments:
        if fragment and fragment != title_text:
            cleaned_content = re.sub(rf"[^，。；！？\n]{{0,80}}{re.escape(fragment)}这类[^，。；！？\n]{{0,160}}[，。；！？]?", "", cleaned_content)
    cleaned_content = re.sub(r"[^，。；！？\n]{0,80}(关键事|曾与梁|段未解|程师)这类[^，。；！？\n]{0,160}[，。；！？]?", "", cleaned_content)
    cleaned_content = re.sub(r"[^，。；！？\n]{0,80}(关键事|曾与梁|段未解|程师)[^，。；！？\n]{0,120}(支点|误判|推进|合作|节点)[^，。；！？\n]{0,120}[，。；！？]?", "", cleaned_content)
    cleaned_content = re.sub(r"[^，。；！？\n]{0,80}(关系边偏向|人物关系网应|relation_type|stage_policy|static_initial_topology)[^，。；！？\n]{0,160}[，。；！？]?", "", cleaned_content)
    clean_clauses = []
    for clause in _extract_narrative_source_clauses(cleaned_content, min_len=10):
        if any(marker in clause for marker in ("这类灰度角色", "label", "title", "relation_type", "关系边偏向", "人物关系网应")):
            continue
        if any(marker in clause for marker in ("关键事", "曾与梁", "段未解", "程师")):
            continue
        if any(fragment and fragment != title_text and f"{fragment}这类" in clause for fragment in title_fragments):
            continue
        pseudo_names = _normalize_person_names(_extract_name_candidates(str(title or ""), clause, []), title=str(title or ""), max_count=8)
        if locked and pseudo_names and not any(name in locked for name in pseudo_names):
            continue
        clean_clauses.append(clause)
    if not clean_clauses:
        return _trim_duplicate_tail(cleaned_content)
    return _ensure_period("，".join(_dedupe_sentences(clean_clauses)))


def _strip_text_structural_leakage(text: str) -> str:
    clean = str(text or "")
    indexes = [clean.find(marker) for marker in TEXT_SOURCE_NOISE_MARKERS if marker and clean.find(marker) >= 0]
    if not indexes:
        return clean
    cut_at = min(indexes)
    clean = clean[:cut_at].rstrip("，,；;：:\n ")
    clean = re.sub(r"[^\n。！？!?]{0,80}$", "", clean).rstrip()
    return _ensure_period(clean) if clean else ""


def _merge_clause_texts(*texts: str, min_len: int = 6, max_clauses: int = 18) -> str:
    clauses: List[str] = []
    for text in texts:
        clauses.extend(_extract_clean_clauses(text, min_len=min_len))
    merged = _dedupe_sentences(clauses)
    if not merged:
        return ""
    return _ensure_period("，".join(merged[:max_clauses]))


def _trim_duplicate_tail(text: str) -> str:
    clauses = _extract_clean_clauses(text, min_len=4)
    if not clauses:
        return _ensure_period(_clean_behavior_sentence(text))
    return _ensure_period("，".join(_dedupe_sentences(clauses)))


def _strip_detail_template_pollution(text: str) -> str:
    s = _clean_linebreaks(_sanitize_text(str(text or ""))).strip()
    if not s:
        return ""
    patterns = (
        r"本章标题为[^。\n]{0,40}[。\n]?",
        r"在本卷第\d+/\d+章[^。\n]{0,80}[。\n]?",
        r"场景与氛围[:：]",
        r"主要事件[:：]",
        r"对话要点[:：]",
        r"情感变化[:：]",
        r"章末推进[:：]",
        r"角色执行轨迹[:：]",
        r"协作与掣肈[:：]",
        r"误解-释放-重建",
        r"事件-对话-情绪-钩子",
        r"本卷围绕人物关系重组、目标升级与阶段决策展开",
        r"章末需要落下一个明确结果",
        r"写作时可直接体现",
    )
    for pat in patterns:
        s = re.sub(pat, "", s)
    return _trim_duplicate_tail(s)


_FEMALE_HINT_CHARS = set("雪妍婉婷娜琳薇瑶菲颖莹静柔雅倩彤茜嫣姝媛霏岚茉蕊")
_MALE_HINT_CHARS = set("峰磊强军涛浩鹏宇辰凯杰毅斌博航阳骁霆霖锋盛")
_FEMALE_NAME_TOKENS = (
    "阿妈",
    "母亲",
    "姐",
    "妹",
    "姑",
    "姨",
    "奶",
    "太太",
    "女士",
    "夫人",
    "公主",
)
_MALE_NAME_TOKENS = (
    "阿爸",
    "父亲",
    "哥",
    "弟",
    "叔",
    "伯",
    "爷",
    "公",
    "先生",
    "少爷",
    "王爷",
    "公子",
)
_FEMALE_CONTEXT_TOKENS = (
    "女主",
    "姑娘",
    "小姐",
    "女孩",
    "姐姐",
    "妹妹",
    "母亲",
    "妻子",
    "闺蜜",
)
_MALE_CONTEXT_TOKENS = (
    "男主",
    "少年",
    "男孩",
    "哥哥",
    "弟弟",
    "父亲",
    "丈夫",
    "兄弟",
)


def _score_gender_from_context(name: str, context: str) -> Tuple[int, int]:
    n = str(name or "").strip()
    text = str(context or "")
    if not n or not text:
        return 0, 0

    f_score = 0
    m_score = 0
    esc = re.escape(n)

    # Strong local cues: title/role words near the name.
    for token in _FEMALE_CONTEXT_TOKENS:
        te = re.escape(token)
        f_score += len(re.findall(rf"{esc}.{{0,20}}{te}|{te}.{{0,20}}{esc}", text)) * 4
    for token in _MALE_CONTEXT_TOKENS:
        te = re.escape(token)
        m_score += len(re.findall(rf"{esc}.{{0,20}}{te}|{te}.{{0,20}}{esc}", text)) * 4

    # Direct pronoun adjacency near the name.
    f_score += len(re.findall(rf"{esc}.{{0,4}}她|她.{{0,4}}{esc}", text)) * 3
    m_score += len(re.findall(rf"{esc}.{{0,4}}他|他.{{0,4}}{esc}", text)) * 3

    # Softer signal: small windows around each mention.
    for m in re.finditer(esc, text):
        s = max(0, m.start() - 6)
        e = min(len(text), m.end() + 6)
        window = text[s:e]
        f_score += window.count("她")
        m_score += window.count("他")

    if n in text:
        if any(token in text for token in _FEMALE_CONTEXT_TOKENS):
            f_score += 1
        if any(token in text for token in _MALE_CONTEXT_TOKENS):
            m_score += 1

    return f_score, m_score


def _infer_person_gender(name: str, context: str) -> str:
    n = str(name or "").strip()
    if not n:
        return "unknown"

    f_score = 0
    m_score = 0

    if any(k in n for k in _FEMALE_NAME_TOKENS):
        f_score += 8
    if any(k in n for k in _MALE_NAME_TOKENS):
        m_score += 8

    last = n[-1]
    if last in _FEMALE_HINT_CHARS:
        f_score += 1
    if last in _MALE_HINT_CHARS:
        m_score += 1

    cf, cm = _score_gender_from_context(n, context)
    f_score += cf
    m_score += cm

    if f_score >= m_score + 2:
        return "female"
    if m_score >= f_score + 2:
        return "male"
    return "unknown"


def _replace_name_with_pronoun_after_first(text: str, name: str, gender: str) -> str:
    s = _clean_behavior_sentence(text)
    n = str(name or "").strip()
    if not s or not n:
        return _ensure_period(s)
    first_idx = s.find(n)
    if first_idx < 0:
        return _ensure_period(s)

    if gender == "female":
        pronoun = "她"
    elif gender == "male":
        pronoun = "他"
    else:
        pronoun = "她" if s.count("她") > s.count("他") else "他"
    head = s[: first_idx + len(n)]
    tail = s[first_idx + len(n) :]
    tail = re.sub(re.escape(n), pronoun, tail)
    tail = re.sub(r"(他|她){2,}", pronoun, tail)
    return _ensure_period((head + tail).strip())


def _compose_long_text(base: str, extras: Sequence[str], min_chars: int, max_parts: int = 10) -> str:
    parts: List[str] = []
    base_text = _clean_behavior_sentence(base)
    if base_text:
        parts.append(base_text)
    for item in extras:
        text = _clean_behavior_sentence(item)
        if not text:
            continue
        parts.append(text)

    parts = _dedupe_sentences(parts)
    if not parts:
        return ""

    selected = parts[:max_parts]
    text = _ensure_period("，".join(selected))
    if len(text) >= min_chars:
        return text

    reinforcement = [
        "这条行动线不会停在当下，它会继续改写人物站位和后续推进节奏",
        "每次推进都会带来新的信息增量，并反过来改变各方对目标与风险的判断",
        "阶段目标就算暂时达成，也只会把更高一级的冲突提前抬上来",
    ]
    for item in reinforcement:
        if item not in selected:
            selected.append(item)
        text = _ensure_period("，".join(selected[:max_parts + 3]))
        if len(text) >= min_chars:
            break
    return text


def _build_story_from_intro(intro: str) -> Dict[str, str]:
    k_start = "开始"
    k_dev = "发展"
    k_climax = "高潮"
    k_end = "结局"

    clauses = _extract_clean_clauses(intro, min_len=6)
    if not clauses:
        return {
            k_start: "主角在突发事件后与家人重新相认，生活节奏被打乱。",
            k_dev: "主角在家人陪伴下持续恢复身体状态，并逐步稳定情绪与生活秩序。",
            k_climax: "临近离开故乡时，主角在情感牵续与未来选择之间做出关键决定。",
            k_end: "主角完成告别后带着决心启程，阶段性冲突收束并进入新的生活阶段。",
        }

    def _find_by_keywords(keywords: Sequence[str], reverse: bool = False) -> Optional[str]:
        seq = list(reversed(clauses)) if reverse else clauses
        for c in seq:
            if any(k in c for k in keywords):
                return c
        return None

    start = _find_by_keywords(("被", "意外", "发现", "回到", "重逢", "遭遇", "开始")) or clauses[0]

    dev_candidates = [c for c in clauses if c != start and any(k in c for k in ("恢复", "陪伴", "照顾", "努力", "沟通", "相处", "准备", "逐步", "安慰"))]
    if not dev_candidates:
        dev_candidates = [c for c in clauses if c != start]
    develop = " ".join(dev_candidates[:2]).strip() or start

    climax = _find_by_keywords(("冲突", "纠葛", "分手", "决定", "抒择", "告别", "爆发", "危机", "痛苦"), reverse=True)
    if not climax:
        climax = clauses[-2] if len(clauses) >= 2 else clauses[-1]

    ending = _find_by_keywords(("启程", "新生", "和好", "迎来", "结束", "出发", "踏上", "走向"), reverse=True) or clauses[-1]

    ordered = [start, develop, climax, ending]
    for i in range(len(ordered)):
        if ordered[i] and ordered[i] not in ordered[:i]:
            continue
        for candidate in clauses:
            if candidate not in ordered[:i]:
                ordered[i] = candidate
                break
        if ordered[i] in ordered[:i]:
            ordered[i] = f"{ordered[i]}并推进了后续变化"

    start, develop, climax, ending = ordered

    return {
        k_start: _ensure_period(start),
        k_dev: _ensure_period(develop),
        k_climax: _ensure_period(climax),
        k_end: _ensure_period(ending),
    }


def _merge_name_actions_from_intro(name: str, intro: str) -> str:
    if not intro or not name:
        return ""

    clauses = _extract_clean_clauses(intro, min_len=5)
    matched: List[str] = []
    for c in clauses:
        if name in c:
            matched.append(c)

    if not matched and name in ("义父", "阿爸"):
        matched = [c for c in clauses if any(k in c for k in ("父", "家", "陪", "照顾", "准备"))][:3]
    if not matched and name == "阿妈":
        matched = [c for c in clauses if any(k in c for k in ("母", "妈", "家", "照顾", "安慰"))][:3]

    if not matched:
        return ""

    merged = "，".join(_dedupe_sentences(matched)[:4])
    merged = _clean_behavior_sentence(merged)
    return _ensure_period(merged)


def _enrich_behavior(name: str, text: str) -> str:
    return _ensure_period(_clean_behavior_sentence(text))


def _build_char_map_from_intro(names: Sequence[str], intro: str) -> Dict[str, str]:
    unique_names: List[str] = []
    for name in names:
        n = str(name).strip()
        if n and n not in unique_names:
            unique_names.append(n)
    if not unique_names:
        unique_names = ["主角", "关键同伴", "外部推手", "记录者"]

    role_tracks = [
        (
            "追查最接近真相的线索",
            "会主动核验证词、试出对方反应，把零散信息拽成可继续追查的路线",
            "只要预判失误，整条调查线就会被带偏",
        ),
        (
            "稳住现场和团队秩序",
            "会先处理眼前乱局，帮大家把信息分类、风险排序，不让情绪比问题跑得更快",
            "一旦没接住，局面就会一起塌下去",
        ),
        (
            "打开外部资源和灰色渠道",
            "会在合适的时候拿出人脉、物资和通行条件，让计划真正能落地",
            "外部交易一旦失控，反噸会比谁都先落到他身上",
        ),
        (
            "试探人心与拆解隐瞒",
            "更擅长通过对话、试探和微小反应判断谁在说真话、谁在隐瞒",
            "最危险的时刻往往是在多种可能里误信其中一条",
        ),
        (
            "执行高风险动作",
            "一到关键节点就往前顶，负责抗压、试错、保护和探路",
            "代价往往最先落在自己身上",
        ),
        (
            "整理旧案与新线索",
            "像重组一张被撕碎的地图，会把看似没有关联的人与事重新连起来",
            "真相被拼完之后，很可能比所有人以为的更难接受",
        ),
    ]

    out: Dict[str, str] = {}
    for idx, name in enumerate(unique_names[:8]):
        focus, action_line, pressure_line = role_tracks[idx % len(role_tracks)]
        if idx == 0:
            behavior = (
                f"{name}被迫站到这条主线的最前面，他要做的不只是跟着事件往前跑，"
                f"而是要主动{focus}，{action_line}，同时承担「{pressure_line}」这份最直接的压力。"
            )
        else:
            behavior = (
                f"{name}在这条主线里主要承担“{focus}”这条任务，"
                f"{action_line}，他的价值就在于能在关键时刻把局面往前推半步。"
                f"但只要稍有偏差，{pressure_line}就会立刻反扑到他身上。"
            )
        out[name] = _ensure_period(_clean_behavior_sentence(behavior))
    return out


def _extract_value_by_keys(obj: Any, keys: Sequence[str]) -> Any:
    if not isinstance(obj, dict):
        return None
    for key in keys:
        if key in obj and obj[key] not in (None, ""):
            return obj[key]
    normalized_targets = {
        re.sub(r"[\s`'\"“”‘’_，,。；;：:]+", "", str(key or "")).strip(): key
        for key in keys
    }
    for raw_key, value in obj.items():
        if value in (None, ""):
            continue
        normalized_key = re.sub(r"[\s`'\"“”‘’_，,。；;：:]+", "", str(raw_key or "")).strip()
        if not normalized_key:
            continue
        if normalized_key in normalized_targets:
            return value
        for target in normalized_targets:
            if target and (normalized_key == target or target in normalized_key or normalized_key in target):
                return value
    return None


def _parse_json_object_from_text(text: str) -> Optional[Dict[str, object]]:
    source = _strip_fences(str(text or "").strip())
    candidates = [source]
    match = re.search(r"\{[\s\S]*\}", source)
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(candidate)
            except Exception:
                continue
            if isinstance(parsed, dict):
                return parsed
    return None


def _extract_outline_items_from_obj(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        if "大纲" in obj:
            inner = obj["大纲"]
            if isinstance(inner, dict):
                return [inner]
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
        if "分卷" in obj and isinstance(obj["分卷"], list):
            return [x for x in obj["分卷"] if isinstance(x, dict)]
        if any(k in obj for k in OUTLINE_PERSON_KEYS) or any(k in obj for k in OUTLINE_STORY_KEYS):
            return [obj]
    return []


def _parse_outline_obj(text: str) -> Optional[Any]:
    return _parse_summary_obj(text)


def _story_map_to_content(story_map: Dict[str, str]) -> str:
    if not isinstance(story_map, dict):
        return ""
    parts: List[str] = []
    for key in ("开始", "发展", "高潮", "结局"):
        value = _clean_behavior_sentence(str(story_map.get(key, "")))
        if value:
            parts.append(value)
    parts = _dedupe_sentences(parts)
    if not parts:
        return ""
    text = _ensure_period("，".join(parts[:12]))
    if len(text) < 260:
        extra = [
            "这条主线不只是事件的连接，也是人物关系和利益站位持续变化的过程。",
            "每一步推进都会带来新信息、新阻力和新代价，从而让后续剧情具有更强的连贯性和压迫感。",
        ]
        text = _ensure_period(text + "".join(extra))
    return text


def _replace_occurrences(
    text: str,
    pattern: str,
    replacements: Sequence[str],
    *,
    keep_first: bool = True,
) -> str:
    if not text or not pattern:
        return text
    seen = 0
    rep_idx = 0

    def _repl(match: re.Match[str]) -> str:
        nonlocal seen, rep_idx
        seen += 1
        if keep_first and seen == 1:
            return match.group(0)
        value = replacements[rep_idx % len(replacements)] if replacements else match.group(0)
        rep_idx += 1
        return value

    return re.sub(pattern, _repl, text)


def _reduce_title_repetition(content: str, title: str) -> str:
    if not isinstance(content, str) or not content.strip():
        return content
    t = str(title or "").strip()
    if not t:
        return content

    aliases = ("该小说", "该故事")
    out = content

    quoted = f"《{t}》"
    quoted_pat = re.escape(quoted)
    has_quoted = re.search(quoted_pat, out) is not None
    if has_quoted:
        out = _replace_occurrences(out, quoted_pat, aliases, keep_first=True)

    # Replace plain title mentions while avoiding the quoted form itself.
    bare_pat = rf"(?<!《){re.escape(t)}(?!》)"
    out = _replace_occurrences(out, bare_pat, aliases, keep_first=not has_quoted)
    return out


def _normalize_summary_char_map(
    raw_char_map: Any,
    fallback_char_map: Dict[str, str],
    title: str,
    intro: str,
) -> Dict[str, str]:
    role_whitelist = {
        "义父",
        "阿爸",
        "阿妈",
        "父亲",
        "母亲",
        "哥哥",
        "姐姐",
        "弟弟",
        "妹妹",
    }

    base_map = _coerce_char_map(raw_char_map, fallback_char_map)
    out: Dict[str, str] = {}
    fallback_map = _coerce_char_map(None, fallback_char_map)
    for raw_name, raw_behavior in base_map.items():
        name = str(raw_name).strip().strip("'\"")
        if not name:
            continue
        if title and name == str(title).strip():
            continue
        if name in out:
            continue
        if not _is_valid_person_name(name, title=title) and name not in role_whitelist:
            continue

        behavior = _clean_behavior_sentence(str(raw_behavior or ""))
        raw_behavior_text = behavior
        for marker in (
            "在全书层面不是陪衬人物",
            "持续推动主线升级的关键节点",
            "他的行动会同时改变调查进度、关系站位和代价承担方式",
            "相关行动会同步影响人物关系、资源流向和下一阶段决策边界",
            "不能被其他角色简单替代",
        ):
            behavior = behavior.replace(marker, "")
        behavior = re.sub(r"他（她）", "他", behavior)
        behavior = re.sub(r"\s+", "", behavior).strip("，。；：: ")
        fallback_behavior = _clean_behavior_sentence(str(fallback_map.get(name, "") or ""))
        if any(marker in raw_behavior_text for marker in SUMMARY_TEMPLATE_MARKERS) or "在全书主线里主要，" in behavior:
            if fallback_behavior:
                behavior = fallback_behavior
        if _looks_like_summary_behavior_pollution(name, behavior, intro):
            behavior = fallback_behavior
        if not behavior:
            behavior = _clean_behavior_sentence(_merge_name_actions_from_intro(name, intro))
        if not behavior:
            behavior = f"{name}围绕关键事件持续行动，推动剧情变化"
        if any(_text_similarity(behavior, existing) >= 0.76 for existing in out.values()):
            behavior = fallback_behavior or behavior
        out[name] = _ensure_period(behavior)
        if len(out) >= 8:
            break

    if out:
        return out

    # Final fallback to keep schema always valid.
    fallback = _coerce_char_map(None, fallback_char_map)
    cleaned: Dict[str, str] = {}
    for name, behavior in out.items():
        cleaned[name] = behavior
    for raw_name, raw_behavior in fallback.items():
        name = str(raw_name).strip().strip("'\"")
        if not name or name in cleaned:
            continue
        behavior = _clean_behavior_sentence(str(raw_behavior or "")) or f"{name}参与关键事件并推进剧情"
        cleaned[name] = _ensure_period(behavior)
        if len(cleaned) >= 6:
            break
    return cleaned


def _normalize_summary_content(
    raw_content: Any,
    raw_story: Any,
    fallback_content: str,
    intro: str,
    title: str,
) -> str:
    content = ""
    fallback_content_clean = _trim_duplicate_tail(fallback_content) or _trim_duplicate_tail(intro)

    if isinstance(raw_content, str) and raw_content.strip():
        content = _clean_linebreaks(_sanitize_text(raw_content))
    elif isinstance(raw_content, dict):
        story_map = _coerce_story_map(raw_content, _build_story_from_intro(intro))
        content = _story_map_to_content(story_map)

    if not content:
        if isinstance(raw_story, dict):
            story_map = _coerce_story_map(raw_story, _build_story_from_intro(intro))
            content = _story_map_to_content(story_map)
        elif isinstance(raw_story, str) and raw_story.strip():
            content = _clean_linebreaks(_sanitize_text(raw_story))

    content = re.sub(r"(?m)^\s*(小说梗概|梗概|内容|故事)\s*[:：]\s*", "", content).strip()
    content = content.strip("'\"")
    noise_markers = (
        "请按固定结构返回",
        "人物名:主要行为",
        "完整梗概",
        "#### 输出",
        "####输出",
        "请生成小说梗概",
    )
    if any(marker in content for marker in noise_markers):
        content = ""
    content = _trim_duplicate_tail(content)
    if content:
        generic_markers = (
            "故事围绕",
            "融合都市异能",
            "在这一阶段",
            "人物关系因此",
            "核心冲突也从",
            "为大纲、细纲和正文",
            "从故事围绕",
            "原本只是被动卷入",
            "阶段性高潮",
            "先从故事围绕",
            "组如何在信息极不对称",
            "主角组拿到第一批足以改变局面的成果",
        )
        sentence_count = content.count("。") + content.count("!") + content.count("?")
        if sentence_count <= 1 and len(content) >= 420:
            content = fallback_content_clean
        elif any(marker in content for marker in generic_markers):
            content = fallback_content_clean
        elif "为了追上" in content or "主动入局" in content:
            content = fallback_content_clean
        elif _text_similarity(content, intro) >= 0.74:
            content = fallback_content_clean
    if not content:
        content = fallback_content_clean
    if len(content) < 360:
        expanded = _merge_clause_texts(content, intro, min_len=6, max_clauses=28)
        if expanded:
            content = _trim_duplicate_tail(expanded)
    if len(content) < 420:
        content = _ensure_period(
            content
            + "在这个基础上，故事还需要继续写出人物目标如何一步步被打乱，以及他们为了继续前进不得不付出哪些更具体的代价。"
            + "与此同时，梳理出取舍、裂痕、误判与反扳的连续变化，让梗概不只是概括性陈述，而是真正能支撑后续分卷和细纲拆解的剧情骨架。"
        )
    return content


OUTLINE_CHAR_TEMPLATE_MARKERS = (
    "职责重心会随卷目标变化",
    "核心目的围绕",
    "而不是复述上一卷的原句",
    "形成新的合作或对抗方式",
    "把卷内冲突真正往前推一层",
)

SUMMARY_TEMPLATE_MARKERS = (
    "在全书层面不是陪衬人物",
    "持续推动主线升级的关键节点",
    "他的行动会同时改变调查进度、关系站位和代价承担方式",
    "相关行动会同步影响人物关系、资源流向和下一阶段决策边界",
    "不能被其他角色简单替代",
)

OUTLINE_STORY_TEMPLATE_MARKERS = (
    "卷首不是复述上卷结果",
    "这一段不能只写调查推进",
    "高潮段必须围绕",
    "结局部分要落实",
    "真正把这一卷推到无法轻易回头的位置",
    "让卷首天然带着紧绷的对抗感",
    "推进方向从一开始就带着分岔",
    "不可回退的折点",
    "余波继续往后压",
    "质量纠偏",
    "用户修订方向",
    "围绕质量问题重组",
    "保留已确认的人名",
    "避免只做同义改写",
)

OUTLINE_PROMPT_LEAKAGE_MARKERS = (
    "质量纠偏",
    "用户修订方向",
    "围绕质量问题重组",
    "保留已确认的人名",
    "输出要求",
    "生成要求",
    "固定输出",
    "这是首稿请求",
    "这是换一稿请求",
    "避免只做同义改写",
)


def _strip_repeated_template_phrases(text: str, markers: Sequence[str]) -> str:
    value = _clean_behavior_sentence(str(text or ""))
    if not value:
        return ""
    for marker in markers:
        value = value.replace(marker, "")
    value = re.sub(r"本卷他（她）主要", "本卷主要", value)
    value = re.sub(r"他（她）", "他", value)
    value = re.sub(r"\s+", "", value)
    value = value.strip("，。；：: ")
    value = re.sub(r"(，){2,}", "，", value)
    return value


def _is_templatey_outline_story_text(text: str) -> bool:
    value = _clean_behavior_sentence(str(text or ""))
    if len(value) < 45:
        return True
    if any(marker in value for marker in OUTLINE_STORY_TEMPLATE_MARKERS):
        return True
    return False


def _is_templatey_outline_char_text(text: str) -> bool:
    value = _clean_behavior_sentence(str(text or ""))
    if len(value) < 24:
        return True
    if any(marker in value for marker in OUTLINE_CHAR_TEMPLATE_MARKERS):
        return True
    return False


def _has_outline_prompt_leakage(obj: Any) -> bool:
    value = _clean_linebreaks(str(obj or ""))
    return bool(value and any(marker in value for marker in OUTLINE_PROMPT_LEAKAGE_MARKERS))


def _outline_items_are_too_similar(items: Sequence[Dict[str, Any]]) -> bool:
    story_blobs: List[str] = []
    for item in items:
        story = _extract_value_by_keys(item, OUTLINE_STORY_KEYS) if isinstance(item, dict) else None
        if isinstance(story, dict):
            blob = _clean_behavior_sentence("".join(str(story.get(key, "") or "") for key in ("开始", "发展", "高潮", "结局")))
            if blob:
                story_blobs.append(blob)
    if len(story_blobs) < 2:
        return False
    for idx in range(1, len(story_blobs)):
        prev = story_blobs[idx - 1]
        curr = story_blobs[idx]
        shorter = max(1, min(len(prev), len(curr)))
        common = len(set(_extract_clean_clauses(prev, min_len=8)) & set(_extract_clean_clauses(curr, min_len=8)))
        prefix_same = prev[:80] == curr[:80]
        length_ratio = abs(len(prev) - len(curr)) / max(len(prev), len(curr), 1)
        if prefix_same or (common >= 2 and length_ratio < 0.35):
            return True
    return False


def _strip_plot_stage_label(text: str) -> str:
    value = _clean_behavior_sentence(str(text or ""))
    if not value:
        return ""
    value = re.sub(r"^(开始|发展|高潮|结局)\s*[:：]\s*", "", value)
    value = re.sub(r"^的第[一二三四五六七八九十0-9]+卷从", "", value)
    value = re.sub(r"^第[一二三四五六七八九十0-9]+卷\s*", "", value)
    value = re.sub(r"^第[一二三四五六七八九十0-9]+卷从", "", value)
    value = re.sub(r"^《[^》]{1,30}》的第[一二三四五六七八九十0-9]+卷", "", value)
    value = re.sub(r"^卷首的核心不是简单抛出新事件", "", value)
    value = re.sub(r"^而是让", "", value)
    value = re.sub(r"\s+", "", value)
    value = value.strip("，。；：: ")
    return value


def _extract_outline_prompt_fields(user_text: str) -> Dict[str, Any]:
    summary_fields = _extract_summary_prompt_fields(user_text)
    title = str(summary_fields.get("title", "")).strip()

    char_raw = _extract_section_any(
        user_text,
        (
            "主要人物和他们的行为",
            "主要人物",
            "人物信息",
            "人物",
        ),
    )
    bg_raw = _extract_section_any(user_text, ("故事背景", "背景", "世界观"))
    intro_raw = _extract_section_any(
        user_text,
        (
            "简介",
            "情节简介",
            "故事简介",
            "小说部分内容的梗概",
            "小说梗概",
            "梗概",
        ),
    )
    intro_block = _final_extract_prompt_block(
        user_text,
        ("小说简介", "简介", "小说梗概", "梗概"),
        ("人物关系拓扑", "关系拓扑", "请生成", "生成要求", "约束"),
    )
    if intro_block:
        intro_raw = intro_block
    names: List[str] = []
    parsed_summary = _parse_summary_obj(_sanitize_text(str(intro_raw or "")))
    summary_items = _extract_summary_items_from_obj(parsed_summary) if parsed_summary is not None else []
    if summary_items:
        first_summary = summary_items[0]
        summary_chars = _extract_value_by_keys(first_summary, SUMMARY_PERSON_KEYS)
        if isinstance(summary_chars, dict):
            names.extend(str(key).strip() for key in summary_chars.keys() if str(key).strip())
        summary_content = _extract_value_by_keys(first_summary, SUMMARY_CONTENT_KEYS)
        summary_story = _extract_value_by_keys(first_summary, SUMMARY_STORY_KEYS)
        if isinstance(summary_content, str) and summary_content.strip():
            intro_raw = summary_content
        elif isinstance(summary_story, str) and summary_story.strip():
            intro_raw = summary_story
        elif isinstance(summary_content, dict):
            intro_raw = _story_map_to_content(_coerce_story_map(summary_content, {}))
        elif isinstance(summary_story, dict):
            intro_raw = _story_map_to_content(_coerce_story_map(summary_story, {}))

    if not title:
        m = re.search(r"《([^>》]{2,40})》", user_text)
        if m:
            title = m.group(1).strip()

    raw_text = str(char_raw or "").strip()
    if raw_text:
        for parser in (ast.literal_eval, json.loads):
            try:
                obj = parser(raw_text)
                if isinstance(obj, dict):
                    names.extend(str(k).strip() for k in obj.keys() if str(k).strip())
                    break
                if isinstance(obj, list):
                    names.extend(str(x).strip() for x in obj if str(x).strip())
                    break
            except Exception:
                pass
        if not names:
            quoted = re.findall(r"['\"]([一-鿿A-Za-z0-9_]{2,12})['\"]", raw_text)
            names.extend(quoted)
        if not names:
            names.extend([x.strip() for x in re.split(r"[,，、/\|;\s]+", raw_text) if x.strip()])

    names = _normalize_person_names(names, title=title, max_count=8)
    intro = _clean_linebreaks(str(intro_raw or "")).strip()
    background = _clean_linebreaks(str(bg_raw or "")).strip()
    if intro:
        intro = _filter_summary_content(intro, names, title=title)
    if not intro:
        intro = str(summary_fields.get("intro", "")).strip()

    if not names:
        names = _extract_name_candidates(title, f"{background}\n{intro}", [])
    if len(names) < 4:
        defaults = _build_default_person_names(title, [], count=6)
        for n in defaults:
            if n not in names:
                names.append(n)
            if len(names) >= 6:
                break

    return {
        "title": title,
        "characters": names[:8],
        "background": background,
        "intro": intro,
    }


def _pick_outline_volume_count(user_text: str, default: int = 4) -> int:
    text = str(user_text or "")
    patterns = (
        r"分卷数量[：:]\s*(\d+)\s*卷",
        r"输出严格为\s*(\d+)\s*个\s*item",
        r"一共有\s*(\d+)\s*[个份条卷]",
        r"生成\s*(\d+)\s*[个条卷]",
        r"返回\s*(\d+)\s*[个条卷]",
    )
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        try:
            value = int(m.group(1))
            return max(1, min(20, value))
        except Exception:
            continue
    return max(1, min(20, int(default)))


def _extract_model_seed_clauses(seed_text: str, names: Optional[Sequence[str]] = None, max_count: int = 10) -> List[str]:
    clean = _sanitize_text(str(seed_text or ""))
    if not clean.strip():
        return []
    name_pool = [str(name).strip() for name in (names or []) if str(name).strip()]
    blocked_markers = (
        "```",
        "python",
        "json",
        "主要人物",
        "故事情节",
        "章节标题",
        "细纲内容",
        "卷名",
        "Their",
        "item",
        "只能包含",
        "固定输出",
        "本大纲旨在",
        "基于您提供",
        "根据您提供",
        "以下是",
        "下面是",
        "旨在将",
        "小说标题",
        "分类标签",
        "人物关系拓扑",
        "详细大纲",
        "大纲",
        "关系恒定",
        "核心冲突",
        "节奏把控",
        "静态关系不变",
        "将抽象",
        "落地为具体",
        "卷一细纲",
        "卷二细纲",
        "卷三细纲",
        "卷四细纲",
        "细纲：",
        "*：",
        "vs.",
        "vs",
        "本细纲",
        "严格遵循",
        "以下原则",
        "输出原则",
        "章节规划原则",
        "章节数",
        "第一章",
        "第二章",
        "第三章",
        "第四章",
        "第五章",
        "第六章",
    )
    noisy_chars = set("{}[]<>\"'“”‘’")
    clauses: List[str] = []
    for clause in _extract_clean_clauses(clean, min_len=8):
        clause = _clean_linebreaks(clause).strip("，。、；;：: ")
        if not clause:
            continue
        if any(marker in clause for marker in blocked_markers):
            continue
        if any(ch in clause for ch in noisy_chars):
            continue
        if re.search(r"^\s*\d+\s*[.、:：]", clause):
            continue
        if re.search(r"[一-鿿]{2,8}\s*与\s*[一-鿿]{2,8}\s*(?:为|是|有)", clause):
            continue
        if len(clause) > 96:
            clause = clause[:96].rstrip("，。、；;：: ")
        if name_pool and not any(name in clause for name in name_pool) and len(clauses) >= 3:
            continue
        if clause not in clauses:
            clauses.append(clause)
        if len(clauses) >= max_count:
            break
    return clauses


def _normalize_outline_char_map(raw_char_map: Any, fallback_char_map: Dict[str, str], intro: str) -> Dict[str, str]:
    base_map = _coerce_char_map(raw_char_map, fallback_char_map)
    out: Dict[str, str] = {}

    for raw_name, raw_behavior in base_map.items():
        name = str(raw_name or "").strip().strip("'\"")
        if not name or name in out:
            continue
        if not _is_valid_person_name(name) and name not in {"义父", "阿爸", "阿妈"}:
            continue

        raw_behavior_text = _clean_behavior_sentence(str(raw_behavior or ""))
        behavior = _strip_repeated_template_phrases(raw_behavior_text, OUTLINE_CHAR_TEMPLATE_MARKERS)
        if not behavior:
            behavior = _clean_behavior_sentence(_merge_name_actions_from_intro(name, intro))
        if any(marker in raw_behavior_text for marker in OUTLINE_CHAR_TEMPLATE_MARKERS) or _is_templatey_outline_char_text(behavior):
            fallback_behavior = _clean_behavior_sentence(str(fallback_char_map.get(name, "") or ""))
            if fallback_behavior and not _is_templatey_outline_char_text(fallback_behavior):
                behavior = fallback_behavior
        if not behavior:
            behavior = f"{name}在本卷中执行关键任务并推动事件变化"
        behavior = behavior.replace("相关行动会同步影响人物关系、资源流向和下一阶段决策边界", "相关动作会继续改写人物站位和卷内节奏")
        behavior = behavior.replace("他的动作会直接改变调查走向和人物站位", "他的推进会直接改写卷内站位和判断")
        out[name] = _ensure_period(behavior)
        if len(out) >= 8:
            break

    if out:
        return out

    for raw_name, raw_behavior in fallback_char_map.items():
        name = str(raw_name or "").strip()
        if not name or name in out:
            continue
        behavior = _clean_behavior_sentence(str(raw_behavior or ""))
        out[name] = _ensure_period(behavior or f"{name}在本卷中负责一条独立行动线。")
        if len(out) >= 6:
            break
    return out


def _normalize_outline_story_map(
    raw_story: Any,
    fallback_story: Dict[str, str],
    volume_index: int,
    total_volumes: int,
) -> Dict[str, str]:
    story = _coerce_story_map(raw_story, fallback_story)
    out: Dict[str, str] = {}

    for key in ("开始", "发展", "高潮", "结局"):
        text = _clean_linebreaks(_sanitize_text(str(story.get(key, "") or "")))
        text = _clean_behavior_sentence(text)
        fallback_text = _clean_behavior_sentence(str(fallback_story.get(key, "") or ""))
        if _is_templatey_outline_story_text(text):
            text = ""
        merged = _ensure_period(text or fallback_text)
        if len(merged) < 70:
            stage_expansions = {
                "开始": "关键线索在开局迅速浮出水面，人物被迫从旁观转入行动，原本可以拖延的选择被推到眼前。",
                "发展": "阻力沿着调查、关系和资源三条线逐层叠加，人物站位随新证据出现分化，局面不断向更危险处倾斜。",
                "高潮": "核心冲突被推到明面，主角必须当场做出取舍，盟友、对手和旁观者都因此付出不同代价。",
                "结局": "本卷收束阶段给出阶段性成果，也留下新的缺口与压力，把尚未解决的问题自然推向下一卷。",
            }
            merged = _ensure_period(merged + stage_expansions.get(key, ""))
        out[key] = merged
    return out


DETAIL_OUTLINE_INDEX_KEYS = (
    "章节序号",
    "序号",
    "章序",
    "chapter_index",
    "chapter_no",
    "index",
)
DETAIL_OUTLINE_TITLE_KEYS = (
    "章节标题",
    "章節標題",
    "标题",
    "標題",
    "章名",
    "title",
    "chapter_title",
)
DETAIL_OUTLINE_CONTENT_KEYS = (
    "细纲内容",
    "細綱內容",
    "内容",
    "內容",
    "章节细纲",
    "章節細綱",
    "细纲",
    "細綱",
    "outline_content",
    "chapter_outline",
    "chapter_content",
    "chapter_detail",
    "content",
    "outline",
    "detail",
)


def _cn_num_to_int(token: str) -> int:
    s = str(token or "").strip()
    if not s:
        return 0
    if s.isdigit():
        return int(s)
    m = {
        "零": 0,
        "一": 1,
        "二": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
        "十": 10,
        "百": 100,
        "两": 2,
    }
    if s in m:
        return m[s]
    if "百" in s:
        parts = s.split("百", 1)
        h = m.get(parts[0], 1) if parts[0] else 1
        tail = _cn_num_to_int(parts[1]) if parts[1] else 0
        return h * 100 + tail
    if "十" in s:
        parts = s.split("十", 1)
        t = m.get(parts[0], 1) if parts[0] else 1
        u = m.get(parts[1], 0) if parts[1] else 0
        return t * 10 + u
    total = 0
    for ch in s:
        if ch in m and m[ch] < 10:
            total = total * 10 + m[ch]
    return total


def _pick_detail_chapter_count(user_text: str, default: int = DETAIL_OUTLINE_DEFAULT_CHAPTERS) -> int:
    text = str(user_text or "")
    digit_patterns = (
        r"(?:章节数量|章节数|章数|细纲章数)\s*[:：]?\s*(\d+)\s*章?",
        r"(?:一共有|共|总共|需要|拆分成|拆成|分成)\s*(\d+)\s*章",
        r"第\s*(\d+)\s*章\s*(?:到|至|[-~—－])\s*第?\s*(\d+)\s*章",
        r"(\d+)\s*章节(?:的细纲)?(?:数目|数量)?",
        r"chapter\s*(\d+)",
    )
    for pat in digit_patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if not m:
            continue
        try:
            if len(m.groups()) >= 2 and m.group(2):
                start = int(m.group(1))
                end = int(m.group(2))
                value = abs(end - start) + 1
            else:
                value = int(m.group(1))
            return max(1, min(30, value))
        except Exception:
            continue

    cn_patterns = (
        r"(?:章节数量|章节数|章数|细纲章数)\s*[:：]?\s*([零一二三四五六七八九十百两]+)\s*章?",
        r"(?:一共有|共|总共|需要|拆分成|拆成|分成)\s*([零一二三四五六七八九十百两]+)\s*章",
        r"第\s*([零一二三四五六七八九十百两]+)\s*章\s*(?:到|至|[-~—－])\s*第?\s*([零一二三四五六七八九十百两]+)\s*章",
        r"([零一二三四五六七八九十百两]+)\s*章节",
    )
    for pat in cn_patterns:
        m = re.search(pat, text)
        if not m:
            continue
        if len(m.groups()) >= 2 and m.group(2):
            start = _cn_num_to_int(m.group(1))
            end = _cn_num_to_int(m.group(2))
            value = abs(end - start) + 1 if start and end else 0
        else:
            value = _cn_num_to_int(m.group(1))
        if value > 0:
            return max(1, min(30, value))
    return max(1, min(30, int(default)))


def _extract_detail_outline_prompt_fields(user_text: str) -> Dict[str, Any]:
    title = _extract_section_any(user_text, ("小说标题", "标题")).strip()
    if not title:
        m = re.search(r"《([^>》]{2,40})》", user_text)
        if m:
            title = m.group(1).strip()

    char_raw = _extract_section_any(
        user_text,
        (
            "主要人物和他们的行为",
            "人物信息",
            "主要人物",
            "角色信息",
            "人物",
        ),
    )
    summary_raw = _extract_section_any(
        user_text,
        (
            "小说部分内容的梗概",
            "本卷梗概",
            "当前分卷梗概",
            "梗概",
            "故事情节",
        ),
    )
    novel_intro_raw = _extract_section_any(
        user_text,
        ("小说简介", "整体简介", "作品简介", "简介"),
    )
    chapter_split = _extract_section_any(
        user_text,
        ("章节划分", "章节数", "细纲章节", "拆章规划"),
    )

    parsed_char: Any = None
    char_text = _clean_linebreaks(str(char_raw or "")).strip()
    if char_text:
        for parser in (ast.literal_eval, json.loads):
            try:
                parsed_char = parser(char_text)
                break
            except Exception:
                pass
    char_map = _coerce_char_map(parsed_char if parsed_char is not None else char_text, {})
    if len(char_map) < 3:
        inferred = _extract_name_candidates(title, f"{summary_raw}\n{novel_intro_raw}", [])
        for n in inferred:
            if n not in char_map:
                char_map[n] = "围绕本卷冲突推进主线行动。"
            if len(char_map) >= 6:
                break
    if len(char_map) < 3:
        fallback_names = _build_default_person_names(title, [], count=6)
        for n in fallback_names:
            if n not in char_map:
                char_map[n] = "在本卷中执行关键任务并推动事件变化。"

    volume_summary = _clean_linebreaks(str(summary_raw or "")).strip()
    novel_intro = _clean_linebreaks(str(novel_intro_raw or "")).strip()
    if not novel_intro:
        novel_intro = volume_summary
    if not volume_summary:
        volume_summary = novel_intro
    if not volume_summary:
        volume_summary = "本卷围绕人物关系重组、目标升级与阶段决策展开。"

    chapter_count = _pick_detail_chapter_count(f"{chapter_split}\n{user_text}", default=DETAIL_OUTLINE_DEFAULT_CHAPTERS)
    return {
        "title": title,
        "char_map": char_map,
        "volume_summary": volume_summary,
        "novel_intro": novel_intro,
        "chapter_count": chapter_count,
    }


def _extract_detail_outline_items_from_obj(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return [x for x in obj if isinstance(x, dict)]
    if isinstance(obj, dict):
        for key in ("章节", "细纲", "chapters", "data", "items"):
            inner = obj.get(key)
            if isinstance(inner, list):
                return [x for x in inner if isinstance(x, dict)]
        if any(k in obj for k in DETAIL_OUTLINE_TITLE_KEYS) or any(k in obj for k in DETAIL_OUTLINE_CONTENT_KEYS):
            return [obj]
    return []


def _parse_detail_outline_obj(text: str) -> Optional[Any]:
    s = _to_simplified_lite(_strip_fences(str(text or "").strip()))
    for parser in (json.loads, ast.literal_eval):
        try:
            return parser(s)
        except Exception:
            pass

    labeled_pat = re.compile(
        r"(?:^|\n)\s*(?:第\s*(\d+)\s*章\s*[:：\-、.]?\s*)?"
        r"(?:章节标题|标题)\s*[:：]\s*([^\n]{1,40})\s*"
        r"\n+\s*(?:细纲内容|内容)\s*[:：]\s*(.+?)"
        r"(?=\n\s*(?:第\s*\d+\s*章\s*[:：\-、.]?\s*)?(?:章节标题|标题)\s*[:：]|\Z)",
        re.DOTALL,
    )
    labeled_items: List[Dict[str, Any]] = []
    for m in labeled_pat.finditer(s):
        idx = int(m.group(1)) if m.group(1) else len(labeled_items) + 1
        title = _clean_linebreaks(m.group(2)).strip()
        content = _clean_linebreaks(m.group(3)).strip()
        if title and content:
            labeled_items.append({"章节序号": idx, "章节标题": title, "细纲内容": content})
    if labeled_items:
        return labeled_items

    # Markdown style: #### 1. 标题 / ### 第一章：标题
    md_pat = re.compile(
        r"#{2,6}\s*(?:(?:第\s*)?([零一二三四五六七八九十百两\d]+)\s*章?)?\s*[\.、:：-]?\s*([^\n]{1,40})\n(.*?)(?=\n\s*#{2,6}\s*(?:(?:第\s*)?[零一二三四五六七八九十百两\d]+\s*章?)?|\Z)",
        re.DOTALL,
    )
    md_items: List[Dict[str, Any]] = []
    for m in md_pat.finditer(s):
        idx = _cn_num_to_int(m.group(1)) if m.group(1) else len(md_items) + 1
        title = m.group(2).strip()
        content = m.group(3).strip()
        if "卷名" in title or "核心目标" in title or "细纲拆解" in title or (not m.group(1) and "章" not in title):
            continue
        md_items.append({"章节序号": idx or len(md_items) + 1, "章节标题": title, "细纲内容": content})
    if md_items:
        return md_items

    # Legacy delimiter style with |||
    if "|||" in s:
        blocks = [x.strip() for x in re.split(r"\s*\|\|\|\s*", s) if x and x.strip()]
        items: List[Dict[str, Any]] = []
        for i, block in enumerate(blocks, 1):
            lines = [ln.strip() for ln in block.splitlines() if ln.strip()]
            title = ""
            content = block
            if lines:
                first = lines[0]
                m = re.match(r"^(?:第\s*)?(\d+)\s*章(?:\s*[：:.\-]\s*([^\n]{1,36}))?$", first)
                if m:
                    if m.group(2):
                        title = m.group(2).strip()
                    content = "\n".join(lines[1:]).strip() or block
            items.append({"章节序号": i, "章节标题": title, "细纲内容": content})
        if items:
            return items

    # Heading style: 第N章：标题
    chapter_pat = re.compile(
        r"(?:^|\n)\s*#*\s*第\s*([零一二三四五六七八九十百两\d]+)\s*章(?:\s*[：:.\-]\s*([^\n]{1,40}))?\s*\n(.*?)(?=(?:\n\s*#*\s*第\s*[零一二三四五六七八九十百两\d]+\s*章)|\Z)",
        re.DOTALL,
    )
    chapter_items: List[Dict[str, Any]] = []
    for m in chapter_pat.finditer(s):
        idx = _cn_num_to_int(m.group(1))
        title = (m.group(2) or "").strip()
        content = (m.group(3) or "").strip()
        chapter_items.append({"章节序号": idx, "章节标题": title, "细纲内容": content})
    if chapter_items:
        return chapter_items

    simple_pat = re.compile(
        r"(?:^|\n)\s*(?:##+\s*)?([^\n]{2,18})\n+(.+?)(?=\n\s*(?:##+\s*)?[^\n]{2,18}\n|\Z)",
        re.DOTALL,
    )
    simple_items: List[Dict[str, Any]] = []
    for m in simple_pat.finditer(s):
        title = _clean_linebreaks(m.group(1)).strip()
        content = _clean_linebreaks(m.group(2)).strip()
        if not title or not content:
            continue
        if any(marker in title for marker in ("章节标题", "细纲内容", "内容：", "标题：")):
            continue
        if len(title) > 18:
            continue
        simple_items.append({"章节序号": len(simple_items) + 1, "章节标题": title, "细纲内容": content})
    if simple_items:
        return simple_items
    return None


def _ensure_unique_detail_titles(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen: Dict[str, int] = {}
    total = len(items)
    for idx, item in enumerate(items, start=1):
        title = _clean_linebreaks(str(item.get("章节标题", "") or "")).strip()
        title = _strip_chapter_title_prefix(title)
        if not title:
            title = _detail_title_from_seed(str(item.get("细纲内容", "") or ""), idx, total)
        if title in seen:
            title = _detail_title_from_seed(f"{title}{idx}", idx, total)
            if title in seen:
                title = f"{title}{idx}"
        seen[title] = idx
        item["章节标题"] = title
    return items


def _strip_chapter_title_prefix(title: str) -> str:
    source = _clean_linebreaks(str(title or "")).strip()
    source = re.sub(r"^[《「『“\"']+|[》」』”\"']+$", "", source).strip()
    patterns = [
        r"^(?:第\s*)?[零一二三四五六七八九十百两\d]+\s*卷\s*(?:第\s*[零一二三四五六七八九十百两\d]+\s*章)?\s*[：:·.\-—、\s]*",
        r"^卷\s*[零一二三四五六七八九十百两\d]+\s*(?:章\s*[零一二三四五六七八九十百两\d]+)?\s*[：:·.\-—、\s]*",
        r"^(?:第\s*)?[零一二三四五六七八九十百两\d]+\s*章\s*[：:·.\-—、\s]*",
    ]
    for pattern in patterns:
        source = re.sub(pattern, "", source).strip()
    return source[:24].strip()


def _content_driven_detail_title(content: str, fallback: str = "") -> str:
    source = _clean_linebreaks(str(content or "")).strip()
    candidates: List[str] = []

    def _clean_scene_core(text: str) -> str:
        cleaned = re.sub(r"[^一-鿿]", "", str(text or ""))
        cleaned = re.sub(
            r"^(暴雨压港的|临时清出的|看似平静的|平静的|带潮气的|被潮气泡软的|被海风反复吹打的|下的|多年的|废弃的|旧城区的|潮湿的|昏暗的|狭长的|临时的|被压低的)",
            "",
            cleaned,
        )
        scene_patterns = [
            "安全屋前厅", "废弃通道", "地下仓库", "旧城区走廊", "废弃档案馆", "地下实验室",
            "海港都市", "雨夜都市", "老工业区", "旧书铺", "江湖客栈", "山野村落", "高校校园",
            "旧码头", "档案室", "档案库", "码头", "前厅", "通道", "仓库", "走廊", "长廊",
            "回廊", "石阶", "石坪", "石桥", "操场", "教室", "终端", "日志", "断点", "残卷",
            "印鉴", "旧信", "古阵", "密诏", "风雪", "海雾", "高墙城", "巨构城",
        ]
        for pattern in scene_patterns:
            if pattern in cleaned:
                return pattern
        if 2 <= len(cleaned) <= 8:
            return cleaned
        compact = _normalize_detail_title_seed(cleaned)
        return compact[:8]

    def _extract_event_core(text: str) -> str:
        cleaned = re.sub(r"[^一-鿿]", "", str(text or ""))
        event_map = [
            ("已经来不及后退", "退路断"),
            ("刚刚开始显形", "显形"),
            ("开始反扑", "反扑"),
            ("新的代价", "代价"),
            ("新的行动窗口", "限窗"),
            ("时间里", "限时"),
            ("贴到每个人后颈", "逼近"),
            ("前兆", "前兆"),
            ("余波", "余波"),
            ("沉重", "沉压"),
            ("灰色势力", "灰影"),
            ("行动窗口", "限时"),
            ("旧案余波", "余波"),
            ("来路不明的新证据", "来证"),
            ("看似偶然实则被设计过的碰面", "设局"),
            ("对不上的记录", "失录"),
            ("异常线索", "疑线"),
            ("关键线索", "疑线"),
            ("新线索", "新线"),
            ("碰面", "碰面"),
            ("证据", "证据"),
            ("记录", "失录"),
            ("信号", "异讯"),
            ("旧案", "旧案"),
            ("裂缝", "裂缝"),
            ("试探", "试探"),
            ("防备", "暗防"),
            ("代价", "代价"),
            ("危险", "逼近"),
            ("站位", "错位"),
            ("局面", "逆流"),
            ("回声", "回声"),
            ("失序", "失序"),
            ("潮声", "潮声"),
            ("回潮", "回潮"),
        ]
        for marker, alias in event_map:
            if marker in cleaned:
                return alias
        if 2 <= len(cleaned) <= 4:
            return cleaned
        compact = _normalize_detail_title_seed(cleaned)
        if 2 <= len(compact) <= 4:
            return compact
        return ""

    quoted_parts = re.findall(r"[“\"']([^“”\"']{2,24})[”\"']", source)
    scene_core = ""
    event_core = ""
    if quoted_parts:
        scene_core = _clean_scene_core(quoted_parts[0])
    if len(quoted_parts) > 1:
        event_core = _extract_event_core(quoted_parts[1])

    if not scene_core:
        scene_hits = re.findall(
            r"(?:安全屋前厅|废弃通道|地下仓库|旧城区走廊|废弃档案馆|地下实验室|旧码头|档案室|档案库|码头|前厅|通道|仓库|走廊|长廊|回廊|石阶|石桥|操场|教室|终端|残卷|印鉴|旧信|古阵|密诏)",
            source,
        )
        if scene_hits:
            scene_core = _clean_scene_core(scene_hits[0])

    tail_sentences = [seg for seg in re.split(r"[。！？]", source) if seg.strip()]
    tail_text = "".join(tail_sentences[-2:]) if tail_sentences else source
    tail_event_core = _extract_event_core(tail_text)
    if tail_event_core:
        event_core = tail_event_core

    if not event_core:
        event_core = _extract_event_core(source)

    if scene_core and event_core:
        combo_candidates = [
            scene_core + event_core,
            scene_core[-4:] + event_core,
            scene_core + event_core[-2:],
        ]
        for combo in combo_candidates:
            combo = re.sub(r"^(的|在|从|把|向|与|及|并|被|让|于|将|这)", "", combo)
            combo = re.sub(r"(异常线索|关键线索|这一章|本章|细纲|内容|主线)$", "", combo)
            if 4 <= len(combo) <= 8 and not _is_templatey_detail_title(combo) and combo not in candidates:
                candidates.append(combo)

    for quoted in quoted_parts:
        cleaned = _clean_scene_core(quoted)
        cleaned = re.sub(r"^(的|在|从|把|向|与|及|并|被|让|于|将|这)", "", cleaned)
        if 3 <= len(cleaned) <= 8 and not _is_templatey_detail_title(cleaned) and cleaned not in candidates:
            candidates.append(cleaned)

    seed_title = _normalize_detail_title_seed(source or fallback)
    if seed_title:
        seed_title = re.sub(r"^(的|在|从|把|向|与|及|并|被|让|于|将|这)", "", seed_title)
        seed_title = re.sub(r"(异常线索|关键线索|这一章|本章|细纲|内容|主线)$", "", seed_title)
        if 3 <= len(seed_title) <= 8 and seed_title not in candidates:
            candidates.append(seed_title)

    for candidate in candidates:
        if not _is_templatey_detail_title(candidate):
            return candidate
    return fallback


def _normalize_detail_title_seed(seed: str) -> str:
    s = _clean_behavior_sentence(str(seed or ""))
    s = re.sub(r"^第\s*\d+\s*章[、:锛?\-]?", "", s)
    s = re.sub(
        r"(本卷|本章|主线|剧情|内容|章节|细纲|对话|情感|钩子|围绕|人物|关系|重组|目标|阶段|推进|冲突|展开|本章以|作为开场|调查推进过程中|直接对应点|章末落点)",
        "",
        s,
    )
    clauses = [x for x in _extract_clean_clauses(s, min_len=2) if 2 <= len(x) <= 16]
    if clauses:
        clauses.sort(key=len, reverse=True)
        for clause in clauses:
            cleaned = re.sub(r"[^一-鿿A-Za-z0-9]", "", clause)
            if 3 <= len(cleaned) <= 10:
                return cleaned[:10]
    s = re.sub(r"[^一-鿿A-Za-z0-9]", "", s)
    return s[:10]


def _is_templatey_detail_title(title: str) -> bool:
    t = _to_simplified_lite(_clean_linebreaks(str(title or "")).strip())
    if not t or len(t) < 3:
        return True
    if not re.search(r"[一-鿿A-Za-z0-9]", t):
        return True
    if any(
        token in t
        for token in (
            "【事件】",
            "事件",
            "---",
            "***",
            "——",
            "———",
            "场景",
            "对话",
            "查清真相",
            "追真相",
            "逼近",
            "隶属",
            "关系恒定",
            "核心冲突",
            "节奏把控",
            "静态关系",
            "家族血缘",
            "角色职能",
        )
    ):
        return True
    if t.startswith(("住的", "的", "在", "把", "被", "将")):
        return True
    if re.search(r"^\s*第\s*(?:\d+|[一二三四五六七八九十两百千]+)\s*章", t, re.IGNORECASE):
        return True
    if any(
        token in t
        for token in (
            "是一部",
            "本章",
            "本卷",
            "作为开场",
            "调查推进",
            "过程中",
            "对应点",
            "章末",
            "推进",
            "结果",
            "人物",
            "关系",
            "主线",
            "内容",
            "细纲",
            "章节标题",
            "标题",
            "細綱",
            "標題",
            "围绕",
            "小说",
            "证据",
        )
    ):
        return True
    if re.search(r"^(护|救|追|查|稳|逼).{2,}$", t):
        return True
    if len(t) >= 6:
        for size in (2, 3):
            if t[:size] == t[-size:]:
                return True
    if t.endswith("的"):
        return True
    if len(t) > 10:
        return True
    if re.search(r"[，。；：,.!?]", t):
        return True
    return False


def _is_templatey_detail_content(text: str) -> bool:
    s = _to_simplified_lite(_clean_linebreaks(str(text or "")).strip())
    if len(s) < 60:
        return True
    if any(
        token in s
        for token in (
            "本章以",
            "本章目标",
            "承接信息",
            "关键人物",
            "伏笔推进",
            "作为开场",
            "直接对应点",
            "章末落点",
            "在这一章",
            "本细纲严格",
            "严格遵循以下原则",
            "输出原则",
            "章节规划原则",
            "行为线也不能只停在口头上",
            "要具体落成",
            "本大纲旨在",
            "基于您提供",
            "根据您提供",
            "以下是",
            "下面是",
            "旨在将",
            "小说标题",
            "分类标签",
            "人物关系拓扑",
            "详细大纲",
            "关系恒定",
            "核心冲突",
            "节奏把控",
            "静态关系不变",
            "静态关系铁律",
            "角色职能定位",
            "剧情推进逻辑",
            "家族/血缘",
            "家族/旧案牵连",
            "双重血缘羁绊",
            "团队执行核心",
            "景交集",
            "全眠",
            "不可更改",
            "将抽象",
            "落地为具体",
            "卷一细纲",
            "卷二细纲",
            "卷三细纲",
            "卷四细纲",
            "细纲：",
            "章节标题",
            "细纲内容",
            "章節標題",
            "細綱內容",
            "*：",
            "vs.",
            "vs",
            "':",
            '":',
        )
    ):
        return True
    if re.search(r"(^|\n)\s*[*#]+\s*", s):
        return True
    if re.search(r"(^|\n|\s)\d+\s*[.、:：]\s*(静态关系|关系恒定|角色职能|剧情推进|核心冲突|节奏把控)", s):
        return True
    if re.search(r"(^|\n|\s)\d+\s*[.、:：]\s*[一-鿿]{2,8}\s*与\s*[一-鿿]{2,8}", s):
        return True
    return False


def _detail_title_from_seed(seed: str, chapter_no: int, chapter_count: int) -> str:
    natural_titles = [
        "雨夜起潮",
        "旧岸回声",
        "锈门暗影",
        "灏灯后的线索",
        "裂缝生光",
        "暗线潮生",
        "灯下错踪",
        "雾港不眠",
    ]
    topic = _normalize_detail_title_seed(seed)
    if topic and 4 <= len(topic) <= 8 and not _is_templatey_detail_title(topic) and not any(x in topic for x in ("是", "在", "为", "故事", "小说", "而")):
        return topic
    if chapter_no == chapter_count:
        return "雾港不眠"
    return natural_titles[(chapter_no - 1) % len(natural_titles)]


def _is_generic_detail_title(title: str) -> bool:
    t = _clean_linebreaks(str(title or "")).strip()
    if not t:
        return True
    return bool(re.fullmatch(r"第\s*[零一二三四五六七八九十百两\d]+\s*章", t))


def _detail_title_from_content(content: str, chapter_no: int, chapter_count: int, fallback: str = "") -> str:
    title = _content_driven_detail_title(content, fallback="")
    if not title or _is_generic_detail_title(title) or _is_templatey_detail_title(title):
        title = _detail_title_from_seed(content or fallback, chapter_no, chapter_count)
    if not title or _is_generic_detail_title(title):
        title = _detail_title_from_seed(fallback or content, chapter_no, chapter_count)
    return title


def _compose_detail_chapter_content(
    *,
    chapter_no: int,
    chapter_count: int,
    chapter_title: str,
    char_map: Dict[str, str],
    volume_summary: str,
    novel_intro: str,
    seed: str,
) -> str:
    names = [str(x).strip() for x in char_map.keys() if str(x).strip()]
    if not names:
        names = ["主角", "关键配角A", "关键配角B"]
    lead = names[(chapter_no - 1) % len(names)]
    support = names[(chapter_no) % len(names)] if len(names) > 1 else names[0]
    support2 = names[(chapter_no + 1) % len(names)] if len(names) > 2 else support

    summary_clauses = _extract_narrative_source_clauses(volume_summary, min_len=6)
    seed_clauses = _extract_narrative_source_clauses(seed or volume_summary, min_len=6)
    scene_hint = _strip_plot_stage_label(summary_clauses[(chapter_no - 1) % len(summary_clauses)]) if summary_clauses else "被雾气和旧事压住的现场"
    event_hint = _strip_plot_stage_label(seed_clauses[(chapter_no - 1) % len(seed_clauses)]) if seed_clauses else "一条把人心和真相同时拉紧的新线索"
    if not scene_hint:
        scene_hint = "被雾气和旧事压住的现场"
    if not event_hint:
        event_hint = "一条把人心和真相同时拉紧的新线索"
    stage_labels = ["试探", "加压", "破局", "反转", "收束"]
    stage = stage_labels[min(len(stage_labels) - 1, int((chapter_no - 1) * len(stage_labels) / max(1, chapter_count)))]
    hooks = [
        "一份新证据被意外翻出",
        "某个人的站位终于露出裂缝",
        "下一步行动被迫提前",
        "一句话把团队信任推向危险边缘",
    ]
    hook = hooks[(chapter_no - 1) % len(hooks)]
    opening = f"{chapter_title}从{scene_hint}切入。{lead}因“{event_hint}”被迫入局，刚摸到问题边缘，就发现真正的阻力比想象更近。"
    pressure = (
        f"{support}倾向于先把局面稳住，{support2}却认为再退就会错过最重要的窗口，"
        "三人在最短的时间里必须边走边判断谁的话还能信，谁的计算已经开始变形。"
    )
    mid_push = (
        f"章节中段把冲突推到{stage}状态，人物之间的对话不再只是交换信息，"
        "而是一次次试探、较力和退让，它既会推动事件往前，也会让原本还能维持的默契出现裂口。"
    )
    turn = (
        f"等线索看似要闭合时，{lead}才意识到这一章真正的变化不在结论，"
        f"而在人心：{support}的站位开始松动，{support2}则被迫提前拿出自己原本不想暴露的那张牌。"
    )
    ending = (
        f"到了章末，{hook}，这个变化不只让本章的代价当场生效，"
        "也直接把下一章推向更深的雾里，让读者能明确感到剧情已经无法回到原先的状态。"
    )
    text = _clean_linebreaks(
        f"{opening}承接上一章留下的线索压力和人物站位变化，{lead}必须接住这条线索带来的后果，不能让既有疑点凭空消失。\n"
        f"{pressure}{mid_push}{lead}推进判断，{support}稳住局面，{support2}制造新的信息差和选择压力。\n"
        f"本章围绕“{event_hint}”进行强化或阶段解释，保留一个可在后续章节继续追查的未决点。{turn}{ending}"
    )
    return _ensure_period(text)


def _is_text_request(user_text: str) -> bool:
    if not user_text:
        return False
    text_keys = (
        "小说章节信息",
        "本章细纲",
        "上一章的结尾",
        "小说开篇第1章",
        "续写第",
        "撰写第 1 章完整正文",
        "请根据以上信息，撰写第 1 章完整正文",
        "只输出正文",
    )
    return any(k in user_text for k in text_keys)


def _is_info_recommend_request(messages: List[Dict[str, str]]) -> bool:
    user_text = _get_last_user_content(messages)
    if not user_text:
        return False
    strong_keywords = [
        "标签大类与标签对应关系",
        "标签明细",
        "只输出以下三个板块",
        "人物信息：",
        "故事背景：",
        "简介：",
    ]
    if sum(1 for k in strong_keywords if k in user_text) >= 4:
        return True
    return all(k in user_text for k in INFO_RECOMMEND_DETECT_KEYWORDS)


def _is_summary_request(messages: List[Dict[str, str]]) -> bool:
    user_text = _get_last_user_content(messages)
    if not user_text:
        return False
    strong_keywords = [
        "全书梗概",
        "固定输出：",
        "主要人物和他们的行为",
        "只能包含 `主要人物和他们的行为` 与 `内容`",
        "严禁输出 `人物信息`、`故事背景`、`简介`",
    ]
    if sum(1 for k in strong_keywords if k in user_text) >= 3:
        return True
    return (
        "固定输出" in user_text
        and "主要人物和他们的行为" in user_text
        and ("全书梗概" in user_text or "小说梗概" in user_text)
    )


def _is_outline_request(messages: List[Dict[str, str]]) -> bool:
    user_text = _get_last_user_content(messages)
    if not user_text:
        return False
    if (
        "你是一位擅长长篇网文结构设计的策划编辑" in user_text
        and "分卷大纲" in user_text
        and "全书梗概" in user_text
    ):
        return True
    strong_keywords = [
        "分卷大纲",
        "只允许输出如下结构的列表字符串",
        "故事情节",
        "开始",
        "发展",
        "高潮",
        "结局",
        "大纲",
    ]
    if sum(1 for k in strong_keywords if k in user_text) >= 4:
        return True
    return (
        "只允许输出如下结构的列表字符串" in user_text
        and "故事情节" in user_text
        and ("当前梗概锁定的人物职责" in user_text or "全书梗概" in user_text)
    )


def _is_detail_outline_request(messages: List[Dict[str, str]]) -> bool:
    user_text = _get_last_user_content(messages)
    if not user_text or "细纲" not in user_text:
        return False
    if any(k in user_text for k in ("本章细纲", "小说章节信息", "上一章的结尾")):
        return False
    if "你是一位长篇网文章节策划，请把当前分卷内容拆成递进明确、可直接用于正文创作的章节细纲" in user_text:
        return True
    strong_keywords = [
        "固定输出：",
        "章节标题",
        "细纲内容",
        "按列表顺序递进",
        "每章内容都要包含场景、事件、对话、情感和章末钩子",
        "每个 item 只能包含",
    ]
    return sum(1 for k in strong_keywords if k in user_text) >= 4


def _detect_task_name(messages: List[Dict[str, str]]) -> str:
    user_text = _get_last_user_content(messages)
    if "标签明细" in user_text and "标签大类与标签对应关系" in user_text:
        return INFO_RECOMMEND_TASK_NAME
    if "当前分卷人物推进重点" in user_text and "章节标题" in user_text and "细纲内容" in user_text:
        return DETAIL_OUTLINE_TASK_NAME
    if _is_outline_request(messages):
        return OUTLINE_TASK_NAME
    if "固定输出" in user_text and "全书梗概" in user_text and "主要人物和他们的行为" in user_text:
        return SUMMARY_TASK_NAME
    if _is_text_request(user_text):
        first_chapter_keys = (
            "开篇第1章",
            "开篇第 1 章",
            "当前是小说开篇第1章",
            "小说开篇第1章",
        )
        non_first_keys = (
            "上一章",
            "续写",
            "非首章",
            "当前是第",
        )
        if any(k in user_text for k in first_chapter_keys) and not any(k in user_text for k in non_first_keys):
            return TEXT_FIRST_CHAPTER_TASK_NAME
        if any(k in user_text for k in non_first_keys):
            return TEXT_NON_FIRST_CHAPTER_TASK_NAME
        return TEXT_TASK_NAME
    if _is_detail_outline_request(messages):
        return DETAIL_OUTLINE_TASK_NAME
    if _is_outline_request(messages):
        return OUTLINE_TASK_NAME
    if _is_summary_request(messages):
        return SUMMARY_TASK_NAME
    if _is_info_recommend_request(messages):
        return INFO_RECOMMEND_TASK_NAME
    return "other"


def _wants_markdown_output(payload: Dict[str, object]) -> bool:
    direct = str(payload.get("output_format") or "").strip().lower()
    if direct in {"markdown", "md"}:
        return True
    response_format = payload.get("response_format")
    if isinstance(response_format, dict):
        fmt = str(response_format.get("type") or "").strip().lower()
        if fmt in {"markdown", "md"}:
            return True
    return False


def _task_supports_markdown(task_name: str) -> bool:
    # Markdown output is fully disabled for the current integration.
    # Text generation still supports streaming, but returns plain text chunks.
    return False


def _wants_markdown_for_task(
    payload: Dict[str, object],
    messages: List[Dict[str, str]],
    task_name: Optional[str] = None,
) -> bool:
    resolved_task = task_name or _resolve_task_name(payload, messages)
    if not _task_supports_markdown(resolved_task):
        return False
    return _wants_markdown_output(payload)


def _resolve_task_name(payload: Dict[str, object], messages: List[Dict[str, str]]) -> str:
    explicit = str(payload.get("task_name") or "").strip().lower()
    aliases = {
        "text_nonfirst_chapter": TEXT_NON_FIRST_CHAPTER_TASK_NAME,
        "text_non_first": TEXT_NON_FIRST_CHAPTER_TASK_NAME,
        "text_nonfirst": TEXT_NON_FIRST_CHAPTER_TASK_NAME,
        "nonfirst_chapter": TEXT_NON_FIRST_CHAPTER_TASK_NAME,
        "text_first": TEXT_FIRST_CHAPTER_TASK_NAME,
    }
    explicit = aliases.get(explicit, explicit)
    valid = {
        INFO_RECOMMEND_TASK_NAME,
        SUMMARY_TASK_NAME,
        OUTLINE_TASK_NAME,
        DETAIL_OUTLINE_TASK_NAME,
        TEXT_TASK_NAME,
        TEXT_FIRST_CHAPTER_TASK_NAME,
        TEXT_NON_FIRST_CHAPTER_TASK_NAME,
    }
    if explicit in valid:
        return explicit
    return _detect_task_name(messages)


def _render_info_recommend_markdown(text: str) -> str:
    clean = _clean_linebreaks(_sanitize_text(text).replace("<|im_end|>", ""))
    person_raw = _extract_markdown_section(clean, "人物信息")
    background = _extract_markdown_section(clean, "故事背景")
    intro = _extract_markdown_section(clean, "简介")
    people = _parse_character_names(person_raw)
    lines = ["# 小说信息推荐", ""]
    lines.append("## 人物信息")
    if people:
        for name in people:
            lines.append(f"- {name}")
    elif person_raw:
        lines.append(person_raw)
    lines.extend(["", "## 故事背景", background or "暂无。", "", "## 简介", intro or "暂无。"])
    return "\n".join(lines).strip()


def _render_summary_markdown(text: str) -> str:
    parsed = _parse_summary_obj(text)
    items = _extract_summary_items_from_obj(parsed) if parsed is not None else []
    if not items:
        return _clean_linebreaks(text)
    item = items[0]
    char_map = _extract_value_by_keys(item, SUMMARY_PERSON_KEYS)
    content = _extract_value_by_keys(item, SUMMARY_CONTENT_KEYS)
    if not isinstance(char_map, dict):
        char_map = {}
    lines = ["# 梗概", "", "## 主要人物和他们的行为"]
    if char_map:
        for name, desc in char_map.items():
            lines.append(f"- **{str(name).strip()}**：{_clean_linebreaks(desc)}")
    else:
        lines.append("- 暂无。")
    lines.extend(["", "## 内容", _clean_linebreaks(content or "") or "暂无。"])
    return "\n".join(lines).strip()


def _render_outline_markdown(text: str) -> str:
    parsed = _parse_outline_obj(text)
    items = _extract_outline_items_from_obj(parsed) if parsed is not None else []
    if not items:
        return _clean_linebreaks(text)
    lines = ["# 大纲", ""]
    story_labels = [("开始", "开始"), ("发展", "发展"), ("高潮", "高潮"), ("结局", "结局")]
    for idx, item in enumerate(items, start=1):
        char_map = _extract_value_by_keys(item, OUTLINE_PERSON_KEYS)
        story_map = _extract_value_by_keys(item, OUTLINE_STORY_KEYS)
        if not isinstance(char_map, dict):
            char_map = {}
        if not isinstance(story_map, dict):
            story_map = {}
        lines.extend([f"## 第{idx}卷", "", "### 主要人物和他们的行为"])
        if char_map:
            for name, desc in char_map.items():
                lines.append(f"- **{str(name).strip()}**：{_clean_linebreaks(desc)}")
        else:
            lines.append("- 暂无。")
        lines.extend(["", "### 故事情节"])
        for field, label in story_labels:
            lines.extend([f"#### {label}", _clean_linebreaks(story_map.get(field, "")) or "暂无。", ""])
    return "\n".join(lines).strip()


def _render_detail_outline_markdown(text: str) -> str:
    parsed = _parse_detail_outline_obj(text)
    items = _extract_detail_outline_items_from_obj(parsed) if parsed is not None else []
    if not items:
        return _clean_linebreaks(text)
    lines = ["# 细纲", ""]
    for idx, item in enumerate(items, start=1):
        title = _clean_linebreaks(_extract_value_by_keys(item, DETAIL_OUTLINE_TITLE_KEYS) or f"第{idx}章")
        content = _clean_linebreaks(_extract_value_by_keys(item, DETAIL_OUTLINE_CONTENT_KEYS) or "")
        lines.extend([f"## 第{idx}章 {title}", "", content or "暂无。", ""])
    return "\n".join(lines).strip()


def _render_text_markdown(text: str, messages: List[Dict[str, str]]) -> str:
    clean = _clean_linebreaks(_sanitize_text(text))
    user_text = _get_last_user_content(messages)
    title_match = re.search(r"\*\*第\s*1\s*章细纲\*\*[:：]?\s*([^\n]+)", user_text)
    chapter_title = title_match.group(1).strip() if title_match else ""
    if chapter_title:
        return f"# 第一章 {chapter_title}\n\n{clean}".strip()
    return f"# 正文\n\n{clean}".strip()


def _render_markdown_for_task(task_name: str, text: str, messages: List[Dict[str, str]]) -> str:
    if task_name == INFO_RECOMMEND_TASK_NAME:
        return _render_info_recommend_markdown(text)
    if task_name == SUMMARY_TASK_NAME:
        return _render_summary_markdown(text)
    if task_name == OUTLINE_TASK_NAME:
        return _render_outline_markdown(text)
    if task_name == DETAIL_OUTLINE_TASK_NAME:
        return _render_detail_outline_markdown(text)
    if task_name in {TEXT_TASK_NAME, TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
        return _render_text_markdown(text, messages)
    return _clean_linebreaks(text)


def _use_direct_structured_resolution(task_name: str) -> bool:
    return allow_direct_structured_resolution(task_name)


def _supports_direct_prompt_resolution(task_name: str) -> bool:
    return _use_direct_structured_resolution(task_name)


def _supports_light_model_resolution(task_name: str) -> bool:
    if _use_direct_structured_resolution(task_name):
        return False
    return task_name in {
        INFO_RECOMMEND_TASK_NAME,
        SUMMARY_TASK_NAME,
        OUTLINE_TASK_NAME,
        DETAIL_OUTLINE_TASK_NAME,
    }


def _build_detail_title_model_prompt(items: List[Dict[str, Any]]) -> str:
    lines = [
        "你是一位擅长拟定小说章节标题的编辑。",
        "请只根据以下每章细纲内容，为每一章拟定一个更像小说章节名的标题。",
        "",
        "要求：",
        "1. 标题要贴合该章内容与章末钩子，不要泛泛而谈。",
        "2. 标题要像小说章节名，不要写成地点+状态、人物+动作、事件摘要或策划提炼句。",
        "3. 可以保留意象、悬念、压迫感、反差感，但不要只把场景名直接拿来拼接。",
        "4. 每个标题建议 4-8 个中文字符，可以略短，但不能是半截短语。",
        "5. 各章标题之间要有区分度，不能只是换一个同义词。",
        "6. 不要解释，不要编号，不要附加说明。",
        "",
        "反例：旧码头逼近、档案室试探、废弃通道退路断",
        "正向风格参考：灰雾压港、灯影沉舟、暗礁回声、潮底封喉",
        "7. 只输出 Python 列表字符串，例如：['潮声夜渡','旧岸回灯']",
        "",
        "章节细纲：",
    ]
    for idx, item in enumerate(items, start=1):
        content = _clean_linebreaks(str(item.get("细纲内容", "") or "")).strip()
        lines.append(f"第{idx}章内容：{content}")
        lines.append("")
    return "\n".join(lines).strip()


def _parse_detail_title_model_output(text: str, expected_count: int) -> List[str]:
    source = _sanitize_text(str(text or "")).strip()
    if not source:
        return []
    for parser in (ast.literal_eval, json.loads):
        try:
            parsed = parser(source)
            if isinstance(parsed, list):
                titles = [_clean_linebreaks(str(x or "")).strip() for x in parsed]
                return [t for t in titles if t][:expected_count]
        except Exception:
            continue

    titles: List[str] = []
    for line in source.splitlines():
        clean = _clean_linebreaks(line).strip()
        clean = re.sub(r"^\s*(?:第\s*\d+\s*(?:章|个)?|[\-\*\d\.\)\(、])\s*", "", clean)
        clean = re.sub(r"^(?:标题|章节标题)\s*[:：]\s*", "", clean)
        clean = clean.strip("[]'\"“”‘’ ")
        if clean:
            titles.append(clean)
    return titles[:expected_count]


def _build_single_detail_title_prompt(content: str) -> str:
    return "\n".join(
        [
            "你是一位擅长拟定小说章节标题的编辑。",
            "请只根据以下章节细纲内容，拟定一个真正像小说章节名的标题。",
            "",
            "要求：",
            "1. 标题要贴合该章内容与章末钩子，优先从具体意象、关键动作、关系裂口或危险信号里提炼。",
            "2. 标题要有小说感，可以含蓄，但不要写成地点+状态、事件摘要、判断结论或策划说明。",
            "3. 尽量避免只用泛化抽象词直接拼接，例如“危局迫近”“旧痕未干”“退路封死”这类标题。",
            "4. 不要反复套用“撕、裂、断、逼”这类单一动词壳，尽量让标题各自有不同的意象和落点。",
            "5. 标题建议 4-8 个中文字符，尽量自然、凝练、可记忆。",
            "6. 只输出标题本身，不要解释，不要引号，不要编号。",
            "",
            "反例：档案室逼近、废弃通道退路断、旧码头显形、危局迫近、旧痕未干",
            "正向风格参考：灰雾压港、暗礁回声、灯影沉舟、潮底封喉、旧账换命、静默即刀锋",
            "",
            "章节细纲：",
            _clean_linebreaks(str(content or "")).strip(),
        ]
    ).strip()


def _write_debug_generation(task_name: str, raw_text: str) -> None:
    if task_name not in {INFO_RECOMMEND_TASK_NAME, SUMMARY_TASK_NAME, OUTLINE_TASK_NAME, DETAIL_OUTLINE_TASK_NAME}:
        return
    try:
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        target = log_dir / f"debug_{task_name}_raw.txt"
        target.write_text(str(raw_text or ""), encoding="utf-8")
    except Exception:
        pass


def _parse_csv_set(value: str) -> List[str]:
    if not value:
        return []
    out: List[str] = []
    for item in str(value).split(","):
        v = item.strip()
        if v and v not in out:
            out.append(v)
    return out


def _apply_stop_strings(text: str, stop: Optional[Sequence[str]]) -> Tuple[str, str]:
    if not stop:
        return text, "stop"

    min_pos: Optional[int] = None
    for marker in stop:
        if not marker:
            continue
        idx = text.find(marker)
        if idx != -1 and (min_pos is None or idx < min_pos):
            min_pos = idx

    if min_pos is None:
        return text, "stop"
    return text[:min_pos], "stop"


def _parse_stop(payload: Dict[str, object]) -> Optional[List[str]]:
    value = payload.get("stop")
    if value is None:
        return None
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            if isinstance(item, str) and item:
                out.append(item)
        return out if out else None
    return None


def _safe_float(value: object, default: float) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    return _safe_int(os.environ.get(name), default)


class UpstreamChatClient:
    def __init__(
        self,
        endpoint: str,
        api_key: str,
        model: Optional[str] = None,
        timeout_seconds: int = 60,
    ) -> None:
        self.endpoint = str(endpoint or "").strip()
        self.api_key = str(api_key or "").strip()
        self.model = str(model or "").strip()
        self.timeout_seconds = max(5, int(timeout_seconds))
        if not self.endpoint:
            raise ValueError("upstream endpoint is empty")
        if not self.api_key:
            raise ValueError("upstream api_key is empty")

    def _build_payload(self, payload: Dict[str, object]) -> Dict[str, object]:
        body: Dict[str, object] = {
            "messages": payload.get("messages", []),
            "stream": False,
        }
        for key in ("temperature", "top_p", "max_tokens", "stop", "repetition_penalty"):
            if key in payload:
                body[key] = payload[key]
        body["model"] = self.model or payload.get("model")
        return body

    def create_completion(self, payload: Dict[str, object]) -> Dict[str, object]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        body = self._build_payload(payload)
        resp = requests.post(
            self.endpoint,
            headers=headers,
            json=body,
            timeout=self.timeout_seconds,
        )
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, dict) or "choices" not in data:
            raise RuntimeError(f"upstream response format invalid: {data}")
        return data


class TokenHubModelRouter:
    ALL_FALLBACK_MODELS = ["deepseek-v4-pro", "deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "kimi-k2.6"]
    DEFAULT_MODELS = {
        INFO_RECOMMEND_TASK_NAME: "deepseek-v4-pro",
        SUMMARY_TASK_NAME: "deepseek-v4-flash",
        OUTLINE_TASK_NAME: "deepseek-v4-flash",
        DETAIL_OUTLINE_TASK_NAME: "deepseek-v4-pro",
        TEXT_TASK_NAME: "deepseek-v4-flash",
        TEXT_FIRST_CHAPTER_TASK_NAME: "deepseek-v4-flash",
        TEXT_NON_FIRST_CHAPTER_TASK_NAME: "deepseek-v4-flash",
    }
    DEFAULT_TOKEN_BUDGETS = {
        INFO_RECOMMEND_TASK_NAME: 1800,
        SUMMARY_TASK_NAME: 1200,
        OUTLINE_TASK_NAME: 1600,
        DETAIL_OUTLINE_TASK_NAME: 2400,
        TEXT_TASK_NAME: 3200,
        TEXT_FIRST_CHAPTER_TASK_NAME: 3200,
        TEXT_NON_FIRST_CHAPTER_TASK_NAME: 3200,
    }
    DEFAULT_FALLBACK_MODELS = {
        INFO_RECOMMEND_TASK_NAME: ["deepseek-v4-pro", "deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "kimi-k2.6"],
        DETAIL_OUTLINE_TASK_NAME: ["deepseek-v4-pro", "deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "kimi-k2.6"],
        SUMMARY_TASK_NAME: ["deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "deepseek-v4-pro", "kimi-k2.6"],
        OUTLINE_TASK_NAME: ["deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "deepseek-v4-pro", "kimi-k2.6"],
        TEXT_TASK_NAME: ["deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "deepseek-v4-pro", "kimi-k2.6"],
        TEXT_FIRST_CHAPTER_TASK_NAME: ["deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "deepseek-v4-pro", "kimi-k2.6"],
        TEXT_NON_FIRST_CHAPTER_TASK_NAME: ["deepseek-v4-flash", "qwen3.5-plus", "glm-5.1", "deepseek-v4-pro", "kimi-k2.6"],
    }

    def __init__(self, base_url: str, api_key: str, timeout_seconds: int = 1800) -> None:
        self.base_url = str(base_url or "https://tokenhub.tencentmaas.com/v1").rstrip("/")
        self.api_key = str(api_key or "").strip()
        self.timeout_seconds = max(10, int(timeout_seconds or 1800))
        if not self.api_key:
            raise ValueError("TOKENHUB_API_KEY is empty; set it in the environment before starting online model mode.")

    @property
    def chat_url(self) -> str:
        return f"{self.base_url}/chat/completions"

    def model_for(self, task_name: str) -> str:
        task = str(task_name or "").strip()
        env_name = f"TOKENHUB_MODEL_{task.upper()}" if task else ""
        if env_name and os.environ.get(env_name):
            return str(os.environ.get(env_name) or "").strip()
        if task in TEXT_STREAM_TASK_NAMES and os.environ.get("TOKENHUB_TEXT_MODEL"):
            return str(os.environ.get("TOKENHUB_TEXT_MODEL") or "").strip()
        if task == DETAIL_OUTLINE_TASK_NAME and os.environ.get("TOKENHUB_DETAIL_MODEL"):
            return str(os.environ.get("TOKENHUB_DETAIL_MODEL") or "").strip()
        if task in {INFO_RECOMMEND_TASK_NAME, SUMMARY_TASK_NAME, OUTLINE_TASK_NAME} and os.environ.get("TOKENHUB_STRUCTURED_MODEL"):
            return str(os.environ.get("TOKENHUB_STRUCTURED_MODEL") or "").strip()
        return str(os.environ.get("TOKENHUB_DEFAULT_MODEL", "") or self.DEFAULT_MODELS.get(task) or "deepseek-v4-flash").strip()

    def model_candidates_for(self, task_name: str) -> List[str]:
        task = str(task_name or "").strip()
        primary = self.model_for(task)
        env_name = f"TOKENHUB_FALLBACK_MODELS_{task.upper()}" if task else ""
        raw = str(os.environ.get(env_name) or os.environ.get("TOKENHUB_FALLBACK_MODELS", "") or "").strip()
        if raw:
            candidates = [item.strip() for item in re.split(r"[,，;；\s]+", raw) if item.strip()]
        else:
            candidates = list(self.DEFAULT_FALLBACK_MODELS.get(task) or self.ALL_FALLBACK_MODELS)
        ordered: List[str] = []
        for model_name in [primary, *candidates]:
            clean = str(model_name or "").strip()
            if clean and clean not in ordered:
                ordered.append(clean)
        return ordered or ["deepseek-v4-flash"]

    def reasoning_for(self, task_name: str) -> str:
        task = str(task_name or "").strip()
        env_name = f"TOKENHUB_REASONING_{task.upper()}" if task else ""
        return str(os.environ.get(env_name, "") or os.environ.get("TOKENHUB_REASONING_EFFORT", "") or "low").strip().lower()

    def thinking_for(self, task_name: str) -> str:
        task = str(task_name or "").strip()
        env_name = f"TOKENHUB_THINKING_{task.upper()}" if task else ""
        if os.environ.get(env_name):
            value = str(os.environ.get(env_name) or "").strip().lower()
        elif task in TEXT_STREAM_TASK_NAMES:
            value = str(os.environ.get("TOKENHUB_TEXT_THINKING", "disabled") or "disabled").strip().lower()
        else:
            value = str(os.environ.get("TOKENHUB_THINKING", "enabled") or "enabled").strip().lower()
        return "disabled" if value in {"0", "false", "off", "no", "disabled", "disable"} else "enabled"

    def max_tokens_for(self, task_name: str, requested: object = None) -> int:
        task = str(task_name or "").strip()
        env_name = f"TOKENHUB_MAX_TOKENS_{task.upper()}" if task else ""
        default_value = self.DEFAULT_TOKEN_BUDGETS.get(task, 1800)
        raw = os.environ.get(env_name) or requested or default_value
        return max(256, _safe_int(raw, default_value))

    def temperature_for(self, task_name: str, requested: object = None) -> float:
        task = str(task_name or "").strip()
        env_name = f"TOKENHUB_TEMPERATURE_{task.upper()}" if task else ""
        if os.environ.get(env_name):
            return max(0.0, min(_safe_float(os.environ.get(env_name), 0.62), 1.5))
        if requested is not None:
            return max(0.0, min(_safe_float(requested, 0.62), 1.5))
        return 0.64 if task in TEXT_STREAM_TASK_NAMES else 0.38

    def top_p_for(self, task_name: str, requested: object = None) -> float:
        task = str(task_name or "").strip()
        env_name = f"TOKENHUB_TOP_P_{task.upper()}" if task else ""
        if os.environ.get(env_name):
            return max(0.01, min(_safe_float(os.environ.get(env_name), 0.9), 1.0))
        if requested is not None:
            return max(0.01, min(_safe_float(requested, 0.9), 1.0))
        return 0.9

    def messages_for(self, payload: Dict[str, object], task_name: str) -> List[Dict[str, object]]:
        raw_messages = payload.get("messages", [])
        messages = list(raw_messages) if isinstance(raw_messages, list) else []
        if task_name not in TEXT_STREAM_TASK_NAMES:
            return messages
        guard = (
            "正文输出格式硬约束：只输出小说正文；使用简体中文与全角中文标点；"
            "人物直接说出口的话必须使用中文双引号“……”，禁止裸露台词、半角引号和英文引号；"
            "动作、心理、对白、信息揭示和场景转换要自然分段，段落之间用空行分隔，避免整章堆成超长段；"
            "每章正文约2500字，优先控制在2400-2700字，最多约3000字；宁可在章末钩子处收束，不要继续扩写；"
            "不要输出标题、解释、Markdown 代码块、提纲或写作说明。"
        )
        return [{"role": "system", "content": guard}, *messages]

    def build_payload(self, payload: Dict[str, object], task_name: str, stream: bool, model_override: Optional[str] = None) -> Dict[str, object]:
        model_name = str(model_override or self.model_for(task_name)).strip()
        messages = self.messages_for(payload, task_name)
        body: Dict[str, object] = {
            "model": model_name,
            "messages": messages,
            "stream": bool(stream),
            "temperature": self.temperature_for(task_name, payload.get("temperature")),
            "top_p": self.top_p_for(task_name, payload.get("top_p")),
            "max_tokens": self.max_tokens_for(task_name, payload.get("max_tokens")),
        }
        if model_name.lower().startswith("deepseek-") or model_name.lower().startswith("kimi-"):
            body["reasoning_effort"] = self.reasoning_for(task_name)
        stop = payload.get("stop")
        if stop:
            body["stop"] = stop
        if "repetition_penalty" in payload:
            body["repetition_penalty"] = payload["repetition_penalty"]
        if model_name.lower() == "kimi-k2.6":
            body["temperature"] = 1
            body["top_p"] = 0.95
        if model_name.lower().startswith("deepseek-"):
            body["thinking"] = {"type": self.thinking_for(task_name)}
        return body

    def task_model_mapping(self) -> Dict[str, Dict[str, object]]:
        mapping: Dict[str, Dict[str, object]] = {}
        for task_name in self.DEFAULT_MODELS:
            mapping[task_name] = {
                "model": self.model_for(task_name),
                "fallback_models": self.model_candidates_for(task_name),
                "reasoning_effort": self.reasoning_for(task_name),
                "thinking": self.thinking_for(task_name),
                "max_tokens": self.max_tokens_for(task_name),
                "temperature": self.temperature_for(task_name),
                "top_p": self.top_p_for(task_name),
                "stream": task_name in TEXT_STREAM_TASK_NAMES,
            }
        return mapping


class TokenHubChatEngine:
    online_mode = True

    def __init__(self, served_model_name: str, router: TokenHubModelRouter) -> None:
        self.served_model_name = served_model_name
        self.router = router

    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.router.api_key}",
            "Content-Type": "application/json",
        }

    def _build_nonstream_response(
        self,
        model_name: str,
        text: str,
        structured_text: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        finish_reason: str = "stop",
    ) -> Dict[str, object]:
        message: Dict[str, object] = {
            "role": "assistant",
            "content": text,
            "tool_calls": [],
        }
        if structured_text is not None:
            message["structured_content"] = structured_text
        return {
            "id": f"chat-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "logprobs": None,
                    "finish_reason": finish_reason,
                    "stop_reason": None,
                }
            ],
            "usage": {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens) + int(completion_tokens),
            },
        }

    def _stream_chunk(
        self,
        stream_id: str,
        created: int,
        model_name: str,
        delta: Dict[str, object],
        finish_reason: Optional[str],
    ) -> str:
        body = {
            "id": stream_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "delta": delta,
                    "logprobs": None,
                    "finish_reason": finish_reason,
                    "stop_reason": None,
                }
            ],
        }
        return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"

    def _normalize_for_task(self, task_name: str, upstream_text: str, messages: List[Dict[str, str]]) -> str:
        clean_text = _sanitize_text(upstream_text)
        if task_name == SUMMARY_TASK_NAME:
            return _normalize_summary_text(clean_text, messages)
        if task_name == INFO_RECOMMEND_TASK_NAME:
            return _normalize_info_recommend_text(clean_text, messages)
        if task_name == OUTLINE_TASK_NAME:
            return _normalize_outline_text(clean_text, messages)
        if task_name == DETAIL_OUTLINE_TASK_NAME:
            return _normalize_detail_outline_text(clean_text, messages)
        if task_name in TEXT_STREAM_TASK_NAMES:
            return _ensure_text_completion(_normalize_text_output(clean_text), messages, task_name=task_name)
        return clean_text

    def generate_once(self, payload: Dict[str, object]) -> Dict[str, object]:
        messages = _extract_messages(payload)
        task_name = _resolve_task_name(payload, messages)
        wants_markdown = _wants_markdown_for_task(payload, messages, task_name)
        stop_strings = _parse_stop(payload)
        last_error: Optional[BaseException] = None
        candidates = self.router.model_candidates_for(task_name)
        for index, candidate_model in enumerate(candidates):
            body = self.router.build_payload(payload, task_name=task_name, stream=False, model_override=candidate_model)
            model_name = str(body.get("model") or candidate_model or self.served_model_name)
            try:
                resp = requests.post(
                    self.router.chat_url,
                    headers=self._headers(),
                    json=body,
                    timeout=self.router.timeout_seconds,
                )
                resp.raise_for_status()
                data = resp.json()
                choices = data.get("choices")
                if not isinstance(choices, list) or not choices:
                    raise RuntimeError(f"TokenHub response choices missing: {data}")
                choice0 = choices[0] if isinstance(choices[0], dict) else {}
                message = choice0.get("message", {}) if isinstance(choice0, dict) else {}
                upstream_text = str(message.get("content", "") or "") if isinstance(message, dict) else ""
                upstream_text, finish_reason = _apply_stop_strings(upstream_text, stop_strings)
                normalized_text = self._normalize_for_task(task_name, upstream_text, messages)
                if not str(normalized_text or "").strip() and index < len(candidates) - 1:
                    raise RuntimeError("TokenHub response content empty after normalization")
                response_text = _render_markdown_for_task(task_name, normalized_text, messages) if wants_markdown else normalized_text
                usage = data.get("usage", {}) if isinstance(data.get("usage"), dict) else {}
                prompt_tokens = _safe_int(usage.get("prompt_tokens"), 0)
                completion_tokens = _safe_int(usage.get("completion_tokens"), len(response_text))
                if index > 0:
                    print(f"[tokenhub] fallback success task={task_name} model={model_name} tried={candidates[:index]}", flush=True)
                return self._build_nonstream_response(
                    model_name=model_name,
                    text=response_text,
                    structured_text=normalized_text if wants_markdown else None,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    finish_reason=str(choice0.get("finish_reason") or finish_reason or "stop"),
                )
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                body_text = exc.response.text[:800] if exc.response is not None else str(exc)
                last_error = RuntimeError(f"TokenHub request failed, model={model_name}, status={status}, body={body_text}")
                print(f"[tokenhub] model failed task={task_name} model={model_name} status={status}", flush=True)
            except Exception as exc:
                last_error = exc
                print(f"[tokenhub] model failed task={task_name} model={model_name} error={exc}", flush=True)
        raise HTTPException(status_code=502, detail=f"TokenHub request failed after fallback: {last_error}") from last_error

    def stream_generate(
        self,
        payload: Dict[str, object],
        include_done_marker: bool = False,
    ) -> Iterable[str]:
        messages = _extract_messages(payload)
        task_name = _resolve_task_name(payload, messages)
        if task_name not in TEXT_STREAM_TASK_NAMES:
            nonstream_payload = dict(payload)
            nonstream_payload["stream"] = False
            response = self.generate_once(nonstream_payload)
            content = ""
            try:
                content = str(response["choices"][0]["message"]["content"] or "")
            except Exception:
                content = ""
            created = int(time.time())
            stream_id = f"chat-{uuid.uuid4().hex}"
            model_name = str(response.get("model") or self.served_model_name)
            yield self._stream_chunk(stream_id, created, model_name, {"role": "assistant"}, None)
            for start in range(0, len(content), 120):
                piece = content[start : start + 120]
                if piece:
                    yield self._stream_chunk(stream_id, created, model_name, {"content": piece}, None)
            yield self._stream_chunk(stream_id, created, model_name, {}, "stop")
            if include_done_marker:
                yield "data: [DONE]\n\n"
            return

        created = int(time.time())
        stream_id = f"chat-{uuid.uuid4().hex}"
        stop_strings = _parse_stop(payload)
        accumulated = ""
        emitted_content = 0
        saw_content = False
        yielded_role = False
        last_error: Optional[BaseException] = None
        candidates = self.router.model_candidates_for(task_name)
        active_model = candidates[0] if candidates else self.served_model_name
        for index, candidate_model in enumerate(candidates):
            body = self.router.build_payload(payload, task_name=task_name, stream=True, model_override=candidate_model)
            model_name = str(body.get("model") or candidate_model or self.served_model_name)
            active_model = model_name
            attempt_accumulated = ""
            attempt_emitted = 0
            attempt_saw_content = False
            try:
                with requests.post(
                    self.router.chat_url,
                    headers=self._headers(),
                    json=body,
                    timeout=self.router.timeout_seconds,
                    stream=True,
                ) as resp:
                    resp.raise_for_status()
                    if not yielded_role:
                        yield self._stream_chunk(stream_id, created, model_name, {"role": "assistant"}, None)
                        yielded_role = True
                    for raw_line in resp.iter_lines(decode_unicode=False):
                        if not raw_line:
                            continue
                        try:
                            line = raw_line.decode("utf-8")
                        except UnicodeDecodeError:
                            line = raw_line.decode("utf-8", errors="replace")
                        line = line.strip()
                        if not line.startswith("data:"):
                            continue
                        data_text = line[5:].strip()
                        if not data_text or data_text == "[DONE]":
                            continue
                        try:
                            obj = json.loads(data_text)
                        except Exception:
                            continue
                        choices = obj.get("choices")
                        if not isinstance(choices, list) or not choices:
                            continue
                        choice0 = choices[0] if isinstance(choices[0], dict) else {}
                        delta = choice0.get("delta", {}) if isinstance(choice0, dict) else {}
                        if not isinstance(delta, dict):
                            continue
                        piece = str(delta.get("content") or "")
                        if piece:
                            attempt_saw_content = True
                            attempt_accumulated += piece
                            visible = attempt_accumulated
                            if stop_strings:
                                visible, _ = _apply_stop_strings(visible, stop_strings)
                            new_piece = visible[attempt_emitted:]
                            attempt_emitted = len(visible)
                            if new_piece:
                                yield self._stream_chunk(stream_id, created, model_name, {"content": new_piece}, None)
                        if choice0.get("finish_reason"):
                            break
                if attempt_saw_content:
                    saw_content = True
                    accumulated = attempt_accumulated
                    emitted_content = attempt_emitted
                    if index > 0:
                        print(f"[tokenhub] stream fallback success task={task_name} model={model_name} tried={candidates[:index]}", flush=True)
                    break
                if index < len(candidates) - 1:
                    last_error = RuntimeError("TokenHub stream produced no content")
                    print(f"[tokenhub] stream no content task={task_name} model={model_name}", flush=True)
                    continue
            except requests.HTTPError as exc:
                status = exc.response.status_code if exc.response is not None else "unknown"
                body_text = exc.response.text[:800] if exc.response is not None else str(exc)
                last_error = RuntimeError(f"TokenHub stream failed, model={model_name}, status={status}, body={body_text}")
                print(f"[tokenhub] stream model failed task={task_name} model={model_name} status={status}", flush=True)
                if attempt_saw_content or yielded_role:
                    raise HTTPException(status_code=502, detail=str(last_error)) from exc
            except Exception as exc:
                last_error = exc
                print(f"[tokenhub] stream model failed task={task_name} model={model_name} error={exc}", flush=True)
                if attempt_saw_content or yielded_role:
                    raise HTTPException(status_code=502, detail=f"TokenHub stream failed: {exc}") from exc
        if not saw_content and last_error is not None:
            raise HTTPException(status_code=502, detail=f"TokenHub stream failed after fallback: {last_error}") from last_error

        if saw_content:
            completed_text = _ensure_text_completion(_normalize_text_output(accumulated), messages, task_name=task_name)
            if len(completed_text) > len(accumulated):
                tail_piece = completed_text[len(accumulated) :]
                if tail_piece:
                    yield self._stream_chunk(stream_id, created, active_model, {"content": tail_piece}, None)
        yield self._stream_chunk(stream_id, created, active_model, {}, "stop")
        if include_done_marker:
            yield "data: [DONE]\n\n"

    def should_stream(self, payload: Dict[str, object], messages: List[Dict[str, str]]) -> bool:
        task_name = _resolve_task_name(payload, messages)
        return task_name in TEXT_STREAM_TASK_NAMES


class LocalQwenChatEngine:
    def __init__(
        self,
        model_path: str,
        served_model_name: str,
        device: str = "auto",
        dtype: str = "float16",
        adapter_path: Optional[str] = None,
        text_nonfirst_adapter_path: Optional[str] = None,
        merge_lora: bool = False,
        max_new_tokens_default: int = 1664,
        trust_remote_code: bool = True,
        upstream_client: Optional[UpstreamChatClient] = None,
        upstream_nonstream_tasks: Optional[Sequence[str]] = None,
    ) -> None:
        self.model_path = model_path
        self.served_model_name = served_model_name
        self.max_new_tokens_default = max_new_tokens_default
        self._lock = threading.Lock()
        self.upstream_client = upstream_client
        self.upstream_nonstream_tasks = set(upstream_nonstream_tasks or [])
        self.global_adapter_path = adapter_path
        self.text_nonfirst_adapter_path = text_nonfirst_adapter_path
        self.online_mode = False

        _ensure_local_model_dependencies()

        if adapter_path and text_nonfirst_adapter_path:
            raise ValueError("Use either --adapter-path or --text-nonfirst-adapter-path, not both.")

        if dtype not in {"bfloat16", "float16", "float32"}:
            raise ValueError(f"Unsupported dtype: {dtype}")

        dtype_map = {
            "bfloat16": torch.bfloat16,
            "float16": torch.float16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map[dtype]

        if device == "auto":
            if torch.cuda.is_available():
                device = "cuda"
            elif _has_xpu():
                device = "xpu"
            else:
                device = "cpu"
        self.device = device

        self.tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=trust_remote_code,
            padding_side="left",
        )
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token

        if self.device == "cuda":
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch_dtype,
                trust_remote_code=trust_remote_code,
                device_map="auto",
            )
        elif self.device == "xpu":
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch_dtype,
                trust_remote_code=trust_remote_code,
            ).to(self.device)
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch_dtype,
                trust_remote_code=trust_remote_code,
            ).to(self.device)

        if adapter_path:
            self.model = PeftModel.from_pretrained(self.model, adapter_path)
            if merge_lora:
                self.model = self.model.merge_and_unload()
        elif text_nonfirst_adapter_path:
            self.model = PeftModel.from_pretrained(self.model, text_nonfirst_adapter_path)

        self.model.eval()

    def _adapter_context_for_task(self, task_name: str):
        if not self.text_nonfirst_adapter_path:
            return nullcontext()
        if not isinstance(self.model, PeftModel):
            return nullcontext()
        if task_name == TEXT_NON_FIRST_CHAPTER_TASK_NAME:
            return nullcontext()
        return self.model.disable_adapter()

    def _build_prompt(self, messages: List[Dict[str, str]], payload: Optional[Dict[str, object]] = None) -> str:
        enable_thinking = False
        if payload is not None and isinstance(payload.get("enable_thinking"), bool):
            enable_thinking = bool(payload.get("enable_thinking"))

        prompt_messages = messages
        try:
            task_name = _resolve_task_name(payload or {}, messages)
        except Exception:
            task_name = "other"
        if task_name == INFO_RECOMMEND_TASK_NAME:
            prompt_messages = [{"role": "system", "content": INFO_RECOMMEND_RELATION_GUIDE}, *messages]

        try:
            return self.tokenizer.apply_chat_template(
                prompt_messages,
                tokenize=False,
                add_generation_prompt=True,
                enable_thinking=enable_thinking,
            )
        except TypeError:
            # Fallback for templates/tokenizers that do not support enable_thinking.
            return self.tokenizer.apply_chat_template(
                prompt_messages,
                tokenize=False,
                add_generation_prompt=True,
            )
        except Exception:
            # Fallback for tokenizers without a usable chat template.
            prompt_lines: List[str] = []
            for msg in prompt_messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                prompt_lines.append(f"{role}: {content}")
            prompt_lines.append("assistant:")
            return "\n".join(prompt_lines)

    def _prepare_generate_kwargs(self, payload: Dict[str, object]) -> Dict[str, object]:
        temperature = _safe_float(payload.get("temperature"), 0.7)
        top_p = _safe_float(payload.get("top_p"), 0.9)
        repetition_penalty = _safe_float(payload.get("repetition_penalty"), 1.0)
        max_new_tokens = _safe_int(payload.get("max_tokens"), self.max_new_tokens_default)
        max_new_tokens = max(1, max_new_tokens)

        do_sample = temperature > 0.0
        kwargs: Dict[str, object] = {
            "max_new_tokens": max_new_tokens,
            "do_sample": do_sample,
            "top_p": max(0.01, min(top_p, 1.0)),
            "repetition_penalty": max(0.8, repetition_penalty),
            "pad_token_id": self.tokenizer.pad_token_id,
            "eos_token_id": self.tokenizer.eos_token_id,
            "use_cache": True,
        }
        if do_sample:
            kwargs["temperature"] = max(0.01, temperature)
        return kwargs

    def _prepare_light_task_generate_kwargs(self, task_name: str, payload: Dict[str, object]) -> Dict[str, object]:
        kwargs = self._prepare_generate_kwargs(payload)
        cap = LIGHT_TASK_TOKEN_CAPS.get(task_name, 1200)
        floor = LIGHT_TASK_TOKEN_FLOORS.get(task_name, 700)
        requested = int(kwargs.get("max_new_tokens", cap) or cap)
        kwargs["max_new_tokens"] = min(max(requested, floor), cap)
        kwargs["do_sample"] = task_name in {INFO_RECOMMEND_TASK_NAME, SUMMARY_TASK_NAME, OUTLINE_TASK_NAME, DETAIL_OUTLINE_TASK_NAME}
        kwargs["repetition_penalty"] = max(_safe_float(payload.get("repetition_penalty"), 1.04), 1.01)
        if kwargs["do_sample"]:
            if task_name == INFO_RECOMMEND_TASK_NAME:
                # The info stage locks names and topology for all later stages; keep it creative
                # enough to avoid same-draft repeats, but not so hot that names drift into mixed text.
                kwargs["temperature"] = min(max(_safe_float(payload.get("temperature"), 0.46), 0.34), 0.54)
                kwargs["top_p"] = min(max(_safe_float(payload.get("top_p"), 0.86), 0.76), 0.90)
            elif task_name in {OUTLINE_TASK_NAME, DETAIL_OUTLINE_TASK_NAME}:
                kwargs["temperature"] = min(max(_safe_float(payload.get("temperature"), 0.54), 0.38), 0.66)
                kwargs["top_p"] = min(max(_safe_float(payload.get("top_p"), 0.88), 0.78), 0.92)
            else:
                kwargs["temperature"] = min(max(_safe_float(payload.get("temperature"), 0.56), 0.36), 0.68)
                kwargs["top_p"] = min(max(_safe_float(payload.get("top_p"), 0.88), 0.78), 0.92)
            kwargs["no_repeat_ngram_size"] = max(int(payload.get("no_repeat_ngram_size") or 0), 3)
        else:
            kwargs.pop("temperature", None)
            kwargs.pop("top_p", None)
        return kwargs

    def _maybe_retitle_detail_outline(self, normalized_text: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        enabled = str(os.environ.get("NOVEL_DETAIL_RETITLE", "0") or "0").strip().lower()
        if enabled in {"1", "true", "yes", "on"}:
            return self._retitle_detail_outline_with_model(normalized_text, messages)
        return normalized_text

    def _prepare_text_task_generate_kwargs(self, task_name: str, payload: Dict[str, object]) -> Dict[str, object]:
        kwargs = self._prepare_generate_kwargs(payload)
        cap = TEXT_TASK_TOKEN_CAPS.get(task_name, 1600)
        floor = TEXT_TASK_TOKEN_FLOORS.get(task_name, 1000)
        requested = int(kwargs.get("max_new_tokens", cap) or cap)
        kwargs["max_new_tokens"] = min(max(requested, floor), cap)
        kwargs["repetition_penalty"] = max(_safe_float(payload.get("repetition_penalty"), 1.06), 1.03)
        kwargs["do_sample"] = True
        kwargs["temperature"] = min(max(_safe_float(payload.get("temperature"), 0.62), 0.42), 0.76)
        kwargs["top_p"] = min(max(_safe_float(payload.get("top_p"), 0.90), 0.78), 0.94)
        kwargs["no_repeat_ngram_size"] = max(int(payload.get("no_repeat_ngram_size") or 0), 4)
        return kwargs

    def _tokenize_prompt(self, prompt: str) -> Dict[str, torch.Tensor]:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        return {k: v.to(self.model.device) for k, v in inputs.items()}

    def _retitle_detail_outline_with_model(self, normalized_text: str, messages: Optional[List[Dict[str, str]]] = None) -> str:
        parsed = _parse_detail_outline_obj(_sanitize_text(normalized_text))
        items = _extract_detail_outline_items_from_obj(parsed) if parsed is not None else []
        if not items:
            return normalized_text

        mode = ""
        if messages:
            try:
                detail_fields = _final_extract_current_detail_fields(_get_last_user_content(messages))
                mode = str(_infer_genre_profile(detail_fields.get("categories", [])).get("mode") or "")
            except Exception:
                mode = ""
        changed = False
        seen: set[str] = set()
        seen_action_roots: set[str] = set()
        normalized_items: List[Dict[str, Any]] = []
        debug_chunks: List[str] = []
        for idx, item in enumerate(items):
            current_title = _clean_linebreaks(str(_extract_value_by_keys(item, DETAIL_OUTLINE_TITLE_KEYS) or f"第{idx + 1}章")).strip()
            content = _clean_linebreaks(str(_extract_value_by_keys(item, DETAIL_OUTLINE_CONTENT_KEYS) or "")).strip()
            prompt = _build_single_detail_title_prompt(content)
            prompt_text = self._build_prompt([{"role": "user", "content": prompt}], payload={"enable_thinking": False})
            kwargs: Dict[str, object] = {
                "max_new_tokens": 48,
                "do_sample": True,
                "temperature": 0.72,
                "top_p": 0.92,
                "repetition_penalty": 1.06,
                "no_repeat_ngram_size": 3,
                "pad_token_id": self.tokenizer.pad_token_id,
                "eos_token_id": self.tokenizer.eos_token_id,
                "use_cache": True,
            }

            with self._lock:
                inputs = self._tokenize_prompt(prompt_text)
                prompt_tokens = int(inputs["input_ids"].shape[-1])
                with torch.no_grad():
                    output_ids = self.model.generate(**inputs, **kwargs)
                generated_ids = output_ids[0, prompt_tokens:]
                raw_text = self.tokenizer.decode(generated_ids, skip_special_tokens=False)

            debug_chunks.append(f"[chapter {idx + 1}]\n{raw_text}\n")
            parsed_titles = _parse_detail_title_model_output(raw_text, 1)
            candidate = parsed_titles[0] if parsed_titles else ""
            candidate = _normalize_detail_title_seed(candidate)
            candidate = re.sub(r"^[\"“”'‘’]+|[\"“”'‘’]+$", "", candidate).strip()
            generic_title_phrases = {
                "危局迫近",
                "危局逼临",
                "旧痕未干",
                "退路封死",
                "信任崩塌",
                "危局迫局",
                "危局逼局",
                "旧街撕开",
                "暗流预演",
                "迟来的校验",
            }
            action_root_match = re.search(r"[撕裂断逼折封锁崩碎破掀]", candidate)
            action_root = action_root_match.group(0) if action_root_match else ""
            if re.search(
                r"(码头|前厅|通道|档案室|仓库|走廊|旧巷|暗巷|安全屋).*(逼近|试探|显形|前兆|新线|限窗|反扑|退路断)$",
                candidate,
            ):
                candidate = ""
            if candidate in generic_title_phrases:
                candidate = ""
            if mode == "youth" and any(token in candidate for token in ("藏尸", "凶信", "血痕", "封喉", "断喉", "尸", "血")):
                candidate = ""
            if action_root and action_root in seen_action_roots and len(candidate) <= 8:
                candidate = ""
            if (
                not candidate
                or len(candidate) < 2
                or len(candidate) > 10
                or _is_templatey_detail_title(candidate)
                or candidate in seen
            ):
                candidate = _content_driven_detail_title(content, fallback=current_title or f"第{idx + 1}章")
            if candidate != current_title:
                changed = True
            seen.add(candidate)
            final_root_match = re.search(r"[撕裂断逼折封锁崩碎破掀]", candidate)
            if final_root_match:
                seen_action_roots.add(final_root_match.group(0))
            normalized_items.append({"章节标题": candidate, "细纲内容": _ensure_period(content)})

        try:
            log_dir = Path(__file__).resolve().parent.parent / "logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            (log_dir / "debug_detail_title_raw.txt").write_text("\n".join(debug_chunks), encoding="utf-8")
        except Exception:
            pass

        return _to_single_quote_literal(normalized_items) if changed else normalized_text

    def _build_nonstream_response(
        self,
        model_name: str,
        text: str,
        structured_text: Optional[str] = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        finish_reason: str = "stop",
    ) -> Dict[str, object]:
        message: Dict[str, object] = {
            "role": "assistant",
            "content": text,
            "tool_calls": [],
        }
        if structured_text is not None:
            message["structured_content"] = structured_text
        return {
            "id": f"chat-{uuid.uuid4().hex}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": model_name,
            "choices": [
                {
                    "index": 0,
                    "message": message,
                    "logprobs": None,
                    "finish_reason": finish_reason,
                    "stop_reason": None,
                }
            ],
            "usage": {
                "prompt_tokens": int(prompt_tokens),
                "completion_tokens": int(completion_tokens),
                "total_tokens": int(prompt_tokens) + int(completion_tokens),
            },
        }

    def _try_generate_with_upstream(
        self,
        payload: Dict[str, object],
        messages: List[Dict[str, str]],
        model_name: str,
        stop_strings: Optional[Sequence[str]],
    ) -> Optional[Dict[str, object]]:
        task_name = _resolve_task_name(payload, messages)
        wants_markdown = _wants_markdown_for_task(payload, messages, task_name)
        if self.upstream_client is None:
            return None
        if task_name not in self.upstream_nonstream_tasks:
            return None
        if bool(payload.get("stream", False)):
            return None

        upstream_resp = self.upstream_client.create_completion(payload)
        choices = upstream_resp.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError(f"upstream choices missing: {upstream_resp}")
        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        message = choice0.get("message", {}) if isinstance(choice0, dict) else {}
        upstream_text = ""
        if isinstance(message, dict):
            upstream_text = str(message.get("content", "") or "")
        upstream_text = _sanitize_text(upstream_text)
        upstream_text, finish_reason = _apply_stop_strings(upstream_text, stop_strings)

        # Task-specific schema normalization.
        if task_name == SUMMARY_TASK_NAME:
            normalized_text = _normalize_summary_text(upstream_text, messages)
        elif task_name == INFO_RECOMMEND_TASK_NAME:
            normalized_text = _normalize_info_recommend_text(upstream_text, messages)
        elif task_name == OUTLINE_TASK_NAME:
            normalized_text = _normalize_outline_text(upstream_text, messages)
        elif task_name == DETAIL_OUTLINE_TASK_NAME:
            normalized_text = _normalize_detail_outline_text(upstream_text, messages)
            normalized_text = self._maybe_retitle_detail_outline(normalized_text, messages)
        else:
            normalized_text = upstream_text

        usage = upstream_resp.get("usage", {}) if isinstance(upstream_resp.get("usage"), dict) else {}
        prompt_tokens = _safe_int(usage.get("prompt_tokens"), 0)
        response_text = _render_markdown_for_task(task_name, normalized_text, messages) if wants_markdown else normalized_text
        completion_tokens = _safe_int(usage.get("completion_tokens"), len(self.tokenizer.encode(response_text, add_special_tokens=False)))
        return self._build_nonstream_response(
            model_name=model_name,
            text=response_text,
            structured_text=normalized_text if wants_markdown else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=choice0.get("finish_reason") if isinstance(choice0, dict) and choice0.get("finish_reason") else finish_reason,
        )

    def generate_once(self, payload: Dict[str, object]) -> Dict[str, object]:
        model_name = str(payload.get("model") or self.served_model_name)
        stop_strings = _parse_stop(payload)
        messages = _extract_messages(payload)
        task_name = _resolve_task_name(payload, messages)
        wants_markdown = _wants_markdown_for_task(payload, messages, task_name)
        upstream_response = self._try_generate_with_upstream(
            payload=payload,
            messages=messages,
            model_name=model_name,
            stop_strings=stop_strings,
        )
        if upstream_response is not None:
            return upstream_response

        if _supports_light_model_resolution(task_name):
            prompt = self._build_prompt(messages, payload)
            generate_kwargs = self._prepare_light_task_generate_kwargs(task_name, payload)

            with self._lock:
                inputs = self._tokenize_prompt(prompt)
                prompt_tokens = int(inputs["input_ids"].shape[-1])
                with self._adapter_context_for_task(task_name):
                    with torch.no_grad():
                        output_ids = self.model.generate(**inputs, **generate_kwargs)
                generated_ids = output_ids[0, prompt_tokens:]
                raw_text = self.tokenizer.decode(generated_ids, skip_special_tokens=False)

            _write_debug_generation(task_name, raw_text)
            text = _sanitize_text(raw_text)
            text, finish_reason = _apply_stop_strings(text, stop_strings)
            if task_name == SUMMARY_TASK_NAME:
                text = _normalize_summary_text(text, messages)
            elif task_name == INFO_RECOMMEND_TASK_NAME:
                text = _normalize_info_recommend_text(text, messages)
            elif task_name == DETAIL_OUTLINE_TASK_NAME:
                text = _normalize_detail_outline_text(text, messages)
                text = self._maybe_retitle_detail_outline(text, messages)
            else:
                text = _normalize_outline_text(text, messages)

            response_text = _render_markdown_for_task(task_name, text, messages) if wants_markdown else text
            completion_tokens = len(self.tokenizer.encode(response_text, add_special_tokens=False))
            return self._build_nonstream_response(
                model_name=model_name,
                text=response_text,
                structured_text=text if wants_markdown else None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                finish_reason=finish_reason,
            )

        if _supports_direct_prompt_resolution(task_name):
            prompt = self._build_prompt(messages, payload)
            with self._lock:
                inputs = self._tokenize_prompt(prompt)
                prompt_tokens = int(inputs["input_ids"].shape[-1])

            if task_name == SUMMARY_TASK_NAME:
                text = _normalize_summary_text("", messages)
            elif task_name == INFO_RECOMMEND_TASK_NAME:
                text = _normalize_info_recommend_text("", messages)
            elif task_name == OUTLINE_TASK_NAME:
                text = _normalize_outline_text("", messages)
            else:
                text = _normalize_detail_outline_text("", messages)
                text = self._maybe_retitle_detail_outline(text, messages)

            text, finish_reason = _apply_stop_strings(text, stop_strings)
            response_text = _render_markdown_for_task(task_name, text, messages) if wants_markdown else text
            completion_tokens = len(self.tokenizer.encode(response_text, add_special_tokens=False))
            return self._build_nonstream_response(
                model_name=model_name,
                text=response_text,
                structured_text=text if wants_markdown else None,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                finish_reason=finish_reason,
            )

        prompt = self._build_prompt(messages, payload)
        if task_name in {TEXT_TASK_NAME, TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
            generate_kwargs = self._prepare_text_task_generate_kwargs(task_name, payload)
        else:
            generate_kwargs = self._prepare_generate_kwargs(payload)

        with self._lock:
            inputs = self._tokenize_prompt(prompt)
            prompt_tokens = int(inputs["input_ids"].shape[-1])
            with self._adapter_context_for_task(task_name):
                with torch.no_grad():
                    output_ids = self.model.generate(**inputs, **generate_kwargs)
            generated_ids = output_ids[0, prompt_tokens:]
            raw_text = self.tokenizer.decode(generated_ids, skip_special_tokens=False)

        text = _sanitize_text(raw_text)
        text, finish_reason = _apply_stop_strings(text, stop_strings)
        if task_name in {TEXT_TASK_NAME, TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
            text = _normalize_text_output(text)
            text = _ensure_text_completion(text, messages, task_name=task_name)
        if task_name == SUMMARY_TASK_NAME:
            text = _normalize_summary_text(text, messages)
        elif task_name == INFO_RECOMMEND_TASK_NAME:
            text = _normalize_info_recommend_text(text, messages)
        elif task_name == OUTLINE_TASK_NAME:
            text = _normalize_outline_text(text, messages)
        elif task_name == DETAIL_OUTLINE_TASK_NAME:
            text = _normalize_detail_outline_text(text, messages)
            text = self._maybe_retitle_detail_outline(text, messages)

        response_text = _render_markdown_for_task(task_name, text, messages) if wants_markdown else text

        # Recompute completion token count after stop/sanitize for usage reporting.
        completion_tokens = len(self.tokenizer.encode(response_text, add_special_tokens=False))
        return self._build_nonstream_response(
            model_name=model_name,
            text=response_text,
            structured_text=text if wants_markdown else None,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
        )

    def stream_generate(
        self,
        payload: Dict[str, object],
        include_done_marker: bool = False,
    ) -> Iterable[str]:
        model_name = str(payload.get("model") or self.served_model_name)
        messages = _extract_messages(payload)
        task_name = _resolve_task_name(payload, messages)
        if _wants_markdown_for_task(payload, messages, task_name):
            nonstream_payload = dict(payload)
            nonstream_payload["stream"] = False
            response = self.generate_once(nonstream_payload)
            content = ""
            try:
                content = str(response["choices"][0]["message"]["content"] or "")
            except Exception:
                content = ""
            created = int(time.time())
            stream_id = f"chat-{uuid.uuid4().hex}"

            def make_chunk(delta: Dict[str, object], finish_reason: Optional[str]) -> str:
                body = {
                    "id": stream_id,
                    "object": "chat.completion.chunk",
                    "created": created,
                    "model": model_name,
                    "choices": [
                        {
                            "index": 0,
                            "delta": delta,
                            "logprobs": None,
                            "finish_reason": finish_reason,
                            "stop_reason": None,
                        }
                    ],
                }
                return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"

            yield make_chunk({"role": "assistant"}, None)
            chunk_size = 120
            for start in range(0, len(content), chunk_size):
                piece = content[start : start + chunk_size]
                if piece:
                    yield make_chunk({"content": piece}, None)
            yield make_chunk({}, "stop")
            if include_done_marker:
                yield "data: [DONE]\n\n"
            return

        stop_strings = _parse_stop(payload)
        prompt = self._build_prompt(messages, payload)
        if task_name in {TEXT_TASK_NAME, TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
            generate_kwargs = self._prepare_text_task_generate_kwargs(task_name, payload)
        else:
            generate_kwargs = self._prepare_generate_kwargs(payload)
        created = int(time.time())
        stream_id = f"chat-{uuid.uuid4().hex}"

        def make_chunk(delta: Dict[str, object], finish_reason: Optional[str]) -> str:
            body = {
                "id": stream_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model_name,
                "choices": [
                    {
                        "index": 0,
                        "delta": delta,
                        "logprobs": None,
                        "finish_reason": finish_reason,
                        "stop_reason": None,
                    }
                ],
            }
            return f"data: {json.dumps(body, ensure_ascii=False)}\n\n"

        self._lock.acquire()
        try:
            inputs = self._tokenize_prompt(prompt)
            streamer = TextIteratorStreamer(
                self.tokenizer,
                skip_prompt=True,
                skip_special_tokens=False,
            )

            def _run_generate_stream() -> None:
                with self._adapter_context_for_task(task_name):
                    with torch.no_grad():
                        kwargs = {**inputs, **generate_kwargs, "streamer": streamer}
                        self.model.generate(**kwargs)

            worker = threading.Thread(
                target=_run_generate_stream,
                daemon=True,
            )
            worker.start()

            yield make_chunk({"role": "assistant"}, None)

            merged_text = ""
            finish_reason: Optional[str] = None
            reasoning_emitted_len = 0
            visible_emitted_len = 0
            for piece in streamer:
                if not isinstance(piece, str):
                    continue
                chunk = _sanitize_text_keep_think(piece)
                if not chunk:
                    continue

                merged_text += chunk
                reasoning_text, visible_text = _split_reasoning_and_visible(merged_text)
                if stop_strings:
                    cut_visible_text, _ = _apply_stop_strings(visible_text, stop_strings)
                    if len(cut_visible_text) < len(visible_text):
                        visible_text = cut_visible_text
                        finish_reason = "stop"
                reasoning_new = reasoning_text[reasoning_emitted_len:]
                visible_new = visible_text[visible_emitted_len:]
                if reasoning_new:
                    reasoning_emitted_len = len(reasoning_text)
                    yield make_chunk({"reasoning_content": reasoning_new}, None)
                if visible_new:
                    visible_emitted_len = len(visible_text)
                    yield make_chunk({"content": visible_new}, None)
                if finish_reason == "stop":
                    break

            worker.join()
            if task_name in {TEXT_TASK_NAME, TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
                _, final_visible_text = _split_reasoning_and_visible(merged_text)
                normalized_visible_text = _normalize_text_output(final_visible_text)
                completed_text = _ensure_text_completion(normalized_visible_text, messages, task_name=task_name)
                if len(completed_text) > len(normalized_visible_text):
                    tail_piece = completed_text[len(normalized_visible_text) :]
                    if tail_piece:
                        yield make_chunk({"content": tail_piece}, None)
            yield make_chunk({}, finish_reason or "stop")
            if include_done_marker:
                yield "data: [DONE]\n\n"
        finally:
            self._lock.release()


def create_app(
    engine: LocalQwenChatEngine,
    include_done_marker: bool = False,
    novel_wiki_root: str = "data/novel_wiki",
) -> FastAPI:
    app = FastAPI(title="Local Qwen OpenAI-Compatible Server", version="0.1.0")
    app.state.engine = engine
    app.state.include_done_marker = include_done_marker
    app.state.novel_wiki = NovelWikiStore(novel_wiki_root)

    def resolve_user_id(payload: Optional[Dict[str, object]] = None, request: Optional[Request] = None) -> str:
        payload = payload or {}
        query_user_id = ""
        if request is not None:
            query_user_id = str(request.query_params.get("user_id") or request.query_params.get("uid") or "").strip()
        rag_options = payload.get("novel_rag")
        rag_user_id = ""
        if isinstance(rag_options, dict):
            rag_user_id = str(rag_options.get("user_id") or rag_options.get("uid") or "").strip()
        return str(
            payload.get("user_id")
            or payload.get("uid")
            or payload.get("author_id")
            or rag_user_id
            or query_user_id
            or "default"
        ).strip() or "default"

    def resolve_novel_id(payload: Optional[Dict[str, object]] = None, default: str = "") -> str:
        payload = payload or {}
        rag_options = payload.get("novel_rag")
        rag_novel_id = ""
        if isinstance(rag_options, dict):
            rag_novel_id = str(
                rag_options.get("novel_id")
                or rag_options.get("project_id")
                or rag_options.get("story_id")
                or ""
            ).strip()
        return str(
            payload.get("novel_id")
            or payload.get("project_id")
            or payload.get("story_id")
            or rag_novel_id
            or default
        ).strip()

    def resolve_payload_topology(payload: Dict[str, object]) -> Optional[Dict[str, Any]]:
        def as_topology(value: object) -> Optional[Dict[str, Any]]:
            if isinstance(value, dict):
                return value
            if isinstance(value, str) and value.strip():
                try:
                    parsed = json.loads(value)
                except Exception:
                    return None
                return parsed if isinstance(parsed, dict) else None
            return None

        rag_options = payload.get("novel_rag")
        if isinstance(rag_options, dict):
            topology = rag_options.get("topology_context") or rag_options.get("topology")
            parsed_topology = as_topology(topology)
            if parsed_topology is not None:
                return parsed_topology
        topology = payload.get("topology_context") or payload.get("topology") or payload.get("novel_topology")
        return as_topology(topology)

    def attach_info_topology(response: Dict[str, object], payload: Dict[str, object], messages: List[Dict[str, str]]) -> Dict[str, object]:
        task_name = _resolve_task_name(payload, messages)
        if task_name != INFO_RECOMMEND_TASK_NAME:
            return response
        rag_options = payload.get("novel_rag")
        if isinstance(rag_options, dict) and rag_options.get("topology") is False:
            return response
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            return response
        choice0 = choices[0] if isinstance(choices[0], dict) else {}
        message = choice0.get("message") if isinstance(choice0, dict) else None
        if not isinstance(message, dict):
            return response
        content = str(message.get("content") or "")
        if not content.strip():
            return response
        novel_id = resolve_novel_id(payload, default="default") or "default"
        user_id = resolve_user_id(payload)
        title = ""
        try:
            fields = _extract_info_prompt_fields(_get_last_user_content(messages))
            title = str(fields.get("title", "") or "")
        except Exception:
            title = ""
        persist = True
        if isinstance(rag_options, dict) and rag_options.get("persist_topology") is False:
            persist = False
        store: NovelWikiStore = app.state.novel_wiki
        topology = store.build_topology_from_info_recommend(novel_id=novel_id, user_id=user_id, info_text=content, title=title, persist=persist)
        message["novel_topology"] = topology
        message["topology"] = topology
        response["novel_topology"] = topology
        response["topology"] = topology
        return response

    def enrich_payload_with_novel_rag(payload: Dict[str, object]) -> Dict[str, object]:
        try:
            messages = _extract_messages(payload)
            task_name = _resolve_task_name(payload, messages)
            if task_name == INFO_RECOMMEND_TASK_NAME:
                return payload
            rag_options = payload.get("novel_rag")
            if isinstance(rag_options, dict) and rag_options.get("enabled") is False:
                return payload
            novel_id = resolve_novel_id(payload)
            if not novel_id:
                return payload
            user_id = resolve_user_id(payload)
            query_parts = [_get_last_user_content(messages)]
            if task_name in {TEXT_TASK_NAME, TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
                query_parts.append("章节正文 近期事件 人物状态 关系变化 世界观规则")
            elif task_name == DETAIL_OUTLINE_TASK_NAME:
                query_parts.append("章节细纲 当前卷 人物关系 伏笔 世界观规则")
                if isinstance(rag_options, dict):
                    current_volume = rag_options.get("current_volume")
                    previous_volume = rag_options.get("previous_volume")
                    if current_volume:
                        if not previous_volume and str(current_volume).isdigit():
                            previous_volume = max(1, int(current_volume) - 1)
                        query_parts.append(f"当前生成第{current_volume}卷细纲，需要承接第{previous_volume or '?'}卷正文记忆、人物状态、未回收伏笔、卷末事实。")
            elif task_name == OUTLINE_TASK_NAME:
                query_parts.append("分卷大纲 主线冲突 人物弧光 阵营关系")
            elif task_name == SUMMARY_TASK_NAME:
                query_parts.append("全书梗概 核心人物 世界观 主线冲突")
            store: NovelWikiStore = app.state.novel_wiki
            current_volume = None
            if isinstance(rag_options, dict):
                try:
                    current_volume = int(rag_options.get("current_volume") or 0) or None
                except Exception:
                    current_volume = None
            context = store.build_rag_context(
                novel_id,
                "\n".join(query_parts),
                task_name=task_name,
                user_id=user_id,
                topology=resolve_payload_topology(payload),
                current_volume=current_volume,
            )
            has_useful_context = any(
                marker in context
                for marker in (
                    "## 相关设定/资料",
                    "## 人物关系拓扑",
                    "## 近期章节记忆",
                    "## 长程连续性记忆",
                    "## 必须承接的长程记忆",
                    "## 世界观硬设定",
                )
            )
            if not context or not has_useful_context:
                return payload
            enriched = dict(payload)
            enriched_messages = [{"role": "system", "content": context}, *messages]
            enriched["messages"] = enriched_messages
            enriched["novel_rag_context"] = context
            return enriched
        except Exception as exc:
            enriched = dict(payload)
            enriched["novel_rag_error"] = str(exc)
            return enriched

    def refine_chapter_memory_with_model(
        engine_ref: LocalQwenChatEngine,
        novel_id: str,
        chapter_no: int,
        title: str,
        content: str,
    ) -> Optional[Dict[str, object]]:
        prompt = (
            "你是小说 Wiki 记忆整理器。请从章节正文中提炼稳定事实，只返回严格 JSON，不要 Markdown。\n"
            "要求：不要预测未来；不要编造正文没有出现的信息；不要把章节里的信任变化、情绪变化、临时合作改写为静态人物关系拓扑。\n"
            "JSON 字段：chapter_summary 字符串；character_states 数组；locations 数组；foreshadows 数组；events 数组；timeline 数组。\n"
            "character_states 可用对象 {\"character\":\"人物名\",\"state\":\"本章后的状态/认知/立场\"}。\n"
            "locations 可用对象 {\"name\":\"地点名\",\"description\":\"本章发生的场景事实\"}。\n"
            "foreshadows 只记录线索、秘密、异常物件、未解释信息。\n"
            f"小说ID：{novel_id}\n章节：第 {chapter_no} 章《{title}》\n正文：\n{content[:3600]}"
        )
        refine_payload: Dict[str, object] = {
            "model": engine_ref.served_model_name,
            "stream": False,
            "temperature": 0.2,
            "max_tokens": 900,
            "novel_rag": {"enabled": False},
            "messages": [
                {"role": "system", "content": "你只输出可被 json.loads 解析的 JSON 对象。"},
                {"role": "user", "content": prompt},
            ],
        }
        try:
            response = engine_ref.generate_once(refine_payload)
            text = str(response.get("choices", [{}])[0].get("message", {}).get("content") or "")
            parsed = _parse_json_object_from_text(text)
            if parsed:
                parsed["refiner"] = "local_llm"
            return parsed
        except Exception:
            return None

    @app.get("/health")
    def health() -> Dict[str, object]:
        online_mode = bool(getattr(engine, "online_mode", False))
        result: Dict[str, object] = {
            "status": "ok",
            "mode": "online" if online_mode else "local",
            "served_model_name": getattr(engine, "served_model_name", ""),
        }
        router = getattr(engine, "router", None)
        if router is not None:
            if hasattr(router, "task_model_mapping"):
                model_mapping = router.task_model_mapping()
            else:
                model_mapping = getattr(router, "DEFAULT_MODELS", {})
            result["tokenhub_base_url"] = getattr(router, "base_url", "")
            result["tokenhub_models"] = model_mapping
            result["task_model_mapping"] = model_mapping
        return result

    @app.post("/v1/novel/wiki/projects/{novel_id}/documents")
    async def upload_novel_wiki_document(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        title = str(payload.get("title") or "").strip()
        content = _normalize_content(payload.get("content", "")).strip()
        if not content:
            raise HTTPException(status_code=400, detail="`content` is required.")
        user_id = resolve_user_id(payload, request)
        store: NovelWikiStore = request.app.state.novel_wiki
        document = store.ingest_document(
            novel_id=novel_id,
            user_id=user_id,
            title=title or "未命名资料",
            content=content,
            source_type=str(payload.get("source_type") or "text"),
            tags=payload.get("tags") if isinstance(payload.get("tags"), list) else None,
            metadata=payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None,
        )
        extracted = store.extract_relations(
            novel_id=novel_id,
            user_id=user_id,
            text=content,
            characters=payload.get("characters") if isinstance(payload.get("characters"), list) else None,
        )
        auto_import = bool(payload.get("auto_import_relations", False))
        imported_relations: List[Dict[str, Any]] = []
        if auto_import:
            for relation in extracted["relations"]:
                imported_relations.append(
                    store.upsert_relation(
                        novel_id=novel_id,
                        user_id=user_id,
                        source=relation["source"],
                        target=relation["target"],
                        relation_type=relation["relation_type"],
                        description=relation["description"],
                        evidence=document.path,
                    )
                )
        return JSONResponse(
            {
                "document": document.__dict__,
                "extracted_relations": extracted["relations"],
                "imported_relations": imported_relations,
                "wiki_status": store.project_status(novel_id, user_id=user_id),
            }
        )

    @app.post("/v1/novel/wiki/projects/{novel_id}/characters")
    async def upsert_novel_character(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        name = str(payload.get("name") or "").strip()
        if not name:
            raise HTTPException(status_code=400, detail="`name` is required.")
        user_id = resolve_user_id(payload, request)
        store: NovelWikiStore = request.app.state.novel_wiki
        try:
            result = store.upsert_character(
                novel_id=novel_id,
                user_id=user_id,
                name=name,
                profile=str(payload.get("profile") or ""),
                aliases=payload.get("aliases") if isinstance(payload.get("aliases"), list) else None,
                faction=str(payload.get("faction") or ""),
                background=str(payload.get("background") or ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(result)

    @app.post("/v1/novel/wiki/projects/{novel_id}/relations")
    async def upsert_novel_relation(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(payload, request)
        try:
            result = store.upsert_relation(
                novel_id=novel_id,
                user_id=user_id,
                source=str(payload.get("source") or ""),
                target=str(payload.get("target") or ""),
                relation_type=str(payload.get("relation_type") or ""),
                description=str(payload.get("description") or ""),
                evidence=str(payload.get("evidence") or ""),
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return JSONResponse(result)

    @app.post("/v1/novel/wiki/projects/{novel_id}/relations/extract")
    async def extract_novel_relations(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        text = _normalize_content(payload.get("text", "")).strip()
        if not text:
            raise HTTPException(status_code=400, detail="`text` is required.")
        user_id = resolve_user_id(payload, request)
        store: NovelWikiStore = request.app.state.novel_wiki
        result = store.extract_relations(
            novel_id=novel_id,
            user_id=user_id,
            text=text,
            characters=payload.get("characters") if isinstance(payload.get("characters"), list) else None,
        )
        return JSONResponse(result)

    @app.post("/v1/novel/wiki/projects/{novel_id}/topology/from-info")
    async def build_topology_from_info_recommend(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        info_text = _normalize_content(payload.get("info_recommend", payload.get("text", ""))).strip()
        if not info_text:
            raise HTTPException(status_code=400, detail="`info_recommend` or `text` is required.")
        user_id = resolve_user_id(payload, request)
        store: NovelWikiStore = request.app.state.novel_wiki
        result = store.build_topology_from_info_recommend(
            novel_id=novel_id,
            user_id=user_id,
            info_text=info_text,
            title=str(payload.get("title") or ""),
            persist=bool(payload.get("persist", False)),
        )
        result["wiki_status"] = store.project_status(novel_id, user_id=user_id)
        return JSONResponse(result)

    @app.post("/v1/novel/wiki/projects/{novel_id}/topology/persist")
    async def persist_novel_topology(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        topology = payload.get("topology")
        if not isinstance(topology, dict) or not topology:
            raise HTTPException(status_code=400, detail="`topology` is required.")
        user_id = resolve_user_id(payload, request)
        store: NovelWikiStore = request.app.state.novel_wiki
        result = store.persist_topology(
            novel_id=novel_id,
            user_id=user_id,
            topology=topology,
            title=str(payload.get("title") or ""),
            source_text=_normalize_content(payload.get("info_recommend", payload.get("text", ""))).strip(),
        )
        result["wiki_status"] = store.project_status(novel_id, user_id=user_id)
        return JSONResponse(result)

    @app.get("/v1/novel/wiki/projects/{novel_id}/topology")
    async def get_novel_topology(novel_id: str, request: Request):
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(request=request)
        return JSONResponse(store.build_topology(novel_id, user_id=user_id))

    @app.get("/v1/novel/wiki/projects/{novel_id}/status")
    async def get_novel_wiki_status(novel_id: str, request: Request):
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(request=request)
        return JSONResponse(store.project_status(novel_id, user_id=user_id))

    @app.get("/v1/novel/wiki/projects/{novel_id}/documents")
    async def list_novel_wiki_documents(novel_id: str, request: Request):
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(request=request)
        return JSONResponse(store.project_status(novel_id, user_id=user_id))

    @app.get("/v1/novel/wiki/projects/{novel_id}/documents/{document_id}")
    async def get_novel_wiki_document(novel_id: str, document_id: str, request: Request):
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(request=request)
        try:
            return JSONResponse(store.get_document(novel_id, document_id=document_id, user_id=user_id))
        except FileNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/v1/novel/wiki/projects/{novel_id}/search")
    async def search_novel_wiki(novel_id: str, request: Request):
        query = str(request.query_params.get("q") or "").strip()
        limit_raw = str(request.query_params.get("limit") or "8")
        try:
            limit = int(limit_raw)
        except ValueError:
            limit = 8
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(request=request)
        return JSONResponse(store.search(novel_id, query=query, limit=limit, user_id=user_id))

    @app.get("/v1/novel/wiki/projects/{novel_id}/continuity")
    async def check_novel_continuity(novel_id: str, request: Request):
        persist_raw = str(request.query_params.get("persist") or "true").strip().lower()
        persist = persist_raw not in {"0", "false", "no"}
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(request=request)
        return JSONResponse(store.continuity_report(novel_id, user_id=user_id, persist=persist))

    @app.post("/v1/novel/wiki/projects/{novel_id}/continuity")
    async def check_novel_continuity_with_payload(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        persist_raw = str(payload.get("persist", request.query_params.get("persist", "true"))).strip().lower()
        persist = persist_raw not in {"0", "false", "no"}
        store: NovelWikiStore = request.app.state.novel_wiki
        user_id = resolve_user_id(payload, request)
        return JSONResponse(
            store.continuity_report(
                novel_id,
                user_id=user_id,
                persist=persist,
                topology=resolve_payload_topology(payload),
            )
        )

    @app.post("/v1/novel/wiki/projects/{novel_id}/chapters/writeback")
    async def writeback_novel_chapter(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        content = _normalize_content(payload.get("content", "")).strip()
        if not content:
            raise HTTPException(status_code=400, detail="`content` is required.")
        user_id = resolve_user_id(payload, request)
        chapter_no = _safe_int(payload.get("chapter_no"), 1)
        title = str(payload.get("title") or f"第{chapter_no}章")
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else None
        refine = bool(payload.get("refine") or payload.get("llm_refine"))
        refined_memory = None
        if refine:
            engine_ref: LocalQwenChatEngine = request.app.state.engine
            refined_memory = refine_chapter_memory_with_model(engine_ref, novel_id, chapter_no, title, content)
        store: NovelWikiStore = request.app.state.novel_wiki
        result = store.writeback_chapter(
            novel_id,
            chapter_no=chapter_no,
            title=title,
            content=content,
            user_id=user_id,
            metadata=metadata,
            refined_memory=refined_memory,
        )
        if refine and not refined_memory:
            result["refine_warning"] = "llm_refine_failed_or_empty; fallback_to_rule_candidates"
        result["wiki_status"] = store.project_status(novel_id, user_id=user_id)
        return JSONResponse(result)

    @app.post("/v1/novel/wiki/projects/{novel_id}/chapters/quality")
    async def check_novel_chapter_quality(novel_id: str, request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc
        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")
        content = _normalize_content(payload.get("content", "")).strip()
        if not content:
            raise HTTPException(status_code=400, detail="`content` is required.")
        user_id = resolve_user_id(payload, request)
        chapter_no = _safe_int(payload.get("chapter_no"), 1)
        title = str(payload.get("title") or f"第{chapter_no}章")
        persist_raw = str(payload.get("persist", request.query_params.get("persist", "true"))).strip().lower()
        persist = persist_raw not in {"0", "false", "no"}
        store: NovelWikiStore = request.app.state.novel_wiki
        return JSONResponse(
            store.quality_check_chapter(
                novel_id,
                chapter_no=chapter_no,
                title=title,
                content=content,
                user_id=user_id,
                detail_outline=str(payload.get("detail_outline") or payload.get("outline") or ""),
                topology=resolve_payload_topology(payload),
                persist=persist,
            )
        )

    @app.post("/v1/chat/completions")
    async def chat_completions(request: Request):
        try:
            payload = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Invalid JSON body: {exc}") from exc

        if not isinstance(payload, dict):
            raise HTTPException(status_code=400, detail="JSON body must be an object.")

        stream = bool(payload.get("stream", False))
        engine_ref: LocalQwenChatEngine = request.app.state.engine

        enriched_payload = enrich_payload_with_novel_rag(payload)

        if stream:
            generator = engine_ref.stream_generate(
                enriched_payload,
                include_done_marker=request.app.state.include_done_marker,
            )
            return StreamingResponse(generator, media_type="text/event-stream")

        response = engine_ref.generate_once(enriched_payload)
        try:
            messages = _extract_messages(enriched_payload)
            response = attach_info_topology(response, enriched_payload, messages)
        except Exception as exc:
            response.setdefault("novel_rag_error", f"topology generation failed: {exc}")
        return JSONResponse(response)

    return app


def _story_clause_pool(text: str, min_len: int = 8) -> List[str]:
    clauses = _extract_clean_clauses(text, min_len=min_len)
    cleaned: List[str] = []
    seen: set[str] = set()
    for clause in clauses:
        value = _clean_behavior_sentence(_strip_plot_stage_label(clause))
        value = value.strip("，。；、 ")
        if len(value) < min_len or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def _pick_clause(pool: Sequence[str], index: int, default: str) -> str:
    if not pool:
        return default
    value = str(pool[index % len(pool)]).strip()
    return value or default


def _normalize_text_output(text: str) -> str:
    clean = _to_simplified_lite(_clean_linebreaks(_sanitize_text(str(text or ""))))
    clean = clean.replace("伮立", "伫立")
    clean = clean.replace("船船票", "船票")
    clean = clean.replace("船票务买人口", "船票买卖人口")
    clean = clean.replace("\\n", "\n").replace("\\r", "").replace("\\t", " ")
    clean = re.sub(r"\\+(?=[一-鿿，。！？；：、“”‘’\"'])", "", clean)
    clean = clean.replace("\\", "")
    clean = re.sub(r"^\s*#.+?$", "", clean, flags=re.MULTILINE)
    clean = clean.replace("```", "")
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", clean) if p.strip()]
    deduped: List[str] = []
    for para in paragraphs:
        if deduped and _text_similarity(para, deduped[-1]) >= 0.92:
            continue
        deduped.append(para)
    clean = "\n\n".join(deduped).strip()
    clean = re.sub(r"\n{3,}", "\n\n", clean)
    clean = _strip_text_structural_leakage(clean)
    if clean and not re.search(r"[。！？!?…」』”\"]\s*$", clean):
        clauses = _extract_clean_clauses(clean, min_len=4)
        if len(clauses) >= 2:
            clean = _ensure_period("，".join(clauses[:-1]))
        else:
            clean = _ensure_period(clean)
    return clean


def _fill_behavior_to_length(parts: Sequence[str], min_chars: int) -> str:
    text = _clean_linebreaks("".join(str(x).strip() for x in parts if str(x).strip()))
    text = _ensure_period(text)
    if len(text) >= min_chars:
        return text
    extra = (
        "这条线不会只停留在口头判断上，后续还会继续改变人物之间的信任顺序、选择成本和局面压力，"
        "让这个角色或段落真正承担起推动主线的作用。"
    )
    return _ensure_period(text + extra)


def _fill_with_varied_tail(parts: Sequence[str], min_chars: int, variant: int) -> str:
    text = _clean_linebreaks("".join(str(x).strip() for x in parts if str(x).strip()))
    text = _ensure_period(text)
    if len(text) >= min_chars:
        return text
    tails = [
        "这也会让他后续的每一次选择都带上更明确的风险与责任，不可能只是旁观或补位。",
        "这样安排的意义不只是补齐功能位，而是让他的行动真正改变局势推进与人物关系。",
        "因此这条线会持续影响后面的站位、信任和代价分配，而不是只在本卷里短暂出现。",
        "后续冲突一旦升级，他承担的这部分功能就会被放到更靠前的位置，直接决定成败。",
    ]
    return _ensure_period(text + tails[variant % len(tails)])


def _final_parse_character_block(raw: Any, title: str = "", fallback_text: str = "") -> Dict[str, str]:
    text = _clean_linebreaks(str(raw or "")).strip()
    parsed = None
    if text:
        for parser in (json.loads, ast.literal_eval):
            try:
                parsed = parser(text)
                break
            except Exception:
                continue
    char_map: Dict[str, str] = {}
    if parsed is not None:
        char_map = _coerce_char_map(parsed, {})
    if char_map:
        cleaned: Dict[str, str] = {}
        for raw_name, raw_behavior in char_map.items():
            name = str(raw_name or "").strip().strip("'\"")
            if not name:
                continue
            if not _is_valid_person_name(name, title=title) and name not in {"义父", "阿爸", "阿妈", "父亲", "母亲"}:
                continue
            behavior = _clean_behavior_sentence(str(raw_behavior or ""))
            if not behavior:
                behavior = _clean_behavior_sentence(_merge_name_actions_from_intro(name, fallback_text))
            cleaned[name] = _ensure_period(behavior or f"{name}围绕主线持续行动，并在关键节点推动局势变化")
        if cleaned:
            return cleaned

    line_map: Dict[str, str] = {}
    for line in text.splitlines():
        value = line.strip().lstrip("-").lstrip("•").strip()
        if not value:
            continue
        match = re.match(r"^([一-鿿A-Za-z0-9_]{2,12})\s*[:：]\s*(.+)$", value)
        if not match:
            continue
        name = match.group(1).strip()
        if not _is_valid_person_name(name, title=title) and name not in {"义父", "阿爸", "阿妈", "父亲", "母亲"}:
            continue
        line_map[name] = _ensure_period(_clean_behavior_sentence(match.group(2)))
    if line_map:
        return line_map

    names = _extract_name_candidates(title, fallback_text, [])
    if not names:
        names = _build_default_person_names(title, [], count=6)
    return _build_char_map_from_intro(names, fallback_text)


def _final_extract_prompt_block(user_text: str, start_labels: Sequence[str], stop_labels: Sequence[str]) -> str:
    text = str(user_text or "")
    start_pos: Optional[int] = None
    matched_end = -1
    for label in start_labels:
        pattern = rf"(?m)^\s*(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*[:：]"
        match = re.search(pattern, text)
        if match and (start_pos is None or match.start() < start_pos):
            start_pos = match.start()
            matched_end = match.end()
    if start_pos is None or matched_end < 0:
        return ""
    tail = text[matched_end:]
    end_pos = len(tail)
    for label in stop_labels:
        pattern = rf"\n\s*(?:\*\*)?{re.escape(label)}(?:\*\*)?\s*[:：]"
        match = re.search(pattern, tail)
        if match and match.start() < end_pos:
            end_pos = match.start()
    return tail[:end_pos].strip()


def _final_parse_grouped_tag_map(user_text: str) -> Dict[str, List[str]]:
    alias_map = {
        "篇幅": "length",
        "风格": "style",
        "时代背景": "era",
        "世界设定": "world",
        "题材": "genre",
        "情绪基调": "tone",
        "场景方向": "scene",
        "人物关系": "relation",
        "剧情驱动": "driver",
        "核心元素": "elements",
    }
    out: Dict[str, List[str]] = {value: [] for value in alias_map.values()}
    for raw_line in str(user_text or "").splitlines():
        line = raw_line.strip().lstrip("-").lstrip("•").strip()
        if not line:
            continue
        match = re.match(r"^(篇幅|风格|时代背景|世界设定|题材|情绪基调|场景方向|人物关系|剧情驱动|核心元素)\s*[:：]\s*(.+)$", line)
        if not match:
            continue
        key = alias_map.get(match.group(1))
        values = [x.strip() for x in re.split(r"[、,，/|；;]+", match.group(2)) if x.strip()]
        for value in values:
            if value not in out[key]:
                out[key].append(value)
    return out


def _infer_genre_profile(categories: Sequence[str]) -> Dict[str, Any]:
    genre_text = "、".join(str(x).strip() for x in categories if str(x).strip())
    if any(k in genre_text for k in ("都市日常", "邻里", "邻里群像", "现实向", "慢节奏", "亲情", "旧物", "旧城", "杂货铺")):
        return {
            "mode": "daily",
            "fallback_scene": "槐安巷尽头的旧杂货铺",
            "ambient_line": "雨后的青石板还带着潮气，木柜抽屉里的樟脑味和旧收音机声一起停在巷子深处。",
            "evidence": "一本缺页的旧物登记本",
            "danger_line": "旧城更新和多年误会正在同时逼近每个人的选择",
            "defaults": {
                "scene": ["旧城区", "槐安巷", "老杂货铺"],
                "driver": ["旧物归还", "邻里误会", "旧城更新"],
                "element": ["旧物登记本", "生锈钥匙", "未寄出的明信片"],
                "relation": ["邻里旧识", "亲情隔阂", "临时搭档"],
                "tone": ["温暖", "克制", "治愈"],
                "era": ["当代"],
                "world": ["南方老城", "现实世界"],
                "style": ["细腻", "生活气"],
                "forbidden": ["海港都市", "雨夜都市", "权力博弈", "阴谋揭秘", "旧案重启", "黑帮", "重大犯罪"],
                "anchors": ["旧物", "杂货铺", "旧城", "邻里", "亲情", "登记本"],
            },
        }
    if any(k in genre_text for k in ("科幻", "星际", "赛博朋克", "机甲", "未来都市", "人工智能", "文明崩坏")):
        return {
            "mode": "sci",
            "fallback_scene": "轨道站外环残骸区",
            "ambient_line": "冷白故障灯沿着金属舱壁一格格闪过去，把原本有序的站内广播切成断续噪声。",
            "evidence": "一段被人为改写的权限日志",
            "danger_line": "整套协议网络的稳定性已经开始从内部松动",
            "defaults": {
                "scene": ["巨构城市", "轨道空间站", "星港中枢"],
                "driver": ["协议失效", "记忆篡改", "权限争夺"],
                "element": ["记忆芯片", "失控终端", "加密协议"],
                "relation": ["互相利用", "搭档", "权力博弈"],
                "tone": ["冷峻", "危机感", "失控感"],
                "era": ["近未来"],
                "world": ["星际文明", "未来秩序"],
                "style": ["冷峻", "电影感"],
                "forbidden": ["海港都市", "雨夜都市", "旧案重启", "关键档案", "旧档案馆"],
                "anchors": ["协议", "芯片", "权限", "星际", "城市", "终端"],
            },
        }
    if any(k in genre_text for k in ("仙侠", "玄幻", "神话", "武侠")):
        return {
            "mode": "xianxia",
            "fallback_scene": "山门禁地外的风雪石阶",
            "ambient_line": "山风卷着雪粒掠过石阶与古松，远处钟声压得很低，像有人把旧誓和禁令一并扣在夜里。",
            "evidence": "一枚忽然复醒的残缺剑印",
            "danger_line": "旧约和禁忌传承正在重新逼近所有人的命数",
            "defaults": {
                "scene": ["宗门禁地", "山门古道", "秘境遗址"],
                "driver": ["禁忌传承", "宿命反噬", "旧约重启"],
                "element": ["残卷", "剑印", "古阵"],
                "relation": ["师徒", "宿敌", "同盟"],
                "tone": ["宿命", "压抑", "史诗感"],
                "era": ["架空古代"],
                "world": ["架空世界", "修真秩序"],
                "style": ["史诗感", "冷峻"],
                "forbidden": ["海港都市", "旧案重启", "关键档案"],
                "anchors": ["剑", "宗门", "灵", "禁地", "传承", "秘境"],
            },
        }
    if any(k in genre_text for k in ("历史", "古代", "宫廷", "权谋")):
        return {
            "mode": "history",
            "fallback_scene": "皇城外苑与雪压长阶之间",
            "ambient_line": "风从宫墙尽头卷过来，雪粒擦着石砖与灯影滑行，整座城看似安静，实际上每一步都压着人心。",
            "evidence": "一封被改过笔迹的密诏副本",
            "danger_line": "朝局表面未乱，真正的清洗却已经开始提前落位",
            "defaults": {
                "scene": ["皇城", "朝堂外苑", "深宫旧署"],
                "driver": ["旧案翻案", "权势倾轧", "清洗重排"],
                "element": ["密诏", "旧卷宗", "边报"],
                "relation": ["权力博弈", "同盟", "背叛"],
                "tone": ["克制拉扯", "宿命", "冷峻"],
                "era": ["古代"],
                "world": ["架空王朝"],
                "style": ["克制", "冷峻"],
                "forbidden": ["海港都市", "雨夜都市", "关键档案"],
                "anchors": ["皇城", "朝堂", "密诏", "旧臣", "边报", "宫门"],
            },
        }
    if any(k in genre_text for k in ("青春", "校园", "言情", "治愈")):
        return {
            "mode": "youth",
            "fallback_scene": "晚自习后的旧教学楼走廊",
            "ambient_line": "窗外细雨把操场灯光晕成一层温吞的雾，楼道里只剩零散脚步和压低的说话声。",
            "evidence": "一封没有署名却被折得很整齐的旧信",
            "danger_line": "看似安静的人际边界正在慢慢失去原先的平衡",
            "defaults": {
                "scene": ["高校校园", "旧教学楼", "社团活动室"],
                "driver": ["关系失衡", "成长分岔", "旧误会重启"],
                "element": ["旧信件", "社团档案", "雨夜操场"],
                "relation": ["青梅竹马", "单向暗恋", "彼此试探"],
                "tone": ["温暖", "细腻", "治愈"],
                "era": ["当代"],
                "world": ["现实世界"],
                "style": ["细腻", "温柔"],
                "forbidden": ["海港都市", "旧案重启", "关键档案", "权力博弈"],
                "anchors": ["校园", "教室", "社团", "雨季", "信", "成长"],
            },
        }
    return {
        "mode": "noir",
        "fallback_scene": "暴雨压住港口的旧码头",
        "ambient_line": "夜风顺着堆满旧缆绳和生锈铁件的空隙灌过来，把港区本就不安稳的声响压得断断续续。",
        "evidence": "一份来路不明的新证据",
        "danger_line": "旧案回潮带来的压力正在一点点逼近所有人的站位边界",
        "defaults": {
            "scene": ["海港都市", "雨夜都市", "旧档案馆"],
            "driver": ["旧案重启", "真相反转", "阴谋揭秘"],
            "element": ["关键档案", "旧案残留", "异常记录"],
            "relation": ["彼此试探", "同盟", "权力博弈"],
            "tone": ["紧张", "神秘", "危机感"],
            "era": ["当代"],
            "world": ["现实世界"],
            "style": ["细腻", "电影感"],
            "forbidden": [],
            "anchors": ["旧案", "档案", "雨夜", "港口", "证据", "线索"],
        },
    }


def _final_unique_names(name_sources: Sequence[str], title: str, min_count: int = 5, max_count: int = 8) -> List[str]:
    names = _normalize_person_names(name_sources, title=title, max_count=max_count)
    if names:
        return names[:max_count]
    if len(names) < min_count:
        defaults = _build_default_person_names(title, [], count=max_count)
        for name in defaults:
            if name not in names:
                names.append(name)
            if len(names) >= min_count:
                break
    return names[:max_count]


def _final_extract_character_map_from_any_text(text: str, title: str = "", max_count: int = 10) -> Dict[str, str]:
    source = _sanitize_text(str(text or ""))
    if not source.strip():
        return {}
    blocked_names = {
        "人物信息",
        "故事背景",
        "小说简介",
        "主要人物",
        "他们行为",
        "故事情节",
        "当前梗概",
        "当前分卷",
        "章节标题",
        "细纲内容",
        "小说标题",
        "分类",
        "标签",
        "题材",
        "分类标签",
        "固定输出",
        "生成要求",
        "开始",
        "发展",
        "高潮",
        "结局",
        "卷名",
        "内容",
        "场景",
        "事件",
        "对话",
        "情感",
        "发生",
        "利益",
        "秩序",
        "记忆",
        "风险",
        "资源",
        "线索",
        "证据",
        "真相",
        "代价",
        "局势",
        "身份",
        "异常",
        "旧案",
        "港务",
        "民间",
        "官方",
        "灰色",
        "人物",
        "阶段",
        "压力",
        "关系锚",
        "关系锚点",
        "阴谋揭",
        "阴谋揭秘",
        "真相反",
        "真相反转",
        "旧案重",
        "旧案重启",
        "能调取",
        "能掌握",
        "能发现",
        "能处理",
        "能进入",
        "会调取",
        "会掌握",
        "可调取",
    }
    out: Dict[str, str] = {}
    next_person_boundary = (
        r"[一-鿿]{2,4}(?:发现|来自|掌握|在|带着|继承|代表|熟悉|知道|试图|负责|被|与|和|将|要|必须|正|会)"
    )

    def trim_person_desc(desc: str) -> str:
        value = re.split(r"(?:只输出以下|固定输出|生成要求|输出要求|标签大类|标签明细)", str(desc or ""))[0]
        value = value.strip("，。、；;：: \n\r\t")
        if not value:
            return ""
        sentence_parts = re.split(r"[。；;\n\r]", value, maxsplit=1)
        value = sentence_parts[0].strip("，。、；;：: \n\r\t")
        value = re.split(rf"，(?={next_person_boundary})", value, maxsplit=1)[0].strip("，。、；;：: \n\r\t")
        return value

    def add_name(name: str, desc: str = "") -> None:
        clean_name = _normalize_person_names([name], title=title, max_count=1)
        if not clean_name:
            return
        name_value = clean_name[0]
        if name_value in blocked_names or name_value in out:
            return
        desc_value = _clean_behavior_sentence(trim_person_desc(desc))
        out[name_value] = desc_value or f"{name_value}围绕本卷关键线索推进选择、误判与代价。"

    for line in source.splitlines():
        stripped_line = line.strip()
        if re.match(r"^\s*[-*•]?\s*\*?\s*注\s*[:：]", stripped_line) or "此处修正" in stripped_line or "原底稿" in stripped_line:
            continue
        match = re.match(r"\s*[-*•]?\s*(?:\*\*)?\s*([一-鿿]{2,4})\s*(?:\*\*)?\s*[:：]\s*(.{2,180})", stripped_line)
        if not match:
            continue
        add_name(match.group(1), match.group(2))
        if len(out) >= max_count:
            return out

    for match in re.finditer(r"(?:^|[\n\r，。；;、\-\*\s])(?:\*\*)?\s*([一-鿿]{2,4})\s*(?:\*\*)?\s*[:：]\s*([^\n\r]{2,180})", source):
        add_name(match.group(1), match.group(2))
        if len(out) >= max_count:
            return out
    if out:
        return out

    for match in re.finditer(r"[\"'“”‘’]([一-鿿]{2,4})[\"'“”‘’]\s*[:：]", source):
        add_name(match.group(1), "")
        if len(out) >= max_count:
            return out
    if out:
        return out

    prose_name_pattern = re.compile(
        r"(?:^|[^一-鿿]|档案管理员|管理员|主角|医师|大夫|掌柜|官员|捕快|弟子|少年|少女)([一-鿿]{2,4})(?=(?:发现|来自|掌握|在|带着|继承|代表|熟悉|知道|试图|负责|被|与(?=[一-鿿])|和(?=[一-鿿])|将|要|必须|正|会|走进|走到|冷笑|说道|说话|低声|停下|推开|拿起|抬头|看见|看向|问道|答道|回头))"
    )
    common_surnames = set("赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田胡凌霍虞万支柯昝管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉龚程邢滑裴陆荣翁荀羊於惠甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘钭厉戎祖武符刘景詹龙叶幸司韶郜黎蓟薄印宿白怀蒲台从鄂索咸籍赖卓蔺屠蒙池乔阴胥能苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀浦尚农温别庄晏柴瞿阎连习容向古易慎戈廖庾终暨居衡步都耿满弘匡国文寇广禄阙东欧殳沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那简饶空曾毋沙乜养鞠须丰巢关蒯相查後荆红游竺权逯盖益桓公")
    modal_prefixes = set("能会可应需将把被在与和对向为从")
    for match in prose_name_pattern.finditer(source):
        candidate = match.group(1)
        if candidate[0] not in common_surnames or candidate[0] in modal_prefixes:
            continue
        start = match.start(1)
        end = min(len(source), start + 90)
        add_name(candidate, source[match.end(1):end])
        if len(out) >= max_count:
            break
    return out


def _merge_character_maps(*maps: Dict[str, str], max_count: int = 10) -> Dict[str, str]:
    merged: Dict[str, str] = {}
    for item in maps:
        if not isinstance(item, dict):
            continue
        for name, desc in item.items():
            if not name or name in merged:
                continue
            merged[str(name)] = str(desc or "")
            if len(merged) >= max_count:
                return merged
    return merged


def _restrict_character_map(char_map: Dict[str, str], allowed_names: Sequence[str]) -> Dict[str, str]:
    if not isinstance(char_map, dict):
        return {}
    allowed = {str(name).strip() for name in allowed_names if str(name).strip()}
    if not allowed:
        return dict(char_map)
    return {str(name): str(desc or "") for name, desc in char_map.items() if str(name).strip() in allowed}


def _normalize_locked_name_variants(text: str, locked_names: Sequence[str]) -> str:
    value = str(text or "")
    names = [str(name).strip() for name in locked_names if 2 <= len(str(name).strip()) <= 4]
    if not value or not names:
        return value
    kinship_guard = re.compile(r"(父亲|母亲|生父|生母|父|母|监护人)$")

    def replace_candidate(src: str, candidate: str, canonical: str) -> str:
        if candidate == canonical:
            return src

        def repl(match: re.Match[str]) -> str:
            prev = src[max(0, match.start() - 8) : match.start()]
            prev_clean = re.sub(r"[（(：:，,\s]*$", "", prev)
            if kinship_guard.search(prev_clean):
                return match.group(0)
            return canonical

        return re.sub(re.escape(candidate), repl, src)

    confusable_groups = [
        set("默墨莫"),
        set("晚婉菀"),
        set("清青"),
        set("威维巍伟"),
        set("舟洲周州"),
        set("禾荷河和舟洲周州"),
        set("东栋"),
        set("澜岚阑栏鸾峦濂瀾"),
    ]

    def same_confusable_tail(candidate: str, canonical: str) -> bool:
        if len(candidate) != 2 or len(canonical) != 2 or candidate[0] != canonical[0]:
            return False
        return any(candidate[1] in group and canonical[1] in group for group in confusable_groups)

    def same_confusable_name(candidate: str, canonical: str) -> bool:
        if len(candidate) != len(canonical) or not candidate or candidate[0] != canonical[0]:
            return False
        for left, right in zip(candidate[1:], canonical[1:]):
            if left == right:
                continue
            if not any(left in group and right in group for group in confusable_groups):
                return False
        return True

    long_variant_bad_tail_chars = set("知试发看站说听图从父母道得了着过在和与必")
    surname_counts: Dict[str, int] = {}
    for n in names:
        surname_counts[n[0]] = surname_counts.get(n[0], 0) + 1
    for name in sorted(names, key=len, reverse=True):
        if len(name) >= 3:
            value = re.sub(rf"{re.escape(name)}[阳山口大]", name, value)
            short_relation_name = f"{name[0]}{name[-1]}"
            if short_relation_name != name and short_relation_name not in names:
                value = re.sub(
                    rf"(?<=与){re.escape(short_relation_name)}(?=(?:是|为|有|存在|关系|旧|同|敌|邻|上|下))",
                    name,
                    value,
                )
        if surname_counts.get(name[0], 0) == 1:
            value = re.sub(
                rf"(?<=与){re.escape(name[0])}(?=(?:是|为|有|存在|关系|旧|敌|邻|同|上|下))",
                name,
                value,
            )
        candidates = sorted(set(re.findall(rf"(?=([一-鿿]{{{len(name)}}}))", value)), key=len, reverse=True)
        for candidate in candidates:
            if candidate == name or candidate in names or candidate[0] != name[0]:
                continue
            if len(name) >= 3 and candidate[-1] in long_variant_bad_tail_chars:
                continue
            ratio = SequenceMatcher(None, candidate, name).ratio()
            # Three/four-character windows can accidentally include a following verb
            # ("沈澜发现" -> "沈澜发"). Keep long-name repair conservative so name
            # normalization never eats prose around the name.
            likely_variant = ratio >= (0.75 if len(name) == 2 else 0.82)
            if same_confusable_tail(candidate, name):
                likely_variant = True
            if same_confusable_name(candidate, name):
                likely_variant = True
            if len(name) >= 3 and (candidate[:2] == name[:2] or candidate[-2:] == name[-2:]):
                likely_variant = True
            if likely_variant:
                value = replace_candidate(value, candidate, name)
        value = re.sub(rf"{re.escape(name)}[（(]\s*{re.escape(name)}\s*[）)]", name, value)
        if len(name) >= 2:
            value = value.replace(f"{name}{name[-1]}", name)
    return value


def _clean_detail_content_to_prose(text: str, locked_names: Sequence[str]) -> str:
    value = _normalize_locked_name_variants(_to_simplified_lite(str(text or "")), locked_names)
    value = value.replace("**", "").replace("__", "").replace("*", "")
    value = re.sub(r"[ \t]*---+[ \t]*", "\n", value)
    value = re.sub(r"【[^】]{1,18}】\s*[:：]?", "", value)
    value = re.sub(r"(?m)^\s*#+\s*", "", value)
    value = re.sub(
        r"(?m)^\s*(?:[-*•]+|\d+\s*[.、:：])\s*(?:场景切入|冲突爆发|人物博弈|关键抉择|本章收尾|情节推进|角色分工|发展阶段|高潮前奏|分歧点|核心事件|剧情脉络|人物动态|阶段定位)\s*[:：]?\s*",
        "",
        value,
    )
    value = re.sub(r"(?m)^\s*(?:阶段定位|核心事件|剧情脉络|人物动态|角色分工|情节推进|核心主题|核心目标)\s*[:：]\s*", "", value)
    value = re.sub(r"（暂定[^）]*）?", "", value)
    value = re.sub(r"\s{2,}", " ", value)
    lines: List[str] = []
    for raw in value.splitlines():
        line = raw.strip(" \t-—•")
        if not line:
            continue
        if any(marker in line for marker in ("本细纲严格", "严格遵循以下原则", "输出原则", "章节规划原则")):
            continue
        line = re.sub(r"^\s*\d+\s*[.、:：]\s*", "", line).strip()
        if line:
            lines.append(line)
    paragraphs = _split_sentences("。".join(lines))
    cleaned: List[str] = []
    for sentence in paragraphs:
        sentence = sentence.strip("，。、；;：: ")
        if not sentence or _looks_like_text_source_noise(sentence):
            continue
        cleaned.append(_ensure_period(sentence))
        if len("".join(cleaned)) >= 360:
            break
    return _clean_linebreaks("".join(cleaned))


def _parse_markdown_outline_items(text: str, locked_names: Sequence[str], title: str = "") -> List[Dict[str, Any]]:
    source = _normalize_locked_name_variants(_to_simplified_lite(_sanitize_text(text)), locked_names)
    source = source.replace("**", "")
    blocks = re.split(r"(?=###\s*第[一二三四五六七八九十\d]+\s*卷)", source)
    items: List[Dict[str, Any]] = []
    name_alt = "|".join(re.escape(str(n)) for n in locked_names if str(n).strip())
    for block in blocks:
        if not re.search(r"###\s*第[一二三四五六七八九十\d]+\s*卷", block):
            continue
        char_map: Dict[str, str] = {}
        for name in locked_names:
            name = str(name).strip()
            if not name:
                continue
            next_names = "|".join(re.escape(str(n)) for n in locked_names if str(n).strip() and str(n).strip() != name)
            stop = rf"\n\s*(?:[*\-•]*\s*)?(?:{next_names})\s*[：:]" if next_names else r"$^"
            m = re.search(rf"{re.escape(name)}\s*[：:]\s*(.+?)(?={stop}|\n\s*\*?\s*故事情节|\n\s*\d+\s*[.、]|$)", block, flags=re.S)
            if m:
                desc = _clean_behavior_sentence(_clean_detail_content_to_prose(m.group(1), locked_names))
                if desc:
                    char_map[name] = _ensure_period(desc[:220])
        story_source = re.split(r"(?:故事情节|故事|情节)\s*[：:]", block, maxsplit=1)
        story_text = story_source[-1] if len(story_source) > 1 else block
        if name_alt:
            story_text = re.sub(rf"(?s)\*?\s*主要人物.*?(?=\n\s*\d+\s*[.、]|\n\s*【起】|\n\s*起[:：])", "", story_text)
        story_text = _clean_detail_content_to_prose(story_text, locked_names)
        sentences = _split_sentences(story_text)
        if len(sentences) < 4:
            sentences = _split_sentences(_clean_detail_content_to_prose(block, locked_names))

        def seg(start: int, end: int, fallback: str) -> str:
            value = "".join(sentences[start:end]).strip()
            return _ensure_period(value or fallback)

        story_map = {
            "开始": seg(0, 2, "卷首先让核心异动落到具体现场，并逼出第一轮选择。"),
            "发展": seg(2, 5, "中段推进线索核验、资源调度和人物试探，让合作关系逐渐承压。"),
            "高潮": seg(5, 8, "高潮用一次误判或公开冲突兑现前文压力，迫使人物承担代价。"),
            "结局": seg(8, 11, "卷尾留下阶段突破，同时把下一卷的风险与关系裂缝推到台前。"),
        }
        if char_map and story_map:
            items.append({"主要人物和他们的行为": char_map, "故事情节": story_map})
        if len(items) >= 6:
            break
    return items


def _is_structural_noise_clause(clause: str) -> bool:
    value = str(clause or "")
    if any(ch in value for ch in ("'", '"', "{", "}", "[", "]", "`")):
        return True
    return bool(re.search(r"(主要人物|他们的行为|故事情节|细纲内容|章节标题|内容)\s*[:：]", value))


def _final_join_paragraphs(paragraphs: Sequence[str]) -> str:
    cleaned: List[str] = []
    for paragraph in paragraphs:
        value = _to_simplified_lite(_clean_linebreaks(str(paragraph or "")).strip())
        if not value:
            continue
        cleaned.append(value)
    return "\n".join(cleaned).strip()


def _final_render_info_recommend(messages: List[Dict[str, str]]) -> str:
    user_text = _get_last_user_content(messages)
    fields = _extract_info_prompt_fields(user_text)
    title = str(fields.get("title", "")).strip()
    categories = [str(x).strip() for x in fields.get("categories", []) if str(x).strip()]
    revision_direction = str(fields.get("revision_direction", "") or "").strip()
    revision_seed = str(fields.get("revision_seed", "") or "").strip()
    previous_draft = str(fields.get("previous_draft", "") or "").strip()
    variation_text = f"{revision_direction}|{revision_seed}".strip("|")
    variation_hash = int(hashlib.md5(variation_text.encode("utf-8")).hexdigest(), 16) if variation_text else 0
    variation_offset = variation_hash % 997 if variation_hash else 0
    tag_map = _final_parse_grouped_tag_map(user_text)
    all_tags = [str(x).strip() for x in fields.get("all_tags", []) if str(x).strip()]
    if not all_tags:
        for values in tag_map.values():
            for value in values:
                if value not in all_tags:
                    all_tags.append(value)

    length_tags = tag_map.get("length", [])
    style_tags = tag_map.get("style", [])
    era_tags = tag_map.get("era", [])
    world_tags = tag_map.get("world", [])
    genre_tags = tag_map.get("genre", []) or categories
    tone_tags = tag_map.get("tone", [])
    scene_tags = tag_map.get("scene", [])
    relation_tags = tag_map.get("relation", [])
    driver_tags = tag_map.get("driver", [])
    element_tags = tag_map.get("elements", [])
    creative_tags = tag_map.get("creative", [])

    title_text = f"《{title}》" if title else "这部小说"
    section_stops = (
        "故事背景",
        "背景",
        "世界观",
        "小说简介",
        "简介",
        "全书梗概",
        "梗概",
        "分卷数量",
        "当前分卷",
        "分卷大纲",
        "章节范围",
        "章节数量",
        "约束",
        "额外要求",
    )
    explicit_person_block = _final_extract_prompt_block(
        user_text,
        ("人物信息", "主要人物", "底稿核心人物设定", "角色信息"),
        section_stops,
    )
    explicit_char_map = _final_parse_character_block(explicit_person_block, title=title, fallback_text="") if explicit_person_block else {}
    source_world = _final_extract_prompt_block(
        user_text,
        ("故事背景", "背景", "世界观", "世界设定"),
        ("小说简介", "简介", "人物关系拓扑", "生成要求", "约束", "请生成"),
    )
    source_intro = _final_extract_prompt_block(
        user_text,
        ("小说简介", "简介", "故事简介", "情节简介"),
        ("人物关系拓扑", "生成要求", "约束", "请生成"),
    )
    source_text = "\n".join([explicit_person_block, source_world, source_intro])

    def source_tags(kind: str) -> List[str]:
        raw = source_text
        out: List[str] = []
        if kind == "scene":
            if any(x in raw for x in ("港城", "港务", "海雾", "沉船", "气象站", "回声站", "监听塔")):
                out.extend(["霜港港城", "海雾气象站", "废弃回声站"])
            if any(x in raw for x in ("校园", "社团", "广播站")):
                out.extend(["高中校园", "广播站", "旧社团档案室"])
            if any(x in raw for x in ("医馆", "太医院", "皇城")):
                out.extend(["云崖医馆", "太医院旧署", "皇城药库"])
        elif kind == "driver":
            if any(x in raw for x in ("旧案", "事故", "沉船", "报告被人改写", "求救信号")):
                out.extend(["旧案重启", "事故报告改写", "求救信号复现"])
            if any(x in raw for x in ("旧信", "社团", "录像")):
                out.extend(["旧误会重启", "档案互相矛盾", "关系重新选择"])
        elif kind == "element":
            if any(x in raw for x in ("潮汐", "沉船", "录音", "气象", "监听塔")):
                out.extend(["异常潮汐记录", "沉船事故档案", "未解码录音"])
            if any(x in raw for x in ("旧信", "录像", "档案")):
                out.extend(["未寄出的旧信", "被删掉的活动录像", "社团档案"])
        elif kind == "world":
            if any(x in raw for x in ("港城", "港务", "海雾", "沉船")):
                out.append("近未来北方港城")
            elif any(x in raw for x in ("校园", "社团", "广播站")):
                out.append("当代校园")
        elif kind == "era":
            if "近未来" in user_text:
                out.append("近未来")
            elif any(x in raw for x in ("当代", "高中", "校园")):
                out.append("当代")
        elif kind == "style":
            if any(x in raw for x in ("冷峻", "海雾", "旧案")):
                out.extend(["冷峻", "悬疑感"])
        deduped: List[str] = []
        for item in out:
            if item and item not in deduped:
                deduped.append(item)
        return deduped

    source_char_map = _final_extract_character_map_from_any_text(source_text, title=title, max_count=10)
    if source_char_map:
        explicit_char_map = _merge_character_maps(source_char_map, _restrict_character_map(explicit_char_map, source_char_map.keys()), max_count=10)
    explicit_names = list(explicit_char_map.keys())
    if explicit_names:
        char_count = min(8, len(explicit_names)) if source_char_map else max(4, min(8, len(explicit_names)))
    else:
        char_count = 5
        if "长篇" in length_tags:
            char_count += 2
        elif "中篇" in length_tags:
            char_count += 1
        if "群像" in genre_tags or "群像并行" in relation_tags:
            char_count += 1
        if len(all_tags) >= 10:
            char_count += 1
    char_count = max(2 if explicit_names else 4, min(8, char_count))

    name_seed_title = f"{title}|{variation_text}" if variation_text else title
    previous_names = _normalize_person_names(_extract_name_candidates(title, previous_draft, []), title=title, max_count=10) if previous_draft else []
    generated_names = _build_default_person_names(
        name_seed_title,
        genre_tags + relation_tags + element_tags + ([revision_direction] if revision_direction else []),
        count=char_count + 8,
    )
    raw_names = explicit_names + [name for name in generated_names if name not in explicit_names]
    if revision_direction and previous_names:
        fresh_names = [name for name in raw_names if name not in previous_names]
        raw_names = fresh_names + [name for name in raw_names if name not in fresh_names]
    names = _final_unique_names(raw_names, title, min_count=char_count, max_count=char_count)
    profile = _infer_genre_profile(genre_tags + categories + creative_tags + all_tags)
    if str(profile.get("mode") or "") == "daily":
        return _final_render_daily_info_recommend(title, all_tags)
    defaults = profile["defaults"]
    default_scenes = defaults["scene"]
    default_drivers = defaults["driver"]
    default_elements = defaults["element"]
    default_relations = defaults["relation"]
    default_tones = defaults["tone"]
    default_era = defaults["era"]
    default_world = defaults["world"]
    default_style = defaults["style"]

    roles = [
        "一线追查者",
        "正面博弈者",
        "关键协力者",
        "摇摆中的支点人物",
        "掌握隐秘信息的人",
        "能调动灰色资源的人",
        "最容易撬开关系裂缝的人",
        "会把危机继续放大的人",
    ]
    goals = [
        "查清正在扩大的异常事件背后到底连着哪条真正的风险链路",
        "确保真相只在自己可控的时机被公开",
        "在合作与试探之间稳住局面并保住关键行动线",
        "在立场摇摆中为自己争取最大生存空间",
        "利用掌握的信息重新划分所有人的站位",
        "把散乱资源与灰色渠道接入主线，让计划能够落地",
        "把潜在裂缝提前放大，逼迫众人表态",
        "在阶段性收束后继续把更大的危机推上台面",
    ]
    def shifted(values: Sequence[str], offset: int = 0) -> List[str]:
        out = [str(x).strip() for x in values if str(x).strip()]
        if not out:
            return []
        shift = offset % len(out)
        return out[shift:] + out[:shift]

    relations = relation_tags or shifted(default_relations, variation_hash // 7 if variation_hash else 0)
    moods = "、".join(tone_tags[:3] or default_tones)
    genres = "、".join(genre_tags[:4] or categories[:4] or ["群像"])
    source_scene_tags = source_tags("scene")
    source_driver_tags = source_tags("driver")
    source_element_tags = source_tags("element")
    source_world_tags = source_tags("world")
    source_era_tags = source_tags("era")
    source_style_tags = source_tags("style")
    scenes = "、".join(scene_tags[:3] or source_scene_tags[:3] or default_scenes)
    drivers = "、".join(driver_tags[:3] or source_driver_tags[:3] or default_drivers)
    elements = "、".join(element_tags[:4] or source_element_tags[:4] or default_elements)
    era_text = "、".join(era_tags[:2] or source_era_tags[:2] or default_era)
    world_text = "、".join(world_tags[:3] or source_world_tags[:3] or default_world)
    style_text = "、".join(style_tags[:3] or source_style_tags[:3] or default_style)

    scene_pool = shifted(scene_tags or source_scene_tags or default_scenes, variation_hash // 11 if variation_hash else 0)
    driver_pool = shifted(driver_tags or source_driver_tags or default_drivers, variation_hash // 13 if variation_hash else 0)
    element_pool = shifted(element_tags or source_element_tags or default_elements, variation_hash // 17 if variation_hash else 0)
    primary_scene = scene_pool[0] if scene_pool else default_scenes[0]
    secondary_scene = scene_pool[1] if len(scene_pool) > 1 else primary_scene
    primary_driver = driver_pool[0] if driver_pool else default_drivers[0]
    secondary_driver = driver_pool[1] if len(driver_pool) > 1 else primary_driver
    primary_element = element_pool[0] if element_pool else default_elements[0]
    secondary_element = element_pool[1] if len(element_pool) > 1 else primary_element
    primary_relation = relations[0] if relations else "彼此试探"
    secondary_relation = relations[1] if len(relations) > 1 else primary_relation

    def relation_anchor(idx: int, current_name: str) -> str:
        main_ref = names[0] if names else current_name
        second_ref = names[1] if len(names) > 1 else main_ref
        third_ref = names[2] if len(names) > 2 else main_ref
        faction_name = f"{title or '主线'}核心阵营"
        if idx == 0 and len(names) > 1:
            return f"关系锚点：与{second_ref}是旧识兼临时盟友；隶属{faction_name}。"
        if idx == 1:
            return f"关系锚点：与{main_ref}有背景交集但互相防备；与{third_ref}存在旧案或档案牵连。"
        if idx == 2:
            return f"关系锚点：与{second_ref}有旧案交集；曾与{main_ref}共同经历关键事故或行动。"
        if idx == 3:
            return f"关系锚点：与{main_ref}存在旧识关系；与{second_ref}在立场上摇摆合作。"
        if idx == 4:
            return f"关系锚点：掌握{main_ref}与{third_ref}共同旧案的线索；与主线阵营保持若即若离的合作。"
        if idx == 5:
            return f"关系锚点：与{main_ref}是资源合作关系；与{second_ref}共享灰色渠道。"
        if idx == 6:
            return f"关系锚点：与{main_ref}存在敌对或利益冲突；与{second_ref}有可被利用的旧交情。"
        return f"关系锚点：与{main_ref}有背景交集；与{second_ref}存在阵营或利益关联。"

    person_lines: List[str] = []
    for idx, name in enumerate(names):
        explicit_detail = _clean_behavior_sentence(str(explicit_char_map.get(name, "") or ""))
        if explicit_detail and len(explicit_detail) >= 18:
            detail = f"{name}：{_ensure_period(explicit_detail)}"
            if "关系锚点" not in detail:
                detail = f"{detail}{relation_anchor(idx, name)}"
            person_lines.append(detail)
            continue
        role = shifted(roles, variation_offset)[idx % len(roles)]
        goal = shifted(goals, variation_offset // 3)[idx % len(goals)]
        relation = relations[idx % len(relations)] if relations else primary_relation
        if idx == 0:
            detail = (
                f"{name}：表面身份适合安放在{primary_scene}这条一线空间里，最强的性格底色是冷静外壳下的持续紧绷。"
                f"他（她）最先被{primary_driver}拖进主线，行动目标就是{goal}；一旦判断失误，{secondary_element}背后牵出的整条链就会反咬到自己身上。"
            )
        elif idx == 1:
            detail = (
                f"{name}：更适合作为与主角正面博弈的人物出现，身份可以站在既合作又防备的位置上。"
                f"他（她）看重的不是一时输赢，而是如何借{primary_driver}把解释权握在自己手里，因此和主线的关系天然带有{relation}的火药味。"
            )
        elif idx == 2:
            detail = (
                f"{name}：适合作为关键协力者进入故事，能在{secondary_scene}与主线行动之间搭起稳定通路。"
                f"他（她）的核心价值不在喊口号，而在于能把{secondary_driver}真正往前推一步；越到局势吃紧的时候，越能看出他（她）是不是还站在同一边。"
            )
        elif idx == 3:
            detail = (
                f"{name}：最适合放在灰度地带，既知道一些不能明说的旧事，又不愿轻易把自己交出去。"
                f"他（她）会因为{goal}被迫反复衡量利弊，表面像在观望，实际上每次摇摆都会改变主线的站位结构。"
            )
        elif idx == 4:
            detail = (
                f"{name}：是那种手里握着关键信息却从不一次说透的人物，和{primary_element}、{secondary_element}这类核心元素绑定度很高。"
                f"他（她）一旦开口，往往不是补充说明，而是把原有判断直接掀翻，让故事从单线追查变成多方互相试探。"
            )
        elif idx == 5:
            detail = (
                f"{name}：适合作为资源调度型人物存在，能把散乱的人脉、灰色渠道和现实条件接到主线里。"
                f"他（她）不一定总站在台前，但每次行动能不能落地，经常都要看他（她）愿不愿意把筹码真正掏出来。"
            )
        elif idx == 6:
            detail = (
                f"{name}：最适合承担关系裂缝制造者的位置，看起来未必最强势，却总能在关键时刻把{primary_relation}推成真正的对立。"
                f"他（她）的推动方式不是硬碰硬，而是让人物彼此之间先失去原本那点脆弱的共识。"
            )
        else:
            detail = (
                f"{name}：更像后期局势放大器，前期可以埋得稍深，一旦真正登场就会把更高层面的风险拖到台前。"
                f"他（她）和主线的关系不在于补齐信息，而在于把原本还能收住的危机继续往上推，逼人物面对不可逆的后果。"
            )
        person_lines.append(f"{detail}{relation_anchor(idx, name)}")

    background_paragraphs = [
        (
            f"{title_text}发生在{era_text}的{world_text}之中，主要舞台集中于{scenes}，空气里始终压着{style_text}的气息。"
            f"这里的秩序并不稳固，记忆、利益、身份与旧债被同一套规则捆在一起；"
            f"{elements}早已嵌入线索流转、权力遮蔽和人物判断，任何一个细节被翻动，都可能牵出更深的裂缝。"
        ),
        (
            f"故事开始时，表面生活仍按惯性运转，深层规则却因{drivers}持续松动。"
            f"有人急于掩埋真相，有人试图借势翻盘，也有人在毫无准备的情况下被卷进漩涡；"
            f"危险因此不只来自外部事件，更来自人物关系、资源分配和旧日立场在高压下的重新洗牌。"
        ),
    ]
    if len(all_tags) >= 8:
        background_paragraphs.append(
            f"当不同势力在同一片舞台上争夺解释权，{primary_scene}便不再只是地点，而是信息、情感和代价集中碰撞的压力场。"
            f"每个人进入局面时都带着既定牵连，旧识、阵营、资源和亏欠共同推着平衡崩塌，新的冲突也由此被迫浮出水面。"
        )

    main_name = names[0]
    second_name = names[1] if len(names) > 1 else names[0]
    third_name = names[2] if len(names) > 2 else names[0]
    fourth_name = names[3] if len(names) > 3 else second_name
    intro_paragraphs = [
        (
            f"{main_name}原本只想弄清一处无法按常规解释的异动。"
            f"一个异常细节、一次错位记录，或一条看似偶然的线索，将他（她）推到{primary_scene}的风口；随着{second_name}与{third_name}相继卷入，"
            f"单点事件迅速扩张成牵连{primary_driver}、资源链和隐藏站位的复杂局面。"
        ),
        (
            f"{main_name}要查清真相、找出真正的推动者，并在局势彻底失控前完成反制。"
            f"外部对手借{drivers}扭曲证据与认知，内部关系又因{relations[0] if relations else '试探与拉扯'}反复震荡；"
            f"一旦判断失误，行动不仅会满盘皆输，{fourth_name}这样的关键人物也可能成为最先付出代价的人。"
        ),
        (
            f"追查越深入，问题越不只是“真相是什么”，而是谁在推动、谁在阻拦、谁在摇摆、谁又被迫站队。"
            f"信任与利用在一次次行动中同步发酵，{elements}不断带出新信息、新代价和新的关系裂痕。"
            f"阶段性成果看似能解释一切，却往往只会提前掀开更深一层的真相、敌意与失衡。"
        ),
    ]
    if "长篇" in length_tags or len(all_tags) >= 10:
        intro_paragraphs.append(
            f"真相逼近时，{main_name}一行人面对的已经不只是单一谜底，而是失败代价、道德取舍和不可逆后果。"
            f"每一次立场重组都会把他们推向更高层面的秩序冲突，也让原本可以回避的选择变得再无退路。"
        )

    return _final_join_paragraphs(
        [
            "人物信息：",
            *person_lines,
            "",
            "故事背景：",
            *background_paragraphs,
            "",
            "简介：",
            *intro_paragraphs,
        ]
    )


def _final_extract_current_summary_fields(user_text: str) -> Dict[str, Any]:
    title = _final_extract_prompt_block(user_text, ("小说标题", "标题"), ("分类/标签", "分类标签", "题材标签", "分类", "底稿核心人物设定", "故事背景", "小说简介")).strip()
    categories = _parse_categories(_final_extract_prompt_block(user_text, ("分类/标签", "分类标签", "题材标签", "分类", "题材", "标签"), ("底稿核心人物设定", "故事背景", "小说简介")))
    creation_raw = _final_extract_prompt_block(user_text, ("底稿核心人物设定", "人物信息", "主要人物"), ("故事背景", "小说简介", "生成要求", "约束"))
    background = _clean_linebreaks(_final_extract_prompt_block(user_text, ("故事背景", "背景", "世界观"), ("小说简介", "生成要求", "约束"))).strip()
    intro = _clean_linebreaks(_final_extract_prompt_block(user_text, ("小说简介", "简介"), ("生成要求", "约束"))).strip()
    return {
        "title": title,
        "categories": categories,
        "creation_char_map": _final_parse_character_block(creation_raw, title=title, fallback_text=f"{background}\n{intro}"),
        "background": background,
        "intro": intro,
    }


def _final_extract_current_outline_fields(user_text: str) -> Dict[str, Any]:
    section_stops = (
        "分类/标签",
        "分类标签",
        "题材标签",
        "分类",
        "题材",
        "标签",
        "底稿核心人物设定",
        "人物信息",
        "主要人物",
        "主要人物和他们的行为",
        "当前梗概锁定的人物职责",
        "故事背景",
        "背景",
        "世界观",
        "小说简介",
        "简介",
        "全书梗概",
        "分卷数量",
        "人物关系拓扑",
        "关系拓扑",
        "约束",
    )
    title = _final_extract_prompt_block(user_text, ("小说标题", "标题"), section_stops).strip()
    categories = _parse_categories(_final_extract_prompt_block(user_text, ("分类/标签", "分类标签", "题材标签", "分类", "题材", "标签"), section_stops))
    creation_raw = _final_extract_prompt_block(user_text, ("底稿核心人物设定", "人物信息", "主要人物"), section_stops)
    locked_raw = _final_extract_prompt_block(user_text, ("当前梗概锁定的人物职责", "主要人物和他们的行为", "当前人物职责"), section_stops)
    background = _clean_linebreaks(_final_extract_prompt_block(user_text, ("故事背景", "背景", "世界观"), section_stops)).strip()
    intro = _clean_linebreaks(_final_extract_prompt_block(user_text, ("小说简介", "简介"), section_stops)).strip()
    summary = _clean_linebreaks(_final_extract_prompt_block(user_text, ("全书梗概", "梗概", "内容"), section_stops)).strip()
    name_source = "\n".join([creation_raw, locked_raw, background, intro, summary])
    global_char_map = _final_extract_character_map_from_any_text(name_source, title=title, max_count=10)
    creation_char_map = _final_parse_character_block(creation_raw, title=title, fallback_text=f"{background}\n{intro}\n{summary}")
    locked_char_map = _final_parse_character_block(locked_raw, title=title, fallback_text="") if str(locked_raw or "").strip() else {}
    if global_char_map:
        allowed_names = list(global_char_map.keys())
        creation_char_map = _merge_character_maps(global_char_map, _restrict_character_map(creation_char_map, allowed_names), max_count=10)
        locked_char_map = _merge_character_maps(global_char_map, _restrict_character_map(locked_char_map, allowed_names), max_count=10)
    return {
        "title": title,
        "categories": categories,
        "creation_char_map": creation_char_map,
        "locked_char_map": locked_char_map,
        "background": background,
        "intro": intro,
        "summary": summary,
    }


def _final_extract_current_detail_fields(user_text: str) -> Dict[str, Any]:
    section_stops = (
        "分类/标签",
        "分类标签",
        "题材标签",
        "分类",
        "题材",
        "标签",
        "底稿核心人物设定",
        "人物信息",
        "主要人物",
        "主要人物和他们的行为",
        "当前分卷人物推进重点",
        "当前人物推进重点",
        "故事背景",
        "背景",
        "世界观",
        "小说简介",
        "简介",
        "当前分卷",
        "当前分卷梗概",
        "本卷梗概",
        "分卷大纲",
        "章节范围",
        "章节数量",
        "卷级闭环承接上下文",
        "滚动承接上下文",
        "前文正文记忆",
        "上一卷正文复盘",
        "本次生成批次",
        "每章内容必须",
        "每章内容都要包含场景、事件、对话、情感和章末钩子",
        "额外要求",
        "人物关系拓扑",
        "关系拓扑",
    )
    title = _final_extract_prompt_block(user_text, ("标题", "小说标题"), section_stops).strip()
    categories = _parse_categories(_final_extract_prompt_block(user_text, ("分类/标签", "分类标签", "题材标签", "分类", "题材", "标签"), section_stops))
    creation_raw = _final_extract_prompt_block(user_text, ("底稿核心人物设定", "人物信息", "主要人物"), section_stops)
    current_raw = _final_extract_prompt_block(user_text, ("当前分卷人物推进重点", "主要人物和他们的行为", "当前人物推进重点"), section_stops)
    background = _clean_linebreaks(_final_extract_prompt_block(user_text, ("故事背景", "背景", "世界观"), section_stops)).strip()
    intro = _clean_linebreaks(_final_extract_prompt_block(user_text, ("小说简介", "简介"), section_stops)).strip()
    volume_summary = _clean_linebreaks(_final_extract_prompt_block(user_text, ("当前分卷梗概", "本卷梗概", "分卷大纲", "梗概", "故事情节"), section_stops)).strip()
    continuity_context = _clean_linebreaks(_final_extract_prompt_block(user_text, ("卷级闭环承接上下文", "滚动承接上下文", "前文正文记忆", "上一卷正文复盘"), section_stops)).strip()
    chapter_count = _pick_detail_chapter_count(user_text, default=DETAIL_OUTLINE_DEFAULT_CHAPTERS)
    name_source = "\n".join([creation_raw, current_raw, background, intro, volume_summary, continuity_context])
    global_char_map = _final_extract_character_map_from_any_text(name_source, title=title, max_count=10)
    creation_char_map = _final_parse_character_block(creation_raw, title=title, fallback_text=f"{background}\n{intro}\n{volume_summary}\n{continuity_context}")
    current_char_map = _final_parse_character_block(current_raw, title=title, fallback_text="") if str(current_raw or "").strip() else {}
    if global_char_map:
        allowed_names = list(global_char_map.keys())
        creation_char_map = _merge_character_maps(global_char_map, _restrict_character_map(creation_char_map, allowed_names), max_count=10)
        current_char_map = _merge_character_maps(global_char_map, _restrict_character_map(current_char_map, allowed_names), max_count=10)
    return {
        "title": title,
        "categories": categories,
        "creation_char_map": creation_char_map,
        "current_char_map": current_char_map,
        "background": background,
        "intro": intro,
        "volume_summary": volume_summary,
        "continuity_context": continuity_context,
        "chapter_count": chapter_count,
    }


def _final_render_daily_info_recommend(title: str, all_tags: Sequence[str]) -> str:
    clean_title = str(title or "").strip() or "旧巷杂货铺"
    title_text = f"《{clean_title}》"
    names = ["陈知夏", "陆怀川", "陈远山", "林阿婆", "赵明辉", "许曼青"]
    person_lines = [
        "陈知夏：二十八岁的品牌策划，因祖父去世回到槐安巷处理陈记杂货铺。她理性、嘴硬、不擅长示弱，目标是尽快清点旧物并转让铺面，却被登记本里的旧事一步步留下。关系锚点：与陈远山是父女；与陆怀川是旧巷改造中的临时搭档；与林阿婆是被观察也被照看的邻里关系。",
        "陆怀川：南桥市旧城更新项目的建筑师，童年曾在槐安巷短住，对老街和陈记杂货铺有隐约记忆。他温和耐心，目标是在改造方案里保留真正有生活痕迹的东西。关系锚点：与陈知夏因杂货铺去留产生合作与分歧；与赵明辉是项目协作关系；与林阿婆有旧邻里渊源。",
        "陈远山：陈知夏的父亲，多年在外地工作，与女儿和杂货铺都保持距离。他沉默、回避、重责任，目标是让女儿远离自己当年不愿面对的误会。关系锚点：与陈知夏是父女；与陈记杂货铺旧账本有直接牵连；与林阿婆是多年知情旧识。",
        "林阿婆：槐安巷老住户，常坐在槐树下看街坊来往，嘴硬心软，知道许多旧物背后的来处。她目标不是阻止改变，而是确认年轻人是否真的愿意听旧巷把话说完。关系锚点：与陈知夏是邻里长辈关系；与陈远山有旧事知情关系；与许曼青常年互相照应。",
        "赵明辉：街道办旧城更新沟通负责人，务实、压力大，不愿把居民诉求简单当成阻力。他目标是在期限、政策和人情之间找到可执行方案。关系锚点：与陆怀川是项目协作关系；与陈知夏围绕铺面去留存在现实冲突；与槐安巷居民是沟通与被质疑的关系。",
        "许曼青：旧书摊老板，年轻时曾帮陈记杂货铺整理寄存物，手里留着几张没有归档的旧照片。她外表散漫，实际记性很好，目标是把一段被误解的亲情交还给该知道的人。关系锚点：与林阿婆是多年邻里；与陈远山有旧照片牵连；与陈知夏是旧物线索的提供者。",
    ]
    background = (
        f"{title_text}发生在南方老城南桥市的旧城区。新城区的地铁、商场和写字楼不断向外扩张，槐安巷却仍保留着骑楼、青砖墙、石板路、早点摊、修鞋铺和槐树下的竹椅。这里的生活节奏很慢，许多关系不是靠通讯录维系，而是靠每天抬头低头的招呼、顺手寄放的物件和多年没有算清的人情。\n\n"
        "巷子尽头的陈记杂货铺开了三十多年，前厅卖针线、电池、糖果、雨伞和搪瓷杯，后间却堆着邻居寄放、遗失、抵押或托店主保管的旧物。每件旧物都有标签，有些写着姓名和日期，有些只剩一句含糊备注。旧物没有神秘力量，却像旧城记忆的索引，牵出迟到的道歉、没寄出的明信片、缺页的账本、打不开的老屋钥匙，以及亲人之间多年不愿说破的沉默。\n\n"
        "旧城更新计划即将推进，槐安巷一部分建筑会被修缮保护，另一部分可能被拆除或商业化改造。老邻居担心熟人关系被打散，年轻人又很难原封不动回到过去。杂货铺的去留因此不只是一间老铺的命运，也是一条旧巷在变化前夜如何保存记忆、承认遗憾并继续生活的选择。"
    )
    intro = (
        "陈知夏回到槐安巷时，只打算用三天处理祖父留下的陈记杂货铺。她熟悉新城区的会议和方案，却不熟悉旧巷里每个人看她时欲言又止的眼神。杂货铺后间的纸箱里压着一本旧物登记本，旧怀表、缺页账本、生锈钥匙、没有寄出的明信片、背面写着陌生名字的老照片，每一件都对应着一个迟迟没有归还的人。\n\n"
        "起初，陈知夏只想尽快把东西清空，却因为一只停在固定时间的怀表，被卷入一场迟到多年的道歉。随后，越来越多的邻居找上门，有人想取回旧物，有人请求她别再翻登记本，也有人在听见某个名字后突然沉默。参与旧城更新的陆怀川提醒她，槐安巷很快要进入改造公示期，杂货铺若再不决定去留，许多东西会和旧墙一起被搬走。\n\n"
        "陈知夏越整理越发现，祖父守着这间小店并不是固执怀旧，而是在替许多人保存最后一次说清楚的机会。旧物把她推向邻里旧事，也把她推向父亲陈远山多年不愿回来的真相。她必须在关店离开和留下承担之间做出选择：是让陈记杂货铺成为旧城更新前被清空的一间老铺，还是让它以新的方式继续替槐安巷保存那些还没说完的话。"
    )
    return _final_join_paragraphs(
        [
            "人物信息：",
            *person_lines,
            "",
            "故事背景：",
            background,
            "",
            "简介：",
            intro,
        ]
    )
def _final_extract_current_text_fields(user_text: str) -> Dict[str, Any]:
    title = _final_extract_prompt_block(
        user_text,
        ("小说标题", "标题"),
        ("分类/标签", "分类标签", "题材标签", "分类", "故事背景", "小说简介", "本卷梗概", "底稿核心人物设定", "当前阶段人物推进重点", "小说章节信息", "第 1 章细纲", "当前章节细纲", "人物关系拓扑", "关系拓扑"),
    ).strip()
    categories = _parse_categories(
        _final_extract_prompt_block(
            user_text,
            ("分类/标签", "分类标签", "题材标签", "分类", "题材", "标签"),
            ("故事背景", "小说简介", "本卷梗概", "底稿核心人物设定", "当前阶段人物推进重点", "小说章节信息", "第 1 章细纲", "当前章节细纲", "人物关系拓扑", "关系拓扑"),
        )
    )
    background = _clean_linebreaks(
        _final_extract_prompt_block(
            user_text,
            ("故事背景", "背景", "世界观"),
            ("小说简介", "本卷梗概", "底稿核心人物设定", "当前阶段人物推进重点", "小说章节信息", "第 1 章细纲", "当前章节细纲", "人物关系拓扑", "关系拓扑"),
        )
    ).strip()
    intro = _clean_linebreaks(
        _final_extract_prompt_block(
            user_text,
            ("小说简介", "简介"),
            ("本卷梗概", "底稿核心人物设定", "当前阶段人物推进重点", "小说章节信息", "第 1 章细纲", "当前章节细纲", "人物关系拓扑", "关系拓扑"),
        )
    ).strip()
    volume_summary = _clean_linebreaks(
        _final_extract_prompt_block(
            user_text,
            ("本卷梗概", "当前分卷梗概", "梗概"),
            ("底稿核心人物设定", "当前阶段人物推进重点", "小说章节信息", "第 1 章细纲", "当前章节细纲", "人物关系拓扑", "关系拓扑"),
        )
    ).strip()
    creation_raw = _final_extract_prompt_block(
        user_text,
        ("底稿核心人物设定", "人物信息", "主要人物"),
        ("当前阶段人物推进重点", "小说章节信息", "第 1 章细纲", "当前章节细纲", "人物关系拓扑", "关系拓扑"),
    )
    current_raw = _final_extract_prompt_block(
        user_text,
        ("当前阶段人物推进重点", "当前分卷人物推进重点", "主要人物和他们的行为", "当前人物职责"),
        ("小说章节信息", "第 1 章细纲", "当前章节细纲", "人物关系拓扑", "关系拓扑"),
    )
    chapter_info = _clean_linebreaks(
        _final_extract_prompt_block(
            user_text,
            ("小说章节信息",),
            ("第 1 章细纲", "当前章节细纲", "上一章正文节选", "前文正文", "人物关系拓扑", "关系拓扑", "---", "请根据以上信息"),
        )
    ).strip()
    chapter_outline = _clean_linebreaks(
        _final_extract_prompt_block(
            user_text,
            ("第 1 章细纲", "当前章节细纲"),
            ("上一章正文节选", "前文正文", "已有正文", "人物关系拓扑", "关系拓扑", "---", "请根据以上信息", "输出要求"),
        )
    ).strip()
    if not chapter_outline:
        chapter_outline_match = re.search(
            r"(?m)^\s*第\s*\d+\s*章细纲\s*[:：]\s*([\s\S]*?)(?=\n\s*(?:上一章正文节选|前文正文|已有正文|人物关系拓扑|关系拓扑|---|请根据以上信息|输出要求)\s*[:：]?|\Z)",
            user_text,
        )
        if chapter_outline_match:
            chapter_outline = _clean_linebreaks(chapter_outline_match.group(1)).strip()
    previous_text = _clean_linebreaks(
        _final_extract_prompt_block(
            user_text,
            ("上一章正文节选", "前文正文", "已有正文"),
            ("人物关系拓扑", "关系拓扑", "---", "请根据以上信息", "输出要求"),
        )
    ).strip()

    chapter_index = 1
    total_chapters = 100
    chapter_match = re.search(r"第\s*(\d+)\s*章", chapter_info)
    total_match = re.search(r"共有\s*(\d+)\s*章", chapter_info)
    if chapter_match:
        chapter_index = max(1, int(chapter_match.group(1)))
    if total_match:
        total_chapters = max(1, int(total_match.group(1)))

    fallback_text = f"{background}\n{intro}\n{volume_summary}\n{chapter_outline}"
    name_source = "\n".join([creation_raw, current_raw, background, intro, volume_summary, chapter_outline])
    global_char_map = _final_extract_character_map_from_any_text(name_source, title=title, max_count=10)
    creation_char_map = _final_parse_character_block(creation_raw, title=title, fallback_text=fallback_text)
    current_char_map = _final_parse_character_block(current_raw, title=title, fallback_text=fallback_text)
    if global_char_map:
        allowed_names = list(global_char_map.keys())
        creation_char_map = _merge_character_maps(global_char_map, _restrict_character_map(creation_char_map, allowed_names), max_count=10)
        current_char_map = _merge_character_maps(global_char_map, _restrict_character_map(current_char_map, allowed_names), max_count=10)
    return {
        "title": title,
        "categories": categories,
        "background": background,
        "intro": intro,
        "volume_summary": volume_summary,
        "chapter_info": chapter_info,
        "chapter_outline": chapter_outline,
        "previous_text": previous_text,
        "chapter_index": chapter_index,
        "total_chapters": total_chapters,
        "creation_char_map": creation_char_map,
        "current_char_map": current_char_map,
    }


def _build_prompt_based_first_chapter(messages: List[Dict[str, str]]) -> str:
    fields = _final_extract_current_text_fields(_get_last_user_content(messages))
    title = fields["title"]
    categories = fields["categories"]
    background = fields["background"]
    intro = fields["intro"]
    volume_summary = fields["volume_summary"]
    chapter_outline = fields["chapter_outline"]
    creation_char_map = fields["creation_char_map"]
    current_char_map = fields["current_char_map"]

    merged_char_map = dict(creation_char_map)
    merged_char_map.update(current_char_map)
    explicit_names = _normalize_person_names(list(merged_char_map.keys()), title=title, max_count=6)
    names = list(explicit_names)
    if len(names) < 2:
        recovered_names = _normalize_person_names(
            _extract_name_candidates(title, f"{background}\n{intro}\n{volume_summary}\n{chapter_outline}", categories),
            title=title,
            max_count=6,
        )
        for name in recovered_names:
            if name not in names:
                names.append(name)
            if len(names) >= 2:
                break
    if len(names) < 2:
        names = _build_default_person_names(title, categories, count=2)
    lead = names[0]
    second = names[1] if len(names) > 1 else lead
    third = names[2] if len(names) > 2 else second

    outline_clauses = _extract_narrative_source_clauses(chapter_outline, min_len=6)
    profile = _infer_genre_profile(categories)
    ambient_line = str(profile.get("ambient_line") or "空气里的细微异样，正在把所有人的注意力一点点拉向同一个方向。").strip()
    evidence_hint = str(profile.get("evidence") or "一份来路不明的新线索").strip()
    danger_line = str(profile.get("danger_line") or "局面的稳定性已经开始从内部松动").strip()
    fallback_scene = str(profile.get("fallback_scene") or "故事真正开始失去平衡的那个现场").strip()
    pressure_seeds = [
        danger_line,
        "表面仍在维持秩序，真正先松开的却是人物彼此默认的安全距离",
        "越往里查，人物之间原本默认的信任顺序就越难维持",
        "眼前这条线索不会只带来信息，还会逼所有人重新选择立场",
        "真正危险的不是异常本身，而是谁先借着异常改写局面",
        "每个人都知道这次推进不会只换来答案，还会换来新的代价",
    ]
    mood_seeds = [
        "人物会第一次清楚地意识到，局势已经开始脱离原先的控制范围",
        "章尾要留住风雨欲来的压迫感，让下一章能够立刻承接",
        "人物表面仍能保持克制，但心里的不安已经先一步坐实",
        "局面的松动要写成既能被看见、也可能被误判的隐性危险",
        "这场试探即使暂时落下，也还会把余震压在人物心里",
        "危险要再往前逼近半步，让下一章一开始就没有退路",
    ]
    scene = outline_clauses[0] if outline_clauses else fallback_scene
    event = outline_clauses[1] if len(outline_clauses) > 1 else f"{evidence_hint}突然把原本还能压住的问题重新拖回众人视线"
    tension = outline_clauses[2] if len(outline_clauses) > 2 else "所有人的判断开始出现肉眼可见的偏差"
    hook = outline_clauses[-1] if outline_clauses else "更深一层的风险已经逼到眼前"
    lead_goal = _clean_behavior_sentence(str(current_char_map.get(lead) or creation_char_map.get(lead) or "")) or f"{lead}必须先把眼前异动和旧线索扣到一起"
    second_goal = _clean_behavior_sentence(str(current_char_map.get(second) or creation_char_map.get(second) or "")) or f"{second}更倾向于先稳住局势再继续推进"
    third_goal = _clean_behavior_sentence(str(current_char_map.get(third) or creation_char_map.get(third) or "")) or f"{third}负责把线索继续往更危险的方向拽深"
    meta_markers = ("会从", "写起", "让卷首", "推进方向", "第1卷", "第 1 卷", "开局", "发展段", "高潮段", "结局部分", "这一卷", "本卷", "负责把", "负责将")
    first_chapter_meta_markers = meta_markers + (
        "主要舞台集中于",
        "后续值得继续写的根本原因",
        "谁来承担公开之后的代价",
        "谁又会因为立场变化变成新的阻力来源",
        "冲突等级会持续升级",
        "人物关系会持续裂变",
        "章尾要留下",
        "还是先切断这个错误的源头",
        "也是他最大的软肋",
    )
    intro_clauses = [
        clause
        for clause in _extract_narrative_source_clauses(intro, min_len=8)
        if not any(marker in clause for marker in first_chapter_meta_markers)
    ]
    summary_clauses = [
        clause
        for clause in _extract_narrative_source_clauses(volume_summary, min_len=8)
        if not any(marker in clause for marker in first_chapter_meta_markers)
    ]
    title_text = f"《{title}》" if title else "这部小说"

    paragraphs = [
        (
            f"{scene}。{ambient_line}"
            f"{lead}原本只是沿着最寻常的一条检查路线往前走，可当他真正看见{event}时，脚步还是不由得慢了一瞬。"
            f"那不是普通意义上的意外发现，而像是谁专门挑了这个时候，把一块本该被彻底封存的残片重新推回了视线中央。"
            "他没有马上弯腰去碰，只觉得后颈那层骤然收紧的冷意忽然更重了。"
            "从这一刻起，事情已经不是查不查的问题，而是谁先伸手，谁就可能把后面的解释权一并拿走。"
        ),
        (
            f"{lead}没有立刻去碰那份证据，先是顺着现场留下的细节把周围重新看了一遍。"
            f"光影、脚步、灯影、被人挪动过的边角，全都在提醒他这件事不是巧合。"
            f"他脑子里最先浮上来的不是结论，而是自己此刻最该守住的那条线：{lead_goal}。"
            f"也正因为他知道这一步不能错，心里那点隐约的不对劲才越发清晰。"
            f"如果有人真在利用这次异动重排所有人的站位，那么眼前这份东西就绝不只是线索，它更像一枚故意掷出来的试探。"
        ),
        (
            f"{second}赶到时，现场的气压已经被压得很低。她第一反应不是追问答案，而是先把还没失控的秩序往回拽，"
            f"因为她很清楚：{second_goal}。"
            f"可越是想稳住局面，她越能感觉到今天这一幕背后另有手笔。"
            f"两个人站在同一份证据前，关注点却并不一致。"
            f"{lead}想顺着异动继续往下追，生怕松手之后真正有用的线索会被迅速扩大的噪音吞掉；"
            f"{second}却更在意谁先知道了这件事、谁又故意把消息放到了这个节点。"
            "对话没有真正吵起来，却句句都带着试探和拉扯，这正是主线开始转动时最该出现的张力。"
        ),
        (
            (
                f"等到{third}被卷进来，局面就不再只是现场判断的分歧，而开始逼近更现实的选择。"
                f"{third_goal}。"
                f"他带来的不只是另一套看法，还有更直接的提醒：现在每往前多走一步，代价都可能比表面看见的更重。"
            )
            if third != second
            else (
                f"随着现场判断继续往下推进，局面就不再只是{lead}与{second}之间的分歧，而开始逼近更现实的选择。"
                f"{second}提出的稳妥方案和{lead}坚持的继续深挖彼此拉扯，让这一章的压力真正落到行动层面。"
                "他们都知道现在每往前多走一步，代价都可能比表面看见的更重。"
            )
            + "谁都没有把话说死，可每个人其实都已经把自己的立场露出来了。"
            + "有人先盯真相，有人先守秩序，也有人更早察觉到外部力量已经开始往里挤。"
            + f"正因为这些反应并不一致，{tension}才会一点点压实，最后逼得他们谁也没法继续装作这只是一次普通排查。"
        ),
        (
            f"随着核验继续往下推进，证据本身开始反过来改变他们对整件事的理解。"
            f"{intro_clauses[0] if intro_clauses else '原本被压住的问题重新露出边缘'}，"
            f"{summary_clauses[0] if summary_clauses else '而真正的危险也第一次有了可以被看见的轮廓'}。"
            f"{lead}逐渐意识到，今晚最可怕的并不是有人先他一步看见了证据，而是对方显然知道该把证据送到谁眼前、又该在什么时候送出来。"
            f"这意味着从这一刻开始，他们查到的每一条新信息都可能不是“自然出现”的，而是被某只手提前计算过的。"
            "这种后知后觉的寒意，会比单纯的惊讶更能把读者拖进故事里面。"
        ),
        (
            f"当他们以为这一轮判断已经足够靠近真相时，{hook}。"
            f"{lead}知道自己已经没有退回局外的余地，{second}也明白稳住局面的代价只会越来越高，至于{third}，他更清楚接下来任何一次试探都可能直接把暗处的人逼到明面。"
            f"这一夜留下的并不是一个可以轻易按下去的结果，而是一道已经真正咬住众人的入口。"
            f"从这一刻起，他们再也不可能用原来的位置看待彼此。"
        ),
        (
            f"{lead}最后一次回头看向现场时，才发现自己真正记住的并不是那份证据，而是每个人在证据出现后第一瞬间的反应。"
            f"{second}的克制、{third}的停顿、以及自己压下去的迟疑，都像被潮气浸湿的暗线，暂时看不出完整形状，却已经牢牢缠住下一步行动。"
            f"他没有把这种判断说出口，只把能带走的记录重新收好。门外的风声压过来，像是在替暗处的人提醒他们：如果现在继续往前，谁都不能保证还能按原来的方式收场。"
            f"也正是在这个安静得过分的尾声里，{lead}第一次确认，今晚不是事件开始，而是某个旧局重新启动。"
        ),
    ]
    return _final_join_paragraphs(paragraphs)


def _looks_like_first_chapter_template_replay(text: str) -> bool:
    clean = _normalize_text_output(text)
    markers = (
        "原本只是沿着最寻常的一条检查路线",
        "那不是普通意义上的意外发现",
        "谁先伸手，谁就可能把后面的解释权",
        "一枚故意掷出来的试探",
        "这一夜留下的并不是一个可以轻易按下去的结果",
    )
    return sum(1 for marker in markers if marker in clean) >= 2


def _build_prompt_based_nonfirst_chapter(messages: List[Dict[str, str]]) -> str:
    fields = _final_extract_current_text_fields(_get_last_user_content(messages))
    title = fields["title"]
    categories = fields["categories"]
    background = fields["background"]
    volume_summary = fields["volume_summary"]
    chapter_outline = fields["chapter_outline"]
    previous_text = fields.get("previous_text", "")
    creation_char_map = fields["creation_char_map"]
    current_char_map = fields["current_char_map"]
    chapter_index = int(fields.get("chapter_index") or 2)

    merged_char_map = dict(creation_char_map)
    merged_char_map.update(current_char_map)
    names = _normalize_person_names(list(merged_char_map.keys()), title=title, max_count=5)
    if len(names) < 2:
        names = _build_default_person_names(title, categories, count=3)
    lead = names[(chapter_index - 1) % len(names)]
    second = names[chapter_index % len(names)] if len(names) > 1 else lead
    third = names[(chapter_index + 1) % len(names)] if len(names) > 2 else second

    profile = _infer_genre_profile(categories)
    outline_lines = _extract_narrative_source_clauses(chapter_outline, min_len=8)
    volume_lines = _extract_narrative_source_clauses(volume_summary, min_len=8)
    background_lines = _extract_narrative_source_clauses(background, min_len=8)
    prev_lines = _extract_narrative_source_clauses(previous_text[-1200:], min_len=8)

    raw_title = ""
    title_match = re.match(r"\s*([^：:\n]{2,16})\s*[:：]", chapter_outline)
    if title_match:
        raw_title = _normalize_detail_title_seed(title_match.group(1))
    chapter_title = raw_title or f"第{chapter_index}章"
    scene_candidates = [
        clause
        for clause in outline_lines + background_lines
        if any(token in clause for token in ("港", "站", "塔", "码头", "安全屋", "前厅", "现场", "档案室", "雨夜", "海雾"))
        and not any(token in clause for token in ("必须", "判断", "推进", "承担", "形成", "这件事"))
    ]
    event_candidates = [
        clause
        for clause in outline_lines + volume_lines
        if not any(token in clause for token in ("气息", "场景", "本章", "这一章", "章尾", "下一章", "必须", "他得先"))
    ]
    def clean_scene_clause(value: str, default: str) -> str:
        cleaned = _clean_behavior_sentence(str(value or ""))
        cleaned = re.sub(r"^[^，。；！？\n]{2,14}\s*[:：]\s*", "", cleaned)
        cleaned = re.sub(r"^(随着动作和观察继续往里走|这一章|本章|通过|并在此过程中)", "", cleaned).strip("，。；： ")
        if not cleaned or _looks_like_text_source_noise(cleaned) or len(cleaned) < 6:
            return default
        return cleaned

    scene = clean_scene_clause(_pick_clause(scene_candidates, chapter_index, ""), str(profile.get("fallback_scene") or "现场"))
    event = clean_scene_clause(_pick_clause(event_candidates, chapter_index + 1, ""), str(profile.get("evidence") or "新线索"))
    prev_anchor = clean_scene_clause(_pick_clause(prev_lines, -1, ""), "上一章留下的余波还没有散尽")
    pressure = clean_scene_clause(_pick_clause(outline_lines + volume_lines, chapter_index + 3, ""), str(profile.get("danger_line") or "局势正在继续逼近"))
    lead_base = _clean_behavior_sentence(str(merged_char_map.get(lead, "")))
    second_base = _clean_behavior_sentence(str(merged_char_map.get(second, "")))

    paragraphs = [
        (
            f"{chapter_title}：{prev_anchor}。"
            f"{scene}仍旧压在众人心头，{lead}没有急着把上一轮判断盖棺定论，"
            f"因为{event}已经把新的压力推到眼前。"
        ),
        (
            f"{lead_base or lead + '必须重新判断线索的方向'}。这一次，他更在意的不是谁先开口，而是谁在沉默里避开了最关键的问题。"
            f"如果前一章只是让裂缝露出边缘，那么这一章就必须让裂缝真正影响行动顺序。"
        ),
        (
            f"{second}的反应比{lead}预想得更冷静。{second_base or '他试图先稳住局面'}，可越是想按程序推进，"
            f"越能感觉到有人把证据、现场和人物关系同时推向更难回头的位置。{third}也被卷进这个判断里，"
            f"他看见的不是单一线索，而是几个人立场开始偏移的前兆。"
        ),
        (
            f"围绕{pressure}，三个人的分歧不再只是态度不同。有人想先保住现场，有人坚持继续深挖，"
            f"也有人已经意识到，再晚一步，暗处的人就会把解释权彻底拿走。对话没有立刻爆开，却每一句都在改变下一步该由谁承担风险。"
        ),
        (
            f"等新的证据被重新放到灯下，{lead}终于意识到，上一章留下的并不是一个孤立问题，而是一条仍在往外扩散的链。"
            f"{second}没有再把话说满，{third}也明白自己不能继续停在旁观的位置上。"
        ),
        (
            f"这一章真正落下来的，不是答案，而是更明确的行动代价。{lead}必须带着新的疑点继续往前，"
            f"而{second}和{third}也从这一刻开始，被迫把各自隐藏的顾虑摆到同一条线上。"
        ),
        (
            f"离开前，{lead}又把现场最容易被忽略的细节重新核了一遍。"
            f"他不再急着解释刚才发生的一切，因为越是急着解释，越容易落进别人提前布好的说法里。"
            f"{second}没有催他，只在旁边把能确认的时间、位置和证据顺序逐项压实；{third}则盯着门外那片迟迟不散的阴影，像是已经听见下一轮麻烦靠近的脚步声。"
            f"这一段沉默让他们第一次意识到，合作不是因为互相信任，而是因为每个人手里都有别人缺失的那一块。"
        ),
        (
            f"等灯光重新暗下去，{lead}终于把这一章真正的结论压在心里：眼前的线索可以继续追，但他们之间的缝隙也会被一起带进下一步。"
            f"如果暗处的人正是想看见这种分裂，那么接下来任何一次选择都不能只看表面收益。"
            f"{second}把最后一句话说得很轻，却足够让所有人听清——下一次再有人抢先一步，他们就不能只问“发生了什么”，还得问“是谁希望我们这样理解”。"
        ),
        (
            f"这句话落下后，没人立刻回应。{lead}把已经确认的线索重新放回顺序里，发现真正改变局面的不是某一个证据，"
            f"而是证据出现后每个人都下意识护住了不同的东西。{second}护住的是可控的秩序，{third}护住的是自己仍不愿完全交出的判断，"
            f"而他自己护住的，则是那条不能再被别人替他解释的真相。"
            f"这些立场暂时还能并排放在同一张桌上，可谁都知道，一旦下一条线索继续往深处走，它们迟早会互相撞开。"
        ),
        (
            f"临走时，{lead}没有再回头看那盏摇晃的灯，只把{event}这个细节牢牢记住。"
            f"如果它只是偶然，暗处的人不会把时间掐得这么准；如果它不是偶然，那么他们今晚所有的争执都可能已经被人预判。"
            f"风声从门缝里挤进来，带着潮湿的冷意。{lead}知道，下一章开始前，他们要面对的已经不是单纯的追查，"
            f"而是一次必须在互不完全信任的前提下继续推进的联手。"
        ),
        (
            f"他把这个判断暂时压住，没有急着说给任何人听。现在说出口只会让分歧提前爆开，"
            f"可不说出口，又意味着下一次行动仍要冒着被误导的风险继续往前。"
            f"{second}看出了他的迟疑，却没有追问；{third}也只是把视线移向门外，像是在等某个迟早会来的信号。"
            f"这一刻的安静比争执更重，因为它把所有人都推到同一个问题面前：他们能不能在互相防备的情况下，先比暗处的人更快一步。"
        ),
    ]
    return _final_join_paragraphs(paragraphs)


def _has_text_output_drift(text: str, messages: List[Dict[str, str]]) -> bool:
    clean = _normalize_text_output(text)
    if not clean:
        return False
    fields = _final_extract_current_text_fields(_get_last_user_content(messages))
    title = fields["title"]
    categories = fields["categories"]
    source_text = "\n".join(
        [
            fields.get("background", ""),
            fields.get("intro", ""),
            fields.get("volume_summary", ""),
            fields.get("chapter_outline", ""),
        ]
    )
    allowed_names = set(fields["creation_char_map"].keys()) | set(fields["current_char_map"].keys())
    prompt_names = set(_final_extract_character_map_from_any_text(source_text, title=title, max_count=12).keys())
    source_name_pool = allowed_names | prompt_names
    generated_names = {
        name
        for name in _final_extract_character_map_from_any_text(clean, title=title, max_count=12).keys()
        if name and name not in source_name_pool
    }
    if len(generated_names) >= 2:
        return True
    leaked_markers = (
        "###",
        "```",
        "章节标题",
        "细纲内容",
        "卷名：",
        "核心目标：",
        "人物映射",
        "实际主角",
        "对应：",
        "主要人物和他们的行为",
        "故事情节",
        "直接输出小说正文",
        "章尾要",
        "章末要",
        "尾声要",
        "收束时要",
        "本章要",
        "请根据以上信息",
        "输出要求",
        "静态关系铁律",
        "静态关系不变",
        "角色职能定位",
        "剧情推进逻辑",
        "关系恒定",
        "核心冲突",
        "节奏把控",
        "家族/血缘",
        "家族/旧案牵连",
        "双重血缘羁绊",
        "团队执行核心",
        "景交集",
        "全眠",
        "不可更改",
        "将抽象",
        "落地为具体",
        "看见第一反应",
        "看见2.",
        "看见1.",
        "看见*",
        "：1.",
        ":1.",
        '":{',
        "':{",
        "': {",
        "の",
    )
    return any(marker in clean for marker in leaked_markers)


def _needs_text_completion(text: str, messages: List[Dict[str, str]]) -> bool:
    clean = _normalize_text_output(text)
    if not clean:
        return True
    task_name = _resolve_task_name({}, messages)
    min_chars = 1250 if task_name == TEXT_FIRST_CHAPTER_TASK_NAME else 1050
    if len(clean) < min_chars:
        return True
    if not re.search(r"[。！？!?…」』”\"]\s*$", clean):
        return True
    tail = clean[-48:]
    if re.search(r"[，、；：—\-（(]\s*$", tail):
        return True
    if re.search(r"(的|了|而|但|并|和|与|把|将|让|向|对|在|被|却)$", tail):
        return True
    compact_len = len(re.sub(r"\s+", "", clean))
    if compact_len >= 2200 and re.search(r"[。！？!?…」』”\"]\s*$", clean):
        # Long streamed prose often ends on a short hook paragraph. Treat that as a
        # valid chapter ending instead of appending deterministic bridge text.
        return False
    paragraphs = [p.strip() for p in re.split(r"\n{2,}", clean) if p.strip()]
    if paragraphs and len(paragraphs[-1]) < 48:
        return True
    return False


def _build_prompt_based_text_tail(messages: List[Dict[str, str]], existing_text: str) -> str:
    fields = _final_extract_current_text_fields(_get_last_user_content(messages))
    title = fields["title"]
    categories = fields["categories"]
    background = fields["background"]
    intro = fields["intro"]
    volume_summary = fields["volume_summary"]
    chapter_outline = fields["chapter_outline"]
    creation_char_map = fields["creation_char_map"]
    current_char_map = fields["current_char_map"]

    merged_char_map = dict(creation_char_map)
    merged_char_map.update(current_char_map)
    names = _normalize_person_names(list(merged_char_map.keys()), title=title, max_count=4)
    if len(names) < 2:
        names = _build_default_person_names(title, categories, count=3)
    lead = names[0]
    second = names[1] if len(names) > 1 else lead
    third = names[2] if len(names) > 2 else second

    profile = _infer_genre_profile(categories)
    meta_markers = ("会从", "写起", "让卷首", "推进方向", "第1卷", "第 1 卷", "开局", "发展段", "高潮段", "结局部分", "这一卷", "本卷", "负责把", "负责将")
    generic_tail_markers = (
        "每一次推进都将迫使",
        "要保住什么",
        "愿意失去什么",
        "彼此咬合",
        "把更大的代价",
        "站队压力",
        "推上台面",
        "冲突等级会持续升级",
        "后续值得继续写的根本原因",
        "谁又会因为立场变化变成新的阻力来源",
        "人物关系会持续裂变",
    )
    chapter_clauses = [
        clause
        for clause in _extract_narrative_source_clauses(chapter_outline, min_len=8)
        if not any(marker in clause for marker in generic_tail_markers)
    ]
    summary_clauses = [
        clause
        for clause in _extract_narrative_source_clauses(volume_summary, min_len=8)
        if not any(marker in clause for marker in meta_markers) and not any(marker in clause for marker in generic_tail_markers)
    ]
    intro_clauses = [
        clause
        for clause in _extract_narrative_source_clauses(intro, min_len=8)
        if not any(marker in clause for marker in meta_markers) and not any(marker in clause for marker in generic_tail_markers)
    ]
    hook_text = (
        chapter_clauses[-1]
        if chapter_clauses
        else (
            summary_clauses[-1]
        if summary_clauses
        else (intro_clauses[-1] if intro_clauses else str(profile.get("danger_line") or "更深一层的风险已经逼到眼前"))
        )
    )
    hook_clauses = _extract_clean_clauses(hook_text, min_len=6)
    hook_line = hook_clauses[0] if hook_clauses else _clean_behavior_sentence(hook_text)
    hook_meta_markers = (
        "意识到自己可能",
        "要让下一步",
        "被旧事和当下心事一起推出来",
        "章末",
        "章尾要留下",
        "人物",
        "继续推进",
        "构建",
        "写成",
        "本章",
        "下一步",
        "主要舞台集中于",
        "谁来承担公开之后的代价",
        "也是他最大的软肋",
        "还是先切断这个错误的源头",
    )
    if any(marker in hook_line for marker in hook_meta_markers):
        hook_line = str(profile.get("evidence") or profile.get("danger_line") or "更深一层的风险已经逼到眼前").strip()
    mood = str(profile.get("danger_line") or "局势已经开始脱离原先的控制范围").strip()
    scene = [
        clause
        for clause in _extract_clean_clauses(background, min_len=8)
        if not any(
            marker in clause
            for marker in (
                "发生在",
                "语境下",
                "世界之中",
                "主要舞台集中于",
                "整体气质偏向",
                "这不是一个单纯依靠设定奇观取胜的世界",
                "身份长期缠绕的场域",
                "这些核心元素不会只作为装饰出现",
                "而是一个秩序记忆利益与身份长期缠绕的场域",
                "这些核心元素不会只作为装饰出现",
                "故事爆发的当下",
                "表面秩序仍在运作",
                "故事爆发的当下",
                "越是标签维度丰富",
            )
        )
    ]
    scene_text = scene[0] if scene else str(profile.get("fallback_scene") or "现场")
    tail_hash = int(hashlib.md5(f"{title}|{'/'.join(categories)}|tail".encode("utf-8")).hexdigest(), 16)
    mode = str(profile.get("mode") or "noir")
    opening_tail_templates_by_mode = {
        "noir": [
            "{scene}那边的潮气和铁锈味一直没散，{lead}知道这点停顿只是把更深的暗流往后压了一寸。",
            "{scene}并没有真正安静下来，{lead}心里很清楚，今晚摸到的只是那条旧线翻身时露出的第一截骨头。",
            "{scene}里还留着没散开的湿冷气息，{lead}明白他们刚才按住的不过是更大动静的前声。",
        ],
        "sci": [
            "{scene}里的故障灯还在断续闪烁，{lead}已经意识到，他们碰到的不是单独异常，而是整条系统链失稳前的预警。",
            "{scene}没有恢复到原先的秩序，{lead}知道刚才那点偏差只是更大范围失真的开端。",
            "{scene}的冷光仍在舱壁间来回跳动，{lead}心里明白，这次暴露出来的不是局部故障，而是底层规则已经开始松动。",
        ],
        "xianxia": [
            "{scene}间的风雪没有歇下，{lead}很清楚眼前这点裂动只会把更旧的禁忌一层层翻出来。",
            "{scene}外的寒气还在往骨头里钻，{lead}知道今夜真正被惊醒的并不只是这一道旧痕。",
            "{scene}里的气机还在发沉，{lead}明白他们碰到的只是更大反噬露出的第一缕边角。",
        ],
        "history": [
            "{scene}外的风雪并没有停，{lead}知道眼前这点松动只是旧局开始改写秩序的先声。",
            "{scene}里的灯影依旧压得很低，{lead}心里明白，这场试探真正牵动的绝不止眼前这一层人事。",
            "{scene}上方的夜色仍旧沉着，{lead}知道刚才翻出的不只是线头，而是整盘旧账重新落位的征兆。",
        ],
        "youth": [
            "{scene}外的雨声还在往下落，{lead}已经明白，今晚被碰破的不是一句话，而是大家勉强维持的那点平静。",
            "{scene}里残留的灯光没有完全熄下去，{lead}知道这次沉默之后，彼此的距离不会再像从前那样轻易退回去。",
            "{scene}边上的风声还很轻，{lead}却已经察觉到，真正改变的不是表面气氛，而是几个人心里默认的站位。",
        ],
    }
    pressure_tail_templates_by_mode = {
        "noir": [
            "围绕{hook}这件事不会在今晚停住，只会顺着更暗的地方继续往前走。",
            "围绕{hook}冒出来的动静既然已经露出头，后面的代价就不可能只落在一个人身上。",
            "和{hook}有关的裂口既然被碰开，接下来每个人都得重新估量自己还能站在哪一边。",
        ],
        "sci": [
            "和{hook}有关的异常既然已经出现，下一次偏移就不会再给他们留下从容回头的时间。",
            "围绕{hook}这次触发既然发生，整套系统里更深的失稳只会来得更快。",
            "{hook}既然已经露出征兆，随后被改写的就不会只是一段数据。",
        ],
        "xianxia": [
            "围绕{hook}露出的第一道口子既然已经出现，后面的反噬就不会只落在一人身上。",
            "和{hook}有关的旧痕既然被翻出来，今夜之后谁都别想再把旧约当成死物。",
            "{hook}既然开始松动，真正的代价只会沿着更深的命数一层层压下来。",
        ],
        "history": [
            "围绕{hook}这件事既然已经被惊动，后手便不会只来一重。",
            "{hook}既然已经露了痕迹，接下来动的就不只是案卷，还有人心和位次。",
            "{hook}既然被摆上灯下，之后每一步都不会再只是试探。",
        ],
        "youth": [
            "围绕{hook}生出的波动既然已经碰破表面的平静，之后的关系就再难退回原来的距离。",
            "{hook}既然被说破半句，之后每个人都得面对自己一直躲开的那部分心思。",
            "和{hook}有关的那点心事既然已经压不回去，后面的靠近和退让就都会变得更明显。",
        ],
    }
    closing_tail_templates_by_mode = {
        "noir": [
            "{second}没有再追问，只把目光压回那条还没说破的线索上。{third}也知道今晚留下的不是答案，而是一道真正开始往里收紧的口子。",
            "{second}把话收住了，掌心却还压着没散干净的凉意。{third}不必再多说，谁都知道这一夜只是把更深的那层局势提前掀开了。",
            "{second}没有把局面硬往回拽，只把呼吸放得更轻。{third}也已经明白，从这一刻起，接下来的每一步都得踩着更深的水走。",
        ],
        "sci": [
            "{second}没有立刻给出判断，只把视线重新落回那道失真的数据上。{third}很清楚，这一处裂缝既然出现，就不会只停在当前这一层。",
            "{second}没有再把话说满，因为那点偏差已经足够说明问题。{third}知道真正要来的不是解释，而是下一轮更难拦住的连锁失真。",
            "{second}把结论压在舌尖上，没有急着落下。{third}也明白，等协议下一次抖动时，他们谁都不会再有现在这样的余裕。",
        ],
        "xianxia": [
            "{second}没有再开口，风雪里的那点寂静反而像旧约将启前的停顿。{third}听得出，今晚之后，有些因果已经不可能再被按回原位。",
            "{second}把剑意压了回去，沉默却比任何一句话都更重。{third}知道这一夜真正留下的不是答案，而是再也避不开的后手。",
            "{second}没有把那口气当场吐尽，只任寒意在山门间慢慢落稳。{third}很清楚，接下来的每一步都会比今晚更接近命数真正翻面的时刻。",
        ],
        "history": [
            "{second}把话压了回去，殿外风雪却把未尽之意全都送到了灯下。{third}知道旧局既已被触动，往后就不可能只靠沉默维持表面的平衡。",
            "{second}没有再追下去，只让那点停顿落在彼此的目光之间。{third}心里明白，今夜翻开的不是一页旧案，而是一段随时可能改写位次的风声。",
            "{second}把神色收得很稳，可灯影下面的气氛已经变了。{third}知道从这里往后，任何一句迟到的话都可能成为别人落刀的凭据。",
        ],
        "youth": [
            "{second}没有把那句话说穿，只把迟疑留在慢慢沉下去的雨声里。{third}明白，今晚之后，几个人之间再也不可能像之前那样装作什么都没发生。",
            "{second}把视线移开了半寸，却没能真的把情绪也一并带走。{third}知道这一点点裂开的沉默，往后只会把彼此推得更近，也推得更难退。",
            "{second}没有继续往下说，楼道里的安静却替他们把后半句话都留了下来。{third}也清楚，从这一刻起，谁都没办法再回到最开始那个轻松的站位。",
        ],
    }
    opening_tail_templates = opening_tail_templates_by_mode.get(mode, opening_tail_templates_by_mode["noir"])
    pressure_tail_templates = pressure_tail_templates_by_mode.get(mode, pressure_tail_templates_by_mode["noir"])
    closing_tail_templates = closing_tail_templates_by_mode.get(mode, closing_tail_templates_by_mode["noir"])
    opening_tail = opening_tail_templates[tail_hash % len(opening_tail_templates)].format(scene=scene_text, lead=lead)
    pressure_tail = pressure_tail_templates[(tail_hash // 5) % len(pressure_tail_templates)].format(hook=hook_line)
    closing_tail = closing_tail_templates[(tail_hash // 11) % len(closing_tail_templates)].format(
        second=second,
        third=third if third != second else lead,
    )

    tail_paragraph = _final_join_paragraphs(
        [
            f"{opening_tail}{pressure_tail}",
            closing_tail,
        ]
    )
    existing = _normalize_text_output(existing_text).rstrip()
    if existing.endswith(("。", "！", "？", "…", "”", "』", "」")):
        return tail_paragraph
    return f"{tail_paragraph}"


def _ensure_text_completion(text: str, messages: List[Dict[str, str]], task_name: str = "") -> str:
    clean = _normalize_text_output(text)
    task_name = task_name or _resolve_task_name({}, messages)
    if task_name in {TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME} and clean:
        try:
            fields_for_names = _final_extract_current_text_fields(_get_last_user_content(messages))
            locked_names = list(fields_for_names.get("creation_char_map", {}).keys()) + list(fields_for_names.get("current_char_map", {}).keys())
            clean = _normalize_locked_name_variants(clean, locked_names)
        except Exception:
            pass
    min_rebuild_chars = 1250 if task_name == TEXT_FIRST_CHAPTER_TASK_NAME else 1150
    if task_name in {TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME} and len(re.sub(r"\s+", "", clean)) < min_rebuild_chars:
        if clean and task_name in {TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
            # Keep real model prose. Short chapters should be expanded by tail completion/quality feedback,
            # not replaced wholesale by deterministic fallback.
            pass
        elif allow_deterministic_fallback("empty"):
            rebuilt = (
                _build_prompt_based_nonfirst_chapter(messages)
                if task_name == TEXT_NON_FIRST_CHAPTER_TASK_NAME
                else _build_prompt_based_first_chapter(messages)
            )
            rebuilt_clean = _normalize_text_output(rebuilt)
            if len(re.sub(r"\s+", "", rebuilt_clean)) >= max(len(re.sub(r"\s+", "", clean)), min_rebuild_chars):
                return rebuilt_clean
    if not clean and task_name == TEXT_NON_FIRST_CHAPTER_TASK_NAME and allow_deterministic_fallback("empty") and _looks_like_first_chapter_template_replay(clean):
        rebuilt = _build_prompt_based_nonfirst_chapter(messages)
        rebuilt_clean = _normalize_text_output(rebuilt)
        if rebuilt_clean:
            return rebuilt_clean
    if clean and _has_text_output_drift(clean, messages) and task_name not in {TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
        rebuilt = (
            _build_prompt_based_nonfirst_chapter(messages)
            if task_name == TEXT_NON_FIRST_CHAPTER_TASK_NAME
            else _build_prompt_based_first_chapter(messages)
        )
        if rebuilt:
            rebuilt_clean = _normalize_text_output(rebuilt)
            if rebuilt_clean and not _has_text_output_drift(rebuilt_clean, messages):
                return rebuilt_clean
    if not _needs_text_completion(clean, messages):
        return clean
    if clean and task_name in {TEXT_TASK_NAME, TEXT_FIRST_CHAPTER_TASK_NAME, TEXT_NON_FIRST_CHAPTER_TASK_NAME}:
        # Never append deterministic prose to a real upstream chapter. A short or
        # softly-ended chapter is preferable to leaking template bridge text into
        # the user's novel; quality checks can ask for regeneration instead.
        return clean
    if not clean and task_name == TEXT_FIRST_CHAPTER_TASK_NAME and allow_deterministic_fallback("empty") and _should_rebuild_first_chapter(clean, messages):
        rebuilt = _build_prompt_based_first_chapter(messages)
        if rebuilt and len(rebuilt) >= max(len(clean), 1100):
            return _normalize_text_output(rebuilt)
    tail = _build_prompt_based_text_tail(messages, clean)
    if not clean:
        completed = _normalize_text_output(tail)
        if task_name == TEXT_FIRST_CHAPTER_TASK_NAME and allow_deterministic_fallback("empty") and _should_rebuild_first_chapter(completed, messages):
            rebuilt = _build_prompt_based_first_chapter(messages)
            if rebuilt:
                return _normalize_text_output(rebuilt)
        return completed
    sep = "" if clean.endswith(("。", "！", "？", "…", "\n")) else "。"
    completed = _normalize_text_output(f"{clean}{sep}\n\n{tail}")
    if not clean and task_name == TEXT_FIRST_CHAPTER_TASK_NAME and allow_deterministic_fallback("empty") and _should_rebuild_first_chapter(completed, messages):
        rebuilt = _build_prompt_based_first_chapter(messages)
        if rebuilt:
            rebuilt_clean = _normalize_text_output(rebuilt)
            if len(rebuilt_clean) >= 1200:
                return rebuilt_clean
    return completed


def _should_rebuild_first_chapter(text: str, messages: List[Dict[str, str]]) -> bool:
    clean = _normalize_text_output(text)
    if len(clean) < 1000:
        return True
    if any(
        marker in clean
        for marker in (
            "主要人物和他们的行为",
            "故事情节",
            "直接输出小说正文",
            "请根据以上信息",
            "静态关系铁律",
            "静态关系不变",
            "角色职能定位",
            "剧情推进逻辑",
            "关系恒定",
            "核心冲突",
            "节奏把控",
            "家族/血缘",
            "不可更改",
            "将抽象",
            "落地为具体",
            "看见第一反应",
            "看见1.",
            "看见2.",
            "看见*",
            "：1.",
            ":1.",
            '":{',
            "':{",
            "': {",
        )
    ):
        return True

    fields = _final_extract_current_text_fields(_get_last_user_content(messages))
    title = fields["title"]
    categories = fields["categories"]
    background = fields["background"]
    intro = fields["intro"]
    volume_summary = fields["volume_summary"]
    chapter_outline = fields["chapter_outline"]
    source_text = "\n".join([background, intro, volume_summary, chapter_outline])
    allowed_names = set(fields["creation_char_map"].keys()) | set(fields["current_char_map"].keys())
    prompt_names = set(_extract_name_candidates(title, source_text, categories))
    source_name_pool = allowed_names | prompt_names

    if source_name_pool:
        visible_name_hits = sum(1 for name in source_name_pool if name and name in clean)
        if visible_name_hits < 2:
            return True

    generated_names = {
        name
        for name in _extract_name_candidates(title, clean, categories)
        if name and name not in source_name_pool
    }
    if len(generated_names) >= 2:
        return True

    suspicious_pattern = re.compile(
        r"(?:[零一二三四五六七八九十两\d]+号[一-鿿]{1,6}|[一-鿿]{2,8}[零一二三四五六七八九十两\d]+号|[一-鿿]{2,8}(?:档案|灯塔|计划|协议|信号|通道|编号))"
    )
    source_terms = set(suspicious_pattern.findall(source_text))
    generated_terms = {term for term in suspicious_pattern.findall(clean) if term not in source_terms}
    if len(generated_terms) >= 2:
        return True

    outline_clauses = _extract_clean_clauses(chapter_outline, min_len=6)
    if outline_clauses:
        anchor_hits = sum(1 for clause in outline_clauses[:3] if clause[:6] and clause[:6] in clean)
        if anchor_hits == 0:
            return True

    profile = _infer_genre_profile(categories)
    mode = str(profile.get("mode") or "noir")
    leaked_meta_markers = (
        "主要舞台集中于",
        "章尾要留下",
        "谁来承担公开之后的代价",
        "谁又会因为立场变化变成新的阻力来源",
        "冲突等级会持续升级",
        "也是他最大的软肋",
        "还是先切断这个错误的源头",
    )
    if any(marker in clean for marker in leaked_meta_markers):
        return True
    drift_markers_by_mode = {
        "youth": ("手电筒", "那人影", "看到明天的太阳", "空旷的楼道", "永远也别想", "阴影里", "回荡"),
        "sci": ("江湖", "宗门", "宫墙", "皇城", "旧码头"),
        "xianxia": ("协议", "终端", "轨道站", "星港", "教学楼"),
        "history": ("协议", "终端", "轨道站", "校园", "社团"),
        "noir": ("宗门", "秘境", "皇城", "晚自习"),
    }
    source_only = str(source_text or "")
    for marker in drift_markers_by_mode.get(mode, ()):
        if marker and marker in clean and marker not in source_only:
            return True
    return False


def _build_prompt_based_summary(messages: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    fields = _final_extract_current_summary_fields(_get_last_user_content(messages))
    title = fields["title"]
    categories = fields["categories"]
    background = fields["background"]
    intro = fields["intro"]
    creation_char_map = fields["creation_char_map"]
    profile = _infer_genre_profile(categories)
    defaults = profile["defaults"]

    explicit_names = _normalize_person_names(list(creation_char_map.keys()), title=title, max_count=8)
    if explicit_names:
        names = explicit_names[:7]
    else:
        names = _final_unique_names(_extract_name_candidates(title, f"{background}\n{intro}", categories), title, min_count=5, max_count=7)
    role_tracks = [
        ("追查异动", "总在最先接触异常线索的位置推进主线", "一旦判断失手，最先被放大的就是他的误差"),
        ("稳住局势", "负责把失衡局面压回可控范围", "他每次出手都在和扩散中的失序赛跑"),
        ("调度资源", "把外部通路和关键资源真正接进主线行动", "资源越往深处调，反噬就越可能提前落下"),
        ("试探人心", "通过对话和反应辨认谁在隐瞒、谁在摇摆", "最危险的时候往往不是冲突爆开，而是他误信了错误的人"),
        ("冒险执行", "在高风险节点先落地行动，把推演变成真实后果", "他替所有人先踩进危险区，也最早看见代价长什么样"),
        ("重组线索", "把旧信息和新证据重新拼成能继续追下去的路线", "他每往前补上一块真相，局势就会跟着变重一层"),
        ("维持共识", "尽量撑住团队合作边界，避免内部先被撕开", "他不是最锋利的人，却经常是最先被裂缝扯住的人"),
    ]
    primary_driver = defaults["driver"][0]
    secondary_driver = defaults["driver"][1] if len(defaults["driver"]) > 1 else primary_driver
    primary_scene = defaults["scene"][0]
    secondary_scene = defaults["scene"][1] if len(defaults["scene"]) > 1 else primary_scene
    primary_relation = defaults["relation"][0]
    elements = "、".join(defaults["element"][:3])
    source_for_summary = f"{background}\n{intro}"
    if any(x in source_for_summary for x in ("霜港", "港城", "海雾", "沉船", "气象站", "回声站")):
        primary_scene = "霜港港城"
        secondary_scene = "废弃回声站"
        primary_driver = "旧案重启"
        secondary_driver = "事故报告改写"
        elements = "异常潮汐记录、沉船事故档案、未解码录音"
    elif any(x in source_for_summary for x in ("校园", "社团", "广播站", "旧信")):
        primary_scene = "高中校园"
        secondary_scene = "旧社团档案室"
        primary_driver = "旧误会重启"
        secondary_driver = "档案互相矛盾"
        elements = "未寄出的旧信、被删掉的活动录像、社团档案"
    char_map: Dict[str, str] = {}
    for idx, name in enumerate(names):
        base = _clean_behavior_sentence(str(creation_char_map.get(name, "") or ""))
        if any(marker in base for marker in ("在全书主线里主要", "持续推动主线升级", "不能被其他角色替代", "相关行动会同步影响人物关系")):
            base = ""
        if not base:
            base = _clean_behavior_sentence(_merge_name_actions_from_intro(name, intro))
        role_label, role_detail, role_risk = role_tracks[idx % len(role_tracks)]
        extras = [
            f"全书里他（她）主要承担“{role_label}”这一侧的推进，{role_detail}。",
            role_risk,
            f"进入中后段后，他（她）和{primary_relation}、{primary_driver}这两条线会形成直接牵引。",
        ]
        behavior = _compose_long_text(base, extras, min_chars=58, max_parts=4)
        char_map[name] = _ensure_period(behavior)

    title_text = f"《{title}》" if title else "这部小说"
    main_name = names[0]
    second_name = names[1] if len(names) > 1 else names[0]
    third_name = names[2] if len(names) > 2 else names[1]
    fourth_name = names[3] if len(names) > 3 else names[2]
    fifth_name = names[4] if len(names) > 4 else fourth_name
    content = _final_join_paragraphs(
        [
            (
                f"{title_text}会从{main_name}被迫卷入一场无法按常规逻辑处理的异常事件写起。最初浮出水面的，也许只是发生在{primary_scene}的一处裂口，"
                f"或是一条和{elements}有关的异常痕迹，但这条裂口很快把{second_name}、{third_name}一并拖进局势中心。"
                f"他们原本不在同一条行动线上，却因为同一组线索开始交叉、对照、互相牵制，故事的起爆点由此成立。随着第一轮追查推进，表面问题会迅速显露出深层结构，读者会很快意识到这不是一次孤立失控，而是{primary_driver}已经开始影响更大的秩序。"
            ),
            (
                f"主线目标会迅速变得清晰：{main_name}必须弄明白事件背后的真正推动者是谁，{primary_driver}为什么会在此刻突然加速，"
                f"以及谁在利用这场混乱重排所有人的站位。阻力不会只来自外部对手，也来自内部判断差异。{second_name}更重视稳住局面，"
                f"{third_name}更倾向于继续深挖，{fourth_name}则会在资源与立场之间反复权衡。正因为每个人推动主线的方式不同，故事不会陷入人物行为同质化，反而会在合作、试探、误判和代价之中不断改写人物彼此的关系。"
            ),
            (
                f"进入中段后，剧情会从单点调查扩张为多线并行：线索核验、人物试探、资源调度、风险扩散和关系重组同时发生。"
                f"{fifth_name}也会成为局势变化的重要支点，既可能短暂促成合作，也可能在关键节点放大误判。每一次行动带回来的都不只是信息，还会改写资源流向、关系边界和阶段目标；"
                f"而{secondary_driver}会在这一阶段逐渐露出轮廓，让主角团意识到自己面对的不是单一谜题，而是一套正在成形的连锁压力。"
            ),
            (
                f"等故事进入更深一层时，真正危险的部分会从“查到什么”转向“查明之后该怎么办”。"
                f"{main_name}要面对的不只是答案本身，还要面对答案一旦公开，是否会让{primary_scene}与{secondary_scene}同时失去原有平衡；"
                f"{second_name}和{third_name}也不会一直维持最初的站位，他们会因为各自守护的秩序、关系和利益逐渐出现偏移。"
                f"于是后续推进会不断带出阶段性胜利与更大代价并存的局面：线索越清楚，人物越难退回原来的位置，原本还能维持的合作也会因为新的判断和旧伤口被反复拉扯。"
            ),
            (
                f"当阶段性真相被掀开后，故事不会立刻收束，反而会把更高层面的对抗推到台前：谁有资格决定真相如何公开，谁来承担公开之后的代价，"
                f"谁又会因为立场变化变成新的阻力来源。于是{title_text}后续值得继续写的根本原因就成立了：人物关系会持续裂变，冲突等级会持续升级，"
                f"而每一次推进都将迫使主角团重新选择‘要保住什么、愿意失去什么’。到了后续阶段，{primary_driver}与{secondary_driver}会彼此咬合，把更大的代价、反转和站队压力一起推上台面。"
            ),
        ]
    )
    return [{"主要人物和他们的行为": char_map, "内容": content}]


def _build_prompt_based_outline(messages: List[Dict[str, str]], seed_text: str = "") -> List[Dict[str, Any]]:
    user_text = _get_last_user_content(messages)
    fields = _final_extract_current_outline_fields(user_text)
    title = fields["title"]
    categories = fields["categories"]
    background = fields["background"]
    intro = fields["intro"]
    summary = fields["summary"]
    creation_char_map = fields["creation_char_map"]
    locked_char_map = fields["locked_char_map"]

    explicit_names = _normalize_person_names(list(locked_char_map.keys()) + list(creation_char_map.keys()), title=title, max_count=8)
    if explicit_names:
        names = explicit_names[:7]
    else:
        merged_names = _extract_name_candidates(title, f"{background}\n{intro}\n{summary}", categories)
        names = _final_unique_names(merged_names, title, min_count=5, max_count=7)
    source_text = f"{summary}\n{intro}\n{background}".strip()
    ignored_clause_markers = (
        "故事发生在",
        "主要舞台",
        "小说标题",
        "分类",
        "标签",
        "世界观",
        "简介",
        "主要人物",
        "他们的行为",
        "分卷数量",
        "章节数量",
        "章节范围",
    )
    seed_clauses = _extract_model_seed_clauses(seed_text, names, max_count=8)
    clauses = seed_clauses + [
        clause
        for clause in _extract_clean_clauses(source_text, min_len=8)
        if not any(marker in clause for marker in ignored_clause_markers)
        and not _is_structural_noise_clause(clause)
        and not clause.strip().endswith(("：", ":"))
        and clause not in seed_clauses
    ]

    def pick_clause(index: int, default: str) -> str:
        if not clauses:
            return default
        return clauses[index % len(clauses)]

    volume_arcs = [
        {
            "phase": "立局",
            "goal": "把第一轮异动、旧案残片和人物站位真正扣在一起",
            "start_focus": "先让异常信号落到具体场景和具体风险上",
            "develop_focus": "围绕首批证据链推进，同时逼出第一轮判断分歧",
            "climax_focus": "让一次错误判断直接引爆后果，逼人物第一次为主线付账",
            "end_focus": "留下阶段突破，但把更深的风险直接推到下一卷门口",
        },
        {
            "phase": "深挖",
            "goal": "翻出旧账、人情债和被压住的隐藏同盟",
            "start_focus": "把上一卷看似压住的问题重新掀开，让余波先反扑回来",
            "develop_focus": "让关系排查、利益交换和暗线调查一起加速",
            "climax_focus": "逼出第一次真正的关系破裂和公开站队",
            "end_focus": "拿到更深的证据，却失去原本安全的合作关系",
        },
        {
            "phase": "对撞",
            "goal": "让幕后势力和主角团选择在明面上正面碰撞",
            "start_focus": "把暗中的压制和试探拉到台面，让所有人不能再装作中立",
            "develop_focus": "让行动推进、立场裂变和外部反扑同步升级",
            "climax_focus": "把牺牲、失控和价值选择压到同一个场面里爆开",
            "end_focus": "给出代价极重的阶段胜利，并留下无法立刻缝合的裂痕",
        },
        {
            "phase": "收束",
            "goal": "完成阶段决断，回收伏线，并把余波推出更大一级局势",
            "start_focus": "先回收前面埋下的余波与倒计时风险",
            "develop_focus": "围绕真相如何处理、责任如何承担、秩序如何重排继续推进",
            "climax_focus": "让最终决定同时影响真相归宿和主要人物命运",
            "end_focus": "阶段主线收住，但把新的世界级余震和人物代价真正留下来",
        },
    ]
    target_volume_count = _pick_outline_volume_count(user_text, default=len(volume_arcs))
    if target_volume_count != len(volume_arcs):
        base_arcs = volume_arcs
        volume_arcs = []
        for idx in range(target_volume_count):
            base_index = min(len(base_arcs) - 1, int(idx * len(base_arcs) / max(1, target_volume_count)))
            base = dict(base_arcs[base_index])
            if target_volume_count > len(base_arcs):
                base["phase"] = f"{base['phase']}·第{idx + 1}段"
                base["goal"] = f"承接全书规划，完成第{idx + 1}卷的阶段推进：{base['goal']}"
            volume_arcs.append(base)
    role_lines = [
        ("裁决方向", "负责判断这一卷先追哪条线、先护住谁、先牺牲什么", "判断只要一偏，这一卷后半程就会被迫改道"),
        ("核验线索", "把证词、物证和现场反馈重新核到能落地执行的程度", "他越想把真相钉死，越会先看见信息缺口"),
        ("调度资源", "把外部通路、人脉和灰色资源接进主线行动", "一旦支撑链路松动，最先塌下来的就是他手里的局面"),
        ("试探人心", "通过试探和对话辨认谁在隐瞒、谁在摇摆、谁在误导", "错信一次，就足够让整卷的站位重新洗牌"),
        ("执行险步", "在需要冒险落地的时候先顶上去，把计划变成行动", "他每往前走一步，代价都会更快落到明面上"),
        ("缝合裂缝", "尽量撑住内部共识，避免团队先在站位分歧里解体", "越想把裂缝按住，越容易成为最先被拉扯的人"),
    ]
    role_templates = [
        "{name}先被推到“{role_focus}”这一环上，这条线一旦没人接住，整卷推进就会散开。",
        "卷内要把“{role_focus}”真正往前推的时候，{name}是最先躲不开的人。",
        "{name}这一卷碰到的第一道硬坎，就是“{role_focus}”到底该怎么稳住。",
        "落到{name}面前最现实的事情，不是表态，而是先把“{role_focus}”做成可执行动作。",
        "{name}这卷先要接住的，是“{role_focus}”这一块别在半路失控。",
        "一旦局势开始加速，最先压到{name}肩上的，往往就是“{role_focus}”这件事。",
        "{name}在本卷真正要扛住的，不是气氛变化，而是“{role_focus}”这条线别被带偏。",
        "这卷里{name}没法后退的位置，就落在“{role_focus}”这一格上。",
        "{name}被推到前面之后，首先得处理的就是“{role_focus}”到底由谁来顶住。",
        "真正把{name}卷进本卷核心的，不是表面波动，而是“{role_focus}”这条线开始往深处塌。",
        "卷内很多动作能不能接上，最后都系在{name}能否先把“{role_focus}”钉稳。",
        "{name}这卷绕不开的现实压力，是“{role_focus}”不能继续停在判断层面。",
        "到这一卷时，{name}必须先把“{role_focus}”接到自己手里，后面的推进才有落点。",
        "对于{name}来说，本卷最不好躲的事情，就是“{role_focus}”迟早要有人先扛下来。",
        "{name}在卷内真正面对的，不是抽象风险，而是“{role_focus}”已经压到脚边。",
        "当局势往前推时，最先把{name}拽进核心位置的，就是“{role_focus}”这道口子。",
        "{name}这一卷要先守住的，不是表面秩序，而是“{role_focus}”别突然塌成缺口。",
        "卷内压力真正落到{name}身上时，首先变重的就是“{role_focus}”这条线。",
        "{name}这卷先得把“{role_focus}”撑起来，不然后面的所有动作都会只剩样子。",
        "如果说这一卷有什么事情最先逼到{name}面前，那一定是“{role_focus}”开始失去缓冲。",
    ]
    hint_templates = [
        "卷内推进还会被“{clause}”这件事持续牵着走。",
        "而“{clause}”会不断反过来挤压他的判断空间。",
        "卷里的很多选择，最后都会被“{clause}”推着提前表态。",
        "他后面的动作迟早会和“{clause}”正面撞上。",
        "这也意味着“{clause}”不会停在背景层，而会一直压着这条线往前跑。",
        "真正把这条线推歪或推稳的，往往就是“{clause}”这件事。",
        "本卷里很多原本还能拖延的决定，最后都会被“{clause}”逼得提前落地。",
        "说到底，这条线往哪个方向拐，很大程度上都会被“{clause}”牵住。",
        "看似还在背景里的“{clause}”，最后会一层层压进卷内的每次选择里。",
        "这一卷真正甩不开的牵引，其实一直都是“{clause}”这件事。",
        "越往后推，越会发现“{clause}”在悄悄改变所有人的判断顺序。",
        "本卷很多动作看似临场决定，实际上都已经被“{clause}”提前框住了去路。",
    ]
    start_followups = [
        "{second}不急着表态，而是先盯住证据能不能落地；{third}更早看见外部阻力会从哪里压进来。卷首的分歧因此落在行动优先级上，而不是停在情绪对抗里。",
        "{second}想先稳住可控范围，{third}却判断继续观望只会错过窗口。{lead}夹在两种判断之间，开局的推进会先形成一条必须选择的岔路。",
        "这一段不靠口号制造张力，而让{second}、{third}在同一条线索前做出不同取舍：一个保局面，一个追源头，{lead}必须先承担选择成本。",
        "{second}会把风险压低处理，{third}则试图把问题直接追到源头。两种做法都合理，却会让{lead}很快意识到这一卷不能按单线调查往下写。",
        "开局真正要写出的不是热闹场面，而是{second}、{third}对“该先救局还是先追真相”的分歧。这个分歧会直接改变{lead}接下来的落点。",
    ]
    develop_followups = [
        "这一段要让证据推进和人心变化互相咬住，尤其要把“{develop_clause}”写成会影响行动安排的现实压力，而不是只补充设定。",
        "发展段的重点不是堆线索，而是让“{develop_clause}”改变每个人的判断顺序。线索越清楚，合作反而越难维持原状。",
        "这里需要把调查、资源和关系三条线并在一起写：{third}越往里推进，{fourth}越会暴露不能明说的顾虑，“{develop_clause}”也会开始反过来限制行动空间。",
        "中段要避免只写发现新信息，而要让“{develop_clause}”成为一次次选择背后的压力源。读者能看见局势在变，也能看见人物为什么跟着变。",
        "这一阶段每拿到一块证据，都应该同步改变谁能合作、谁被排除、谁开始隐藏更多。“{develop_clause}”会成为人物站位重排的触发点。",
    ]
    climax_followups = [
        "高潮不能只靠事件爆开，还要让“{climax_clause}”逼出一次当场选择：有人保真相，有人保关系，有人必须为前面的误判付出代价。",
        "卷内最高压的场面要把“{climax_clause}”变成真实后果。此前能模糊处理的关系、秘密和承诺，都要在这里被迫亮明。",
        "这一段要让冲突有明确代价，而不是单纯升级声量。“{climax_clause}”会把{lead}和{selected_last}推到同一个选择题前，谁退让都会留下后患。",
        "高潮的核心是让人物再也不能只用试探维持局面。“{climax_clause}”一旦落地，合作边界、风险承担和后续目标都会被改写。",
        "这里要写的是卷内判断的清算：前面谁隐瞒、谁误判、谁过度自信，都要被“{climax_clause}”逼成看得见的后果。",
    ]
    ending_followups = [
        "收束段不急着把所有问题盖住，而要让“{end_clause}”把下一阶段的压力来源亮出来：谁得利、谁受损、谁从此不再可信。",
        "卷尾需要给读者一个阶段答案，同时把“{end_clause}”留下的后果摆清楚。下一卷要追的不是同一个谜题，而是这次选择制造出的新局面。",
        "结尾要收住本卷主线，也要把“{end_clause}”转化成新的任务、敌意或人情债。读者应当能看见下一步压力从哪里来。",
        "这一卷最后不能只做归纳，而要让“{end_clause}”改变人物之间的默认关系。有人得到证据，有人失去退路，有人会带着隐瞒进入下一阶段。",
        "卷尾最好留下清晰的余量：答案解决了一部分问题，却让“{end_clause}”带来的站位变化真正落地。下一卷的入口由此自然打开。",
    ]

    def pick_followup(pool: Sequence[str], volume_index: int, slot: str, **kwargs: Any) -> str:
        if not pool:
            return ""
        index = int(hashlib.md5(f"{title}|{volume_index}|{slot}".encode("utf-8")).hexdigest(), 16) % len(pool)
        return pool[index].format(**kwargs)

    items: List[Dict[str, Any]] = []
    title_text = f"《{title}》" if title else "这部小说"
    for volume_index, arc in enumerate(volume_arcs, start=1):
        selected = [names[(volume_index - 1 + idx) % len(names)] for idx in range(min(6, len(names)))]
        selected = list(dict.fromkeys(selected))
        lead = selected[0]
        second = selected[1] if len(selected) > 1 else lead
        third = selected[2] if len(selected) > 2 else second
        fourth = selected[3] if len(selected) > 3 else third

        char_map: Dict[str, str] = {}
        template_order = sorted(
            range(len(role_templates)),
            key=lambda i: hashlib.md5(f"{title}|{volume_index}|role|{i}".encode("utf-8")).hexdigest(),
        )
        hint_order = sorted(
            range(len(hint_templates)),
            key=lambda i: hashlib.md5(f"{title}|{volume_index}|hint|{i}".encode("utf-8")).hexdigest(),
        )
        for idx, name in enumerate(selected[:6]):
            base = _clean_behavior_sentence(str(locked_char_map.get(name) or creation_char_map.get(name) or ""))
            base = base.replace("相关行动会同步影响人物关系、资源流向和下一阶段决策边界", "")
            base = base.replace("他的动作会直接改变调查走向和人物站位", "")
            role_focus, role_action, role_risk = role_lines[(volume_index + idx - 1) % len(role_lines)]
            if idx == 0:
                lead_action = role_action[2:] if role_action.startswith("负责") else role_action
                action = _compose_long_text(
                    base,
                    [
                        f"{name}在第{volume_index}卷主导“{arc['goal']}”这条卷内目标。",
                        f"他本卷重点是{lead_action}。",
                        role_risk,
                    ],
                    min_chars=84,
                    max_parts=5,
                )
            else:
                clause_hint = pick_clause(volume_index + idx + 5, "")
                template = role_templates[template_order[idx % len(template_order)]]
                extras = [
                    template.format(name=name, role_focus=role_focus),
                    role_action,
                    role_risk,
                ]
                if clause_hint:
                    hint_template = hint_templates[hint_order[idx % len(hint_order)]]
                    extras.append(hint_template.format(clause=clause_hint))
                action = _compose_long_text(
                    base,
                    extras,
                    min_chars=76,
                    max_parts=5,
                )
            char_map[name] = _ensure_period(action or f"{name}在本卷推进关键行动，并改变人物站位与事件节奏。")

        start_clause = pick_clause(volume_index - 1, "旧案残片和当前异动在同一时间重新浮上水面")
        develop_clause = pick_clause(volume_index + 2, "人物关系在合作、试探和防备之间持续摇摆")
        climax_clause = pick_clause(volume_index + 4, "阶段推进把所有人都推到了不能再后退的位置")
        end_clause = pick_clause(volume_index + 6, "阶段性答案只会把更大的问题提前推到台前")

        story_map = {
            "开始": _final_join_paragraphs(
                [
                    f"{title_text}第{volume_index}卷的开局重点是“{arc['start_focus']}”。{start_clause}会先压到{lead}面前，迫使他立刻判断这卷最先该追哪条线、先保住谁。",
                    pick_followup(
                        start_followups,
                        volume_index,
                        "start",
                        lead=lead,
                        second=second,
                        third=third,
                    ),
                ]
            ),
            "发展": _final_join_paragraphs(
                [
                    f"进入发展段后，本卷要完成“{arc['develop_focus']}”。{third}负责把线索继续往里拽，{fourth}会把隐藏立场和顾虑逐步暴露出来。",
                    pick_followup(
                        develop_followups,
                        volume_index,
                        "develop",
                        third=third,
                        fourth=fourth,
                        develop_clause=develop_clause,
                    ),
                ]
            ),
            "高潮": _final_join_paragraphs(
                [
                    f"高潮段围绕“{arc['climax_focus']}”展开。{lead}和{selected[-1]}必须在同一个关键选择上正面碰撞，前面压住的误判、秘密和代价都要在这里兑现。",
                    pick_followup(
                        climax_followups,
                        volume_index,
                        "climax",
                        lead=lead,
                        selected_last=selected[-1],
                        climax_clause=climax_clause,
                    ),
                ]
            ),
            "结局": _final_join_paragraphs(
                [
                    f"结局部分重点落实“{arc['end_focus']}”。卷尾既要交代这一卷究竟保住了什么、失去了什么，也要让新的问题直接推向下一卷。",
                    pick_followup(
                        ending_followups,
                        volume_index,
                        "ending",
                        end_clause=end_clause,
                    ),
                ]
            ),
        }
        items.append({"主要人物和他们的行为": char_map, "故事情节": story_map})
    return items


def _build_prompt_based_detail_outline(messages: List[Dict[str, str]], seed_text: str = "") -> List[Dict[str, Any]]:
    fields = _final_extract_current_detail_fields(_get_last_user_content(messages))
    title = fields["title"]
    categories = fields["categories"]
    background = fields["background"]
    intro = fields["intro"]
    volume_summary = fields["volume_summary"]
    continuity_context = fields.get("continuity_context", "")
    chapter_count = int(fields["chapter_count"])
    creation_char_map = fields["creation_char_map"]
    current_char_map = fields["current_char_map"]

    explicit_names = _normalize_person_names(list(current_char_map.keys()) + list(creation_char_map.keys()), title=title, max_count=6)
    names = list(explicit_names)
    if len(names) < 3:
        recovered_names = _normalize_person_names(
            _extract_name_candidates(title, f"{background}\n{intro}\n{volume_summary}\n{continuity_context}", []),
            title=title,
            max_count=6,
        )
        for name in recovered_names:
            if name not in names:
                names.append(name)
            if len(names) >= 3:
                break
    if len(names) < 2:
        names = _build_default_person_names(title, [], count=3)
    profile = _infer_genre_profile(categories)
    mode = profile.get("mode", "noir")
    seed_map = {
        "noir": {
            "titles": ["雨夜起潮", "旧岸回声", "锈门暗影", "灯下错踪", "裂缝生光", "暗潮回涌"],
            "scenes": ["暴雨压港的旧码头", "被封存多年的档案室", "凌晨仍亮着灯的旧城区走廊", "临时清出的安全屋前厅", "高架桥下的废弃通道", "带潮气的地下仓库"],
            "events": ["一份来路不明的新证据", "一段和旧案对不上的记录", "一次看似偶然实则被设计过的碰面", "一条把灰色势力牵进来的异常线索", "一个足以改写站位的小型失控事件", "一份被提前调包的关键材料"],
            "hooks": ["新线索已经被摆到明面上", "某个人的站位第一次出现无法回避的裂缝", "团队刚建立的默契被迫接受新一轮试探", "更深一层的旧案余波已经开始反扑", "新的行动窗口被压缩到更短的时间里", "真正的危险还没登场，但所有人都已感受到前兆"],
            "pressure": ["旧案回潮带来的压力正在一点点逼近所有人的站位边界", "表面还算稳定的局面，实际上已经开始从内部松动", "越往里查，人物之间原本默认的信任顺序就越难维持", "眼前这条线索不会只带来信息，还会逼所有人重新选择立场", "真正危险的不是异常本身，而是谁先借着异常改写局面", "每个人都知道这次推进不会只换来答案，还会换来新的代价"],
        },
        "sci": {
            "titles": ["残轨失火", "权限裂缝", "静默终端", "失序回廊", "冷灯坐标", "协议回声"],
            "scenes": ["轨道站外环残骸区", "巨构城市夜间检修层", "被封存的协议档案库", "中继塔下的维护通道", "主城边缘的失压走廊", "星港调度厅的隔离区"],
            "events": ["一段被改写过的权限日志", "一枚忽然复醒的记忆芯片", "一次被人故意推迟的系统校验", "一台本应注销却再次上线的终端", "一条带有伪装签名的内部指令", "一份与旧协议冲突的调度记录"],
            "hooks": ["必须核验的协议节点已经暴露出来", "有人提前知道系统失稳会从哪里开始扩散", "第一条真正指向旧核心协议的证据已经落地", "局部故障的背后开始显出人为操控的痕迹", "新的权限裂缝会迫使所有人提前站队", "表面修复刚完成，更深一层的失序却已经启动"],
            "pressure": ["协议网络的稳定性已经开始从内部松动", "每一次排障都在逼人物重新判断谁还值得信任", "线索越清楚，权限边界就越显得危险", "真正的风险不是故障本身，而是谁在借故障改写秩序", "局势看似还能压住，实际已经开始失去原先的缓冲", "他们每推进一步，系统和人心都会同时变得更不稳定"],
        },
        "xianxia": {
            "titles": ["雪阶惊印", "禁地回钟", "古阵微明", "山门夜雪", "残卷入局", "灵灯照骨"],
            "scenes": ["山门禁地外的风雪石阶", "藏经阁后方的封印长廊", "夜雪压住的古松石坪", "秘境入口前的断碑台", "钟楼下的空寂回廊", "被封死的剑冢外环"],
            "events": ["一枚忽然复醒的残缺剑印", "一页与宗门旧录对不上的残卷", "一次被人故意提前触发的阵纹回响", "一缕不该出现在此地的灵息残痕", "一段和旧誓互相咬合的禁令记录", "一枚指向旧约裂口的古符"],
            "hooks": ["禁地线索已经显形", "旧誓与现局第一次被硬生生扣到一起", "有人提前知道传承异动会从哪一层爆开", "宗门里原本压住的裂缝开始浮到明面上", "再往前一步，所有人都得为旧约付账", "更深一层的传承危险已经逼近眼前"],
            "pressure": ["旧约和禁忌传承正在重新逼近所有人的命数", "越往里查，人物彼此之间默认的信任就越难维持", "真正危险的不是异象本身，而是谁在借异象改写命数", "风雪压住表面声息，暗处的站位却已经开始松动", "每一次追查都会让代价先一步显形", "他们离真相越近，离失控也越近"],
        },
        "history": {
            "titles": ["雪夜传诏", "宫门暗印", "旧臣回声", "长阶失衡", "灯下密折", "寒署微澜"],
            "scenes": ["皇城外苑与雪压长阶之间", "深宫旧署的夜值回廊", "被封档的案牍库外厅", "宫门外的雪夜石桥", "朝堂后廊的昏灯角落", "边报尚未入库的驿馆前厅"],
            "events": ["一封被改过笔迹的密诏副本", "一页和旧卷宗对不上的边报摘录", "一次被人刻意拖迟的传诏记录", "一枚本应封存却再次出现的印鉴", "一条指向旧臣旧案的内廷口供", "一份在雪夜里突然现身的密折"],
            "hooks": ["案牍线索已经摆到案前", "原本压住的朝局裂缝第一次显形", "有人提前知道这道密诏会落到谁手里", "第一条真正指向旧臣旧案的证据已经出现", "再往前一步，所有人都得提前站队", "表面秩序尚在，真正的清洗却已经开始提前落位"],
            "pressure": ["朝局表面未乱，真正的清洗却已经开始提前落位", "局面越显得安静，人物之间的提防就越难掩住", "真正危险的不是案子本身，而是谁借案重排人心", "每往里查一步，旧臣与新局就会咬得更紧", "表面还算稳的秩序，实际上已经开始从内部松动", "他们每推进一步，代价都会先落到站位最薄的一层人身上"],
        },
        "youth": {
            "titles": ["雨廊失序", "晚灯未落", "旧信回潮", "操场回声", "课桌裂缝", "风停之前"],
            "scenes": ["晚自习后的旧教学楼走廊", "雨夜操场边的看台底层", "社团档案室的窄窗边", "灯还没灭的空教室后排", "校门口通往旧街的连廊", "被临时封住的器材室门外"],
            "events": ["一封没有署名却被折得很整齐的旧信", "一页和社团记录对不上的旧日志", "一次看似偶然却被人刻意安排的重逢", "一段被故意删掉的活动影像记录", "一份突然出现在课桌里的匿名纸条", "一条把旧误会重新拖回眼前的消息"],
            "hooks": ["那封旧信已经落到手里", "原本还能装作没发生的关系裂缝开始松动", "有人提前知道这段旧事会在今晚被翻出来", "新的误会和旧问题已经真正扣到一起", "再往前一步，所有人都得承认自己不再能退回原位", "表面的平静还在，真正的情绪失衡却已经开始扩散"],
            "pressure": ["看似安静的人际边界正在慢慢失去原先的平衡", "越往里试探，人物之间原本还能藏住的话就越难藏住", "真正危险的不是秘密本身，而是谁先借秘密改写关系", "表面还能维持体面，心里的失衡却已经开始向外渗开", "每一次追问都会让下一次沉默变得更难承受", "人物越想装作平静，真正的情绪就越会在细节里暴露出来"],
        },
    }
    active_seeds = seed_map.get(mode, seed_map["noir"])
    title_seeds = active_seeds["titles"]
    scene_seeds = active_seeds["scenes"]
    event_seeds = active_seeds["events"]
    hook_seeds = active_seeds["hooks"]
    pressure_seeds = active_seeds["pressure"]
    model_seed_clauses = _extract_model_seed_clauses(seed_text, names, max_count=12)
    if model_seed_clauses:
        event_seeds = (model_seed_clauses[:4] + [item for item in event_seeds if item not in model_seed_clauses])[:8]
        hook_pool = model_seed_clauses[4:8] or model_seed_clauses[:4]
        pressure_pool = model_seed_clauses[8:12] or model_seed_clauses[:4]
        hook_seeds = (hook_pool + [item for item in hook_seeds if item not in hook_pool])[:8]
        pressure_seeds = (pressure_pool + [item for item in pressure_seeds if item not in pressure_pool])[:8]
    prompt_scene_candidates: List[str] = []
    prompt_scene_text = f"{background}\n{intro}\n{volume_summary}\n{continuity_context}"
    generic_scene_tokens = {"海港都市", "雨夜都市", "旧城区", "都市", "城区", "港区"}
    for match in re.findall(r"[一-鿿]{0,8}(?:档案馆|旧档案馆|码头|雨夜码头|灯塔|旧灯塔|记录中心|异常记录中心|异常中心|仓库|走廊|安全屋|通道|旧街)", prompt_scene_text):
        scene = re.sub(r"^(当代|虚构|一座|主要|集中于|发生在|以及|和|与|里|中|的)+", "", match).strip("，。、；;：: ")
        if 3 <= len(scene) <= 12 and scene not in generic_scene_tokens and scene not in prompt_scene_candidates:
            prompt_scene_candidates.append(scene)
    if prompt_scene_candidates:
        scene_seeds = (prompt_scene_candidates + [scene for scene in scene_seeds if scene not in prompt_scene_candidates])[:8]
    turn_map = {
        "noir": [
            "这一下不会只带来信息，更会把彼此提防的边界再往前推一格",
            "谁先开口、谁先沉默，都会比表面上的答案更早暴露真实站位",
            "旧线索和眼前异动开始互相咬合，人物谁都没法再把这件事当成局外风声",
            "原本还能维持的合作姿态开始发紧，真正的防备在细节里先一步显出来",
            "局势真正变重的地方，不是异常本身，而是有人借着异常试图改写下一步节奏",
            "这一次推进会把原本藏在暗处的裂缝硬生生照亮一瞬",
        ],
        "sci": [
            "权限和判断会同时开始失稳，任何一个小误差都会被放大成系统级后果",
            "他们越想把故障按回原位，越会发现真正失控的根源不在明面上",
            "表面上的排障动作会逐渐变成对规则边界的逼近和试探",
            "谁掌握日志、谁握着权限，谁就先握住了重排秩序的机会",
            "局面的危险开始从设备层蔓延到人物之间的信任边界",
            "每推进一层，原本还能解释通的异常都会变得更像人为结果",
        ],
        "xianxia": [
            "异象带来的不只是惊疑，更会逼人物把旧誓和现局放到同一张桌面上重新衡量",
            "看似安静的禁地和传承线索，会一步步把人物推到再也回不去的命数关口",
            "每一次试探阵纹和旧录，都像在同时碰醒更深一层的因果",
            "真正变重的不是灵息，而是人物意识到有人早就盯着这场异动在等结果",
            "表面的守礼和克制会逐渐撑不住，真正的立场差会在追查里自己显出来",
            "这次推进会让原本还能模糊处理的旧约突然有了现实代价",
        ],
        "history": [
            "案牍和密诏牵出来的，不只是旧事，更会把朝局里原本藏住的试探一起带出来",
            "人物越想守住分寸，分寸本身反而越会成为彼此较量的锋口",
            "这一步查下去，真正开始失衡的不会只是案子，而是所有人的站位和退路",
            "表面秩序越完整，暗里那点互相试探的力道就越显得锋利",
            "真正让局势变重的，是有人已经把这条线当成了重排人心的机会",
            "一次看似谨慎的压制，反而会把更深一层的风波提前拽出水面",
        ],
        "youth": [
            "旧事一旦被重新翻出来，人物之间原本还能装作若无其事的边界就会开始发紧",
            "越是想把情绪按住，越会在动作和停顿里暴露出真正的失衡",
            "这次推进带来的不是简单误会，而是把旧关系重新拉回了必须面对的位置上",
            "表面仍能维持体面，真正的拉扯却已经在细枝末节里一点点冒出来",
            "人物嘴上还能说得轻，可真正先变重的是谁也不敢承认的那部分心事",
            "这一章留下的后劲，会让下一次见面不可能再像从前那样轻松",
        ],
    }
    aftertaste_map = {
        "noir": [
            "危险还没完全现形，却已经贴到每个人后颈",
            "真正麻烦的东西并没有过去，而是刚刚开始显形",
            "下一步行动像是被局势硬逼出来，谁都没法再停在原地",
            "停顿背后压着人人都知道来不及后退的沉重",
        ],
        "sci": [
            "系统层面的失稳和人物层面的失衡同时留下余波",
            "真正的故障核心仍在更深处等待被触发",
            "下一次排查像被整套系统反过来逼出来",
            "秩序表面尚在，内部却已开始裂开",
        ],
        "xianxia": [
            "因果还未真正结清，反而越牵越紧",
            "异象暂时压住了，命数的回响却并没有停",
            "下一步追查像是被旧誓和传承同时往前推了一把",
            "风雪未停，真正危险才刚刚露出轮廓",
        ],
        "history": [
            "朝局表面仍然安静，更深一层的试探却已经悄悄落位",
            "局势正在悄悄改写每个人的退路",
            "下一次动作像是被朝局和人心同时往前推出来",
            "雪夜尚静，真正的清洗却已提前起步",
        ],
        "youth": [
            "情绪并未爆开，却已经再也回不到原位",
            "下一次见面已经不可能像这一次之前那样轻松",
            "下一步靠近像是被旧事和当下心事一起推出来",
            "那点真正的失衡持续压在人物心口",
        ],
    }
    meta_markers = (
        "第1卷",
        "第2卷",
        "第3卷",
        "第4卷",
        "第5卷",
        "第6卷",
        "第7卷",
        "第8卷",
        "开局重点",
        "进入发展段",
        "高潮段",
        "结局部分",
        "卷尾",
        "本卷",
        "这一卷",
        "会从",
        "写起",
        "让卷首",
        "推进方向",
        "负责把",
        "负责将",
        "本大纲旨在",
        "基于您提供",
        "根据您提供",
        "以下是",
        "下面是",
        "旨在将",
        "详细大纲",
        "第1-",
        "第2-",
        "第3-",
        "第4-",
        "章尾",
        "章末",
        "尾声",
    )
    summary_clauses = [clause for clause in _extract_clean_clauses(volume_summary, min_len=6) if not any(marker in clause for marker in meta_markers)]
    summary_clauses = [clause for clause in summary_clauses if not _is_structural_noise_clause(clause)]
    intro_clauses = [clause for clause in _extract_clean_clauses(intro, min_len=6) if not any(marker in clause for marker in meta_markers) and not _is_structural_noise_clause(clause)]
    continuity_clauses = [
        clause
        for clause in _extract_clean_clauses(continuity_context, min_len=8)
        if not any(marker in clause for marker in ("当前生成", "处理策略", "章节数", "已有正文", "正文定稿"))
        and not _is_structural_noise_clause(clause)
    ]
    title_hash = int(hashlib.md5(f"{title}|{mode}|detail".encode("utf-8")).hexdigest(), 16)

    title_clean = re.sub(r"(手记|协议|未署名|档案库|档案|证词|雨季|旧臣心|失序录|剑冢录|坠落|长安|雪尽|录|书|集|篇|志)$", "", title)
    title_clean = re.sub(r"[^一-鿿A-Za-z0-9]", "", title_clean)
    title_tokens: List[str] = []
    for size in (2, 3):
        for i in range(0, max(0, len(title_clean) - size + 1)):
            frag = title_clean[i : i + size]
            if 2 <= len(frag) <= 3 and frag not in title_tokens:
                title_tokens.append(frag)
    if 2 <= len(title_clean) <= 3 and title_clean not in title_tokens:
        title_tokens.insert(0, title_clean)
    title_tokens = title_tokens[:8]

    genre_title_parts = {
        "noir": {
            "prefix": ["雨夜", "旧岸", "灯下", "雾港", "锈门", "暗潮", "港桥", "冷灯"],
            "suffix": ["回声", "暗痕", "错踪", "沉响", "夜痕", "余波", "旧影", "冷声"],
        },
        "sci": {
            "prefix": ["冷轨", "阈域", "星站", "序链", "核层", "残轨", "静默", "回廊"],
            "suffix": ["断点", "回波", "残响", "失序", "冷讯", "裂隙", "余光", "故障"],
        },
        "xianxia": {
            "prefix": ["山门", "夜雪", "古阵", "灵灯", "禁地", "断碑", "雪阶", "钟楼"],
            "suffix": ["回钟", "残印", "夜雪", "断阵", "微明", "旧誓", "照骨", "惊痕"],
        },
        "history": {
            "prefix": ["雪夜", "宫门", "长阶", "灯下", "旧署", "寒署", "密折", "案前"],
            "suffix": ["夜传", "暗印", "微澜", "旧声", "寒影", "回诏", "失衡", "秘折"],
        },
        "youth": {
            "prefix": ["雨廊", "晚灯", "操场", "课桌", "旧信", "风停", "连廊", "校门"],
            "suffix": ["未停", "回声", "裂缝", "失序", "旧页", "余温", "暗潮", "风停"],
        },
    }
    title_parts = genre_title_parts.get(mode, genre_title_parts["noir"])

    opening_templates = [
        "“{scene}”先把气压压低，{lead}刚接住“{event}”，就意识到这件事绝不是偶发。",
        "{lead}在“{scene}”里碰见“{event}”时，第一反应不是惊讶，而是立刻意识到有人抢在他们前面动过手脚。",
        "平静的“{scene}”被“{event}”一下撕开了口子，{lead}也因此被硬生生拖进更深一层的麻烦。",
        "“{scene}”里原本还能维持的平静，被“{event}”一下撕开了口子，{lead}也因此提前撞上这一阶段真正的危险。",
    ]
    conflict_templates = [
        "{second}和{third}对这次推进给出不一样的反应：一人先盯着局面别失控，另一人却认定再迟半步线索就会沉下去，这让试探和拉扯自然浮到台面上。",
        "{lead}、{second}、{third}在这里会形成清楚的三角张力：有人盯真相，有人守秩序，也有人更早看见代价将落到谁身上。",
        "{second}更担心节奏一乱就会被人牵着走，{third}则宁可把风险提前挑明，而{lead}只能在两种判断之间硬生生选边。",
        "随着核验继续往里推进，{lead}、{second}、{third}谁都不再只是旁观者，他们对同一件事的不同判断会把冲突自然推到明面上。",
        "{second}想把外部波动先拦住，{third}却更在意别让真正的线索再一次从手边滑过去，这让三个人的站位很快出现偏差。",
        "人一多，判断就开始分叉：{second}先看后果，{third}先追源头，{lead}却知道自己必须在两边之间给出更快的决定。",
        "{second}不愿让场面先散，{third}却觉得该翻开的东西不能再压着不动，{lead}因此被逼着站到最先承受代价的位置上。",
        "这段真正的力点，不是争执有多响，而是{second}、{third}和{lead}对同一步行动给出了完全不同的优先级。",
    ]
    ending_templates = [
        "到最后，{hook}，这会把下一步行动直接逼到台前。",
        "等最后一盏灯暗下去，{hook}，人物也因此明白眼前这一轮判断根本还没到头。",
        "危险已经贴近却还没彻底爆开，{hook}。",
        "雨声压低之后，{hook}，谁都知道自己已经回不到原来的位置上了。",
    ]
    focus_templates = [
        "{lead}此刻最重要的，不是立刻给出答案，而是把眼前异样和主线真正扣到一起。",
        "落到{lead}身上的第一件事，不是急着下结论，而是先分清这次异动究竟在替谁开路。",
        "{lead}很清楚现在最不能做的就是被表面现象带着走，他得先把真正危险的那条线扣准。",
        "对{lead}来说，眼前这一步真正要守住的，不是场面上的平静，而是主线最先偏移的方向。",
    ]

    items: List[Dict[str, Any]] = []
    seen_titles: set[str] = set()
    for chapter_no in range(1, chapter_count + 1):
        lead = names[(chapter_no - 1) % len(names)]
        second = names[chapter_no % len(names)] if len(names) > 1 else lead
        third = names[(chapter_no + 1) % len(names)] if len(names) > 2 else second
        offset = (title_hash + chapter_no - 1) % 997
        stage_pool = turn_map.get(mode, turn_map["noir"])
        aftertaste_pool = aftertaste_map.get(mode, aftertaste_map["noir"])
        scene = scene_seeds[(title_hash // 5 + chapter_no * 3) % len(scene_seeds)]
        event = event_seeds[(title_hash // 7 + chapter_no * 5) % len(event_seeds)]
        hook = hook_seeds[(title_hash // 11 + chapter_no * 7) % len(hook_seeds)]
        stage = stage_pool[(title_hash // 13 + chapter_no * 2) % len(stage_pool)]
        support_clause = pressure_seeds[(title_hash // 17 + chapter_no * 3) % len(pressure_seeds)]
        if continuity_clauses and chapter_no <= max(2, chapter_count // 3):
            support_clause = continuity_clauses[(chapter_no - 1) % len(continuity_clauses)]
        mood_clause = aftertaste_pool[(title_hash // 19 + chapter_no * 5) % len(aftertaste_pool)]

        seed_clauses = _extract_clean_clauses(
            f"{title}\n{event}\n{scene}\n{summary_clauses[(chapter_no - 1) % len(summary_clauses)] if summary_clauses else ''}\n{continuity_clauses[(chapter_no - 1) % len(continuity_clauses)] if continuity_clauses else ''}",
            min_len=2,
        )
        seed_tokens: List[str] = []
        for raw in seed_clauses:
            token = re.sub(r"[^一-鿿A-Za-z0-9]", "", raw)
            if 2 <= len(token) <= 3 and token not in seed_tokens:
                seed_tokens.append(token)
        title_core = title_tokens[offset % len(title_tokens)] if title_tokens else ""
        alt_core = title_tokens[(offset // 23) % len(title_tokens)] if title_tokens else ""
        seed_core = seed_tokens[(offset // 29) % len(seed_tokens)] if seed_tokens else ""
        prefix = title_parts["prefix"][(title_hash // 23 + chapter_no * 3) % len(title_parts["prefix"])]
        suffix = title_parts["suffix"][(title_hash // 29 + chapter_no * 5) % len(title_parts["suffix"])]
        if chapter_no % 4 == 1:
            raw_candidates = (
                f"{title_core}{suffix}" if len(title_core) >= 2 else "",
                title_seeds[(offset // 19) % len(title_seeds)],
                f"{prefix}{suffix}",
                f"{seed_core}{suffix}" if len(seed_core) >= 2 else "",
            )
        elif chapter_no % 4 == 2:
            raw_candidates = (
                f"{prefix}{suffix}",
                f"{alt_core}{suffix}" if len(alt_core) >= 2 else "",
                title_seeds[(offset // 31) % len(title_seeds)],
                f"{seed_core}{suffix}" if len(seed_core) >= 2 else "",
            )
        elif chapter_no % 4 == 3:
            raw_candidates = (
                f"{seed_core}{suffix}" if len(seed_core) >= 2 else "",
                f"{prefix}{suffix}",
                title_seeds[(offset // 19) % len(title_seeds)],
                f"{title_core}{suffix}" if len(title_core) >= 2 else "",
            )
        else:
            raw_candidates = (
                title_seeds[(offset // 31) % len(title_seeds)],
                f"{prefix}{suffix}",
                f"{alt_core}{suffix}" if len(alt_core) >= 2 else "",
                f"{seed_core}{suffix}" if len(seed_core) >= 2 else "",
            )
        title_candidates: List[str] = []
        for candidate in raw_candidates:
            candidate = str(candidate or "").strip()
            if not candidate:
                continue
            if len(candidate) < 4 or len(candidate) > 8:
                continue
            if re.search(r"(.)\1{2,}", candidate):
                continue
            if candidate not in title_candidates:
                title_candidates.append(candidate)
        fallback_title = next((t for t in title_candidates if t not in seen_titles), "")
        if not fallback_title:
            for fallback_title in title_seeds:
                if fallback_title not in seen_titles:
                    fallback_title = fallback_title
                    break
        if not fallback_title:
            fallback_title = title_seeds[(chapter_no - 1) % len(title_seeds)]

        open_tmpl = opening_templates[(title_hash // 31 + chapter_no) % len(opening_templates)]
        conflict_tmpl = conflict_templates[(title_hash // 37 + chapter_no * 2) % len(conflict_templates)]
        end_tmpl = ending_templates[(title_hash // 41 + chapter_no * 3) % len(ending_templates)]
        focus_tmpl = focus_templates[(title_hash // 43 + chapter_no * 5) % len(focus_templates)]
        stage = turn_map.get(mode, turn_map["noir"])[(title_hash // 47 + chapter_no * 2) % len(turn_map.get(mode, turn_map["noir"]))]
        mood_clause = aftertaste_map.get(mode, aftertaste_map["noir"])[(title_hash // 53 + chapter_no * 3) % len(aftertaste_map.get(mode, aftertaste_map["noir"]))]
        paragraph_one = (
            open_tmpl.format(lead=lead, scene=scene, event=event)
            + focus_tmpl.format(lead=lead)
            + f"随着动作和观察继续往里走，{support_clause}。"
        )
        paragraph_two = (
            conflict_tmpl.format(lead=lead, second=second, third=third)
            + f"{stage}。"
            + end_tmpl.format(hook=hook)
            + f"{mood_clause}。"
        )
        carry_line = ""
        if continuity_clauses:
            carry_line = f"本章承接上一卷记忆：{continuity_clauses[(chapter_no - 1) % len(continuity_clauses)]}。"
        content = _final_join_paragraphs([paragraph_one, carry_line, paragraph_two])
        title_text = _content_driven_detail_title(content, fallback=fallback_title) or fallback_title
        if title_text in seen_titles:
            title_text = fallback_title if fallback_title not in seen_titles else f"{fallback_title[:7]}{chapter_no}"
        seen_titles.add(title_text)
        items.append({"章节标题": title_text, "细纲内容": _ensure_period(_clean_linebreaks(content))})
    return items


def _extract_loose_labeled_section(text: str, label: str, stop_labels: Sequence[str]) -> str:
    source = str(text or "")
    if not source.strip():
        return ""
    stops = {str(item or "").strip() for item in stop_labels if str(item or "").strip()}

    def normalize_label_line(line: str) -> Tuple[str, str]:
        raw = str(line or "").strip()
        raw = re.sub(r"^\s*[-•]?\s*", "", raw)
        raw = re.sub(r"^#{1,6}\s*", "", raw).strip()
        raw = raw.strip("* \t")
        match = re.match(r"^([一-鿿A-Za-z0-9_ ]{1,20})\s*[:：]\s*(.*)$", raw)
        if match:
            return match.group(1).strip().strip("* "), match.group(2).strip()
        return raw.strip("* "), ""

    lines = source.splitlines()
    capturing = False
    captured: List[str] = []
    for line in lines:
        line_label, inline_value = normalize_label_line(line)
        if not capturing:
            if line_label == label:
                capturing = True
                if inline_value:
                    captured.append(inline_value)
            continue
        if line_label in stops:
            break
        captured.append(line)
    return "\n".join(captured).strip()


_INFO_PUBLIC_META_PATTERNS = (
    r"生成要求",
    r"硬性限制",
    r"请根据",
    r"下面是",
    r"以下为",
    r"我为你",
    r"输出(?:内容|格式|结果)?",
    r"本次(?:生成|换稿|修订)",
    r"上一版|上一稿|换稿",
    r"用户|模型|prompt|提示词",
    r"标签(?:大类|明细|维度|体系)",
    r"需要(?:交代|写清|呈现|明确|控制)",
    r"必须(?:交代|写清|明确|包含|出现|保持|控制)",
    r"应该(?:呈现|写成|避免|补充)",
    r"可以(?:写成|吸收|用于|作为)",
    r"建议(?:先|将|把|补)",
    r"主线目标会(?:非常)?明确",
    r"长期推进方向",
    r"后续(?:故事)?(?:为什么)?值得继续写",
    r"创作(?:流程|策略|要求|方向|关键词)",
    r"读者会看得出",
)


def _clean_info_public_field(value: str) -> str:
    text = _clean_linebreaks(str(value or "").replace("**", "")).strip()
    if not text:
        return ""
    paragraphs: List[str] = []
    for raw in re.split(r"\n+", text):
        line = raw.strip().lstrip("-•>").strip()
        line = re.sub(r"^\d+(?:\.\d+)?[、.．]\s*", "", line).strip()
        if not line:
            continue
        if any(re.search(pattern, line, flags=re.IGNORECASE) for pattern in _INFO_PUBLIC_META_PATTERNS):
            continue
        line = re.sub(r"(?:生成要求|硬性限制|输出|说明)\s*[:：].*$", "", line).strip()
        if line:
            paragraphs.append(line)
    if not paragraphs:
        return ""
    cleaned = "\n".join(paragraphs).strip()
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    parts = [part.strip() for part in cleaned.splitlines() if part.strip()]
    if parts and re.fullmatch(r"[“\"「『].{2,80}[”\"」』][。！？!?]?", parts[-1]):
        parts = parts[:-1]
    elif parts:
        parts[-1] = re.sub(r"[“\"「『][^“”\"「」『』]{2,80}[”\"」』][。！？!?]?\s*$", "", parts[-1]).strip() or parts[-1]
    return "\n".join(parts).strip()


def _has_info_public_meta(value: str) -> bool:
    text = str(value or "")
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in _INFO_PUBLIC_META_PATTERNS)


def _model_sentences_for_structuring(text: str, locked_names: Sequence[str] = ()) -> List[str]:
    source = _repair_mixed_language_artifacts(str(text or ""), locked_names)
    source = _clean_detail_content_to_prose(_sanitize_text(source), locked_names)
    source = re.sub(r"(?m)^\s*(?:#+|\*+|-+)\s*", "", source)
    sentences: List[str] = []
    for sentence in _split_sentences(source):
        value = _clean_linebreaks(sentence).strip(" '\"\n\r\t")
        if len(value) < 8:
            continue
        if _is_structural_noise_clause(value):
            continue
        if any(marker in value for marker in ("输出格式", "请根据", "不要解释", "严格 JSON", "严格JSON")):
            continue
        sentences.append(_ensure_period(value))
    return sentences


def _repair_known_name_variants(text: str, canonical_names: Sequence[str]) -> str:
    value = str(text or "")
    names = [str(name or "").strip() for name in canonical_names if str(name or "").strip()]
    if not names:
        return value
    prefix_counts: Dict[str, int] = {}
    for name in names:
        if len(name) >= 3:
            prefix_counts[name[:-1]] = prefix_counts.get(name[:-1], 0) + 1
    for name in names:
        if len(name) >= 3:
            prefix = re.escape(name[:-1])
            if prefix_counts.get(name[:-1], 0) == 1:
                value = re.sub(rf"{prefix}\s+[A-Za-z][A-Za-z\s\-]{{1,24}}", name, value)
                value = re.sub(rf"{prefix}[A-Za-z][A-Za-z\s\-]{{1,24}}", name, value)
        if len(name) >= 2:
            value = re.sub(rf"{re.escape(name[0])}某", name, value)
    return value


def _repair_mixed_language_artifacts(text: str, canonical_names: Sequence[str] = ()) -> str:
    value = str(text or "")
    value = re.sub(r"[“\"'‘’]([^“”\"'‘’]{1,8})[”\"'‘’]\s*([一-鿿]{2,4})(?=\s*(?:\*\*)?\s*[:：])", r"\2", value)
    value = _repair_known_name_variants(value, canonical_names)
    if canonical_names:
        value = _normalize_locked_name_variants(value, canonical_names)
    replacements = [
        (r"故事\s*背\s*景\s*[:：]?", "故事背景："),
        (r"故事\s*(?:background|backgroud|Background)\s*[:：]?", "故事背景："),
        (r"(?:story\s*)?background\s*[:：]", "故事背景："),
        (r"(?m)^\s*[-•]?\s*故事\s*[:：]?\s*$", "故事背景："),
        (r"(?m)^\s*[-•]?\s*(?:#{1,6}\s*)?小说简介\s*[:：]?\s*$", "简介："),
        (r"(?:introduction|intro|简介\s*intro)\s*[:：]", "简介："),
        (r"(?:novel\s*)?synopsis\s*[:：]", "简介："),
        (r"故事\s*synopsis\s*[:：]", "简介："),
        (r"最高\s*bidder", "最高出价者"),
        (r"\bbidder\b", "出价者"),
        (r"\bunderworld\b", "灰色地带"),
        (r"(?:关系\s*)?(?:anchor|anchored|anchort|relation\s*anchor|relationship\s*anchor)\s*point\s*[;；:：]?", "关系锚点："),
        (r"关系\s*(?:anchor|ancher|anchort|anchored)\s*[;；:：]?", "关系锚点："),
        (r"关系\s*(?:Anchor|Ancher|Anchort)\s*[;；:：]?", "关系锚点："),
        (r"关系\s*[._-]\s*(?:anchor|ancher|anchort|anchored)\s*[;；:：]?", "关系锚点："),
        (r"关系\s*anch(?:or|er|os|o)?s?\s*[;；:：]?", "关系锚点："),
        (r"关系\s*安\s*cho\s*[;；:：]?", "关系锚点："),
        (r"关系\s*安\s*点\s*[;；:：]?", "关系锚点："),
        (r"关系\s*节\s*点\s*[;；:：]?", "关系锚点："),
        (r"关系\s*点\s*[;；:：]?", "关系锚点："),
        (r"关系\s*系?统点\s*[;；:：]?", "关系锚点："),
        (r"关系\s*安孔\s*[;；:：]?", "关系锚点："),
        (r"关系\s+[A-Za-z]{3,20}\s*[;；:：]?", "关系锚点："),
        (r"(?:relation\s*)?anchors?\s*[;；:：]", "关系锚点："),
        (r"relationanchors?\s*[;；:：]", "关系锚点："),
        (r"关系\s*[:：]", "关系锚点："),
        (r"关系\s*锚\s*point\s*[;；:：]?", "关系锚点："),
        (r"关系\s*anchor\s*point\s*[;；:：]?", "关系锚点："),
        (r"关系\s*anchort\s*point\s*[;；:：]?", "关系锚点："),
        (r"关系锚点：\s*[sS]\s*[;；:：]?", "关系锚点："),
        (r"锚点关系锚点\s*[:：]?", "关系锚点："),
        (r"锚点关系\s*[:：]?", "关系锚点："),
    ]
    for pattern, repl in replacements:
        value = re.sub(pattern, repl, value, flags=re.IGNORECASE)
    value = re.sub(r"关系\s*锚\s*点\s*[:：]?", "关系锚点：", value)
    value = re.sub(r"([一-鿿])\s+(医生|警官|法医|律师|队长|主任)(?=\s*[:：])", r"\1\2", value)
    value = re.sub(r"(?m)^\s*(?:[-•]\s*)?#{1,6}\s*故事\s*[:：]?\s*$", "故事背景：", value)
    value = re.sub(r"(?m)^\s*(?:[-•]\s*)?#{1,6}\s*(故事背景|简介)\s*[:：]?\s*$", r"\1：", value)
    value = re.sub(r"(?m)^\s*(?:[-•]\s*)?#{1,6}\s*$", "简介：", value)
    value = re.sub(r"(?m)^\s*(?:[-•]\s*)?(?:#{1,6}|\*{2,})\s*$", "", value)
    value = re.sub(r"关系锚点\s*[;；]\s*", "关系锚点：", value)
    value = re.sub(r"关系锚点：\s*：+", "关系锚点：", value)
    return value


def _extract_named_role_from_source(name: str, source: str, title: str = "") -> str:
    clean_name = str(name or "").strip()
    if not clean_name or not _is_valid_person_name(clean_name, title=title):
        return ""
    text = _repair_mixed_language_artifacts(_clean_linebreaks(str(source or "")), [clean_name])
    match = re.search(
        rf"(?ms)^\s*[-•]?\s*{re.escape(clean_name)}\s*[:：]\s*(.+?)(?=\n\s*[-•]?\s*[一-鿿]{{2,4}}\s*[:：]|\n\s*(?:故事背景|简介|人物关系|主要人物|故事情节)\s*[:：]|\Z)",
        text,
    )
    if not match:
        return ""
    desc = _clean_behavior_sentence(_clean_detail_content_to_prose(match.group(1), [clean_name]))
    desc = re.split(r"(?:关系锚点|故事背景|简介)\s*[:：]", desc, maxsplit=1)[0]
    return _ensure_period(desc[:260]) if desc else ""


def _join_model_sentences(sentences: Sequence[str], start: int, end: int, fallback: str = "") -> str:
    value = "".join(sentences[start:end]).strip()
    return _ensure_period(value or fallback)


def _split_model_sentences(sentences: Sequence[str], count: int) -> List[List[str]]:
    count = max(1, count)
    if not sentences:
        return [[] for _ in range(count)]
    chunk_size = max(1, math.ceil(len(sentences) / count))
    chunks = [list(sentences[i : i + chunk_size]) for i in range(0, len(sentences), chunk_size)]
    while len(chunks) < count:
        chunks.append([])
    return chunks[:count]


def _repair_primary_short_name_variants(text: str, primary_name: str, known_names: Sequence[str]) -> str:
    """Repair obvious protagonist short-name drift without touching relatives.

    Some small local models shorten a locked name in prose after generating a
    stable character list, e.g. "沈听澜" later becomes "沈澜发现" or "沈涛不得".
    This repair is deliberately context-limited: it only fires before common
    protagonist action verbs and never rewrites a name already present in the
    locked character set.
    """

    value = str(text or "")
    primary = str(primary_name or "").strip()
    if len(primary) < 2 or not value:
        return value
    locked = {str(name or "").strip() for name in known_names if str(name or "").strip()}
    surname = primary[0]
    action_tail = r"(?:不得|意识到|发现|知道|必须|拖着|重新|看着|手中|面对|深入|学会|试图|站在|和他的|和她的|在)"
    for candidate in sorted(set(re.findall(rf"{re.escape(surname)}[一-鿿]", value))):
        if candidate in locked or candidate == primary or not _is_valid_person_name(candidate):
            continue
        if candidate[-1] in "家父母":
            continue
        value = re.sub(rf"{re.escape(candidate)}(?={action_tail})", primary, value)
    short_action_verbs = (
        "不得不",
        "不得",
        "发现",
        "明白",
        "握紧",
        "意识到",
        "知道",
        "决定",
        "必须",
        "试图",
        "站在",
        "面对",
        "深入",
        "看见",
        "听见",
        "和他的",
        "和她的",
        "回到",
        "走进",
        "想起",
        "终于",
    )
    for verb in short_action_verbs:
        value = re.sub(rf"(?<![一-鿿]){re.escape(surname)}{verb}", f"{primary}{verb}", value)
    for other_name in locked:
        other = str(other_name or "").strip()
        if other == primary or not other.startswith(surname):
            continue
        # In the public synopsis the first listed character is the narrative
        # center. Repair only narrow protagonist-action contexts; keep normal
        # descriptions such as "沈振浩是..." untouched.
        for context in (
            "站在",
            "在整理父亲",
            "本该",
            "本不该",
            "不得不",
            "发现",
            "感到",
            "明夜潜入",
            "准备拼凑",
            "必须在证据",
            "步步为营。他不仅要",
        ):
            value = re.sub(rf"{re.escape(other)}(?={context})", primary, value)
    if len(primary) >= 3:
        prefix = re.escape(primary[:2])
        tail_confusable = set()
        for group in (set("澜岚阑栏鸾峦濂瀾"), set("舟洲周州"), set("威维巍伟"), set("清青"), set("禾荷河和舟洲周州"), set("东栋")):
            if primary[-1] in group:
                tail_confusable = group
                break
        if tail_confusable:
            same_surname_candidates = sorted(
                set(re.findall(rf"(?=({re.escape(surname)}[一-鿿]{{{len(primary) - 1}}}))", value)),
                key=len,
                reverse=True,
            )
            protagonist_context = r"(?:在|必须|不得|发现|面对|步步|本不该|试图|继续|整理|触碰|追查|最终|，他|，她|。他|。她)"
            for candidate in same_surname_candidates:
                if candidate in locked or candidate == primary:
                    continue
                if candidate[-1] not in tail_confusable:
                    continue
                value = re.sub(rf"{re.escape(candidate)}(?={protagonist_context})", primary, value)
            tail_chars = "".join(re.escape(ch) for ch in tail_confusable)
            value = re.sub(
                rf"{prefix}[{tail_chars}](?=(?:的失踪|的日记|独有|本该|不得不|发现|站在|感到))",
                primary,
                value,
            )
        value = re.sub(rf"{prefix}父亲", f"{primary}父亲", value)
        value = re.sub(rf"{prefix}父", f"{primary}的父亲", value)
        value = re.sub(rf"{prefix}的(?=(?:父亲|母亲|父母|家人|身份|目标|选择))", f"{primary}的", value)
        value = re.sub(rf"{prefix}从父亲", f"{primary}遵从父亲", value)
        value = re.sub(rf"{prefix}着到了", f"{primary}知道了", value)
    value = re.sub(rf"{re.escape(primary)}道(?=[，。；：、\s])", f"{primary}知道", value)
    value = re.sub(rf"{re.escape(primary)}图(?=[揭打查接靠])", f"{primary}试图", value)
    value = re.sub(rf"{re.escape(primary)}须", f"{primary}必须", value)
    value = re.sub(rf"{re.escape(primary)}父亲", f"{primary}的父亲", value)
    value = re.sub(rf"{re.escape(primary)}认知到", f"{primary}意识到", value)
    return value


def _build_summary_items_from_model_text(
    raw_text: str,
    locked_names: Sequence[str],
    title: str,
    intro: str,
) -> List[Dict[str, Any]]:
    def loose_content_from_key(source: str) -> str:
        matches = list(re.finditer(r"['\"“”‘’]?\s*内容\s*['\"“”‘’]?\s*[:：]", str(source or "")))
        if not matches:
            return ""
        segment = source[matches[-1].end() :]
        segment = re.split(r"<\|im_end\|>|<\|endoftext\|>|```", segment, maxsplit=1)[0]
        segment = segment.strip()
        segment = re.sub(r"^[\"'“”‘’\\s]+", "", segment)
        segment = re.sub(r"[\"'“”‘’\\s]*[\]}）)]*\s*[,;；]*\s*$", "", segment)
        return _clean_linebreaks(segment).strip()

    sentences = _model_sentences_for_structuring(raw_text, locked_names)
    keyed_content = loose_content_from_key(raw_text)
    content_source = keyed_content or "".join(sentences) or _clean_detail_content_to_prose(raw_text, locked_names)
    content = _filter_summary_content(content_source, list(locked_names), title=str(title or ""))
    if not content:
        return []

    char_map: Dict[str, str] = {}
    extracted = _final_extract_character_map_from_any_text(
        "\n".join([str(raw_text or ""), str(intro or "")]),
        title=str(title or ""),
        max_count=10,
    )
    locked_set = set(locked_names)
    candidate_names = list(locked_names) or list(extracted.keys())
    for name in candidate_names[:8]:
        if not name:
            continue
        if locked_set and name not in locked_set:
            continue
        desc = ""
        if name in extracted:
            desc = _clean_behavior_sentence(str(extracted.get(name) or ""))
        if not desc:
            hit = next((s for s in sentences if name in s), "")
            desc = _clean_behavior_sentence(hit or _merge_name_actions_from_intro(name, content_source))
        if desc:
            char_map[name] = _ensure_period(desc[:240])

    return [{"主要人物和他们的行为": char_map, "内容": content}]


def _build_outline_items_from_model_text(
    raw_text: str,
    locked_order: Sequence[str],
    title: str,
    intro_text: str,
    volume_count: int,
) -> List[Dict[str, Any]]:
    sentences = _model_sentences_for_structuring(raw_text, locked_order)
    if len(sentences) < 4:
        sentences = _model_sentences_for_structuring(intro_text, locked_order)
    if not sentences:
        return []
    volume_count = max(1, min(20, int(volume_count or 1)))
    chunks = _split_model_sentences(sentences, volume_count)
    items: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        if not chunk:
            continue
        quarter = max(1, math.ceil(len(chunk) / 4))
        story_map = {
            "开始": _join_model_sentences(chunk, 0, quarter),
            "发展": _join_model_sentences(chunk, quarter, quarter * 2),
            "高潮": _join_model_sentences(chunk, quarter * 2, quarter * 3),
            "结局": _join_model_sentences(chunk, quarter * 3, len(chunk)),
        }
        char_map: Dict[str, str] = {}
        segment_text = "".join(chunk)
        for name in list(locked_order)[:8]:
            if not name:
                continue
            hit = next((s for s in chunk if name in s), "")
            if not hit:
                hit = _merge_name_actions_from_intro(name, segment_text) or _merge_name_actions_from_intro(name, intro_text)
            cleaned = _clean_behavior_sentence(hit)
            if cleaned:
                char_map[name] = _ensure_period(cleaned[:240])
        if not char_map:
            extracted = _final_extract_character_map_from_any_text(
                "\n".join([segment_text, intro_text]),
                title=str(title or ""),
                max_count=8,
            )
            char_map = {name: _ensure_period(_clean_behavior_sentence(desc)[:240]) for name, desc in extracted.items()}
        items.append({"主要人物和他们的行为": char_map, "故事情节": story_map})
    return items


def _build_detail_items_from_model_text(
    raw_text: str,
    chapter_count: int,
    locked_names: Sequence[str],
) -> List[Dict[str, Any]]:
    sentences = _model_sentences_for_structuring(raw_text, locked_names)
    if not sentences:
        paragraphs = [
            _clean_linebreaks(p).strip()
            for p in re.split(r"\n{2,}", _clean_detail_content_to_prose(raw_text, locked_names))
            if _clean_linebreaks(p).strip()
        ]
        sentences = [_ensure_period(p) for p in paragraphs if len(p) >= 20]
    if not sentences:
        return []
    chapter_count = max(1, min(30, chapter_count))
    chunks = _split_model_sentences(sentences, chapter_count)
    items: List[Dict[str, Any]] = []
    for idx, chunk in enumerate(chunks, start=1):
        content = _trim_duplicate_tail(_clean_linebreaks("".join(chunk))).strip()
        if not content:
            continue
        title = _content_driven_detail_title(content, fallback=f"第{idx}章") or f"第{idx}章"
        items.append({"章节序号": idx, "章节标题": title, "细纲内容": _ensure_period(content)})
    return _ensure_unique_detail_titles(items)


def _names_likely_same_variant(left: str, right: str) -> bool:
    a = str(left or "").strip()
    b = str(right or "").strip()
    if a == b:
        return True
    if not (2 <= len(a) <= 4 and 2 <= len(b) <= 4) or a[0] != b[0]:
        return False
    groups = (
        set("澜岚阑栏鸾峦濂瀾"),
        set("舟洲周州"),
        set("威维巍伟"),
        set("清青"),
        set("禾荷河和舟洲周州"),
        set("东栋"),
        set("默墨莫黙"),
    )
    if len(a) == len(b):
        ok = True
        for ca, cb in zip(a[1:], b[1:]):
            if ca == cb:
                continue
            if not any(ca in group and cb in group for group in groups):
                ok = False
                break
        if ok:
            return True
    return SequenceMatcher(None, a, b).ratio() >= 0.82 and (a[:2] == b[:2] or a[-1] == b[-1])


def _normalize_info_recommend_text(text: str, messages: List[Dict[str, str]]) -> str:
    clean = _clean_linebreaks(_to_simplified_lite(_sanitize_text(text)))
    user_text = _get_last_user_content(messages)
    fields = _extract_info_prompt_fields(user_text)
    title = str(fields.get("title", "")).strip()
    categories = [str(x).strip() for x in fields.get("categories", []) if str(x).strip()]
    all_tags = [str(x).strip() for x in fields.get("all_tags", []) if str(x).strip()]
    revision_direction = str(fields.get("revision_direction", "") or "").strip()
    previous_draft = str(fields.get("previous_draft", "") or "").strip()
    clean = _clean_linebreaks(_repair_mixed_language_artifacts(clean, ()))
    initial_names = [
        name.strip()
        for name in re.findall(r"(?m)^\s*[-•]?\s*(?:\*\*)?\s*([一-鿿]{2,4})\s*(?:\*\*)?\s*[:：]", clean)
        if _is_valid_person_name(name.strip(), title=title)
    ]
    if initial_names:
        clean = _clean_linebreaks(_repair_mixed_language_artifacts(clean, initial_names))

    fallback_cache: Optional[str] = None

    def get_fallback() -> str:
        nonlocal fallback_cache
        if fallback_cache is None:
            fallback_cache = _final_render_info_recommend(messages)
        return fallback_cache

    def get_stable_fallback_if_needed(reason: str) -> str:
        fallback = get_fallback()
        return fallback if fallback else clean

    def should_force_stable_fallback(value: str, names: Sequence[str]) -> bool:
        raw = str(value or "")
        if re.search(r"(读者|让我们一起|本书|本作|这部作品|将带给|走进这个|见证)", raw):
            return True
        daily_profile = any(k in "、".join(categories + all_tags) for k in ("都市日常", "治愈", "邻里", "现实向", "慢节奏", "亲情"))
        if daily_profile and re.search(r"(权力网络|黑帮|犯罪集团|重大案件|连环|凶杀|刑警|失踪|案件|阴谋|幽灵|犯罪|绑架|命案|尸体|定时炸弹)", raw):
            return True
        locked = [str(n or "").strip() for n in names if str(n or "").strip()]
        if locked:
            primary = locked[0]
            if len(primary) >= 2:
                surname = primary[0]
                short_bad = re.findall(rf"{re.escape(surname)}[一-鿿]", raw)
                allowed = set(locked)
                for hit in short_bad:
                    if hit not in allowed and hit not in primary and hit != primary[:2]:
                        if daily_profile or raw.count(hit) >= 2:
                            return True
        return False

    if not clean:
        return get_fallback() if allow_deterministic_fallback("empty") else ""

    if revision_direction and previous_draft:
        if _text_similarity(clean[:2200], previous_draft[:2200]) >= 0.72:
            return clean
        previous_names = set(_normalize_person_names(_extract_name_candidates(title, previous_draft, categories), title=title, max_count=12))
        current_names = set(_normalize_person_names(_extract_name_candidates(title, clean, categories), title=title, max_count=12))
        if previous_names and current_names:
            overlap = previous_names & current_names
            if len(overlap) >= max(3, min(len(previous_names), len(current_names)) // 2):
                return clean
    profile = _infer_genre_profile(categories + all_tags)
    defaults = profile.get("defaults", {}) if isinstance(profile, dict) else {}
    forbidden = [str(x).strip() for x in defaults.get("forbidden", []) if str(x).strip()]
    anchors = [str(x).strip() for x in defaults.get("anchors", []) if str(x).strip()]

    person_raw = _extract_loose_labeled_section(clean, "人物信息", ("故事背景", "故事", "简介", "小说简介"))
    if person_raw:
        person_raw = re.split(
            r"(?m)^\s*(?:[-•]\s*)?(?:#{1,6}\s*)?(?:人物关系|故事背景|故事|简介|小说简介)\s*[:：]?\s*$",
            person_raw,
            maxsplit=1,
        )[0].strip()
    background = _clean_info_public_field(_extract_loose_labeled_section(clean, "故事背景", ("简介", "小说简介")))
    intro = _clean_info_public_field(
        _extract_loose_labeled_section(clean, "简介", ())
        or _extract_loose_labeled_section(clean, "小说简介", ())
    )
    if background and not intro:
        bg_lines = [line.strip() for line in background.splitlines() if line.strip()]
        plot_start = -1
        plot_markers = ("雨夜", "为查明", "随着磁带", "随着调查", "按下播放器", "当陈", "在层层剥茧")
        for idx, line in enumerate(bg_lines):
            compact = line.lstrip("> ").strip()
            if idx >= 2 and any(marker in compact for marker in plot_markers):
                plot_start = idx
                break
        if plot_start >= 0:
            intro = _clean_info_public_field("\n".join(bg_lines[plot_start:]))
            background = _clean_info_public_field("\n".join(bg_lines[:plot_start]))
    if background and not intro:
        bg_sentences = _split_sentences(background)
        intro = _clean_info_public_field("".join(bg_sentences[-6:]).strip())
    if intro and not background:
        intro_sentences = _split_sentences(intro)
        background = _clean_info_public_field("".join(intro_sentences[:4]).strip())
    if _has_info_public_meta(background) or _has_info_public_meta(intro):
        return get_stable_fallback_if_needed("meta_public_field")
    source_text = "\n".join([person_raw, background, intro])
    source_char_map = _final_extract_character_map_from_any_text(source_text, title=title, max_count=10)
    source_names = list(source_char_map.keys())
    if source_names:
        alias_map: Dict[str, str] = {}
        canonical_names: List[str] = []
        for name in source_names:
            canonical = next((item for item in canonical_names if _names_likely_same_variant(name, item)), "")
            if canonical:
                alias_map[name] = canonical
                if source_char_map.get(name) and not source_char_map.get(canonical):
                    source_char_map[canonical] = source_char_map.get(name, "")
            else:
                canonical_names.append(name)
        if alias_map:
            for alias, canonical in alias_map.items():
                person_raw = re.sub(re.escape(alias), canonical, person_raw)
                background = re.sub(re.escape(alias), canonical, background)
                intro = re.sub(re.escape(alias), canonical, intro)
                if alias in source_char_map:
                    source_char_map.pop(alias, None)
            source_names = canonical_names
    if source_names:
        background = _repair_known_name_variants(background, source_names)
        intro = _repair_known_name_variants(intro, source_names)
        background = _normalize_locked_name_variants(background, source_names)
        intro = _normalize_locked_name_variants(intro, source_names)
        background = _repair_primary_short_name_variants(background, source_names[0], source_names)
        intro = _repair_primary_short_name_variants(intro, source_names[0], source_names)

    english_artifact_pattern = re.compile(
        r"(Relation\s*Anchors?|Novel\s*Synopsis|Story\s*Background|Character\s*Information|"
        r"Here\s+is|Below\s+is|```|<\|im_end\|>)",
        re.IGNORECASE,
    )
    if english_artifact_pattern.search("\n".join([person_raw, background, intro])):
        return get_stable_fallback_if_needed("english_artifact")

    blocked_person_names = {
        "人物关系",
        "人物信息",
        "故事背景",
        "小说简介",
        "简介",
        "故事",
        "关系锚点",
        "主要人物",
        "注",
    }
    person_lines: List[str] = []
    seen_person_names: set[str] = set()
    for raw_line in person_raw.splitlines():
        line = raw_line.strip().lstrip("-").lstrip("•").strip()
        if not line:
            continue
        if re.match(r"^\s*\*?\s*注\s*[:：]", line) or "此处修正" in line or "原底稿" in line:
            continue
        if line in {"###", "##", "#", "**"} or re.fullmatch(r"#{1,6}\s*", line):
            continue
        match = re.match(r"^(?:\*\*)?\s*([一-鿿]{2,4})\s*(?:\*\*)?\s*[:：]\s*(.+)$", line)
        if match:
            name = match.group(1).strip()
            if name in blocked_person_names or not _is_valid_person_name(name, title=title):
                continue
            if name in seen_person_names:
                continue
            desc = _clean_behavior_sentence(match.group(2))
            desc = re.split(r"(?:故事背景|简介|人物关系)\s*[:：]", desc, maxsplit=1)[0].strip()
            if desc:
                seen_person_names.add(name)
                person_lines.append(f"{name}：{_ensure_period(desc)}")

    def source_anchor_for(name: str) -> str:
        clean_name = str(name or "").strip()
        if not clean_name:
            return ""
        for raw in clean.replace("**", "").splitlines():
            line = raw.strip()
            if not re.match(rf"^\s*[-•]?\s*{re.escape(clean_name)}\s*[:：]", line):
                continue
            match = re.search(r"关系锚点\s*[:：]\s*(.+)$", line)
            if not match:
                continue
            anchor = _clean_behavior_sentence(match.group(1))
            anchor = _normalize_locked_name_variants(anchor.replace("“", "").replace("”", ""), list(source_char_map.keys()))
            anchor = re.split(r"(?:故事背景|简介|人物信息)\s*[:：]", anchor, maxsplit=1)[0].strip()
            return _ensure_period(anchor[:180]) if anchor else ""
        return ""

    if source_char_map and (
        len(person_lines) < min(6, len(source_char_map))
        or any(marker in "\n".join(person_lines) for marker in ("**", "关系.anchor", "关系_", "”是", "\"是"))
    ):
        rebuilt_lines: List[str] = []
        for name, desc in list(source_char_map.items())[:8]:
            cleaned_desc = _clean_behavior_sentence(desc).replace("**", "").strip()
            cleaned_desc = re.split(r"关系锚点\s*[:：]", cleaned_desc, maxsplit=1)[0].strip()
            if not cleaned_desc:
                continue
            anchor = source_anchor_for(name)
            line = f"{name}：{_ensure_period(cleaned_desc)}"
            if anchor:
                line += f"关系锚点：{anchor}"
            rebuilt_lines.append(line)
        if len(rebuilt_lines) >= max(4, min(6, len(source_char_map))):
            person_lines = rebuilt_lines

    parsed_person_names = [line.split("：", 1)[0].lstrip("- ").strip() for line in person_lines if "：" in line]
    if source_names and parsed_person_names:
        overlap = set(source_names) & set(parsed_person_names)
        extras = [name for name in parsed_person_names if name not in set(source_names)]
        if extras:
            return get_stable_fallback_if_needed("unexpected_person_names")
        if len(overlap) < min(2, len(source_names)):
            return get_stable_fallback_if_needed("weak_name_overlap")

    if len(person_lines) < 4:
        if source_names:
            person_lines = []
            for name, desc in list(source_char_map.items())[:8]:
                cleaned_desc = _clean_behavior_sentence(desc)
                if cleaned_desc:
                    person_lines.append(f"{name}：{_ensure_period(cleaned_desc)}")
        if len(person_lines) < 4:
            return get_stable_fallback_if_needed("few_person_lines")
    if len(person_lines) < 4:
        generated_names = _build_default_person_names(title, categories, count=6)
        first_name = generated_names[0] if generated_names else "主角"
        second_name = generated_names[1] if len(generated_names) > 1 else first_name
        person_lines = []
        for idx, name in enumerate(generated_names):
            if idx == 0:
                anchor = f"关系锚点：与{second_name}是旧识兼临时盟友；隶属{title or '主线'}核心阵营。"
            elif idx == 1:
                anchor = f"关系锚点：与{first_name}有背景交集但互相防备；与{generated_names[2] if len(generated_names) > 2 else first_name}存在家族或旧案牵连。"
            elif idx == 2:
                anchor = f"关系锚点：与{second_name}是家族/旧识关系；曾与{first_name}同门或同阵营。"
            else:
                anchor = f"关系锚点：与{first_name}存在主线交集；与{second_name}存在阵营或利益关联。"
            person_lines.append(f"- {name}：围绕主线行动，并在关键节点推动局势变化。{anchor}")
    else:
        parsed_names = []
        for line in person_lines[:8]:
            parsed_names.append(line.split("：", 1)[0].strip())
        first_name = parsed_names[0] if parsed_names else "主角"
        second_name = parsed_names[1] if len(parsed_names) > 1 else first_name
        enriched_lines = []
        for idx, line in enumerate(person_lines[:8]):
            if "关系锚点" in line:
                enriched_lines.append(f"- {line}")
                continue
            name = parsed_names[idx] if idx < len(parsed_names) else first_name
            if idx == 0:
                anchor = f"关系锚点：与{second_name}是旧识兼临时盟友；隶属{title or '主线'}核心阵营。"
            elif idx == 1:
                anchor = f"关系锚点：与{first_name}有背景交集但互相防备；与{parsed_names[2] if len(parsed_names) > 2 else first_name}存在家族或旧案牵连。"
            else:
                anchor = f"关系锚点：与{first_name}存在主线交集；与{second_name}存在阵营或利益关联。"
            enriched_lines.append(f"- {line}{anchor}")
        person_lines = enriched_lines

    final_names_for_public = [line.lstrip("- ").split("：", 1)[0].strip() for line in person_lines if "：" in line]
    if final_names_for_public:
        primary_name = final_names_for_public[0]
        if primary_name and primary_name not in intro[:260]:
            intro = _ensure_period(f"{primary_name}最先撞见这条主线的异常入口，并在保全自身与追问真相之间被迫做出选择。{intro}")
        if len(background) < 120:
            background = _ensure_period(
                background
                + f"{title or '故事'}的公共背景还会持续影响{primary_name}与周围人物的选择，"
                "旧关系、现实压力和隐藏线索会在同一舞台上交错推进。"
            )
        if len(intro) < 220:
            other_names = "、".join(final_names_for_public[1:4]) or "身边人"
            intro = _ensure_period(
                intro
                + f"随着{other_names}陆续卷入，人物之间原本稳定的信任顺序开始改变，"
                "每一次追查都必须付出新的代价，也会把更深的秘密推到台前。"
            )

    content_blob = "\n".join([background, intro, person_raw, clean])
    has_forbidden = any(token and token in content_blob for token in forbidden)
    has_anchor = not anchors or any(token and token in content_blob for token in anchors[:6])

    if has_forbidden:
        return get_stable_fallback_if_needed("forbidden_content")
    if len(background) < 120 or len(intro) < 220:
        return get_stable_fallback_if_needed("short_public_fields")
    if not has_anchor and background:
        background = _ensure_period(background) + f"整体设定仍会围绕{('、'.join(anchors[:3]) if anchors else '核心冲突')}展开。"

    background = _clean_linebreaks(background.replace("**", ""))
    intro = _clean_linebreaks(intro.replace("**", ""))
    normalized = "\n".join(
        [
            "人物信息：",
            *person_lines,
            "",
            "故事背景：",
            background,
            "",
            "简介：",
            intro,
        ]
    ).strip()
    final_names = [line.lstrip("- ").split("：", 1)[0].strip() for line in person_lines if "：" in line]
    if should_force_stable_fallback(normalized, final_names):
        return get_stable_fallback_if_needed("final_quality")
    return normalized


def _normalize_summary_text(text: str, messages: List[Dict[str, str]]) -> str:
    main_key = "主要人物和他们的行为"
    content_key = "内容"

    user_text = _get_last_user_content(messages)
    fields = _extract_summary_prompt_fields(user_text)
    title = fields.get("title", "")
    intro = fields.get("intro", "")
    person_block = _final_extract_prompt_block(
        user_text,
        ("人物信息", "主要人物", "底稿核心人物设定", "角色信息"),
        ("故事背景", "背景", "世界观", "小说简介", "简介", "人物关系拓扑", "关系拓扑", "请生成", "生成要求", "约束"),
    )
    locked_source = "\n".join(
        [
            str(person_block or fields.get("characters_raw", "") or ""),
        ]
    )
    locked_char_map = _final_extract_character_map_from_any_text(
        locked_source,
        title=str(title or ""),
        max_count=12,
    )
    locked_order = list(locked_char_map.keys())
    locked_names = set(locked_order)

    fallback_items_cache: Optional[List[Dict[str, Any]]] = None

    def get_fallback_items() -> List[Dict[str, Any]]:
        nonlocal fallback_items_cache
        if fallback_items_cache is None:
            fallback_items_cache = _build_prompt_based_summary(messages)
        return fallback_items_cache

    def get_fallback_item() -> Dict[str, Any]:
        fallback_items = get_fallback_items()
        return fallback_items[0] if fallback_items else {}

    raw_text = _repair_mixed_language_artifacts(_sanitize_text(text), locked_order)
    parsed = _parse_summary_obj(raw_text)
    raw_items = _extract_summary_items_from_obj(parsed) if parsed is not None else []
    if not raw_items:
        model_items = _build_summary_items_from_model_text(
            raw_text=raw_text,
            locked_names=locked_order,
            title=str(title or ""),
            intro=str(intro or ""),
        )
        if model_items:
            return _to_single_quote_literal(model_items)
        fallback_items = get_fallback_items() if allow_deterministic_fallback("empty") else []
        return _to_single_quote_literal(fallback_items)

    first = raw_items[0]
    raw_char_map = _extract_value_by_keys(first, SUMMARY_PERSON_KEYS)
    raw_content = _extract_value_by_keys(first, SUMMARY_CONTENT_KEYS)
    raw_story = _extract_value_by_keys(first, SUMMARY_STORY_KEYS)

    raw_char_map = _coerce_char_map(raw_char_map, {})
    char_map: Dict[str, str] = {}
    for raw_name, behavior in raw_char_map.items():
        name = str(raw_name or "").strip().strip("'\"")
        if not name or name in char_map:
            continue
        if not _is_valid_person_name(name, title=title):
            continue
        if locked_names and name not in locked_names:
            continue
        cleaned = _clean_behavior_sentence(str(behavior or ""))
        for marker in SUMMARY_TEMPLATE_MARKERS:
            cleaned = cleaned.replace(marker, "")
        cleaned = cleaned.strip("，。；：: ")
        if not cleaned:
            cleaned = _clean_behavior_sentence(_merge_name_actions_from_intro(name, intro))
        if cleaned:
            char_map[name] = _ensure_period(cleaned)
        if len(char_map) >= 8:
            break

    if len(char_map) < 4:
        # Keep the model's actual character set if it gave fewer roles. Do not synthesize a full cast
        # unless the model returned no usable names at all.
        source_for_missing = "\n".join([raw_text, locked_source, str(intro or "")])
        for name in locked_order:
            if len(char_map) >= min(8, max(4, len(locked_names))):
                break
            if name in char_map:
                continue
            hit = next((s for s in _model_sentences_for_structuring(source_for_missing, locked_order) if name in s), "")
            desc = _clean_behavior_sentence(
                hit
                or _extract_named_role_from_source(name, locked_source, title=str(title or ""))
                or _merge_name_actions_from_intro(name, source_for_missing)
            )
            if desc:
                char_map[name] = _ensure_period(desc[:240])
        if not char_map:
            model_items = _build_summary_items_from_model_text(
                raw_text=raw_text,
                locked_names=locked_order,
                title=str(title or ""),
                intro=str(intro or ""),
            )
            model_char_map = model_items[0].get(main_key, {}) if model_items else {}
            char_map = model_char_map if isinstance(model_char_map, dict) else {}
            if not char_map and allow_deterministic_fallback("schema_empty"):
                fallback_item = get_fallback_item()
                fallback_char_map = fallback_item.get(main_key, {}) if isinstance(fallback_item, dict) else {}
                char_map = fallback_char_map if isinstance(fallback_char_map, dict) else {}
                if locked_names:
                    char_map = {name: value for name, value in char_map.items() if name in locked_names}

    if isinstance(raw_content, str) and raw_content.strip():
        content = _clean_linebreaks(_sanitize_text(raw_content)).strip()
    elif isinstance(raw_story, str) and raw_story.strip():
        content = _clean_linebreaks(_sanitize_text(raw_story)).strip()
    elif isinstance(raw_content, dict):
        content = _story_map_to_content(_coerce_story_map(raw_content, {}))
    elif isinstance(raw_story, dict):
        content = _story_map_to_content(_coerce_story_map(raw_story, {}))
    else:
        content = ""
    content = re.sub(r"(?m)^\s*(小说梗概|梗概|内容|故事)\s*[:：]\s*", "", content).strip("'\" \n\r\t")
    content = content.replace("```json", "").replace("```python", "").replace("```", "").strip()
    content = _trim_duplicate_tail(content)
    content = _filter_summary_content(content, list(char_map.keys()) or locked_order, title=str(title or ""))
    if len(content) < 220:
        content = content or _filter_summary_content(raw_text, list(char_map.keys()) or locked_order, title=str(title or ""))

    cleanup_names = list(dict.fromkeys([*locked_order, *char_map.keys()]))
    for name, behavior in list(char_map.items()):
        cleaned_behavior = _normalize_locked_name_variants(str(behavior or ""), cleanup_names)
        cleaned_behavior = re.sub(rf"{re.escape(str(name))}[一-鿿](?=[、，。；;\s])", str(name), cleaned_behavior)
        for locked_name in cleanup_names:
            cleaned_behavior = cleaned_behavior.replace(f"{locked_name}{locked_name[-1]}", locked_name)
            cleaned_behavior = re.sub(rf"{re.escape(locked_name)}[澜岚阑栏鸾峦叶](?=[、，。；;\s])", locked_name, cleaned_behavior)
        char_map[name] = _ensure_period(_clean_behavior_sentence(cleaned_behavior))

    normalized = [{main_key: char_map, content_key: content}]
    rendered = _to_single_quote_literal(normalized)
    for locked_name in cleanup_names:
        rendered = re.sub(rf"{re.escape(str(locked_name))}[一-鿿](?=[、，。；;\s])", str(locked_name), rendered)
    return rendered


def _normalize_outline_text(text: str, messages: List[Dict[str, str]]) -> str:
    main_key = "主要人物和他们的行为"
    story_key = "故事情节"

    user_text = _get_last_user_content(messages)
    prompt_volume_count = _pick_outline_volume_count(user_text, default=4)
    prompt_fields = _extract_outline_prompt_fields(user_text)
    intro_text = str(prompt_fields.get("intro", "")).strip()
    if not intro_text:
        intro_text = str(prompt_fields.get("background", "")).strip()
    locked_order = _normalize_person_names(prompt_fields.get("characters", []), title=str(prompt_fields.get("title", "") or ""), max_count=12)
    locked_names = set(locked_order)

    text = _repair_mixed_language_artifacts(_normalize_locked_name_variants(str(text or ""), locked_order), locked_order)
    parsed = _parse_outline_obj(_sanitize_text(text))
    raw_items = _extract_outline_items_from_obj(parsed) if parsed is not None else []
    fallback_items_cache: Optional[List[Dict[str, Any]]] = None

    def get_fallback_items() -> List[Dict[str, Any]]:
        nonlocal fallback_items_cache
        if fallback_items_cache is None:
            fallback_items_cache = _build_prompt_based_outline(messages, seed_text="")
        return fallback_items_cache

    def complete_outline_items(items: Sequence[Dict[str, Any]]) -> str:
        completed: List[Dict[str, Any]] = [item for item in items if isinstance(item, dict)]
        if len(completed) < prompt_volume_count:
            model_items = _build_outline_items_from_model_text(
                raw_text=text,
                locked_order=locked_order,
                title=str(prompt_fields.get("title", "") or ""),
                intro_text=intro_text,
                volume_count=prompt_volume_count,
            )
            for candidate in model_items:
                if len(completed) >= prompt_volume_count:
                    break
                if isinstance(candidate, dict):
                    completed.append(candidate)
        if len(completed) < prompt_volume_count and allow_deterministic_fallback("hard_failure"):
            for candidate in get_fallback_items():
                if len(completed) >= prompt_volume_count:
                    break
                if isinstance(candidate, dict):
                    completed.append(candidate)

        normalized: List[Dict[str, Any]] = []
        for idx, item in enumerate(completed[:prompt_volume_count]):
            raw_char_map = _extract_value_by_keys(item, OUTLINE_PERSON_KEYS)
            raw_story = _extract_value_by_keys(item, OUTLINE_STORY_KEYS)
            char_map = _normalize_outline_char_map(raw_char_map, {}, intro_text)
            if locked_order:
                if char_map and not (set(char_map.keys()) & locked_names):
                    char_map = {}
                source_for_actions = "\n".join([_clean_linebreaks(str(item)), intro_text, user_text])
                for name in locked_order[:8]:
                    if name in char_map and str(char_map.get(name) or "").strip():
                        continue
                    desc = (
                        _extract_named_role_from_source(name, source_for_actions, title=str(prompt_fields.get("title", "") or ""))
                        or _merge_name_actions_from_intro(name, source_for_actions)
                    )
                    if desc:
                        char_map[name] = _ensure_period(_clean_behavior_sentence(desc)[:240])
                char_map = {name: char_map.get(name, "") for name in locked_order[:8] if str(char_map.get(name, "")).strip()}
            story_map = _normalize_outline_story_map(
                raw_story=raw_story,
                fallback_story=_build_story_from_intro(intro_text),
                volume_index=idx,
                total_volumes=prompt_volume_count,
            )
            normalized.append({main_key: char_map, story_key: story_map})
        return _to_single_quote_literal(normalized[:prompt_volume_count]).replace("###", "").replace("##", "").replace("#", "")

    if not raw_items:
        markdown_items = _parse_markdown_outline_items(text, locked_order, title=str(prompt_fields.get("title", "") or ""))
        if markdown_items:
            return complete_outline_items(markdown_items)
        model_items = _build_outline_items_from_model_text(
            raw_text=text,
            locked_order=locked_order,
            title=str(prompt_fields.get("title", "") or ""),
            intro_text=intro_text,
            volume_count=prompt_volume_count,
        )
        if model_items:
            return complete_outline_items(model_items)
        fallback_items = get_fallback_items() if allow_deterministic_fallback("empty") else []
        return complete_outline_items(fallback_items)

    normalized_items: List[Dict[str, Any]] = []
    for idx, raw in enumerate(raw_items[:6]):
        raw_char_map = _extract_value_by_keys(raw, OUTLINE_PERSON_KEYS)
        raw_story = _extract_value_by_keys(raw, OUTLINE_STORY_KEYS)
        raw_names = set(raw_char_map.keys()) if isinstance(raw_char_map, dict) else set()
        has_name_drift = bool(locked_names and raw_names and not (raw_names & locked_names))
        raw_story_keys = set(raw_story.keys()) if isinstance(raw_story, dict) else set()
        needs_fallback = (
            has_name_drift
            or
            not isinstance(raw_char_map, dict)
            or not raw_char_map
            or not isinstance(raw_story, dict)
            or not {"开始", "发展", "高潮", "结局"}.issubset(raw_story_keys)
        )
        fallback_char_map: Dict[str, str] = {}
        fallback_story: Dict[str, str] = {}
        if needs_fallback:
            if has_name_drift:
                raw_char_map = {}
            if not isinstance(raw_story, dict) or not raw_story:
                model_items = _build_outline_items_from_model_text(
                    raw_text=_clean_linebreaks(str(raw)),
                    locked_order=locked_order,
                    title=str(prompt_fields.get("title", "") or ""),
                    intro_text=intro_text,
                    volume_count=max(prompt_volume_count, len(raw_items)),
                )
                if model_items:
                    model_story = model_items[min(idx, len(model_items) - 1)].get(story_key, {})
                    if isinstance(model_story, dict):
                        fallback_story = model_story
                if not fallback_story:
                    fallback_story = _build_story_from_intro(intro_text)
        char_map = _normalize_outline_char_map(raw_char_map, fallback_char_map, intro_text)
        if locked_order:
            restricted = {name: char_map.get(name) or fallback_char_map.get(name) or "" for name in locked_order if name in char_map or name in fallback_char_map}
            if len(restricted) < min(2, len(locked_order)):
                model_items = _build_outline_items_from_model_text(
                    raw_text=_clean_linebreaks(str(raw)),
                    locked_order=locked_order,
                    title=str(prompt_fields.get("title", "") or ""),
                    intro_text=intro_text,
                    volume_count=max(prompt_volume_count, len(raw_items)),
                )
                retry_map = model_items[min(idx, len(model_items) - 1)].get(main_key, {}) if model_items else {}
                if isinstance(retry_map, dict):
                    restricted = {
                        name: str(retry_map.get(name) or char_map.get(name) or "").strip()
                        for name in locked_order
                        if str(retry_map.get(name) or char_map.get(name) or "").strip()
                    }
            if restricted:
                char_map = restricted
        char_map = {
            name: re.sub(rf"^({re.escape(str(name))}){{2,}}", str(name), re.sub(
                rf"^{re.escape(str(name))}是当前创作链路中已锁定的人物，后续阶段必须保持姓名、身份和关系一致，?",
                "",
                str(value or ""),
            ))
            for name, value in char_map.items()
        }
        if not char_map and locked_order:
            model_items = _build_outline_items_from_model_text(
                raw_text=_clean_linebreaks(str(raw)),
                locked_order=locked_order,
                title=str(prompt_fields.get("title", "") or ""),
                intro_text=intro_text,
                volume_count=max(prompt_volume_count, len(raw_items)),
            )
            retry_map = model_items[min(idx, len(model_items) - 1)].get(main_key, {}) if model_items else {}
            if isinstance(retry_map, dict) and retry_map:
                char_map = {str(name): str(value) for name, value in retry_map.items() if str(name).strip() and str(value).strip()}
            if not char_map:
                source_for_actions = "\n".join([intro_text, _clean_linebreaks(str(raw))])
                for name in locked_order[:8]:
                    desc = _merge_name_actions_from_intro(name, source_for_actions)
                    if desc:
                        char_map[name] = _ensure_period(_clean_behavior_sentence(desc)[:240])
        story_map = _normalize_outline_story_map(
            raw_story=raw_story,
            fallback_story=fallback_story if isinstance(fallback_story, dict) else _build_story_from_intro(intro_text),
            volume_index=idx,
            total_volumes=max(prompt_volume_count, len(raw_items)),
        )
        story_blob = json.dumps(story_map, ensure_ascii=False)
        if any(marker in story_blob for marker in ("关系失", "夏知远和家族", "和家族必须", "后社", "景交集", "全眠", "衡这两", "关键事", "曾与梁", "段未解", "程师", "当前创作链路", "后续阶段必须保持")):
            if not fallback_story:
                model_items = _build_outline_items_from_model_text(
                    raw_text=_clean_linebreaks(str(raw)),
                    locked_order=locked_order,
                    title=str(prompt_fields.get("title", "") or ""),
                    intro_text=intro_text,
                    volume_count=max(prompt_volume_count, len(raw_items)),
                )
                fallback = model_items[min(idx, len(model_items) - 1)] if model_items else {}
                fallback_story = fallback.get(story_key, {}) if isinstance(fallback, dict) else {}
            story_map = _normalize_outline_story_map(
                raw_story=fallback_story if isinstance(fallback_story, dict) else {},
                fallback_story=_build_story_from_intro(intro_text),
                volume_index=idx,
                total_volumes=max(prompt_volume_count, len(raw_items)),
            )
            retry_blob = json.dumps(story_map, ensure_ascii=False)
            if any(marker in retry_blob for marker in ("关系失", "夏知远和家族", "和家族必须", "后社", "景交集", "全眠", "衡这两", "关键事", "曾与梁", "段未解", "程师", "当前创作链路", "后续阶段必须保持")):
                story_map = _build_story_from_intro(intro_text)
        normalized_items.append({main_key: char_map, story_key: story_map})

    if not normalized_items:
        fallback_items = get_fallback_items() if allow_deterministic_fallback("hard_failure") else []
        normalized_items = fallback_items[:prompt_volume_count]

    if len(normalized_items) < prompt_volume_count:
        model_items = _build_outline_items_from_model_text(
            raw_text=text,
            locked_order=locked_order,
            title=str(prompt_fields.get("title", "") or ""),
            intro_text=intro_text,
            volume_count=prompt_volume_count,
        )
        for candidate in model_items:
            if len(normalized_items) >= prompt_volume_count:
                break
            if not isinstance(candidate, dict):
                continue
            normalized_items.append(candidate)
    if len(normalized_items) < prompt_volume_count and allow_deterministic_fallback("hard_failure"):
        fallback_items = get_fallback_items()
        for candidate in fallback_items:
            if len(normalized_items) >= prompt_volume_count:
                break
            normalized_items.append(candidate)

    return complete_outline_items(normalized_items)


def _normalize_detail_outline_text(text: str, messages: List[Dict[str, str]]) -> str:
    try:
        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        (log_dir / "debug_detail_outline_raw.txt").write_text(str(text or ""), encoding="utf-8")
        (log_dir / "debug_detail_outline_prompt.txt").write_text(_get_last_user_content(messages), encoding="utf-8")
    except Exception:
        pass

    fields = _final_extract_current_detail_fields(_get_last_user_content(messages))
    chapter_count = int(fields.get("chapter_count", DETAIL_OUTLINE_DEFAULT_CHAPTERS))
    chapter_count = max(1, min(30, chapter_count))
    creation_char_map = fields.get("creation_char_map", {})
    current_char_map = fields.get("current_char_map", {})
    char_map: Dict[str, str] = {}
    if isinstance(creation_char_map, dict):
        char_map.update(creation_char_map)
    if isinstance(current_char_map, dict):
        char_map.update(current_char_map)
    locked_names = list(char_map.keys())
    volume_summary = str(fields.get("volume_summary", "")).strip()
    novel_intro = str(fields.get("intro", "")).strip()
    continuity_context = str(fields.get("continuity_context", "")).strip()

    text = _repair_mixed_language_artifacts(_normalize_locked_name_variants(str(text or ""), locked_names), locked_names)
    parsed = _parse_detail_outline_obj(_to_simplified_lite(_sanitize_text(text)))
    raw_items = _extract_detail_outline_items_from_obj(parsed) if parsed is not None else []
    fallback_items_cache: Optional[List[Dict[str, Any]]] = None
    model_items_cache: Optional[List[Dict[str, Any]]] = None

    def get_fallback_items() -> List[Dict[str, Any]]:
        nonlocal fallback_items_cache
        if fallback_items_cache is None:
            fallback_items_cache = _build_prompt_based_detail_outline(messages, seed_text=text)
        return fallback_items_cache

    def get_fallback_item(idx: int) -> Dict[str, Any]:
        fallback_items = get_fallback_items()
        return fallback_items[idx - 1] if idx - 1 < len(fallback_items) else {}

    def get_model_items() -> List[Dict[str, Any]]:
        nonlocal model_items_cache
        if model_items_cache is None:
            model_items_cache = _build_detail_items_from_model_text(
                "\n".join([text, volume_summary, novel_intro, continuity_context]),
                chapter_count,
                locked_names,
            )
        return model_items_cache

    source_material = _clean_linebreaks("\n".join([text, volume_summary, novel_intro, continuity_context])).strip()

    def build_source_item(idx: int, seed: str = "") -> Dict[str, Any]:
        source_seed = _clean_linebreaks("\n".join([seed, source_material])).strip()
        if not source_seed:
            return {}
        title = _detail_title_from_content(source_seed, idx, chapter_count, fallback=f"第{idx}章")
        content = _compose_detail_chapter_content(
            chapter_no=idx,
            chapter_count=chapter_count,
            chapter_title=title,
            char_map=char_map,
            volume_summary=volume_summary,
            novel_intro=novel_intro,
            seed=source_seed,
        )
        return {"章节标题": title, "细纲内容": _ensure_period(_clean_linebreaks(content))}

    if not raw_items:
        model_items = get_model_items()
        if model_items:
            raw_items = model_items
        elif source_material:
            raw_items = [build_source_item(idx) for idx in range(1, chapter_count + 1)]
        else:
            fallback_items = get_fallback_items() if allow_deterministic_fallback("empty") else []
            return _to_single_quote_literal(fallback_items[:chapter_count])

    normalized_by_idx: Dict[int, Dict[str, Any]] = {}
    seen_titles: set[str] = set()
    polluted_markers = (
        "这一章先把场景落在",
        "卷首的核心不是简单抛出新事件",
        "为了追上",
        "主动入局",
        "构建出节奏紧张",
        "通过连续的谜团揭示",
        "章末必须",
        "章尾要",
        "章末要",
        "尾声要",
        "收束时要",
        "本章要",
        "会从",
        "写起",
        "负责把",
        "负责将",
        "卷名：",
        "核心目标：",
        "人物映射",
        "实际主角",
        "对应",
        "严格遵循本卷人物",
        "注：",
        "本大纲旨在",
        "基于您提供",
        "根据您提供",
        "以下是",
        "下面是",
        "旨在将",
        "人物关系拓扑",
        "详细大纲",
        "关系恒定",
        "核心冲突",
        "节奏把控",
        "静态关系不变",
        "静态关系铁律",
        "角色职能定位",
        "剧情推进逻辑",
        "家族/血缘",
        "不可更改",
        "将抽象",
        "落地为具体",
        "卷一细纲",
        "卷二细纲",
        "卷三细纲",
        "卷四细纲",
        "细纲：",
        "*：",
        "vs.",
        "vs",
        "###",
        "```",
        "の",
        "第一章：",
        "第二章：",
    )

    for i, raw in enumerate(raw_items):
        if not isinstance(raw, dict):
            continue
        idx_val = _extract_value_by_keys(raw, DETAIL_OUTLINE_INDEX_KEYS)
        idx = 0
        if idx_val not in (None, ""):
            m = re.search(r"\d+", str(idx_val))
            if m:
                try:
                    idx = int(m.group(0))
                except Exception:
                    idx = 0
        if idx <= 0:
            idx = i + 1
        idx = max(1, min(chapter_count, idx))
        if idx in normalized_by_idx:
            continue

        title_raw = _extract_value_by_keys(raw, DETAIL_OUTLINE_TITLE_KEYS)
        content_raw = _extract_value_by_keys(raw, DETAIL_OUTLINE_CONTENT_KEYS)

        title = _to_simplified_lite(_clean_linebreaks(str(title_raw or "")).replace("**", "").strip())
        title = re.sub(r"(?:章节标题|标题|细纲内容|内容)\s*[:：]\s*", "", title)
        if "，" in title or "。" in title or "：" in title or ":" in title:
            title = _content_driven_detail_title(str(content_raw or title), fallback="")
        title = re.sub(r"^\s*第\s*\d+\s*章\s*[:：\-、.．]?\s*", "", title)
        title = re.sub(r"^[\"“”'‘’]+|[\"“”'‘’]+$", "", title)
        title = re.sub(r"\s+", "", title)

        if title and 2 <= len(title) <= 10 and not _is_templatey_detail_title(title):
            compact_title = _normalize_detail_title_seed(title)
            if compact_title and 2 <= len(compact_title) <= 10 and not _is_templatey_detail_title(compact_title):
                title = compact_title
        else:
            title = _detail_title_from_content(str(content_raw or raw), idx, chapter_count, fallback=f"第{idx}章")

        if title in seen_titles:
            alt_title = _content_driven_detail_title(str(content_raw or ""), fallback="")
            if alt_title and alt_title not in seen_titles and not _is_templatey_detail_title(alt_title):
                title = alt_title
            else:
                title = f"{(title or '第' + str(idx) + '章')[:7]}{idx}"
        seen_titles.add(title)

        content = _to_simplified_lite(_clean_linebreaks(str(content_raw or "")).replace("**", "").strip())
        if not content and isinstance(raw, dict):
            content = _to_simplified_lite(_clean_linebreaks(str(raw)).strip())
        content = _sanitize_text(content).strip()
        content = re.sub(r"^[\"“”'‘’{\\s]*(?:章节标题|标题)\s*[:：]\s*[^，。；！？\n]{1,40}[，。；！？\n]+", "", content).strip()
        content = re.sub(r"^[\"“”'‘’{\\s]*(?:细纲内容|内容)\s*[:：]\s*", "", content).strip()
        content = _clean_detail_content_to_prose(content, locked_names)
        if any(marker in title for marker in ("卷主", "对应", "实际主角", "注：", "###")):
            title = _detail_title_from_content(str(content_raw or content), idx, chapter_count, fallback=f"第{idx}章")

        if _has_chapter_list_leakage(content):
            content = re.split(r"(?=\n?\s*第\s*[一二三四五六七八九十\d]+\s*章)", content, maxsplit=1)[0].strip() or content
        content = _trim_duplicate_tail(content)
        if len(content) < 120:
            # Keep model prose when it is usable; only expand fragments so the downstream text stage
            # receives a complete chapter brief instead of an accidental half-line.
            model_items = _build_detail_items_from_model_text(str(raw), 1, locked_names)
            if model_items:
                content = str(model_items[0].get("细纲内容", "") or content).strip()
            if len(content) < 120:
                source_item = build_source_item(idx, seed=content)
                if source_item:
                    title = str(source_item.get("章节标题") or title).strip() or title
                    content = str(source_item.get("细纲内容") or content).strip()
            if len(content) < 120 and allow_deterministic_fallback("hard_failure"):
                content = _compose_detail_chapter_content(
                    chapter_no=idx,
                    chapter_count=chapter_count,
                    chapter_title=title,
                    char_map=char_map,
                    volume_summary=volume_summary,
                    novel_intro=novel_intro,
                    seed=content or volume_summary,
                )
        content = re.sub(r"#+\s*", "", content.replace("の", "的"))
        title = re.sub(r"#+\s*", "", title.replace("の", "的")).strip()

        normalized_by_idx[idx] = {
            "章节标题": title,
            "细纲内容": _ensure_period(_clean_linebreaks(content)),
        }

    if _has_outline_prompt_leakage(raw_items) or _outline_items_are_too_similar(raw_items):
        fallback_items = get_fallback_items() if allow_deterministic_fallback("quality_rebuild") else []
        if fallback_items:
            return complete_outline_items(fallback_items[:prompt_volume_count])

    normalized_items: List[Dict[str, Any]] = []
    for idx in range(1, chapter_count + 1):
        if idx in normalized_by_idx:
            normalized_items.append(normalized_by_idx[idx])
            continue
        model_items = get_model_items()
        candidate = model_items[idx - 1] if idx - 1 < len(model_items) else {}
        if candidate:
            title = str(candidate.get("章节标题") or "").strip()
            content = str(candidate.get("细纲内容") or "").strip()
            if content:
                title = _detail_title_from_content(content, idx, chapter_count, fallback=title or f"第{idx}章")
                normalized_items.append({"章节标题": title, "细纲内容": _ensure_period(_clean_linebreaks(content))})
                continue
        source_item = build_source_item(idx)
        if source_item:
            normalized_items.append(source_item)
            continue
        if allow_deterministic_fallback("hard_failure"):
            fallback = get_fallback_item(idx)
            if fallback:
                normalized_items.append(fallback)

    if not normalized_items:
        fallback_items = get_fallback_items() if allow_deterministic_fallback("hard_failure") else []
        normalized_items = fallback_items[:chapter_count]
    normalized_items = _ensure_unique_detail_titles(normalized_items[:chapter_count])
    return _to_single_quote_literal(normalized_items)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Local OpenAI-compatible server for Qwen models")
    parser.add_argument("--model-path", type=str, default="", help="Base model path, required only in local model mode")
    parser.add_argument(
        "--served-model-name",
        type=str,
        default="ChiYong-MoE-Novel-18B-A6B",
        help="Model name exposed in API responses",
    )
    parser.add_argument("--adapter-path", type=str, default=None, help="Optional LoRA adapter path")
    parser.add_argument(
        "--text-nonfirst-adapter-path",
        type=str,
        default=None,
        help="Optional LoRA adapter path applied only to text_non_first_chapter",
    )
    parser.add_argument("--merge-lora", action="store_true", help="Merge LoRA into base model")
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=54862)
    parser.add_argument("--device", type=str, default="auto", choices=["auto", "cuda", "xpu", "cpu"])
    parser.add_argument("--dtype", type=str, default="float16", choices=["bfloat16", "float16", "float32"])
    parser.add_argument("--max-new-tokens", type=int, default=1536)
    parser.add_argument(
        "--include-done-marker",
        dest="include_done_marker",
        action="store_true",
        default=True,
        help="Append SSE [DONE] marker (default: enabled)",
    )
    parser.add_argument(
        "--no-done-marker",
        dest="include_done_marker",
        action="store_false",
        help="Disable SSE [DONE] marker",
    )
    parser.add_argument("--trust-remote-code", action="store_true", default=True)
    parser.add_argument("--no-trust-remote-code", dest="trust_remote_code", action="store_false")
    parser.add_argument("--upstream-endpoint", type=str, default="", help="Optional upstream OpenAI-compatible endpoint")
    parser.add_argument("--upstream-model", type=str, default="", help="Optional upstream model name override")
    parser.add_argument("--upstream-api-key", type=str, default="", help="Optional upstream API key (avoid; prefer env)")
    parser.add_argument(
        "--upstream-api-key-env",
        type=str,
        default="DEEPSEEK_API_KEY",
        help="Env var name containing upstream API key",
    )
    parser.add_argument(
        "--upstream-timeout-seconds",
        type=int,
        default=60,
        help="Upstream request timeout seconds",
    )
    parser.add_argument(
        "--upstream-nonstream-tasks",
        type=str,
        default="info_recommend,summary,outline,detail_outline",
        help="Comma-separated task names routed to upstream for non-stream requests",
    )
    parser.add_argument(
        "--novel-wiki-root",
        type=str,
        default="data/novel_wiki",
        help="Root directory for novel Wiki materials and topology files",
    )
    parser.add_argument(
        "--online-model",
        dest="online_model",
        action="store_true",
        default=None,
        help="Use TokenHub online model mode",
    )
    parser.add_argument(
        "--local-model",
        dest="online_model",
        action="store_false",
        help="Use local Hugging Face model mode",
    )
    parser.add_argument(
        "--tokenhub-base-url",
        type=str,
        default="",
        help="TokenHub OpenAI-compatible base URL; defaults to TOKENHUB_BASE_URL",
    )
    parser.add_argument(
        "--tokenhub-api-key-env",
        type=str,
        default="TOKENHUB_API_KEY",
        help="Env var name containing TokenHub API key",
    )
    parser.add_argument(
        "--tokenhub-timeout-seconds",
        type=int,
        default=0,
        help="TokenHub request timeout seconds; defaults to TOKENHUB_TIMEOUT_SECONDS or 1800",
    )
    return parser


def main() -> None:
    parser = _build_arg_parser()
    args = parser.parse_args()

    online_model = _env_flag("NOVEL_USE_ONLINE_MODEL", True) if args.online_model is None else bool(args.online_model)
    if online_model:
        tokenhub_api_key = os.getenv(args.tokenhub_api_key_env, "")
        tokenhub_base_url = args.tokenhub_base_url or os.getenv("TOKENHUB_BASE_URL", "https://tokenhub.tencentmaas.com/v1")
        tokenhub_timeout = args.tokenhub_timeout_seconds or _env_int("TOKENHUB_TIMEOUT_SECONDS", 1800)
        router = TokenHubModelRouter(
            base_url=tokenhub_base_url,
            api_key=tokenhub_api_key,
            timeout_seconds=tokenhub_timeout,
        )
        engine = TokenHubChatEngine(served_model_name=args.served_model_name, router=router)
    else:
        if not args.model_path:
            parser.error("--model-path is required in local model mode")
        upstream_api_key = args.upstream_api_key or os.getenv(args.upstream_api_key_env, "")
        upstream_client: Optional[UpstreamChatClient] = None
        upstream_tasks = _parse_csv_set(args.upstream_nonstream_tasks)
        if args.upstream_endpoint and upstream_api_key:
            upstream_client = UpstreamChatClient(
                endpoint=args.upstream_endpoint,
                api_key=upstream_api_key,
                model=args.upstream_model or None,
                timeout_seconds=args.upstream_timeout_seconds,
            )

        engine = LocalQwenChatEngine(
            model_path=args.model_path,
            served_model_name=args.served_model_name,
            device=args.device,
            dtype=args.dtype,
            adapter_path=args.adapter_path,
            text_nonfirst_adapter_path=args.text_nonfirst_adapter_path,
            merge_lora=args.merge_lora,
            max_new_tokens_default=args.max_new_tokens,
            trust_remote_code=args.trust_remote_code,
            upstream_client=upstream_client,
            upstream_nonstream_tasks=upstream_tasks,
        )
    app = create_app(
        engine=engine,
        include_done_marker=args.include_done_marker,
        novel_wiki_root=args.novel_wiki_root,
    )

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()





