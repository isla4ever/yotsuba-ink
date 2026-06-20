"""
Build high-quality request-only JSONL for the info_recommend task.

Output format (one line per request):
{"request": {"model": "...", "messages": [...], "stream": false, ...}, "meta": {...}}
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


INFO_TASK_ALIASES = {
    "info_recommend",
    "info",
    "novel_info",
    "info-recommend",
    "information_recommend",
    "信息推荐",
    "小说信息推荐",
}

DEFAULT_TAGS = [
    "现代言情",
    "青春文学",
    "现实小说",
    "悬疑推理",
    "都市生活",
    "武侠小说",
    "仙侠玄幻",
    "历史传奇",
]

SYNTH_TITLE_PREFIX = [
    "雾城",
    "长夜",
    "风雪",
    "春潮",
    "镜海",
    "纸月",
    "星火",
    "归途",
    "白昼",
    "深巷",
    "旧港",
    "云岭",
    "寒汐",
    "青岚",
    "赤砂",
]

SYNTH_TITLE_MID = [
    "迷局",
    "余烬",
    "回声",
    "纪事",
    "密语",
    "长歌",
    "折光",
    "断章",
    "航线",
    "潮生",
    "试炼",
    "边界",
    "重影",
    "誓约",
    "星图",
]

SYNTH_TITLE_SUFFIX = [
    "之旅",
    "奇遇",
    "计划",
    "手记",
    "档案",
    "前夜",
    "纪年",
    "风暴",
    "命题",
    "余波",
    "孤岛",
    "彼岸",
    "回廊",
    "归档",
    "重生录",
]


def _iter_jsonl(paths: Sequence[Path]) -> Iterable[Dict]:
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


def _normalize_task(raw) -> str:
    if raw is None:
        return ""
    key = str(raw).strip().lower()
    if key in {x.lower() for x in INFO_TASK_ALIASES}:
        return "info_recommend"
    return ""


def _candidate_sources(record: Dict) -> List[Dict]:
    out = [record]
    for key in ("input", "fields", "data", "payload", "task_input"):
        value = record.get(key)
        if isinstance(value, dict):
            out.append(value)
    return out


def _pick_value(record: Dict, keys: Sequence[str], default=None):
    for src in _candidate_sources(record):
        for key in keys:
            if key in src and src[key] not in (None, ""):
                return src[key]
    return default


def _clean_text(text: str) -> str:
    s = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    s = re.sub(r"\s+", " ", s)
    return s


def _to_list(value) -> List[str]:
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
        except json.JSONDecodeError:
            pass
        parts = re.split(r"[,\uFF0C;/\|]", s)
        return [p.strip() for p in parts if p.strip()]
    return [str(value).strip()]


def _normalize_categories(raw) -> List[str]:
    tags = _to_list(raw)
    out: List[str] = []
    seen = set()
    for t in tags:
        x = _clean_text(t)
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    if len(out) < 3:
        for t in DEFAULT_TAGS:
            if t in seen:
                continue
            out.append(t)
            seen.add(t)
            if len(out) >= 3:
                break
    return out[:3]


def _format_categories_literal(categories: Sequence[str]) -> str:
    escaped = [c.replace("\\", "\\\\").replace("'", "\\'") for c in categories]
    return "[" + ", ".join(f"'{x}'" for x in escaped) + "]"


def _extract_candidates(records: Iterable[Dict]) -> List[Tuple[str, List[str]]]:
    out: List[Tuple[str, List[str]]] = []
    seen = set()
    for rec in records:
        task = _normalize_task(_pick_value(rec, ("task", "task_type", "scene", "业务类型")))
        title = _pick_value(rec, ("title", "novel_title", "小说标题"))
        categories = _pick_value(rec, ("categories", "tags", "分类"))
        if task != "info_recommend":
            # Accept title+categories records as fallback.
            if not title or categories in (None, ""):
                continue
        title_text = _clean_text(str(title or ""))
        if not title_text:
            continue
        cats = _normalize_categories(categories)
        if len(cats) < 2:
            continue
        key = (title_text, tuple(cats))
        if key in seen:
            continue
        seen.add(key)
        out.append((title_text, cats))
    return out


def _build_synthetic_candidates(count: int, rng: random.Random) -> List[Tuple[str, List[str]]]:
    out: List[Tuple[str, List[str]]] = []
    seen = set()
    max_attempts = max(1000, count * 10)
    attempts = 0
    while len(out) < count and attempts < max_attempts:
        attempts += 1
        title = f"{rng.choice(SYNTH_TITLE_PREFIX)}{rng.choice(SYNTH_TITLE_MID)}{rng.choice(SYNTH_TITLE_SUFFIX)}"
        cats = rng.sample(DEFAULT_TAGS, k=3)
        key = (title, tuple(cats))
        if key in seen:
            continue
        seen.add(key)
        out.append((title, cats))
    return out


def _build_prompt(title: str, categories: List[str], variant_id: int) -> str:
    cat_literal = _format_categories_literal(categories)
    common_tail = (
        "\n    **小说标题**:\n"
        f"    {title}\n\n"
        "    **分类**:\n"
        f"    {cat_literal}\n\n"
        "    请根据以上信息，生成详细的小说信息。\n"
    )

    if variant_id == 0:
        return (
            "\n    #### 角色:\n"
            "    你是一位才华横溢的小说作家助手，擅长将小说基本信息转换为详细的小说描述。"
            "你的任务是根据提供的小说标题和分类，生成详细的小说信息，包括人物信息、故事背景和简介。"
            "请确保内容准确、连贯、具有吸引力，并使用简体中文。\n\n"
            "    #### 输入:\n"
            "    **小说标题**: 提供小说的标题。\n"
            "    **分类**: 提供小说的分类信息。\n\n"
            "    #### 输出:\n"
            "    请严格输出以下三个部分，不要增加额外标题或解释：\n"
            "    **人物信息**:\n"
            "    ['角色A', '角色B', '角色C', '角色D', '角色E']\n"
            "    **故事背景**:\n"
            "    一段完整描述（120-220字）。\n"
            "    **简介**:\n"
            "    一段完整摘要（220-420字），包含冲突、推进和阶段性结果。\n"
            "    人物信息需 5-8 人，人物名称不得重复。\n"
            "    最后一行追加 `<|im_end|>`。\n"
            + common_tail
        )

    if variant_id == 1:
        return (
            "\n    #### 角色:\n"
            "    你是资深网文策划编辑。请根据给定的标题和分类，产出可直接用于立项的小说信息推荐稿。"
            "用词自然，风格统一，避免空泛描述，使用简体中文。\n\n"
            "    #### 输出规范:\n"
            "    1) **人物信息**: 使用 Python 列表字符串形式，列出 5-8 个主要人物名称。\n"
            "    2) **故事背景**: 聚焦时代环境、地点格局、核心矛盾，不少于 120 字。\n"
            "    3) **简介**: 概述主要剧情线与关键转折，不少于 240 字。\n"
            "    4) 不得输出 JSON，不得输出多余说明，不得出现乱码。\n"
            "    5) 末尾必须包含 `<|im_end|>`。\n"
            + common_tail
        )

    return (
        "\n    #### 角色:\n"
        "    你是一位商业化小说研发顾问，负责生成高完成度的“小说信息推荐”内容。"
        "请结合标题与分类，写出可读性强、细节充足、逻辑自洽的结果，使用简体中文。\n\n"
        "    #### 强约束格式:\n"
        "    **人物信息**:\n"
        "    ['角色1', '角色2', '角色3', '角色4', '角色5']\n\n"
        "    **故事背景**:\n"
        "    描述故事发生的时空、社会环境、核心冲突与风险来源。\n\n"
        "    **简介**:\n"
        "    按“开端-发展-转折-阶段性结果”写成连贯段落，突出剧情驱动力与人物关系变化。\n\n"
        "    其他要求：\n"
        "    - 人物姓名唯一，避免重复。\n"
        "    - 背景与简介内容不能相互矛盾。\n"
        "    - 输出结束时添加 `<|im_end|>`。\n"
        + common_tail
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build request pool for info_recommend via upstream API")
    parser.add_argument("--input", type=str, nargs="+", required=True, help="Input structured JSONL files")
    parser.add_argument("--output", type=str, required=True, help="Output request-only JSONL")
    parser.add_argument("--target-count", type=int, default=1200, help="Total requests to generate")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--model", type=str, default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--temperature", type=float, default=0.75)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--synthetic-count", type=int, default=1200, help="Extra synthetic title/tag candidates")
    args = parser.parse_args()

    input_paths = [Path(x) for x in args.input]
    for p in input_paths:
        if not p.exists():
            raise FileNotFoundError(f"Input file not found: {p}")

    rng = random.Random(args.seed)
    candidates = _extract_candidates(_iter_jsonl(input_paths))
    if not candidates:
        raise RuntimeError("No title/category candidates found from input.")
    if args.synthetic_count > 0:
        candidates.extend(_build_synthetic_candidates(args.synthetic_count, rng))

    # Keep first occurrence order after merge.
    deduped: List[Tuple[str, List[str]]] = []
    seen = set()
    for title, cats in candidates:
        key = (title, tuple(cats))
        if key in seen:
            continue
        seen.add(key)
        deduped.append((title, cats))
    candidates = deduped

    # Shuffle once for diversity, then cycle with prompt variants to reach target-count.
    rng.shuffle(candidates)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    generated = 0
    cursor = 0
    variant = 0
    with out_path.open("w", encoding="utf-8") as f:
        while generated < max(1, args.target_count):
            title, categories = candidates[cursor]
            prompt = _build_prompt(title, categories, variant_id=variant % 3)
            req = {
                "model": args.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "max_tokens": args.max_tokens,
            }
            row = {
                "request": req,
                "meta": {
                    "task": "info_recommend",
                    "title": title,
                    "categories": categories,
                    "variant_id": variant % 3,
                },
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            generated += 1

            cursor += 1
            if cursor >= len(candidates):
                cursor = 0
                rng.shuffle(candidates)
            variant += 1

    print(f"input_candidates={len(candidates)}")
    print(f"generated_requests={generated}")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()
