"""
Run 3 regression tests for detail-outline endpoint.

Checks:
1) response content is parseable list
2) chapter count matches requested count
3) each item has {"章节标题", "细纲内容"}
4) each "细纲内容" has minimum length
5) no obvious mojibake/replacement-char issue

Can auto-start local server and stop it after tests.
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


def _build_prompt(case: Dict[str, Any]) -> str:
    characters_literal = str(case["characters"]).replace('"', "'")
    return (
        "\n#### 角色：\n"
        "你是一位资深小说章节策划助手。请将给定分卷内容细化为可直接写作的章节细纲。\n\n"
        "#### 输入：\n"
        "1. 人物信息：本卷涉及人物及其主要行为。\n"
        "2. 小说部分内容的梗概：本卷主线、冲突与阶段目标。\n"
        "3. 小说简介：全书主线与长期主题。\n"
        "4. 章节划分：本卷需要拆分的章节数量。\n\n"
        "#### 输出格式（必须严格遵守）：\n"
        "仅输出一个列表字符串，列表每项为：\n"
        "{'章节标题': str, '细纲内容': str}\n"
        f"共输出 {case['chapter_count']} 项，按列表顺序表示章节先后。\n"
        "每章“细纲内容”必须覆盖：主要事件、场景描述、对话要点、人物情感变化。\n\n"
        f"**小说标题**：\n{case['title']}\n\n"
        f"**人物信息**：\n{characters_literal}\n\n"
        f"**小说部分内容的梗概**：\n{case['volume_summary']}\n\n"
        f"**小说简介**：\n{case['novel_intro']}\n\n"
        f"**章节划分**：\n一共 {case['chapter_count']} 章\n"
    )


def _cases() -> List[Dict[str, Any]]:
    return [
        {
            "name": "campus_friendship",
            "title": "冬以嫣的青春之旅",
            "chapter_count": 3,
            "characters": {
                "冬以嫣": "创办爱心社团，组织公益行动，在友情冲突中承担协调任务。",
                "阮桐": "在亲密关系中经历误解、分手与重建，并在关键节点做出选择。",
                "白轩": "在情感拉扯中反复摇摆，造成关系裂缝后尝试修复。",
                "何思颖": "在竞争关系中最终选择放手，推动矛盾收束。",
            },
            "volume_summary": "本卷围绕大学第一学期的社团成长与情感纠葛展开。冬以嫣在公益实践中建立影响力，阮桐在关系波动中完成自我确认，友情与爱情在同一时间窗持续拉扯并相互影响。",
            "novel_intro": "《冬以嫣的青春之旅》讲述年轻人在成长阶段处理理想、关系与现实代价的过程，强调行动后果、情绪变化与关系重构之间的因果链条。",
        },
        {
            "name": "wuxia_medical",
            "title": "寒川封丹录",
            "chapter_count": 4,
            "characters": {
                "韩子陌": "追查灵药线索，平衡医术探索与门派争斗，持续推进核心调查。",
                "羽漠尘": "围绕封丹会暗线提供关键支援，同时隐藏自身立场。",
                "韩子盛": "在家族责任与个人立场之间多次抉择，推动关系转折。",
                "赵开": "掌握会场信息入口，反复试探主角行动边界。",
            },
            "volume_summary": "本卷聚焦封丹会前后的一轮高压博弈。主角组在追索灵药真相时遭遇身份伪装、规则限制与多方布局，冲突从个人恩怨逐步升级为势力层面的资源争夺。",
            "novel_intro": "《寒川封丹录》以医武并行的世界观展开叙事，通过连续反转与关系揭示构建长线悬念，强调角色在风险压力下的决策代价。",
        },
        {
            "name": "scifi_colony",
            "title": "火星回廊协议",
            "chapter_count": 5,
            "characters": {
                "陆峤": "主导调查路线，统筹证据链与实地行动，压缩风险暴露窗口。",
                "秦沅": "负责谈判与调度，在危机升级时稳定外部关系并争取时间。",
                "许闻声": "破解黑箱数据，连续提供反证，推动调查从猜测进入验证。",
                "白栀": "组织居民疏散与后勤保障，维持秩序并缓冲舆情冲击。",
            },
            "volume_summary": "本卷围绕回廊协议篡改事件展开。调查线、治理线与民生线并行推进，角色在资源受限和舆论冲击下完成阶段反制，但也暴露了更深层的系统性风险。",
            "novel_intro": "《火星回廊协议》以近未来殖民社会为背景，聚焦技术决策、权力边界与公共安全之间的冲突，强调群像行动与制度后果。",
        },
    ]


def _wait_health(base_url: str, timeout_s: int = 1200) -> None:
    start = time.time()
    last_err = ""
    while time.time() - start < timeout_s:
        try:
            resp = requests.get(f"{base_url}/health", timeout=3)
            if resp.status_code == 200:
                return
            last_err = f"status={resp.status_code} body={resp.text[:160]}"
        except Exception as exc:  # noqa: BLE001
            last_err = str(exc)
        time.sleep(2)
    raise RuntimeError(f"health_timeout: {last_err}")


def _parse_list_text(content: str) -> Optional[List[Dict[str, Any]]]:
    s = str(content or "").strip()
    if not s:
        return None
    for parser in (ast.literal_eval, json.loads):
        try:
            obj = parser(s)
            if isinstance(obj, list):
                return [x for x in obj if isinstance(x, dict)]
        except Exception:
            continue
    return None


def _validate_case(
    *,
    case: Dict[str, Any],
    content: str,
    min_content_chars: int,
) -> Dict[str, Any]:
    parsed = _parse_list_text(content)
    errors: List[str] = []
    warn: List[str] = []
    if parsed is None:
        errors.append("content_not_parseable_list")
        return {
            "ok": False,
            "errors": errors,
            "warnings": warn,
            "chapter_count_expected": case["chapter_count"],
            "chapter_count_actual": 0,
        }

    expected = int(case["chapter_count"])
    actual = len(parsed)
    if actual != expected:
        errors.append(f"chapter_count_mismatch:{actual}!={expected}")

    for i, item in enumerate(parsed, 1):
        title = str(item.get("章节标题", "")).strip()
        body = str(item.get("细纲内容", "")).strip()
        if not title:
            errors.append(f"chapter_{i}_missing_title")
        if not body:
            errors.append(f"chapter_{i}_missing_content")
            continue
        if len(body) < min_content_chars:
            errors.append(f"chapter_{i}_content_too_short:{len(body)}")
        if "本章标题为，" in body:
            errors.append(f"chapter_{i}_title_placeholder_broken")
        if "\ufffd" in body or "\ufffd" in title:
            errors.append(f"chapter_{i}_encoding_replacement_char")
        # Warn on obvious template repeat.
        if body.count("阶段目标达成后不会立即收束") > 1:
            warn.append(f"chapter_{i}_template_repeat")

    return {
        "ok": len(errors) == 0,
        "errors": errors,
        "warnings": warn,
        "chapter_count_expected": expected,
        "chapter_count_actual": actual,
    }


def _start_server(
    *,
    python_exe: str,
    root: Path,
    model_path: str,
    adapter_path: str,
    served_model: str,
    port: int,
    device: str,
    dtype: str,
    max_new_tokens: int,
    out_log: Path,
    err_log: Path,
) -> subprocess.Popen[Any]:
    cmd = [
        python_exe,
        "deploy/openai_compat_server.py",
        "--model-path",
        model_path,
        "--served-model-name",
        served_model,
        "--adapter-path",
        adapter_path,
        "--host",
        "127.0.0.1",
        "--port",
        str(port),
        "--device",
        device,
        "--dtype",
        dtype,
        "--max-new-tokens",
        str(max_new_tokens),
    ]
    out_log.parent.mkdir(parents=True, exist_ok=True)
    fout = out_log.open("w", encoding="utf-8")
    ferr = err_log.open("w", encoding="utf-8")
    proc = subprocess.Popen(cmd, cwd=str(root), stdout=fout, stderr=ferr)
    # keep handles on proc for later close
    proc._stdout_handle = fout  # type: ignore[attr-defined]
    proc._stderr_handle = ferr  # type: ignore[attr-defined]
    return proc


def _stop_server(proc: Optional[subprocess.Popen[Any]]) -> None:
    if proc is None:
        return
    try:
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=25)
            except Exception:
                if os.name == "nt":
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        check=False,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    proc.kill()
    finally:
        try:
            proc._stdout_handle.close()  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            proc._stderr_handle.close()  # type: ignore[attr-defined]
        except Exception:
            pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Run 3-case detail-outline regression")
    parser.add_argument("--port", type=int, default=54868)
    parser.add_argument("--served-model-name", default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--model-path", default=r"D:\models\Qwen3.5-4B")
    parser.add_argument("--adapter-path", default="outputs/detail_outline_hqcorr_len32_r4_stable_v6/final")
    parser.add_argument("--python-server", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--device", default="auto")
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--max-new-tokens", type=int, default=2600)
    parser.add_argument("--min-content-chars", type=int, default=260)
    parser.add_argument("--request-max-tokens", type=int, default=2800)
    parser.add_argument("--temperature", type=float, default=0.72)
    parser.add_argument("--top-p", type=float, default=0.88)
    parser.add_argument("--timeout-seconds", type=int, default=240)
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument("--skip-start-server", action="store_true")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    logs_dir = (root / args.logs_dir).resolve()
    logs_dir.mkdir(parents=True, exist_ok=True)

    py_server = Path(args.python_server)
    if not py_server.is_absolute():
        py_server = (root / py_server).resolve()
    if not py_server.exists():
        py_server = Path(sys.executable)

    timestamp = int(time.time())
    out_log = logs_dir / f"detail_outline_reg_server_{timestamp}.out.log"
    err_log = logs_dir / f"detail_outline_reg_server_{timestamp}.err.log"

    proc: Optional[subprocess.Popen[Any]] = None
    base_url = f"http://127.0.0.1:{args.port}"
    try:
        if not args.skip_start_server:
            proc = _start_server(
                python_exe=str(py_server),
                root=root,
                model_path=args.model_path,
                adapter_path=args.adapter_path,
                served_model=args.served_model_name,
                port=args.port,
                device=args.device,
                dtype=args.dtype,
                max_new_tokens=args.max_new_tokens,
                out_log=out_log,
                err_log=err_log,
            )
            _wait_health(base_url, timeout_s=1600)

        all_results: List[Dict[str, Any]] = []
        for idx, case in enumerate(_cases(), 1):
            payload = {
                "model": args.served_model_name,
                "messages": [{"role": "user", "content": _build_prompt(case)}],
                "stream": False,
                "max_tokens": args.request_max_tokens,
                "temperature": args.temperature,
                "top_p": args.top_p,
            }
            request_path = logs_dir / f"_detail_outline_reg_case{idx}_{case['name']}_request.json"
            response_path = logs_dir / f"_detail_outline_reg_case{idx}_{case['name']}_response.json"
            content_path = logs_dir / f"_detail_outline_reg_case{idx}_{case['name']}_content.txt"
            request_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

            r = requests.post(f"{base_url}/v1/chat/completions", json=payload, timeout=args.timeout_seconds)
            obj = r.json()
            response_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
            content = str(obj.get("choices", [{}])[0].get("message", {}).get("content", ""))
            content_path.write_text(content, encoding="utf-8")

            validation = _validate_case(case=case, content=content, min_content_chars=args.min_content_chars)
            row = {
                "case_index": idx,
                "case_name": case["name"],
                "http_status": r.status_code,
                "validation": validation,
                "request_file": str(request_path),
                "response_file": str(response_path),
                "content_file": str(content_path),
            }
            all_results.append(row)
            print(
                f"[case{idx}] {case['name']} status={r.status_code} ok={validation['ok']} "
                f"errors={len(validation['errors'])}"
            )

        ok = all(x["validation"]["ok"] for x in all_results)
        report = {
            "ok": ok,
            "timestamp": timestamp,
            "server": {
                "port": args.port,
                "served_model_name": args.served_model_name,
                "model_path": args.model_path,
                "adapter_path": args.adapter_path,
                "device": args.device,
                "dtype": args.dtype,
            },
            "results": all_results,
            "server_logs": {
                "out": str(out_log) if out_log.exists() else "",
                "err": str(err_log) if err_log.exists() else "",
            },
        }
        report_path = logs_dir / f"detail_outline_regression_report_{timestamp}.json"
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report={report_path}")
        return 0 if ok else 2
    finally:
        _stop_server(proc)


if __name__ == "__main__":
    raise SystemExit(main())
