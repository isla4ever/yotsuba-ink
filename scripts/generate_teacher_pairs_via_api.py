"""
Generate teacher request/response pairs via an OpenAI-compatible API (e.g. DeepSeek).

Input JSONL supports one of:
1) {"request": {...}}
2) {"messages": [...], "model": "...", "stream": false}

Output JSONL:
{"request": {...}, "response": {...}, "meta": {"index": 1, "status": "ok"}}
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests


def _read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                yield i, json.loads(s)
            except Exception as exc:
                yield i, {"_parse_error": str(exc), "_raw": s}


def _build_request(record: Dict[str, Any], default_model: str) -> Optional[Dict[str, Any]]:
    if not isinstance(record, dict):
        return None
    if isinstance(record.get("request"), dict):
        req = dict(record["request"])
    elif isinstance(record.get("messages"), list):
        req = {
            "model": record.get("model") or default_model,
            "messages": record["messages"],
            "stream": False,
        }
    else:
        return None
    req["stream"] = False
    if not req.get("model"):
        req["model"] = default_model
    return req


def _to_upstream_payload(req: Dict[str, Any], upstream_model: str) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": upstream_model or req.get("model"),
        "messages": req.get("messages", []),
        "stream": False,
    }
    for key in ("temperature", "top_p", "max_tokens", "stop", "repetition_penalty"):
        if key in req:
            payload[key] = req[key]
    return payload


def _post_once(
    *,
    endpoint: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: float,
) -> Dict[str, Any]:
    resp = requests.post(endpoint, headers=headers, json=payload, timeout=timeout_seconds)
    resp.raise_for_status()
    return resp.json()


def _call_with_retry(
    *,
    endpoint: str,
    headers: Dict[str, str],
    payload: Dict[str, Any],
    timeout_seconds: float,
    max_retries: int,
    retry_backoff_seconds: float,
) -> Dict[str, Any]:
    last_exc: Optional[Exception] = None
    for attempt in range(max_retries + 1):
        try:
            return _post_once(
                endpoint=endpoint,
                headers=headers,
                payload=payload,
                timeout_seconds=timeout_seconds,
            )
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            if attempt >= max_retries:
                break
            sleep_s = retry_backoff_seconds * (2 ** attempt)
            time.sleep(max(0.0, sleep_s))
    raise RuntimeError(f"request_failed_after_retries: {last_exc}")


def _build_jobs(
    *,
    input_path: Path,
    request_model_default: str,
    upstream_model: str,
    max_requests: int,
    skip_first: int,
) -> List[Tuple[int, Dict[str, Any], Dict[str, Any]]]:
    jobs: List[Tuple[int, Dict[str, Any], Dict[str, Any]]] = []
    skipped = 0
    for idx, record in _read_jsonl(input_path):
        if skipped < max(0, int(skip_first)):
            skipped += 1
            continue
        if max_requests and len(jobs) >= max_requests:
            break
        req = _build_request(record, default_model=request_model_default)
        if req is None:
            jobs.append(
                (
                    idx,
                    {},
                    {
                        "meta": {"index": idx, "status": "skip", "reason": "invalid_input_record"},
                        "record": record,
                    },
                )
            )
            continue
        upstream_payload = _to_upstream_payload(req, upstream_model=upstream_model)
        jobs.append((idx, req, upstream_payload))
    return jobs


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate teacher pairs via OpenAI-compatible API")
    parser.add_argument("--input", required=True, help="Input JSONL")
    parser.add_argument("--output", required=True, help="Output JSONL")
    parser.add_argument("--endpoint", required=True, help="Upstream endpoint, e.g. https://api.deepseek.com/v1/chat/completions")
    parser.add_argument("--model", default="deepseek-chat", help="Upstream model")
    parser.add_argument("--request-model-default", default="ChiYong-MoE-Novel-18B-A6B", help="Default model in stored request")
    parser.add_argument("--api-key", default="", help="API key (prefer env)")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY", help="Env var for API key")
    parser.add_argument("--sleep-seconds", type=float, default=0.3, help="Sleep between requests")
    parser.add_argument("--max-requests", type=int, default=0, help="0 means no limit")
    parser.add_argument("--timeout-seconds", type=float, default=90.0)
    parser.add_argument("--concurrency", type=int, default=1, help="Parallel workers for upstream calls")
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--retry-backoff-seconds", type=float, default=1.5)
    parser.add_argument("--append", action="store_true", help="Append mode for resume")
    parser.add_argument("--skip-first", type=int, default=0, help="Skip first N input records (for resume)")
    args = parser.parse_args()

    api_key = args.api_key or os.getenv(args.api_key_env, "")
    if not api_key:
        raise SystemExit(f"API key is empty. Set --api-key or env {args.api_key_env}.")

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    jobs = _build_jobs(
        input_path=in_path,
        request_model_default=args.request_model_default,
        upstream_model=args.model,
        max_requests=args.max_requests,
        skip_first=args.skip_first,
    )

    count = len(jobs)
    ok = 0
    fail = 0

    if count == 0:
        print("done: total=0, ok=0, fail=0, output=", out_path)
        return

    def make_line(idx: int, req: Dict[str, Any], upstream_payload: Dict[str, Any]) -> Dict[str, Any]:
        if not req:
            return upstream_payload
        try:
            data = _call_with_retry(
                endpoint=args.endpoint,
                headers=headers,
                payload=upstream_payload,
                timeout_seconds=args.timeout_seconds,
                max_retries=args.max_retries,
                retry_backoff_seconds=args.retry_backoff_seconds,
            )
            return {"request": req, "response": data, "meta": {"index": idx, "status": "ok"}}
        except Exception as exc:  # noqa: BLE001
            return {"request": req, "meta": {"index": idx, "status": "fail", "error": str(exc)}}

    mode = "a" if args.append else "w"
    with out_path.open(mode, encoding="utf-8") as fout:
        if args.concurrency <= 1:
            for idx, req, upstream_payload in jobs:
                if not req:
                    line = upstream_payload
                    fail += 1
                else:
                    line = make_line(idx, req, upstream_payload)
                    if line.get("meta", {}).get("status") == "ok":
                        ok += 1
                    else:
                        fail += 1
                    time.sleep(max(0.0, args.sleep_seconds))
                fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                fout.flush()
        else:
            with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
                future_map = {}
                for idx, req, upstream_payload in jobs:
                    if not req:
                        line = upstream_payload
                        fail += 1
                        fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                        fout.flush()
                        continue
                    fut = ex.submit(make_line, idx, req, upstream_payload)
                    future_map[fut] = idx
                    if args.sleep_seconds > 0:
                        time.sleep(args.sleep_seconds)
                for fut in concurrent.futures.as_completed(future_map):
                    line = fut.result()
                    if line.get("meta", {}).get("status") == "ok":
                        ok += 1
                    else:
                        fail += 1
                    fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                    fout.flush()

    print(f"done: total={count}, ok={ok}, fail={fail}, output={out_path}")


if __name__ == "__main__":
    main()
