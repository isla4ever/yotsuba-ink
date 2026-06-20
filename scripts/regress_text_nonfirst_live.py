from __future__ import annotations

import argparse
import json
import os
import hashlib
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import requests


BAD_PHRASES = (
    "请根据以上信息",
    "当前章需要承接并推进",
    "章末钩子",
    "主要舞台集中于",
    "本章要留下",
    "下一章",
    "\\",
)


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


def _extract_user_text(item: Dict[str, Any]) -> str:
    messages = item.get("messages") or []
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content", "") or "")
    return ""


def _extract_assistant_text(item: Dict[str, Any]) -> str:
    messages = item.get("messages") or []
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "assistant":
            return str(msg.get("content", "") or "")
    return ""


def _pick_cases(dataset_path: Path, wanted: int) -> List[Dict[str, Any]]:
    buckets: List[Tuple[str, Tuple[str, ...]]] = [
        ("xianxia", ("仙侠", "武侠")),
        ("scifi", ("科幻", "未来", "星际")),
        ("suspense", ("悬疑", "现实", "都市")),
    ]
    selected: List[Dict[str, Any]] = []
    seen_keys = set()
    bucket_hit = {name: False for name, _ in buckets}
    rows: List[Dict[str, Any]] = []
    with dataset_path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rows.append(json.loads(line))

    for bucket_name, keywords in buckets:
        for row in rows:
            user_text = _extract_user_text(row)
            if any(k in user_text for k in keywords):
                key = hashlib.md5(user_text.encode("utf-8", errors="ignore")).hexdigest()
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                row["_bucket"] = bucket_name
                selected.append(row)
                bucket_hit[bucket_name] = True
                break

    if len(selected) < wanted:
        for row in rows:
            user_text = _extract_user_text(row)
            key = hashlib.md5(user_text.encode("utf-8", errors="ignore")).hexdigest()
            if key in seen_keys:
                continue
            seen_keys.add(key)
            row["_bucket"] = "fallback"
            selected.append(row)
            if len(selected) >= wanted:
                break
    return selected[:wanted]


def _run_one_case(base_url: str, model_name: str, case: Dict[str, Any], timeout_seconds: int) -> Dict[str, Any]:
    user_text = _extract_user_text(case)
    ref_text = _extract_assistant_text(case)
    req = {
        "model": model_name,
        "messages": [{"role": "user", "content": user_text}],
        "stream": True,
    }
    url = f"{base_url}/v1/chat/completions"
    merged: List[str] = []
    parsed_chunks = 0
    done = False
    status = None
    err = ""
    first_chunk_seconds = None
    t0 = time.time()
    try:
        with requests.post(url, json=req, timeout=timeout_seconds, stream=True) as r:
            status = r.status_code
            if status != 200:
                err = r.text[:1200]
            else:
                for raw in r.iter_lines(decode_unicode=True):
                    if raw is None:
                        continue
                    line = str(raw).strip()
                    if not line.startswith("data: "):
                        continue
                    payload = line[6:]
                    if payload == "[DONE]":
                        done = True
                        break
                    try:
                        obj = json.loads(payload)
                    except Exception:
                        continue
                    parsed_chunks += 1
                    choices = obj.get("choices") or []
                    if not choices:
                        continue
                    delta = (choices[0] or {}).get("delta") or {}
                    text = delta.get("content")
                    if isinstance(text, str) and text:
                        if first_chunk_seconds is None:
                            first_chunk_seconds = round(time.time() - t0, 2)
                        merged.append(text)
    except Exception as exc:  # noqa: BLE001
        err = f"{type(exc).__name__}: {exc}"

    content = "".join(merged).strip()
    bad_hits = [p for p in BAD_PHRASES if p in content]
    ends_ok = bool(content) and content[-1] in "。！？!?”’」』"
    valid = (
        status == 200
        and done
        and parsed_chunks > 0
        and len(content) >= 900
        and not bad_hits
    )
    return {
        "bucket": case.get("_bucket", "unknown"),
        "status_code": status,
        "first_chunk_seconds": first_chunk_seconds,
        "elapsed_seconds": round(time.time() - t0, 2),
        "parsed_chunks": parsed_chunks,
        "done_marker": done,
        "content_len": len(content),
        "ref_len": len(ref_text),
        "ends_ok": ends_ok,
        "bad_phrase_hits": bad_hits,
        "valid": valid,
        "error": err,
        "prompt_head": user_text[:220],
        "content_preview": content[:300],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Live regression for non-first chapter streaming generation")
    parser.add_argument("--dataset", required=True)
    parser.add_argument("--adapter-path", required=True)
    parser.add_argument("--model-path", default=r"D:\models\Qwen3.5-4B")
    parser.add_argument("--python-exe", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=54870)
    parser.add_argument("--dtype", default="float16")
    parser.add_argument("--max-new-tokens", type=int, default=1400)
    parser.add_argument("--served-model-name", default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--case-count", type=int, default=3)
    parser.add_argument("--startup-timeout-seconds", type=int, default=240)
    parser.add_argument("--request-timeout-seconds", type=int, default=900)
    parser.add_argument("--logs-dir", default="logs")
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]
    logs_dir = root / args.logs_dir
    logs_dir.mkdir(parents=True, exist_ok=True)
    ts = _now_ts()
    out_log = logs_dir / f"regress_text_nonfirst_server_{ts}.out.log"
    err_log = logs_dir / f"regress_text_nonfirst_server_{ts}.err.log"
    report_path = logs_dir / f"regress_text_nonfirst_report_{ts}.json"
    dataset_path = (root / args.dataset).resolve()

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

    cases = _pick_cases(dataset_path, args.case_count)
    base_url = f"http://{args.host}:{args.port}"
    results: List[Dict[str, Any]] = []
    server_proc = None
    all_passed = False
    try:
        with out_log.open("w", encoding="utf-8") as fout, err_log.open("w", encoding="utf-8") as ferr:
            server_proc = subprocess.Popen(cmd, cwd=str(root), stdout=fout, stderr=ferr)
            if not _wait_health(base_url, timeout_seconds=args.startup_timeout_seconds):
                raise RuntimeError("server_start_timeout")
            for case in cases:
                results.append(
                    _run_one_case(
                        base_url=base_url,
                        model_name=args.served_model_name,
                        case=case,
                        timeout_seconds=args.request_timeout_seconds,
                    )
                )
            all_passed = all(x.get("valid") for x in results)
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
        "dataset": str(dataset_path),
        "adapter_path": args.adapter_path,
        "model_path": args.model_path,
        "served_model_name": args.served_model_name,
        "base_url": base_url,
        "server_out_log": str(out_log),
        "server_err_log": str(err_log),
        "all_passed": all_passed,
        "cases": results,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
