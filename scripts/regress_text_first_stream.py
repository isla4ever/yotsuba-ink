"""
Regression test for first-chapter text generation (streaming).

What it validates:
1) local server boots with selected adapter
2) /v1/chat/completions returns SSE stream
3) stream contains JSON chunks and [DONE]
4) merged assistant text is non-empty and long enough
5) no obvious replacement-char encoding corruption
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

import requests


def _now_ts() -> int:
    return int(time.time())


def _wait_health(base_url: str, timeout_seconds: int) -> bool:
    deadline = time.time() + max(1, timeout_seconds)
    url = f"{base_url}/health"
    while time.time() < deadline:
        try:
            r = requests.get(url, timeout=5)
            if r.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(1.0)
    return False


def _build_cases(model_name: str) -> List[Dict[str, Any]]:
    case1 = {
        "name": "case1_clothing_designer",
        "request": {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "\n#### 角色：\n"
                        "你是一位才华横溢的小说作家助手，擅长理解和模仿小说的风格。"
                        "你的任务是根据提供的本章细纲，结合小说的整体风格和背景，生成完整的小说开篇内容。"
                        "请注意模仿小说的语言风格、叙述节奏和人物性格，确保开篇内容引人入胜，并为后续情节做好铺垫。\n\n"
                        "#### 输入：\n"
                        "1. **小说章节信息**: 提供创作总篇幅和本章的位置信息。\n"
                        "2. **开篇细纲**：提供小说开篇一章的详细细纲，包括主要事件、场景描述、对话要点等。\n\n"
                        "#### 输出：\n"
                        "请根据提供的细纲，生成出完整的小说开篇内容，确保内容与小说整体风格一致，叙述流畅，人物性格和情节发展合理。\n\n"
                        "**小说章节信息**\n本小说共有85章，当前是小说开篇第1章。\n\n"
                        "**本章细纲**：\n"
                        "辛仪是一名优秀的服装设计师，她为了妈妈的生活质量，带着男友刘宇航回到老家。"
                        "妈妈要求她马上结婚，辛仪瞒着妈妈与刘宇航相恋。刘宇航拜见了未来岳母大人，妈妈对他很满意。"
                        "辛仪为了第一次见男友家长，费心搭配衣服，最终以美丽的打扮出现在刘宇航面前，他对她的打扮赞赏有加。"
                        "他们一起出门去帮父母选礼物。\n\n---\n\n请根据以上信息，撰写小说的开篇内容。\n"
                    ),
                }
            ],
            "stream": True,
        },
    }
    case2 = {
        "name": "case2_mountain_town_mystery",
        "request": {
            "model": model_name,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "\n#### 角色：\n"
                        "你是一位才华横溢的小说作家助手，擅长理解和模仿小说的风格。"
                        "请根据本章细纲，创作小说第1章的完整正文，要求情节完整、人物性格明确、结尾留出悬念。\n\n"
                        "**小说章节信息**\n本小说共有96章，当前是小说开篇第1章。\n\n"
                        "**本章细纲**：\n"
                        "雨夜，林昭回到阔别十年的山城，在旧宅门口捡到一封没有寄件人的信。"
                        "信中只写着“别进后院”，她却在停电后听到后院井边传来脚步声。"
                        "青梅竹马陆沉赶来修电，发现井盖被人新换过。"
                        "两人沿着湿泥脚印追到祠堂，看到墙上出现了与林昭母亲失踪案相关的旧符号。"
                        "章节结尾：林昭在祠堂供桌下找到一把刻有自己名字的铜钥匙。\n\n"
                        "请根据以上信息，撰写小说开篇正文。\n"
                    ),
                }
            ],
            "stream": True,
        },
    }
    return [case1, case2]


def _run_one_case(base_url: str, case: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
    req = case["request"]
    url = f"{base_url}/v1/chat/completions"
    stream_lines: List[str] = []
    merged = []
    parsed_chunks = 0
    done = False
    role_seen = False
    err = ""
    status = None
    t0 = time.time()
    try:
        with requests.post(url, json=req, timeout=timeout_seconds, stream=True) as r:
            status = r.status_code
            if r.status_code != 200:
                err = r.text[:1200]
            else:
                for raw in r.iter_lines(decode_unicode=True):
                    if raw is None:
                        continue
                    line = str(raw).strip()
                    if not line:
                        continue
                    stream_lines.append(line)
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        done = True
                        break
                    try:
                        obj = json.loads(payload)
                        parsed_chunks += 1
                        choices = obj.get("choices") or []
                        if not choices:
                            continue
                        delta = (choices[0] or {}).get("delta") or {}
                        if delta.get("role") == "assistant":
                            role_seen = True
                        text = delta.get("content")
                        if isinstance(text, str) and text:
                            merged.append(text)
                    except Exception:
                        # keep raw line for debugging
                        pass
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"

    content = "".join(merged)
    elapsed = round(time.time() - t0, 2)
    valid = (
        status == 200
        and done
        and parsed_chunks > 0
        and len(content.strip()) >= 220
        and "\ufffd" not in content
    )
    return {
        "name": case["name"],
        "status_code": status,
        "elapsed_seconds": elapsed,
        "done_marker": done,
        "parsed_chunks": parsed_chunks,
        "assistant_role_seen": role_seen,
        "content_len": len(content),
        "valid": valid,
        "error": err,
        "request": req,
        "stream_lines": stream_lines,
        "content": content,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Regression test for first-chapter streaming generation")
    parser.add_argument("--model-path", default=r"D:\models\Qwen3.5-4B")
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--python-exe", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=54862)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--max-new-tokens", type=int, default=1536)
    parser.add_argument("--served-model-name", default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--startup-timeout-seconds", type=int, default=240)
    parser.add_argument("--request-timeout-seconds", type=int, default=600)
    parser.add_argument("--logs-dir", default="logs")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    logs_dir = root / args.logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = _now_ts()
    out_log = logs_dir / f"regress_text_first_server_{ts}.out.log"
    err_log = logs_dir / f"regress_text_first_server_{ts}.err.log"
    report_path = logs_dir / f"regress_text_first_report_{ts}.json"

    py = args.python_exe
    if str(py).startswith(".\\"):
        py = str((root / py).resolve())

    cmd = [
        py,
        "deploy/openai_compat_server.py",
        "--model-path",
        args.model_path,
        "--adapter-path",
        args.adapter_path,
        "--served-model-name",
        args.served_model_name,
        "--host",
        args.host,
        "--port",
        str(args.port),
        "--dtype",
        args.dtype,
        "--max-new-tokens",
        str(args.max_new_tokens),
    ]

    server_proc = None
    base_url = f"http://{args.host}:{args.port}"
    results = []
    ok = False
    try:
        with out_log.open("w", encoding="utf-8") as fout, err_log.open("w", encoding="utf-8") as ferr:
            server_proc = subprocess.Popen(cmd, cwd=str(root), stdout=fout, stderr=ferr)
            if not _wait_health(base_url, timeout_seconds=args.startup_timeout_seconds):
                raise RuntimeError("server_start_timeout")

            for case in _build_cases(args.served_model_name):
                result = _run_one_case(base_url, case, timeout_seconds=args.request_timeout_seconds)
                results.append(result)

            ok = all(x.get("valid") for x in results)
    finally:
        if server_proc is not None:
            try:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(server_proc.pid), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    server_proc.terminate()
            except Exception:
                pass

    report = {
        "timestamp": ts,
        "base_url": base_url,
        "model_path": args.model_path,
        "adapter_path": args.adapter_path,
        "served_model_name": args.served_model_name,
        "server_out_log": str(out_log),
        "server_err_log": str(err_log),
        "all_passed": ok,
        "cases": [
            {
                k: v
                for k, v in c.items()
                if k not in {"request", "stream_lines", "content"}
            }
            for c in results
        ],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    # Persist full echo artifacts for debug/replay.
    for c in results:
        name = c["name"]
        (logs_dir / f"{name}_{ts}_request.json").write_text(
            json.dumps(c["request"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (logs_dir / f"{name}_{ts}_stream_lines.txt").write_text(
            "\n".join(c["stream_lines"]),
            encoding="utf-8",
        )
        (logs_dir / f"{name}_{ts}_content.txt").write_text(
            c["content"],
            encoding="utf-8",
        )

    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
