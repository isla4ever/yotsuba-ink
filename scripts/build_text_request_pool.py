"""
Build request-only JSONL for text generation tasks:
1) text_first_chapter
2) text_non_first_chapter

Output line format:
{"request": {...}, "meta": {...}}
"""

from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple


_TITLE_PREFIX = ["霜城", "星屿", "长夜", "潮生", "回廊", "旧港", "临川", "青岚", "雾海", "赤砂"]
_TITLE_MID = ["迷局", "微光", "归航", "裂变", "余烬", "暗河", "长歌", "回响", "远汐", "折光"]
_TITLE_SUFFIX = ["纪事", "之旅", "手记", "风暴", "档案", "谜录", "行录", "夜话", "图谱", "长卷"]

_CATEGORY_POOL = [
    ["现实小说", "青春文学"],
    ["现代言情", "现实小说", "青春文学"],
    ["悬疑推理", "现实小说"],
    ["仙侠玄幻", "武侠小说"],
    ["科幻未来", "悬疑推理"],
    ["都市职场", "现实小说"],
]

_NAME_POOL = [
    "林晚舟",
    "沈青禾",
    "周砚川",
    "程以宁",
    "顾南乔",
    "宋临安",
    "叶轻舟",
    "苏婉儿",
    "秦明月",
    "陆无尘",
]

_NAME_STOPWORDS = {
    "小说",
    "章节",
    "细纲",
    "场景",
    "事件",
    "对话",
    "情感",
    "发展",
    "开始",
    "结局",
    "目录",
    "阶段推进",
    "上一章",
    "当前章",
    "本卷梗概",
    "诗曰",
}

_COMMON_SURNAMES = set(
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平黄和穆萧尹姚邵湛汪祁毛禹狄米贝明计成戴宋庞熊纪舒屈项祝董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林钟徐邱骆高夏蔡田樊胡凌霍虞万支柯昝卢莫经房裘缪丁贲邓郁崔龚嵇邢裴陆荣翁荀羊惠甄曲家封储靳焦牧山侯伊宁仇栾甘武符刘景詹龙叶司宫宁白乔黎蒋卓傅莫赖涂辛欧阳司马上官夏侯诸葛闻人东方尉迟公孙慕容"
)

