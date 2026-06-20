"""
Build request-only JSONL for detail-outline (章节细纲) task.

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


DETAIL_TASK_ALIASES = {
    "detail_outline",
    "detailed_outline",
    "细纲",
    "章节细纲",
}

TITLE_PREFIX = ["冬港", "星屿", "雨巷", "长夜", "荒潮", "回廊", "旧城", "青岚", "临川", "镜海"]
TITLE_MID = ["归航", "微光", "迷局", "奇遇", "残响", "潮生", "回声", "重启", "裂变", "回响"]
TITLE_SUFFIX = ["之旅", "档案", "手记", "风暴", "长歌", "纪事", "余烬", "行录", "夜话", "谜录"]


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


def _clean_text(text: Any) -> str:
    s = str(text or "").replace("\r", "\n").strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    s = re.sub(r"[ \t]+", " ", s)
    return s.strip()


def _normalize_task(value: Any) -> str:
    key = str(value or "").strip().lower()
    if key in DETAIL_TASK_ALIASES:
        return "detail_outline"
    if key in {"outline", "summary", "info_recommend"}:
        return key
    return ""


def _pick_value(record: Dict[str, Any], keys: Sequence[str], default: Any = None) -> Any:
    sources = [record]
    for k in ("input", "fields", "data", "payload", "task_input"):
        v = record.get(k)
        if isinstance(v, dict):
            sources.append(v)
    for src in sources:
        for key in keys:
            if key in src and src[key] not in (None, ""):
                return src[key]
    return default


def _parse_literal(text: str) -> Any:
    s = _clean_text(text)
    if not s:
        return None
    for parser in (ast.literal_eval, json.loads):
        try:
            return parser(s)
        except Exception:
            pass
    return None


def _normalize_char_map(value: Any) -> Dict[str, str]:
    if isinstance(value, dict):
        out = {str(k).strip(): _clean_text(v) for k, v in value.items() if str(k).strip()}
        if out:
            return out
    if isinstance(value, list):
        out = {str(x).strip(): "围绕本卷冲突推进关键行动。" for x in value if str(x).strip()}
        if out:
            return out
    if isinstance(value, str):
        parsed = _parse_literal(value)
        if parsed is not None and parsed is not value:
            out = _normalize_char_map(parsed)
            if out:
                return out
        names = [x.strip() for x in re.split(r"[,，;；/|\s]+", value) if x.strip()]
        if names:
            return {n: "围绕本卷冲突推进关键行动。" for n in names[:8]}
    return {}


def _extract_outline_chars_and_summary(text: str) -> Tuple[Dict[str, str], str]:
    obj = _parse_literal(text)
    if not isinstance(obj, list) or not obj:
        return {}, ""
    first = obj[0] if isinstance(obj[0], dict) else {}
    if not isinstance(first, dict):
        return {}, ""
    char_map = _normalize_char_map(
        first.get("主要人物和他们的行为")
        or first.get("主要人物")
        or first.get("人物信息")
        or first.get("characters")
    )
    story = first.get("故事情节") or first.get("故事") or first.get("内容") or first.get("story")
    summary = ""
    if isinstance(story, dict):
        parts = [str(story.get(k, "")).strip() for k in ("开始", "发展", "高潮", "结局")]
        summary = _clean_text(" ".join([p for p in parts if p]))
    elif isinstance(story, str):
        summary = _clean_text(story)
    return char_map, summary


def _extract_summary_chars_and_content(text: str) -> Tuple[Dict[str, str], str]:
    obj = _parse_literal(text)
    if not isinstance(obj, list) or not obj:
        return {}, ""
    first = obj[0] if isinstance(obj[0], dict) else {}
    if not isinstance(first, dict):
        return {}, ""
    char_map = _normalize_char_map(
        first.get("主要人物和他们的行为")
        or first.get("主要人物")
        or first.get("人物信息")
        or first.get("characters")
    )
    content = _clean_text(
        first.get("内容")
        or first.get("故事")
        or first.get("小说梗概")
        or first.get("summary")
        or ""
    )
    return char_map, content


def _synth_char_map(rng: random.Random) -> Dict[str, str]:
    names_pool = ["林晚舟", "沈言", "周砚川", "程以宁", "顾南乔", "宋临安", "陆无尘", "苏婉儿", "秦明月", "叶轻舟"]
    rng.shuffle(names_pool)
    picked = names_pool[: rng.randint(4, 7)]
    return {n: "围绕本卷主线推进调查、协作与对抗，并在关键节点做出可追踪的决策。" for n in picked}


def _synth_title(rng: random.Random) -> str:
    return f"{rng.choice(TITLE_PREFIX)}{rng.choice(TITLE_MID)}{rng.choice(TITLE_SUFFIX)}"


def _extract_candidates(records: Iterable[Dict[str, Any]], rng: random.Random) -> List[Tuple[str, Dict[str, str], str, str, int]]:
    out: List[Tuple[str, Dict[str, str], str, str, int]] = []
    seen = set()
    for rec in records:
        task = _normalize_task(_pick_value(rec, ("task", "task_type", "scene", "业务类型"), ""))
        if task not in {"detail_outline", "outline", "summary"}:
            continue

        title = _clean_text(_pick_value(rec, ("title", "novel_title", "小说标题"), ""))
        char_map: Dict[str, str] = {}
        volume_summary = ""
        novel_intro = ""
        chapter_count = 0

        if task == "detail_outline":
            char_map = _normalize_char_map(_pick_value(rec, ("characters", "人物信息", "人物"), {}))
            volume_summary = _clean_text(_pick_value(rec, ("partial_summary", "summary_content", "本卷梗概", "梗概"), ""))
            novel_intro = _clean_text(_pick_value(rec, ("intro", "introduction", "小说简介", "简介", "background"), ""))
            chapter_count = int(_pick_value(rec, ("chapter_count", "章节数", "count"), 0) or 0)
            if not novel_intro:
                novel_intro = volume_summary
        elif task == "outline":
            char_map, volume_summary = _extract_outline_chars_and_summary(str(_pick_value(rec, ("assistant",), "")))
            novel_intro = _clean_text(_pick_value(rec, ("intro", "introduction", "简介", "background"), ""))
            if not novel_intro:
                novel_intro = volume_summary
            chapter_count = rng.randint(3, 6)
        elif task == "summary":
            char_map, volume_summary = _extract_summary_chars_and_content(str(_pick_value(rec, ("assistant",), "")))
            novel_intro = _clean_text(_pick_value(rec, ("intro", "introduction", "简介", "background"), ""))
            if not novel_intro:
                novel_intro = volume_summary
            chapter_count = rng.randint(3, 6)

        if not title:
            title = _synth_title(rng)
        if not char_map:
            char_map = _synth_char_map(rng)
        if not volume_summary:
            volume_summary = (
                "本卷以人物关系重组和目标升级为主线，围绕线索核验、利益对抗与情感拉扯推进事件，"
                "并在章节末尾持续预埋新的冲突入口。"
            )
        if not novel_intro:
            novel_intro = (
                f"《{title}》讲述主角与同伴在多方博弈中逐步接近真相的过程，"
                "剧情强调行动后果、关系变化与阶段性决策。"
            )
        if chapter_count <= 0:
            chapter_count = rng.randint(3, 6)
        chapter_count = max(2, min(12, chapter_count))

        key = (title, tuple(char_map.keys()), volume_summary[:160], novel_intro[:160], chapter_count)
        if key in seen:
            continue
        seen.add(key)
        out.append((title, char_map, volume_summary, novel_intro, chapter_count))
    return out


def _build_synthetic_candidates(count: int, rng: random.Random) -> List[Tuple[str, Dict[str, str], str, str, int]]:
    out: List[Tuple[str, Dict[str, str], str, str, int]] = []
    seen = set()
    while len(out) < count:
        title = _synth_title(rng)
        char_map = _synth_char_map(rng)
        volume_summary = (
            "本卷围绕关键线索的首次闭环展开，角色在协作与分歧中推动调查，"
            "随着外部压力增加，冲突从信息差升级到策略对抗，并在卷末形成新的风险入口。"
        )
        novel_intro = (
            f"《{title}》聚焦角色群像在连续事件中的成长与抉择，"
            "强调因果推进、人物关系变化以及阶段性胜负后的连锁代价。"
        )
        chapter_count = rng.randint(3, 8)
        key = (title, tuple(char_map.keys()), chapter_count)
        if key in seen:
            continue
        seen.add(key)
        out.append((title, char_map, volume_summary, novel_intro, chapter_count))
    return out


def _single_quote_literal(value: Any) -> str:
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
        return "[" + ", ".join(_single_quote_literal(x) for x in value) + "]"
    if isinstance(value, dict):
        return "{" + ", ".join(f"{_single_quote_literal(str(k))}: {_single_quote_literal(v)}" for k, v in value.items()) + "}"
    return _single_quote_literal(str(value))


def _build_prompt(
    title: str,
    char_map: Dict[str, str],
    volume_summary: str,
    novel_intro: str,
    chapter_count: int,
    variant: int,
) -> str:
    char_literal = _single_quote_literal(char_map)
    if variant == 0:
        return (
            "\n#### 角色：\n"
            "你是一位资深小说章节策划助手。请把给定分卷梗概细化为可直接写作的章节细纲。\n\n"
            "#### 输入：\n"
            "1. 人物信息：本卷涉及人物及其主要行为。\n"
            "2. 小说部分内容的梗概：本卷主线、冲突与阶段目标。\n"
            "3. 小说简介：全书主线与长期主题。\n"
            "4. 章节划分：本卷需要拆分的章节数量。\n\n"
            "#### 输出格式（必须严格遵守）：\n"
            "仅输出一个列表字符串，列表每项为：\n"
            "{'章节标题': str, '细纲内容': str}\n"
            f"共输出 {chapter_count} 项，按列表顺序表示章节先后。\n"
            "约束：\n"
            "- 每章必须给出“章节标题”。\n"
            "- 每章“细纲内容”需覆盖：主要事件、场景描述、对话要点、人物情感变化。\n"
            "- 每章细纲内容建议不少于 320 字。\n"
            "- 不要输出代码块，不要输出额外解释。\n\n"
            f"**小说标题**：\n{title}\n\n"
            f"**人物信息**：\n{char_literal}\n\n"
            f"**小说部分内容的梗概**：\n{volume_summary}\n\n"
            f"**小说简介**：\n{novel_intro}\n\n"
            f"**章节划分**：\n一共 {chapter_count} 章\n"
        )
    if variant == 1:
        return (
            "\n任务：生成章节细纲（稳定结构版）。\n"
            "只允许输出以下结构列表：\n"
            "[\n"
            "  {'章节标题': '...', '细纲内容': '...'},\n"
            "  ...\n"
            "]\n"
            "规则：\n"
            f"1) 输出固定 {chapter_count} 章；2) 每章有标题；3) 细纲内容详细可拆写；4) 章节先后仅靠列表顺序。\n\n"
            f"小说标题：{title}\n"
            f"人物信息：{char_literal}\n"
            f"本卷梗概：{volume_summary}\n"
            f"小说简介：{novel_intro}\n"
            f"章节数：{chapter_count}\n"
        )
    return (
        "\n你是长篇网文分章总策划。请把当前分卷内容拆成章节细纲。\n"
        "固定输出：\n"
        "[{'章节标题': str, '细纲内容': str}, ...]\n"
        f"共 {chapter_count} 章，按列表顺序递进。\n"
        "每章内容需同时包含：场景、事件、对话、情感、章末钩子。\n\n"
        f"标题：{title}\n"
        f"人物：{char_literal}\n"
        f"分卷梗概：{volume_summary}\n"
        f"小说简介：{novel_intro}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build request pool for detail-outline task via upstream API")
    parser.add_argument("--input", type=str, nargs="+", required=True, help="Input structured JSONL files")
    parser.add_argument("--output", type=str, required=True, help="Output request-only JSONL")
    parser.add_argument("--target-count", type=int, default=1000, help="Total requests to generate")
    parser.add_argument("--synthetic-count", type=int, default=1200, help="Extra synthetic candidates")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--model", type=str, default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--temperature", type=float, default=0.72)
    parser.add_argument("--top-p", type=float, default=0.88)
    parser.add_argument("--max-tokens", type=int, default=2600)
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
        raise RuntimeError("No detail-outline candidates found from input.")

    rng.shuffle(candidates)
    selected = candidates[: max(1, args.target_count)]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i, (title, char_map, volume_summary, novel_intro, chapter_count) in enumerate(selected):
            prompt = _build_prompt(title, char_map, volume_summary, novel_intro, chapter_count, variant=i % 3)
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
                    "task": "detail_outline",
                    "title": title,
                    "variant": i % 3,
                    "chapter_count": chapter_count,
                    "character_count": len(char_map),
                },
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            written += 1

    print(f"candidates={len(candidates)}")
    print(f"written={written}")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()
