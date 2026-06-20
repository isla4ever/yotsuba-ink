"""
Send summary (梗概) test requests to local OpenAI-compatible API.

Example:
  .\\.venv\\Scripts\\python.exe scripts/test_summary_live.py
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, List

import requests


def _build_prompt(title: str, categories: List[str], intro: str) -> str:
    cat_literal = "[" + ", ".join(f"'{c}'" for c in categories) + "]"
    return (
        "#### 角色:\n"
        "你是一位才华横溢的小说作家助手，擅长将小说信息转换为详细的小说内容梗概。\n\n"
        "#### 输入:\n"
        f"**小说标题**: {title}\n"
        f"**分类**: {cat_literal}\n"
        f"**情节简介**: {intro}\n\n"
        "#### 输出:\n"
        "请按固定结构返回：\n"
        "[{'主要人物和他们的行为': {人物名: 主要行为, ...}, '内容': '完整梗概'}]\n"
        "请生成小说梗概。\n"
    )


def _send_one(url: str, model: str, case: Dict[str, object], timeout: int) -> Dict:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": _build_prompt(case["title"], case["categories"], case["intro"])}],
        "stream": False,
        "max_tokens": 24,
        "temperature": 0.4,
        "top_p": 0.8,
    }
    resp = requests.post(url, json=payload, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send summary test requests to local OpenAI-compatible API")
    parser.add_argument("--url", default="http://127.0.0.1:54862/v1/chat/completions")
    parser.add_argument("--model", default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--timeout", type=int, default=120)
    parser.add_argument("--out-dir", default="logs")
    args = parser.parse_args()

    cases = [
        {
            "name": "case1_rebirth",
            "title": "齐月的重生之旅",
            "categories": ["现实小说", "青春文学"],
            "intro": "齐月在家人陪伴下从低谷恢复，经历告别与启程，最终迎来新生。",
        },
        {
            "name": "case2_wuxia",
            "title": "箭楼奇遇",
            "categories": ["悬疑推理", "武侠小说", "仙侠玄幻"],
            "intro": "三名年轻人调查箭楼异象，发现尘封线索并卷入势力争夺，在险境中逐步接近真相。",
        },
        {
            "name": "case3_urban",
            "title": "旧港回声",
            "categories": ["都市生活", "现实小说", "悬疑推理"],
            "intro": "女主重返旧港查找失踪真相，与旧友和家人关系重组，在多方压力下完成自我和解。",
        },
    ]

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    for idx, case in enumerate(cases, 1):
        obj = _send_one(args.url, args.model, case, args.timeout)
        content = str(obj.get("choices", [{}])[0].get("message", {}).get("content", ""))
        resp_path = out_dir / f"_summary_{case['name']}_response.json"
        content_path = out_dir / f"_summary_{case['name']}_content.txt"
        resp_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
        content_path.write_text(content, encoding="utf-8")
        print(f"[{idx}] {case['name']}: len={len(content)}")
        print(content)
        print("-" * 80)


if __name__ == "__main__":
    main()
