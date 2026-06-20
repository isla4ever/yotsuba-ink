"""
Send detail-outline test requests to local OpenAI-compatible API.

Example:
  .\\.venv\\Scripts\\python.exe scripts/test_detail_outline_live.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import requests


def _single_quote_literal(value: object) -> str:
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


def _build_prompt(case: Dict[str, object]) -> str:
    char_literal = _single_quote_literal(case["characters"])
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
        f"共输出 {case['chapter_count']} 项，按列表顺序表示章节先后。\n"
        "每章内容需要覆盖：主要事件、场景描述、对话要点、人物情感变化。\n\n"
        f"**小说标题**：\n{case['title']}\n\n"
        f"**人物信息**：\n{char_literal}\n\n"
        f"**小说部分内容的梗概**：\n{case['volume_summary']}\n\n"
        f"**小说简介**：\n{case['novel_intro']}\n\n"
        f"**章节划分**：\n一共 {case['chapter_count']} 章\n"
    )


def _send_one(url: str, model: str, case: Dict[str, object], timeout: int) -> Dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _build_prompt(case)}],
        "stream": False,
        "max_tokens": 2600,
        "temperature": 0.72,
        "top_p": 0.88,
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send detail-outline test requests to local OpenAI-compatible API")
    parser.add_argument("--url", default="http://127.0.0.1:54862/v1/chat/completions")
    parser.add_argument("--model", default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--out-dir", default="logs")
    args = parser.parse_args()

    cases: List[Dict[str, object]] = [
        {
            "name": "case1_campus",
            "title": "冬以嫣的青春之旅",
            "chapter_count": 3,
            "characters": {
                "冬以嫣": "创办爱心社团，组织公益行动并在友情冲突中主动承担协调任务。",
                "阮桐": "在恋爱与自我价值之间反复拉扯，经历误解、分手与重建。",
                "白轩": "在情感选择中摇摆，引发关系裂痕后尝试修复。",
                "何思颖": "在竞争关系中做出放手决定，推动矛盾走向收束。",
            },
            "volume_summary": "本卷围绕大学第一学期的社团成长与情感纠葛展开。冬以嫣在公益行动中建立影响力，阮桐在亲密关系中遭遇反复，友情与爱情在同一时间窗持续拉扯。",
            "novel_intro": "《冬以嫣的青春之旅》讲述青年人在成长阶段处理理想、关系与现实代价的过程，故事强调人物行动与情感变化的因果关联。",
        },
        {
            "name": "case2_scifi",
            "title": "火星回廊协议",
            "chapter_count": 4,
            "characters": {
                "陆岚": "带队追查协议篡改源头，平衡技术线和行动线。",
                "秦渡": "负责调度与对外谈判，在危机升级时压住冲突扩散。",
                "许闻声": "解密黑箱数据并提供关键反证。",
                "白栀": "组织居民疏散并维持内部秩序。",
            },
            "volume_summary": "本卷聚焦回廊协议被篡改后的应急处置。调查线、政治线和民生线并行推进，主角组在资源断供和舆论压力下完成阶段反击。",
            "novel_intro": "《火星回廊协议》以近未来殖民社会为背景，围绕安全、自治与权力边界展开多线冲突，强调技术决策与人性选择的双重代价。",
        },
    ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, case in enumerate(cases, 1):
        obj = _send_one(args.url, args.model, case, args.timeout)
        content = str(obj.get("choices", [{}])[0].get("message", {}).get("content", ""))
        resp_path = out_dir / f"_detail_outline_{case['name']}_response.json"
        content_path = out_dir / f"_detail_outline_{case['name']}_content.txt"
        req_path = out_dir / f"_detail_outline_{case['name']}_request.json"
        req_path.write_text(
            json.dumps(
                {
                    "model": args.model,
                    "messages": [{"role": "user", "content": _build_prompt(case)}],
                    "stream": False,
                    "max_tokens": 2600,
                    "temperature": 0.72,
                    "top_p": 0.88,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        resp_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        content_path.write_text(content, encoding="utf-8")
        print(f"[{idx}] {case['name']}: len={len(content)} -> {resp_path.name}")


if __name__ == "__main__":
    main()