_DIRTY_CONTEXT_PATTERNS = [
    re.compile(r"[「」『』]"),
    re.compile(r"第[\u4e00-\u9fff0-9]+回"),
    re.compile(r"(补红楼梦|晴雯姐|林黛玉|薛宝钗|贾母|宝玉|蘅芜院|怡红院|嫏嬛)"),
    re.compile(r"(总兵|庄丁|赛儿|韩爷|邓九公|舅母|太太|公公|老爷|乡试|乩盘|衙门)"),
    re.compile(r"(蜕不得壳|肋，按天上二十四气|二万五千人|一万人马|谢三儿的窝窝)"),
    re.compile(r"(京门子|东投亲|方才听得老爷|死老子骨肉未寒|邓九公又把围著京门子)"),
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
                except Exception:
                    continue
                if isinstance(obj, dict):
                    yield obj


def _clean_text(text: Any) -> str:
    s = str(text or "").replace("\r", "\n").strip()
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def _truncate(text: str, n: int) -> str:
    s = _clean_text(text)
    if len(s) <= n:
        return s
    return s[:n].rstrip()


def _tail_slice(text: str, n: int) -> str:
    s = _clean_text(text)
    if len(s) <= n:
        return s
    return s[-n:].lstrip()


def _split_sentences(text: str) -> List[str]:
    s = _clean_text(text)
    if not s:
        return []
    parts = re.split(r"(?<=[。！？!?；;])\s*", s)
    out: List[str] = []
    for part in parts:
        p = part.strip()
        if len(p) >= 8:
            out.append(p)
    return out


def _clean_previous_context(text: Any) -> str:
    s = _clean_text(text)
    if not s:
        return ""
    s = re.sub(r"目录\s*", "", s)
    s = re.sub(r"第[\u4e00-\u9fff0-9]+[章节回卷段]\s*", "", s)
    s = re.sub(r"卷[\u4e00-\u9fff0-9]+\s*", "", s)
    s = re.sub(r"第\d+页[–-]第\d+页", "", s)
    s = re.sub(r"诗曰[:：]?", "", s)
    s = re.sub(r"[A-Za-z0-9]+回本", "", s)
    s = re.sub(r"\s{2,}", " ", s)
    return s.strip(" ：:，,。")


def _outline_focus_text(outline: str) -> str:
    s = _clean_text(outline)
    if not s:
        return ""
    s = re.sub(r"第\d+章[:：]?", "", s)
    s = re.sub(r"-\s*(场景|事件|对话要点|情感变化)\s*[:：]", "", s)
    s = s.replace("|||", " ")
    s = re.sub(r"\s+", " ", s)
    return _truncate(s, 120)


def _build_previous_bridge(previous_tail: str, chapter_outline: str) -> str:
    prev_sents = _split_sentences(previous_tail)
    outline_focus = _outline_focus_text(chapter_outline)
    carry = prev_sents[-2:] if prev_sents else []
    if outline_focus:
        carry.append(f"当前章需要承接并推进：{_truncate(outline_focus, 48)}")
    if not carry:
        carry = [
            "上一章刚形成新的行动压力，人物之间的信任与目标尚未稳定。",
            "当前章需要在承接既有情绪和局势的基础上，继续推进冲突与决策。",
        ]
    text = " ".join(carry)
    return _truncate(text, 140)


def _has_repeated_span(text: str) -> bool:
    s = _clean_text(text)
    if len(s) < 40:
        return False
    for size in (10, 12, 16):
        seen = set()
        for i in range(0, max(0, len(s) - size + 1), max(1, size // 2)):
            span = s[i : i + size]
            if len(set(span)) <= 2:
                continue
            if span in seen:
                return True
            seen.add(span)
    return False


def _is_dirty_context(text: str) -> bool:
    s = _clean_text(text)
    if not s:
        return False
    if any(p.search(s) for p in _DIRTY_CONTEXT_PATTERNS):
        return True
    if _has_repeated_span(s):
        return True
    if sum(s.count(ch) for ch in ("「", "」", "『", "』")) >= 2:
        return True
    return False


def _extract_names(text: str, limit: int = 6) -> List[str]:
    out: List[str] = []
    for tok in re.findall(r"[\u4e00-\u9fff]{2,4}", text):
        if tok in out:
            continue
        if tok in _NAME_STOPWORDS:
            continue
        if any(bad in tok for bad in ("阶段", "推进", "目录", "场景", "事件", "情感", "对话", "梗概", "当前章", "上一章", "第", "卷", "回", "诗")):
            continue
        if len(tok) < 2 or len(tok) > 3:
            continue
        out.append(tok)
        if len(out) >= limit:
            break
    return out


def _looks_like_person_name(text: str) -> bool:
    s = _clean_text(text)
    if not re.fullmatch(r"[\u4e00-\u9fff]{2,3}", s):
        return False
    if s in _NAME_STOPWORDS:
        return False
    if any(bad in s for bad in ("阶段", "推进", "场景", "事件", "情感", "目录", "梗概", "当前", "上一", "诗")):
        return False
    if s[:2] in {"欧阳", "司马", "上官", "夏侯", "诸葛", "闻人", "东方", "尉迟", "公孙", "慕容"}:
        return True
    return s[0] in _COMMON_SURNAMES


def _synth_title(rng: random.Random) -> str:
    return f"{rng.choice(_TITLE_PREFIX)}{rng.choice(_TITLE_MID)}{rng.choice(_TITLE_SUFFIX)}"


def _build_char_map(names: List[str], rng: random.Random) -> Dict[str, str]:
    if len(names) < 4:
        pool = _NAME_POOL[:]
        rng.shuffle(pool)
        for n in pool:
            if n not in names:
                names.append(n)
            if len(names) >= 6:
                break
    names = names[:6]
    actions = [
        "围绕主线持续调查关键线索，并在关键节点做出决策。",
        "协调团队分工与资源调度，在冲突升级时稳定行动节奏。",
        "在信息不完整条件下推进验证与试探，促成阶段突破。",
        "在关系拉扯中反复取舍，推动事件进入下一阶段。",
        "承担风险处置任务，处理突发问题并回收后果。",
    ]
    out: Dict[str, str] = {}
    for i, n in enumerate(names):
        out[n] = actions[i % len(actions)]
    return out


def _synth_intro(title: str, categories: Sequence[str]) -> str:
    cats = "、".join(categories[:3])
    return (
        f"《{title}》是一部以{cats}为主要风格的长篇网文，"
        "通过多线叙事展现角色在压力环境下的选择与成长，"
        "强调因果推进、关系重构与阶段性代价。"
    )


def _synth_summary(title: str) -> str:
    return (
        f"本卷围绕《{title}》的阶段主线展开：主角组在目标推进中遭遇外部阻力与内部分歧，"
        "通过连续行动逐步接近真相，并在卷末形成新的冲突入口。"
    )


def _outline_to_bullets(outline: str) -> str:
    s = _clean_text(outline)
    if not s:
        return (
            "- 场景：公共空间与私密场景交替。\n"
            "- 事件：线索确认、关系碰撞、阶段决策。\n"
            "- 对话要点：立场冲突与信息交换。\n"
            "- 情感变化：由犹疑转向主动承担。"
        )
    lines = [ln.strip() for ln in s.splitlines() if ln.strip()]
    head = "\n".join(lines[:10])
    if "- 场景" in head or "- 事件" in head:
        return head
    return (
        f"- 场景：{_truncate(head, 80)}\n"
        f"- 事件：{_truncate(s, 140)}\n"
        "- 对话要点：围绕目标分歧展开交锋并推动决策。\n"
        "- 情感变化：由犹疑转向主动，关系张力提升。"
    )


def _build_first_prompt(
    *,
    title: str,
    categories: Sequence[str],
    intro: str,
    volume_summary: str,
    characters: Dict[str, str],
    total_chapters: int,
    chapter_outline: str,
    min_chars: int,
) -> str:
    char_literal = str(characters).replace('"', "'")
    cats_literal = str(list(categories)).replace('"', "'")
    return (
        "\n#### 角色：\n"
        "你是一位才华横溢的小说作家助手，擅长理解并模仿网文风格。"
        "请根据小说全局信息与第1章细纲，创作完整开篇正文。\n\n"
        "#### 输入：\n"
        "1. 小说基础信息：标题、分类、简介、本卷梗概、主要人物行为。\n"
        "2. 小说章节信息：总章节数与当前章节位置。\n"
        "3. 开篇细纲：第1章关键场景、事件、对话、情感变化。\n\n"
        "#### 输出要求：\n"
        f"- 只输出正文，不输出解释、标签或代码块。\n"
        f"- 字数不少于{min_chars}字。\n"
        "- 风格稳定，叙事流畅，人物行为一致，章节结尾需有自然推进点。\n\n"
        f"**小说标题**：\n{title}\n\n"
        f"**分类**：\n{cats_literal}\n\n"
        f"**小说简介**：\n{intro}\n\n"
        f"**本卷梗概**：\n{volume_summary}\n\n"
        f"**主要人物和行为**：\n{char_literal}\n\n"
        f"**小说章节信息**：\n本小说共有{total_chapters}章，当前是小说开篇第1章。\n\n"
        f"**第1章细纲**：\n{chapter_outline}\n\n"
        "---\n\n"
        "请根据以上信息，撰写第1章完整正文。\n"
    )


def _build_non_first_prompt(
    *,
    title: str,
    categories: Sequence[str],
    intro: str,
    volume_summary: str,
    characters: Dict[str, str],
    total_chapters: int,
    chapter_index: int,
    previous_bridge: str,
    previous_tail: str,
    chapter_outline: str,
    min_chars: int,
) -> str:
    char_literal = str(characters).replace('"', "'")
    cats_literal = str(list(categories)).replace('"', "'")
    return (
        "\n#### 角色：\n"
        "你是一位才华横溢的小说作家助手，擅长保持长篇风格一致性。"
        "请基于前文结尾与当前章细纲，续写完整章节正文。\n\n"
        "#### 输入：\n"
        "1. 小说基础信息：标题、分类、简介、本卷梗概、主要人物行为。\n"
        "2. 小说章节信息：总章节数与当前章节位置。\n"
        "3. 上一章承接摘要：用于明确已发生事件、人物状态与未完成压力。\n"
        "4. 上一章结尾片段：用于承接叙事语境与语气。\n"
        "5. 当前章细纲：场景、事件、对话与情感变化。\n\n"
        "#### 输出要求：\n"
        f"- 只输出正文，不输出解释、标签或代码块。\n"
        f"- 字数不少于{min_chars}字。\n"
        "- 与上一章衔接自然，推进当前章冲突并形成章末钩子。\n"
        "- 不要机械复述上一章结尾原句，要在承接的基础上继续往前写。\n"
        "- 优先延续人物情绪、关系位置与场景余波，再进入当前章核心事件。\n\n"
        f"**小说标题**：\n{title}\n\n"
        f"**分类**：\n{cats_literal}\n\n"
        f"**小说简介**：\n{intro}\n\n"
        f"**本卷梗概**：\n{volume_summary}\n\n"
        f"**主要人物和行为**：\n{char_literal}\n\n"
        f"**小说章节信息**：\n本小说共有{total_chapters}章，当前是第{chapter_index}章。\n\n"
        f"**上一章承接摘要**：\n{previous_bridge}\n\n"
        f"**上一章的结尾片段**：\n{previous_tail}\n\n"
        f"**第{chapter_index}章细纲**：\n{chapter_outline}\n\n"
        "---\n\n"
        f"请根据以上信息，续写第{chapter_index}章完整正文。\n"
    )


def _collect_text_records(records: Iterable[Dict[str, Any]], mode: str) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for rec in records:
        if str(rec.get("task", "")).strip() != "text":
            continue
        chapter_index = int(rec.get("chapter_index") or 1)
        previous_tail = _clean_text(rec.get("previous_tail", ""))
        if mode == "first":
            if chapter_index > 1 and previous_tail:
                continue
        else:
            if chapter_index <= 1 or not previous_tail:
                continue
        out.append(rec)
    return out


def _build_candidates(records: List[Dict[str, Any]], mode: str, rng: random.Random) -> List[Dict[str, Any]]:
    cands: List[Dict[str, Any]] = []
    for rec in records:
        total_chapters = int(rec.get("total_chapters") or rng.randint(60, 180))
        chapter_index = int(rec.get("chapter_index") or (1 if mode == "first" else rng.randint(2, max(3, total_chapters))))
        if mode == "first":
            chapter_index = 1
        if chapter_index >= total_chapters:
            total_chapters = chapter_index + 5

        chapter_outline_raw = _clean_text(rec.get("chapter_outline", ""))
        previous_tail_raw = _clean_previous_context(rec.get("previous_tail", ""))

        source_blob = f"{chapter_outline_raw}\n{previous_tail_raw}"
        if _is_dirty_context(source_blob):
            continue

        names = [n for n in _extract_names(chapter_outline_raw + "\n" + previous_tail_raw, limit=12) if _looks_like_person_name(n)]
        title = _synth_title(rng)
        categories = rng.choice(_CATEGORY_POOL)
        intro = _synth_intro(title, categories)
        volume_summary = _synth_summary(title)
        char_map = _build_char_map(names, rng)

        chapter_outline = _outline_to_bullets(_truncate(chapter_outline_raw, 520))
        previous_tail = _tail_slice(previous_tail_raw, 520)
        previous_bridge = _build_previous_bridge(previous_tail_raw, chapter_outline_raw)
        if mode == "non_first" and not previous_tail:
            previous_tail = (
                "上一章末尾，主角在争执后暂时达成行动共识，却在离开前收到一条含糊警告，"
                "这条信息让团队意识到真正的风险才刚刚开始。"
            )
        if mode == "non_first" and not previous_bridge:
            previous_bridge = (
                "上一章刚刚形成新的行动压力，人物关系尚未稳定，当前章需要在承接风险的同时推进事件。"
            )

        cands.append(
            {
                "title": title,
                "categories": categories,
                "intro": intro,
                "volume_summary": volume_summary,
                "characters": char_map,
                "total_chapters": total_chapters,
                "chapter_index": chapter_index,
                "chapter_outline": chapter_outline,
                "previous_bridge": previous_bridge,
                "previous_tail": previous_tail,
            }
        )
    return cands


def _build_synthetic(mode: str, count: int, rng: random.Random) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for _ in range(max(0, count)):
        title = _synth_title(rng)
        categories = rng.choice(_CATEGORY_POOL)
        intro = _synth_intro(title, categories)
        volume_summary = _synth_summary(title)
        names = _NAME_POOL[:]
        rng.shuffle(names)
        char_map = _build_char_map(names[:6], rng)
        total_chapters = rng.randint(70, 220)
        chapter_index = 1 if mode == "first" else rng.randint(2, min(60, total_chapters - 1))
        chapter_outline = (
            "- 场景：核心角色在公开场域与私密场域之间切换，形成信息落差。\n"
            "- 事件：目标推进受阻后转入备用方案，关键证据在对峙中浮出水面。\n"
            "- 对话要点：围绕责任归属、行动优先级与风险边界展开三轮交锋。\n"
            "- 情感变化：主角由防御转向主动承担，同伴从怀疑转向有限协作。"
        )
        previous_tail = (
            "上一章结束时，主角在高压对峙中做出暂时妥协，"
            "但离场前确认了新的风险入口，团队关系进入重组阶段。"
        )
        previous_bridge = (
            "上一章已经完成临时妥协和风险确认，当前章需要承接紧张关系并把决策真正落地。"
        )
        out.append(
            {
                "title": title,
                "categories": categories,
                "intro": intro,
                "volume_summary": volume_summary,
                "characters": char_map,
                "total_chapters": total_chapters,
                "chapter_index": chapter_index,
                "chapter_outline": chapter_outline,
                "previous_bridge": previous_bridge,
                "previous_tail": previous_tail,
            }
        )
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build request pool for text first/non-first chapter generation")
    parser.add_argument("--input", type=str, nargs="+", required=True, help="Input structured JSONL")
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--mode", choices=["first", "non_first"], required=True)
    parser.add_argument("--target-count", type=int, default=500)
    parser.add_argument("--synthetic-count", type=int, default=400)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--model", type=str, default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--temperature", type=float, default=0.82)
    parser.add_argument("--top-p", type=float, default=0.92)
    parser.add_argument("--max-tokens", type=int, default=2400)
    parser.add_argument("--min-output-chars", type=int, default=1200)
    args = parser.parse_args()

    rng = random.Random(args.seed)
    input_paths = [Path(x) for x in args.input]
    for p in input_paths:
        if not p.exists():
            raise FileNotFoundError(f"input file not found: {p}")

    raw_records = list(_iter_jsonl(input_paths))
    text_records = _collect_text_records(raw_records, mode=args.mode)
    candidates = _build_candidates(text_records, mode=args.mode, rng=rng)
    candidates.extend(_build_synthetic(args.mode, args.synthetic_count, rng))
    rng.shuffle(candidates)

    if not candidates:
        raise RuntimeError("no candidates generated")

    selected = candidates[: max(1, args.target_count)]
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    with out_path.open("w", encoding="utf-8") as f:
        for item in selected:
            if args.mode == "first":
                prompt = _build_first_prompt(
                    title=item["title"],
                    categories=item["categories"],
                    intro=item["intro"],
                    volume_summary=item["volume_summary"],
                    characters=item["characters"],
                    total_chapters=item["total_chapters"],
                    chapter_outline=item["chapter_outline"],
                    min_chars=args.min_output_chars,
                )
                task_name = "text_first_chapter"
            else:
                prompt = _build_non_first_prompt(
                    title=item["title"],
                    categories=item["categories"],
                    intro=item["intro"],
                    volume_summary=item["volume_summary"],
                    characters=item["characters"],
                    total_chapters=item["total_chapters"],
                    chapter_index=item["chapter_index"],
                    previous_bridge=item["previous_bridge"],
                    previous_tail=item["previous_tail"],
                    chapter_outline=item["chapter_outline"],
                    min_chars=args.min_output_chars,
                )
                task_name = "text_non_first_chapter"

            req = {
                "model": args.model,
                "messages": [{"role": "user", "content": prompt}],
                # Keep stream=true to mimic online runtime contract.
                "stream": True,
                "temperature": args.temperature,
                "top_p": args.top_p,
                "max_tokens": args.max_tokens,
            }
            line = {
                "request": req,
                "meta": {
                    "task": task_name,
                    "title": item["title"],
                    "total_chapters": item["total_chapters"],
                    "chapter_index": item["chapter_index"],
                    "min_output_chars": args.min_output_chars,
                },
            }
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
            written += 1

    print(f"mode={args.mode}")
    print(f"raw_text_records={len(text_records)}")
    print(f"candidates={len(candidates)}")
    print(f"written={written}")
    print(f"output={out_path}")


if __name__ == "__main__":
    main()
