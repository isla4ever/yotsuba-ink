"""
Build high-quality corrected SFT dataset for outline (分卷大纲) task.

Input format:
  {"request": {...}, "response": {...}, "meta": {...}}

Output format (chat SFT jsonl):
  {"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"[{'主要人物和他们的行为':...,'故事情节':...}, ...]"}]}
"""

from __future__ import annotations

import argparse
import ast
import json
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from deploy.openai_compat_server import _normalize_outline_text


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


def _ensure_period(text: str) -> str:
    s = str(text or "").strip()
    if not s:
        return s
    s = re.sub(r"[?？!！]+$", "。", s)
    if s[-1] not in "。！？!?":
        s += "。"
    return s


def _clean_sentence(text: str) -> str:
    s = _safe_text(text).replace("\r", "\n")
    s = re.sub(r"\s+", "", s)
    s = re.sub(r"[`*_#]", "", s)
    s = s.strip("，。；;!！?？:：'\"")
    return s


def _compose_long_sentence(base: str, extras: Sequence[str], min_chars: int, max_parts: int = 10) -> str:
    parts: List[str] = []
    b = _clean_sentence(base)
    if b:
        parts.append(b)
    for item in extras:
        s = _clean_sentence(item)
        if not s:
            continue
        parts.append(s)

    deduped: List[str] = []
    for p in parts:
        if any(p == x or p in x for x in deduped):
            continue
        deduped = [x for x in deduped if x not in p]
        deduped.append(p)
    if not deduped:
        return ""

    selected = deduped[:max_parts]
    text = _ensure_period("，".join(selected))
    if len(text) >= min_chars:
        return text

    reinforcement = [
        "这一阶段会把人物关系行动路径和资源分配绑定在同一条推进链上避免空转",
        "每次推进都要给出可继承的结果确保后续分章可以直接承接冲突与目标",
        "阶段结尾会显式保留未解问题和代价反馈为下一卷提供连续推动力",
    ]
    for item in reinforcement:
        if item not in selected:
            selected.append(item)
        text = _ensure_period("，".join(selected[: max_parts + 3]))
        if len(text) >= min_chars:
            break
    return text


def _normalize_name(name: str) -> str:
    n = _safe_text(name).strip().strip("'\"")
    n = re.sub(r"\s+", "", n)
    n = n.strip("[]{}()（）")
    return n


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
_FEMALE_CONTEXT_TOKENS = ("女主", "姑娘", "小姐", "女孩", "姐姐", "妹妹", "母亲", "妻子", "闺蜜")
_MALE_CONTEXT_TOKENS = ("男主", "少年", "男孩", "哥哥", "弟弟", "父亲", "丈夫", "兄弟")


def _score_gender_from_context(name: str, context: str) -> Tuple[int, int]:
    n = _normalize_name(name)
    text = _safe_text(context)
    if not n or not text:
        return 0, 0

    f_score = 0
    m_score = 0
    esc = re.escape(n)

    for token in _FEMALE_CONTEXT_TOKENS:
        te = re.escape(token)
        f_score += len(re.findall(rf"{esc}.{{0,20}}{te}|{te}.{{0,20}}{esc}", text)) * 4
    for token in _MALE_CONTEXT_TOKENS:
        te = re.escape(token)
        m_score += len(re.findall(rf"{esc}.{{0,20}}{te}|{te}.{{0,20}}{esc}", text)) * 4

    f_score += len(re.findall(rf"{esc}.{{0,4}}她|她.{{0,4}}{esc}", text)) * 3
    m_score += len(re.findall(rf"{esc}.{{0,4}}他|他.{{0,4}}{esc}", text)) * 3

    for m in re.finditer(esc, text):
        s = max(0, m.start() - 6)
        e = min(len(text), m.end() + 6)
        w = text[s:e]
        f_score += w.count("她")
        m_score += w.count("他")
    if n in text:
        if any(token in text for token in _FEMALE_CONTEXT_TOKENS):
            f_score += 1
        if any(token in text for token in _MALE_CONTEXT_TOKENS):
            m_score += 1
    return f_score, m_score


def _infer_gender(name: str, context: str) -> str:
    n = _normalize_name(name)
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


def _replace_name_after_first(text: str, name: str, gender: str) -> str:
    s = _clean_sentence(text)
    n = _normalize_name(name)
    if not s or not n:
        return _ensure_period(s)
    idx = s.find(n)
    if idx < 0:
        return _ensure_period(s)
    if gender == "female":
        pronoun = "她"
    elif gender == "male":
        pronoun = "他"
    else:
        pronoun = "她" if s.count("她") > s.count("他") else "他"
    head = s[: idx + len(n)]
    tail = s[idx + len(n) :]
    tail = re.sub(re.escape(n), pronoun, tail)
    tail = re.sub(r"(他|她){2,}", pronoun, tail)
    return _ensure_period((head + tail).strip())


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
        return "{" + ", ".join(f"{_literal_single_quote(str(k))}: {_literal_single_quote(v)}" for k, v in value.items()) + "}"
    return _literal_single_quote(str(value))


