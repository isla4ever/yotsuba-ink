"""
Build request-only JSONL for outline (分卷大纲) task.

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


OUTLINE_TASK_ALIASES = {
    "outline",
    "大纲",
    "分卷大纲",
    "总体大纲",
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

TITLE_PREFIX = ["雾港", "深巷", "星火", "长夜", "旧城", "寒川", "远岚", "青崖", "沉沙", "云陌"]
TITLE_MID = ["回声", "纪事", "迷局", "命题", "奇遇", "微光", "余烬", "归程", "旧案", "潮生"]
TITLE_SUFFIX = ["之旅", "手记", "档案", "风暴", "前夜", "重生", "长歌", "航线", "卷轴", "遗录"]

BACKGROUND_TEMPLATES = [
    "故事发生在新旧秩序交错的地域，旧案线索与现实冲突同步推进，人物在信任博弈与资源争夺中不断调整立场。",
    "在多方势力并行活动的世界中，主角组既要处理外部对抗，也要应对内部分歧，主线持续围绕真相、代价与抉择展开。",
    "剧情以连续事件推动分卷递进，每一卷都承担明确功能：铺垫信息、加压冲突、触发反转、形成阶段收束并预埋后续伏笔。",
]

INTRO_TEMPLATES = [
    "主角在突发事件后被迫回到故乡调查旧案，随着关键证据逐步出现，人物关系从合作转向博弈，最终在高压节点做出决定性选择。",
    "看似偶然的危机不断叠加，主角组在追查过程中遭遇误导、背叛与反转，经过多轮试错后完成阶段闭环并开启新的风险线。",
    "围绕一条核心目标，角色在连续对抗中暴露真实诉求，剧情通过多线交汇推动冲突升级，最终形成有代价的阶段性结果。",
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


def _clean_text(text: Any) -> str:
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
    if isinstance(value, dict):
        return [str(k).strip() for k in value.keys() if str(k).strip()]
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return []
        for parser in (ast.literal_eval, json.loads):
            try:
                obj = parser(s)
                if isinstance(obj, list):
                    return [str(x).strip() for x in obj if str(x).strip()]
                if isinstance(obj, dict):
                    return [str(k).strip() for k in obj.keys() if str(k).strip()]
            except Exception:
                pass
        parts = re.split(r"[,\uFF0C;\uFF1B/\|、]", s)
        return [p.strip() for p in parts if p.strip()]
    return [str(value).strip()]


def _normalize_task(value: Any) -> str:
    key = str(value or "").strip().lower()
    if key in {x.lower() for x in OUTLINE_TASK_ALIASES}:
        return "outline"
    return key


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


def _extract_markdown_section(text: str, label: str) -> str:
    pattern = rf"\*\*{re.escape(label)}\*\*\s*[:：]\s*([\s\S]*?)(?=\n\s*\*\*[^*]+\*\*\s*[:：]|\Z)"
    m = re.search(pattern, text, re.IGNORECASE)
    if not m:
        return ""
    return _clean_text(m.group(1))


def _parse_summary_assistant(text: str) -> Tuple[Dict[str, str], str]:
    raw = _clean_text(text)
    if not raw:
        return {}, ""
    for parser in (ast.literal_eval, json.loads):
        try:
            obj = parser(raw)
            break
        except Exception:
            obj = None
    if obj is None and "[" in raw and "]" in raw:
        try:
            obj = ast.literal_eval(raw[raw.find("[") : raw.rfind("]") + 1])
        except Exception:
            obj = None
    if not isinstance(obj, list) or not obj:
        return {}, ""
    first = obj[0] if isinstance(obj[0], dict) else {}
    if not isinstance(first, dict):
        return {}, ""

    char_map: Dict[str, str] = {}
    for key in ("主要人物和他们的行为", "主要人物", "人物信息", "人物"):
        value = first.get(key)
        if isinstance(value, dict):
            char_map = {str(k).strip(): _clean_text(v) for k, v in value.items() if str(k).strip()}
            if char_map:
                break
        if isinstance(value, list):
            char_map = {str(x).strip(): "围绕主线持续行动并推动冲突发展。" for x in value if str(x).strip()}
            if char_map:
                break

    intro = ""
    for key in ("内容", "故事情节", "故事", "梗概", "小说梗概"):
        value = first.get(key)
        if isinstance(value, str) and value.strip():
            intro = _clean_text(value)
            break
        if isinstance(value, dict):
            parts = [str(value.get(k, "")).strip() for k in ("开始", "发展", "高潮", "结局")]
            intro = _clean_text(" ".join([p for p in parts if p]))
            if intro:
                break
    return char_map, intro


def _normalize_char_map(value: Any) -> Dict[str, str]:
    if isinstance(value, dict):
        out = {str(k).strip(): _clean_text(v) for k, v in value.items() if str(k).strip()}
        if out:
            return out
    names = _to_list(value)
    if names:
        return {n: "围绕主线推进事件，持续执行关键行动并影响阶段走向。" for n in names if n}
    return {}


def _extract_candidates(records: Iterable[Dict[str, Any]], rng: random.Random) -> List[Tuple[str, Dict[str, str], str, str]]:
    out: List[Tuple[str, Dict[str, str], str, str]] = []
    seen = set()
    for rec in records:
        task = _normalize_task(_pick_value(rec, ("task", "task_type", "scene", "业务类型"), ""))
        title = _clean_text(_pick_value(rec, ("title", "novel_title", "小说标题"), ""))

        char_map: Dict[str, str] = {}
        background = ""
        intro = ""

        if task == "summary":
            char_map = _normalize_char_map(_pick_value(rec, ("characters", "人物", "人物信息"), {}))
            background = _clean_text(_pick_value(rec, ("background", "故事背景"), ""))
            intro = _clean_text(_pick_value(rec, ("intro", "简介", "情节简介"), ""))
            if not intro:
                summary_assistant = _pick_value(rec, ("assistant",), "")
                parsed_char, parsed_intro = _parse_summary_assistant(str(summary_assistant))
                if parsed_char and not char_map:
                    char_map = parsed_char
                if parsed_intro:
                    intro = parsed_intro
        elif task == "info_recommend":
            info_text = _clean_text(_pick_value(rec, ("assistant", "info_recommend_content"), ""))
            persons_raw = _extract_markdown_section(info_text, "人物信息")
            bg = _extract_markdown_section(info_text, "故事背景")
            it = _extract_markdown_section(info_text, "简介")
            char_map = _normalize_char_map(persons_raw)
            background = _clean_text(bg)
            intro = _clean_text(it)
        elif task == "outline":
            char_map = _normalize_char_map(_pick_value(rec, ("characters", "人物", "人物信息"), {}))
            background = _clean_text(_pick_value(rec, ("background", "故事背景"), ""))
            intro = _clean_text(_pick_value(rec, ("intro", "summary_content", "简介"), ""))

        if not title:
            continue
        if not char_map:
            fallback_names = [f"角色{idx + 1}" for idx in range(4)]
            char_map = {n: "围绕主线推进关键行动并在冲突阶段承担执行任务。" for n in fallback_names}
        if not background:
            background = rng.choice(BACKGROUND_TEMPLATES)
        if not intro:
            intro = rng.choice(INTRO_TEMPLATES)

        key = (title, tuple(char_map.keys()), background[:120], intro[:120])
        if key in seen:
            continue
        seen.add(key)
        out.append((title, char_map, background, intro))
    return out


def _build_synthetic_candidates(count: int, rng: random.Random) -> List[Tuple[str, Dict[str, str], str, str]]:
    out: List[Tuple[str, Dict[str, str], str, str]] = []
    seen = set()
    while len(out) < count:
        title = f"{rng.choice(TITLE_PREFIX)}{rng.choice(TITLE_MID)}{rng.choice(TITLE_SUFFIX)}"
        names = [rng.choice(["林晚舟", "沈言", "周砚川", "程以宁", "顾南乔", "宋临安", "陆无尘", "苏婉儿"]) for _ in range(6)]
        uniq_names = []
        for n in names:
            if n not in uniq_names:
                uniq_names.append(n)
            if len(uniq_names) >= 5:
                break
        char_map = {n: "围绕卷内目标持续行动，在冲突升级时做出关键选择并推动局势变化。" for n in uniq_names}
        background = rng.choice(BACKGROUND_TEMPLATES)
        intro = rng.choice(INTRO_TEMPLATES)
        key = (title, tuple(uniq_names), background, intro)
        if key in seen:
            continue
        seen.add(key)
        out.append((title, char_map, background, intro))
    return out


def _single_quote_literal(value: Any) -> str:
    if isinstance(value, str):
        s = value.replace("\\", "\\\\").replace("'", "\\'").replace("\r", "\\r").replace("\n", "\\n")
        return "'" + s + "'"
    if isinstance(value, bool):
        return "True" if value else "False"
    if value is None:
        return "None"
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_single_quote_literal(x) for x in value) + "]"
    if isinstance(value, dict):
        parts = [f"{_single_quote_literal(str(k))}: {_single_quote_literal(v)}" for k, v in value.items()]
        return "{" + ", ".join(parts) + "}"
    return _single_quote_literal(str(value))


def _build_prompt(title: str, char_map: Dict[str, str], background: str, intro: str, variant: int) -> str:
    person_literal = _single_quote_literal(char_map)
    if variant == 0:
        return (
            "\n            #### 角色：\n"
            "            你是一位才华横溢的小说作家助手，擅长将小说的主要人物、故事背景和简介转换为分卷大纲。\n"
            "            你的任务是根据提供的基本信息，生成多个详细的分卷梗概，供后续按卷拆章使用。\n\n"
            "            #### 输入：\n"
            "            1. **主要人物**：提供小说中的主要人物及其关键行为。\n"
            "            2. **故事背景**：提供小说的故事背景信息。\n"
            "            3. **简介**：提供小说的简短简介。\n\n"
            "            #### 输出（必须严格遵守）：\n"
            "            返回一个列表字符串，每个元素是一个JSON对象：\n"
            "            {'主要人物和他们的行为': {str:str,...}, '故事情节': {'开始':str, '发展':str, '高潮':str, '结局':str}}\n"
            "            要求：\n"
            "            - 默认输出3个分卷对象，最多4个；\n"
            "            - 每卷人物行为具体，不重复堆砌模板句；\n"
            "            - 每卷四段故事都要完整，能支撑后续拆章；\n"
            "            - 每个故事节点建议80-140字，总输出控制在1200-1600字。\n"
            "            - 不要输出代码块、不要输出额外解释。\n\n"
            f"            **小说标题**：\n            {title}\n\n"
            f"            **主要人物**：\n            {person_literal}\n\n"
            f"            **故事背景**：\n            {background}\n\n"
            f"            **简介**：\n            {intro}\n\n"
            "            请根据以上信息生成分卷大纲。\n"
        )
    if variant == 1:
        return (
            "\n            任务：生成分卷大纲（稳定结构版）。\n"
            "            仅允许输出如下结构的列表字符串：\n"
            "            [\n"
            "              {'主要人物和他们的行为': {...}, '故事情节': {'开始':..., '发展':..., '高潮':..., '结局':...}},\n"
            "              ...\n"
            "            ]\n"
            "            约束：\n"
            "            1) 输出3-4卷；2) 每卷人物行为不少于4人；3) 四段故事逻辑连贯且可拆章；4) 每个故事节点80-140字。\n\n"
            f"            小说标题：{title}\n"
            f"            主要人物：{person_literal}\n"
            f"            故事背景：{background}\n"
            f"            简介：{intro}\n"
        )
    return (
        "\n            你是网文总编，请生成高可用分卷大纲训练样本。\n"
        "            固定输出：\n"
        "            [{'主要人物和他们的行为': {...}, '故事情节': {'开始':str,'发展':str,'高潮':str,'结局':str}}, ...]\n"
        "            规则：默认3卷、最多4卷；每卷必须可独立拆成章节；分卷之间保持递进，不得重复；总输出1200-1600字。\n\n"
        f"            标题：{title}\n"
        f"            主要人物：{person_literal}\n"
        f"            背景：{background}\n"
        f"            简介：{intro}\n"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build request pool for outline task via upstream API")
    parser.add_argument("--input", type=str, nargs="+", required=True, help="Input structured JSONL files")
    parser.add_argument("--output", type=str, required=True, help="Output request-only JSONL")
    parser.add_argument("--target-count", type=int, default=1000, help="Total requests to generate")
    parser.add_argument("--synthetic-count", type=int, default=1000, help="Extra synthetic candidates")
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
        raise RuntimeError("No outline candidates found from input.")

    rng.shuffle(candidates)
    selected = candidates[: max(1, args.target_count)]

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        for i, (title, char_map, background, intro) in enumerate(selected):
            prompt = _build_prompt(title, char_map, background, intro, variant=i % 3)
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
                    "task": "outline",
                    "title": title,
                    "variant": i % 3,
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
