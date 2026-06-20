import argparse
import json
from pathlib import Path
from typing import List

import requests


def _parse_categories(raw: str) -> List[str]:
    s = str(raw or "").strip()
    if not s:
        return ["悬疑推理", "武侠小说", "仙侠玄幻"]
    if s.startswith("[") and s.endswith("]"):
        try:
            arr = json.loads(s.replace("'", '"'))
            if isinstance(arr, list):
                out = [str(x).strip() for x in arr if str(x).strip()]
                if out:
                    return out
        except Exception:
            pass
    parts = [x.strip() for x in s.split(",") if x.strip()]
    return parts or ["悬疑推理", "武侠小说", "仙侠玄幻"]


def _build_prompt(title: str, categories: List[str]) -> str:
    return f"""
    #### 角色:
    你是一位才华横溢的小说作家助手，擅长将小说基本信息转换为详细的小说描述。你的任务是根据提供的小说标题和分类，生成详细的小说信息，包括人物信息、故事背景和简介。请确保这些信息准确且具有吸引力。

    #### 输入:
    **小说标题**: 提供小说的标题。
    **分类**: 提供小说的分类信息。

    输出:
    请根据提供的小说标题和分类，生成详细的小说信息。输出应包括以下内容:
    人物信息: 列出主要角色的名字及其简短描述。
    故事背景: 描述故事发生的地点、时间和主要冲突。
    简介: 提供一个简短但吸引人的故事摘要。

    **小说标题**:
    {title}

    **分类**:
    {categories}

    请根据以上信息，生成详细的小说信息。
    """


def main() -> None:
    parser = argparse.ArgumentParser(description="Send info_recommend test request to local OpenAI-compatible API")
    parser.add_argument("--url", default="http://127.0.0.1:54862/v1/chat/completions")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--title", default="箭楼奇遇")
    parser.add_argument("--categories", default="悬疑推理,武侠小说,仙侠玄幻")
    parser.add_argument("--max-tokens", type=int, default=900)
    parser.add_argument("--temperature", type=float, default=0.7)
    parser.add_argument("--top-p", type=float, default=0.9)
    parser.add_argument("--out-json", default="logs/_info_recommend_interface_response.json")
    parser.add_argument("--out-content", default="logs/_info_recommend_interface_content.txt")
    args = parser.parse_args()

    categories = _parse_categories(args.categories)
    payload = {
        "model": "ChiYong-MoE-Novel-18B-A6B",
        "messages": [{"role": "user", "content": _build_prompt(args.title, categories)}],
        "stream": False,
        "max_tokens": args.max_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
    }

    headers = {"Content-Type": "application/json"}
    if args.api_key:
        headers["Authorization"] = f"Bearer {args.api_key}"

    resp = requests.post(args.url, headers=headers, json=payload, timeout=240)
    resp.raise_for_status()
    obj = resp.json()

    out_json = Path(args.out_json)
    out_txt = Path(args.out_content)
    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_txt.parent.mkdir(parents=True, exist_ok=True)

    with out_json.open("w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)

    content = obj.get("choices", [{}])[0].get("message", {}).get("content", "")
    with out_txt.open("w", encoding="utf-8") as f:
        f.write(str(content))

    print(f"saved_json={out_json}")
    print(f"saved_content={out_txt}")
    print(f"content_len={len(str(content))}")
    print(str(content)[:1200])


if __name__ == "__main__":
    main()