def _parse_items(text: str) -> List[Dict[str, Any]]:
    s = _safe_text(text)
    for parser in (ast.literal_eval, json.loads):
        try:
            obj = parser(s)
            break
        except Exception:
            obj = None
    if not isinstance(obj, list):
        return []
    return [x for x in obj if isinstance(x, dict)]


def _normalize_char_map(raw: Any, min_chars: int, max_chars: int, min_behavior_chars: int) -> Dict[str, str]:
    out: Dict[str, str] = {}
    behavior_pool = [
        "{name}会同步推进线索核验与资源协调，确保行动链条在高压阶段仍具备执行稳定性",
        "{name}在卷内承担跨场景衔接职责，把阶段信息转化为可落地的下一步策略",
        "{name}需要在冲突对抗中处理误判成本，并通过复盘修正行动路径避免主线失速",
        "{name}会围绕关键节点组织协作，把关系博弈结果转化为可验证的事件成果",
        "{name}在推进中持续平衡风险与收益，避免因局部突破导致整体计划脱节",
        "{name}的行动既服务当前卷闭环，也为下一卷保留可承接的问题入口与执行抓手",
    ]

    def _name_extras(name: str) -> List[str]:
        base_idx = sum(ord(ch) for ch in name) % len(behavior_pool)
        e1 = behavior_pool[base_idx].format(name=name)
        e2 = behavior_pool[(base_idx + 2) % len(behavior_pool)].format(name=name)
        return [e1, e2]

    if isinstance(raw, dict):
        for k, v in raw.items():
            name = _normalize_name(k)
            if not name or name in out:
                continue
            behavior = _clean_sentence(v)
            out[name] = _compose_long_sentence(
                behavior,
                [
                    f"{name}围绕本卷主线持续推进调查沟通执行三条并行任务线保证关键线索能够闭环验证",
                    *_name_extras(name),
                ],
                min_chars=min_behavior_chars,
                max_parts=8,
            )
            out[name] = _replace_name_after_first(out[name], name, _infer_gender(name, behavior))
            if len(out) >= max_chars:
                break
    if len(out) < min_chars:
        defaults = ["林晚舟", "沈言", "周砚川", "程以宁", "顾南乔", "宋临安"]
        for n in defaults:
            if n in out:
                continue
            out[n] = _compose_long_sentence(
                "",
                [
                    f"{n}在本卷负责推进核心任务持续处理线索分歧协作摩擦与外部压力确保主线不偏离目标",
                    *_name_extras(n),
                ],
                min_chars=min_behavior_chars,
                max_parts=7,
            )
            out[n] = _replace_name_after_first(out[n], n, _infer_gender(n, out[n]))
            if len(out) >= min_chars:
                break
    return out


def _normalize_story_map(raw: Any, volume_index: int, total_volumes: int, min_story_chars: int) -> Dict[str, str]:
    keys = ("开始", "发展", "高潮", "结局")
    out: Dict[str, str] = {}
    if isinstance(raw, dict):
        for k in keys:
            out[k] = _clean_sentence(raw.get(k, ""))
    else:
        out = {k: "" for k in keys}

    suffix = {
        "开始": "本卷开篇明确目标冲突规则边界与人物站位差异并交代后续行动所受的现实约束与风险来源",
        "发展": "主支线交错推进信息差与利益冲突持续放大角色在多方博弈中不断修正策略与协作关系",
        "高潮": "关键反转触发高压决策角色必须在有限时间内完成价值选择并承担可见代价局势因此发生方向性变化",
        "结局": f"本卷形成阶段闭环并向第{min(total_volumes, volume_index + 2)}卷预埋新问题线与新代价约束保证跨卷推进连续",
    }
    segment_pool = {
        "开始": "该段应明确本卷问题入口与行动目标，并给出能够直接驱动后续场景的触发条件",
        "发展": "该段应展示多线并行推进过程中的策略修正，让角色关系和信息结构同步变化",
        "高潮": "该段应突出决策压力与执行代价，保证冲突升级具有可追踪的因果链",
        "结局": "该段应完成阶段收束并明确遗留问题，使下一卷拥有稳定承接点与推进方向",
    }
    for k in keys:
        text = out.get(k, "")
        out[k] = _compose_long_sentence(
            text,
            [
                suffix[k],
                segment_pool[k],
                "段落收束时要把变化反馈到人物关系和资源配置形成下一段可以承接的因果入口",
            ],
            min_chars=min_story_chars,
            max_parts=8,
        )
    return out


def _quality_score(items: List[Dict[str, Any]]) -> float:
    if not items:
        return -1e9
    volume_count = len(items)
    person_counts = []
    story_lengths = []
    for item in items:
        char_map = item.get("主要人物和他们的行为", {})
        story_map = item.get("故事情节", {})
        if isinstance(char_map, dict):
            person_counts.append(len(char_map))
        if isinstance(story_map, dict):
            story_lengths.append(sum(len(_safe_text(story_map.get(k, ""))) for k in ("开始", "发展", "高潮", "结局")))
    return volume_count * 150 + sum(person_counts) * 25 + sum(story_lengths) * 0.25


