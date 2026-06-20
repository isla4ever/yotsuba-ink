"""
Build request-only JSONL for summary (梗概) task, for upstream teacher generation.

Output line format:
{"request": {"model": "...", "messages": [...], "stream": false, ...}, "meta": {...}}
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


SUMMARY_TASK_ALIASES = {
    "summary",
    "synopsis",
    "梗概",
    "分卷梗概",
    "小说梗概",
}

GENRES_POOL = [
    "现实小说",
    "青春文学",
    "现代言情",
    "悬疑推理",
    "武侠小说",
    "仙侠玄幻",
    "都市生活",
    "历史传奇",
]

TITLE_PREFIX = [
    "雾港",
    "深巷",
    "星火",
    "长夜",
    "旧城",
    "寒川",
    "远岚",
    "青崖",
]
TITLE_MID = [
    "回声",
    "纪事",
    "迷局",
    "命题",
    "奇遇",
    "微光",
    "余烬",
    "归程",
]
TITLE_SUFFIX = [
    "之旅",
    "手记",
    "档案",
    "风暴",
    "前夜",
    "重生",
    "长歌",
    "航线",
]

INTRO_TEMPLATES = [
    "{protagonist}在一次意外后被迫回到故乡，与家人重逢。随着旧事被重新揭开，{protagonist}在亲情、友情与现实压力之间反复抉择，逐步完成自我修复，并在关键转折中做出新的生活决定。",
    "{protagonist}卷入一场看似偶然却层层递进的事件，身边人各自行动，推动冲突持续升级。经历误解、分离与和解后，{protagonist}最终确认目标，与重要同伴一起迈向新的阶段。",
    "{protagonist}在成长道路上遭遇连续挫折，被迫面对过去留下的伤痕。家人和同伴的介入改变了局面，主线在调查、对抗与情感重建中推进，最终迎来阶段性新生。",
]


def _iter_jsonl(paths: Sequence[Path]) -> Iterable[Dict[str, Any]]:
    for path in paths:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    obj = json.loads(s)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict):
                    yield obj


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


def _normalize_task(raw: Any) -> str:
    if raw is None:
        return ""
    key = str(raw).strip().lower()
    if key in {x.lower() for x in SUMMARY_TASK_ALIASES}:
        return "summary"
    return ""


def _clean_text(text: str) -> str:
    s = str(text or "").replace("\r", "\n").strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


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
        for parser in (ast.literal_eval, json.loads):
            try:
                obj = parser(s)
                if isinstance(obj, list):
                    return [str(x).strip() for x in obj if str(x).strip()]
            except Exception:
                pass
        parts = re.split(r"[,\uFF0C;\uFF1B/\|、]", s)
        return [p.strip() for p in parts if p.strip()]
    return [str(value).strip()]


def _normalize_categories(value: Any) -> List[str]:
    out: List[str] = []
    seen = set()
    for item in _to_list(value):
        v = _clean_text(item)
        if not v or v in seen:
            continue
        if len(v) > 12:
            continue
        seen.add(v)
        out.append(v)
        if len(out) >= 3:
            break
    while len(out) < 3:
        candidate = random.choice(GENRES_POOL)
        if candidate in seen:
            continue
        seen.add(candidate)
        out.append(candidate)
    return out


def _extract_markdown_section(text: str, label: str) -> str:
    pattern = rf"\*\*{re.escape(label)}\*\*\s*[:：]\s*([\s\S]*?)(?=\n\s*\*\*[^*]+\*\*\s*[:：]|\Z)"
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return ""
    return _clean_text(m.group(1))


def _extract_info_blocks(info_text: str) -> Dict[str, str]:
    s = _clean_text(info_text)
    if not s:
        return {"characters": "", "background": "", "intro": ""}
    return {
        "characters": _extract_markdown_section(s, "人物信息"),
        "background": _extract_markdown_section(s, "故事背景"),
        "intro": _extract_markdown_section(s, "简介"),
    }


def _infer_protagonist(title: str, characters: str) -> str:
    m = re.search(r"([\u4e00-\u9fff]{2,4})的", title)
    if m:
        return m.group(1)
    names = re.findall(r"[\u4e00-\u9fff]{2,4}", characters)
    if names:
        return names[0]
    return "主角"


def _build_intro_fallback(title: str, characters: str, rng: random.Random) -> str:
    protagonist = _infer_protagonist(title, characters)
    template = rng.choice(INTRO_TEMPLATES)
    return template.format(protagonist=protagonist)


def _format_categories_literal(categories: Sequence[str]) -> str:
    escaped = [str(x).replace("\\", "\\\\").replace("'", "\\'") for x in categories]
    return "[" + ", ".join(f"'{x}'" for x in escaped) + "]"


def _build_prompt(title: str, categories: List[str], intro: str, variant: int) -> str:
    category_literal = _format_categories_literal(categories)
    if variant == 0:
        return (
            "\n                #### 角色:\n"
            "                你是一位才华横溢的小说作家助手，擅长将小说信息转换为详细的小说内容梗概。\n"
            "                请根据小说标题、分类和情节简介，输出稳定可解析的梗概结果。\n\n"
            "                #### 输入:\n"
            "                **小说标题**: 提供小说的标题。\n"
            "                **分类**: 提供小说的分类信息。\n"
            "                **情节简介**: 提供小说的情节简介。\n\n"
            "                #### 输出格式(必须严格一致):\n"
            "                返回一个列表字符串，列表仅包含1个对象，且对象只允许2个键：\n"
            "                1) '主要人物和他们的行为': {人物名: 主要行为, ...}\n"
            "                2) '内容': 完整梗概正文\n"
            "                注意：\n"
            "                - 人物名不要重复，不要出现小说标题作为人物名。\n"
            "                - 主要行为只描述人物做了什么，不要写“角色作用/功能定位”。\n"
            "                - '内容' 需要是完整连贯的一段梗概，不要拆成开始/发展/高潮/结局四段键值。\n"
            "                - 不要输出代码块，不要输出额外解释。\n\n"
            "                **小说标题**:\n"
            f"                {title}\n\n"
            "                **分类**:\n"
            f"                {category_literal}\n\n"
            "                **情节简介**:\n"
            f"                {intro}\n\n"
            "                请根据以上信息，生成详细的小说梗概。\n"
        )
    if variant == 1:
        return (
            "\n                任务：生成小说梗概（稳定结构版）。\n"
            "                你必须只返回一个列表字符串，结构如下：\n"
            "                [{'主要人物和他们的行为': {'人物A': '行为...', '人物B': '行为...'}, '内容': '完整梗概...'}]\n"
            "                输出限制：\n"
            "                1) 保持简体中文；2) 人物名称唯一；3) 内容逻辑自洽，避免重复句。\n\n"
            f"                小说标题：{title}\n"
            f"                分类：{category_literal}\n"
            f"                情节简介：{intro}\n"
        )
    return (
        "\n                你是网文策划编辑，请将“标题+分类+情节简介”扩展为可直接入库训练的梗概样本。\n"
        "                固定输出：\n"
        "                [{'主要人物和他们的行为': {...}, '内容': '...'}]\n"
        "                约束：人物行为要具体；内容段落要完整；不要输出多余文本。\n\n"
        f"                标题：{title}\n"
        f"                分类：{category_literal}\n"
        f"                情节简介：{intro}\n"
    )


def _extract_candidates(records: Iterable[Dict[str, Any]], rng: random.Random) -> List[Tuple[str, List[str], str]]:
    out: List[Tuple[str, List[str], str]] = []
    seen = set()
    for rec in records:
        task = _normalize_task(_pick_value(rec, ("task", "task_type", "scene", "业务类型")))
        title = _clean_text(str(_pick_value(rec, ("title", "novel_title", "小说标题"), "")))
        categories = _normalize_categories(_pick_value(rec, ("categories", "tags", "分类"), []))

        if task != "summary":
            if not title:
                continue

        info_content = _pick_value(rec, ("info_recommend_content", "小说信息推荐", "info_content"), "")
        info_blocks = _extract_info_blocks(str(info_content))
        intro = _clean_text(
            str(
                _pick_value(
                    rec,
                    ("intro", "introduction", "summary_intro", "情节简介", "简介"),
                    "",
                )
            )
        )
        if not intro:
            intro = _clean_text(info_blocks.get("intro", ""))
        if not intro:
            background = _clean_text(info_blocks.get("background", ""))
            intro = background
        if not intro:
            intro = _build_intro_fallback(title, info_blocks.get("characters", ""), rng)

        key = (title, tuple(categories), intro)
        if key in seen:
            continue
        seen.add(key)
        out.append((title, categories, intro))
    return out


def _build_synthetic_candidates(count: int, rng: random.Random) -> List[Tuple[str, List[str], str]]:
    out: List[Tuple[str, List[str], str]] = []
    seen = set()
    attempts = 0
    max_attempts = max(1000, count * 10)
    while len(out) < count and attempts < max_attempts:
        attempts += 1
        title = f"{rng.choice(TITLE_PREFIX)}{rng.choice(TITLE_MID)}{rng.choice(TITLE_SUFFIX)}"
        categories = rng.sample(GENRES_POOL, k=3)
        intro = _build_intro_fallback(title, "", rng)
        key = (title, tuple(categories), intro)
        if key in seen:
            continue
        seen.add(key)
        out.append((title, categories, intro))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build request pool for summary task via upstream API")
    parser.add_argument("--input", type=str, nargs="+", required=True, help="Input structured JSONL files")
    parser.add_argument("--output", type=str, required=True, help="Output request-only JSONL")
    parser.add_argument("--target-count", type=int, default=1200, help="Total requests to generate")
    parser.add_argument("--synthetic-count", type=int, default=1200, help="Extra synthetic candidates")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--model", type=str, default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--temperature", type=float, default=0.72)
    parser.add_argument("--top-p", type=float, default=0.88)
    parser.add_argument("--max-tokens", type=int, default=980)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    input_paths = [Path(x) for x in args.input]
    for p in input_paths:
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")

    candidates = _extract_candidates(_iter_jsonl(input_paths), rng)
    if args.synthetic_count > 0:
        candidates.extend(_build_synthetic_candidates(args.synthetic_count, rng))
    if not candidates:
        raise RuntimeError("No summary candidates found from input.")

    rng.shuffle(candidates)
    selected = candidates[: max(1, args.target_count)]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i, (title, categories, intro) in enumerate(selected):
            prompt = _build_prompt(title, categories, intro, variant=i % 3)
            req = {
                "model": args.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "max_tokens": args.max_tokens,
            }
            line = {
                "request": req,
                "meta": {
                    "task": "summary",
                    "title": title,
                    "categories": categories,
                    "variant": i % 3,
                },
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            written += 1

    print(f"candidates={len(candidates)}")
    print(f"written={written}")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()