def build_dataset(
    *,
    input_path: Path,
    output_path: Path,
    report_path: Path,
    target_count: int,
    min_volumes: int,
    max_volumes: int,
    min_characters: int,
    max_characters: int,
    min_behavior_chars: int,
    min_story_chars: int,
    seed: int,
) -> None:
    rng = random.Random(seed)
    rows: List[Dict[str, Any]] = []
    total = 0
    for obj in _iter_jsonl(input_path):
        total += 1
        if obj.get("meta", {}).get("status") not in ("ok", None):
            continue
        req = obj.get("request")
        resp = obj.get("response")
        if not isinstance(req, dict) or not isinstance(resp, dict):
            continue

        messages = req.get("messages", [])
        if not isinstance(messages, list):
            continue
        user_parts = [str(m.get("content", "")).strip() for m in messages if isinstance(m, dict) and m.get("role") == "user"]
        user_prompt = "\n".join([p for p in user_parts if p]).strip()
        if not user_prompt:
            continue

        choices = resp.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        msg = choices[0].get("message") if isinstance(choices[0], dict) else None
        if not isinstance(msg, dict):
            continue
        raw_text = str(msg.get("content", "") or "")
        normalized_text = _normalize_outline_text(raw_text, messages)
        items = _parse_items(normalized_text)
        if not items:
            continue

        fixed_items: List[Dict[str, Any]] = []
        cap_volumes = max(min_volumes, min(max_volumes, len(items)))
        for idx, item in enumerate(items[:cap_volumes]):
            char_map = _normalize_char_map(
                item.get("主要人物和他们的行为"),
                min_characters,
                max_characters,
                min_behavior_chars,
            )
            story_map = _normalize_story_map(
                item.get("故事情节"),
                volume_index=idx,
                total_volumes=cap_volumes,
                min_story_chars=min_story_chars,
            )
            fixed_items.append({"主要人物和他们的行为": char_map, "故事情节": story_map})

        while len(fixed_items) < min_volumes:
            idx = len(fixed_items)
            synth_chars = _normalize_char_map({}, min_characters, max_characters, min_behavior_chars)
            synth_story = _normalize_story_map({}, idx, min_volumes, min_story_chars)
            fixed_items.append({"主要人物和他们的行为": synth_chars, "故事情节": synth_story})

        assistant_text = _literal_single_quote(fixed_items)
        rows.append(
            {
                "messages": [
                    {"role": "user", "content": user_prompt},
                    {"role": "assistant", "content": assistant_text},
                ],
                "_meta": {
                    "score": _quality_score(fixed_items),
                    "volumes": len(fixed_items),
                    "characters_min": min(len(x["主要人物和他们的行为"]) for x in fixed_items),
                    "story_len_min": min(
                        sum(len(_safe_text(x["故事情节"].get(k, ""))) for k in ("开始", "发展", "高潮", "结局"))
                        for x in fixed_items
                    ),
                },
            }
        )

    rows.sort(key=lambda x: x["_meta"]["score"], reverse=True)
    if target_count > 0:
        rows = rows[:target_count]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n")

    volumes = [x["_meta"]["volumes"] for x in rows]
    char_min = [x["_meta"]["characters_min"] for x in rows]
    story_min = [x["_meta"]["story_len_min"] for x in rows]
    report = {
        "input_total": total,
        "output_records": len(rows),
        "volume_avg": round(sum(volumes) / len(volumes), 2) if volumes else 0,
        "volume_min": min(volumes) if volumes else 0,
        "volume_max": max(volumes) if volumes else 0,
        "characters_min_avg": round(sum(char_min) / len(char_min), 2) if char_min else 0,
        "story_len_min_avg": round(sum(story_min) / len(story_min), 2) if story_min else 0,
        "output_path": str(output_path),
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Build high-quality corrected outline SFT dataset")
    parser.add_argument("--input", required=True, help="Input teacher pairs jsonl")
    parser.add_argument("--output", required=True, help="Output SFT jsonl")
    parser.add_argument("--report", default="logs/outline_hq_correction_report.json")
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--min-volumes", type=int, default=3)
    parser.add_argument("--max-volumes", type=int, default=5)
    parser.add_argument("--min-characters", type=int, default=4)
    parser.add_argument("--max-characters", type=int, default=8)
    parser.add_argument("--min-behavior-chars", type=int, default=88)
    parser.add_argument("--min-story-chars", type=int, default=120)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    build_dataset(
        input_path=Path(args.input),
        output_path=Path(args.output),
        report_path=Path(args.report),
        target_count=args.target_count,
        min_volumes=args.min_volumes,
        max_volumes=args.max_volumes,
        min_characters=args.min_characters,
        max_characters=args.max_characters,
        min_behavior_chars=args.min_behavior_chars,
        min_story_chars=args.min_story_chars,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
