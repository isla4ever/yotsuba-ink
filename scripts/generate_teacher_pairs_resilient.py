"""
Resilient teacher pair generation for OpenAI-compatible APIs.

Designed for unstable or quota-limited upstream providers:
- resume from existing output
- keep retrying network/SSL/transient errors
- detect TPD-like 429 quota limits and cooldown
- optionally cap max_tokens to reduce token pressure

Input JSONL line format:
{"request": {...}, ...}
or
{"messages":[...], "model":"...", "stream":false}

Output JSONL line format:
{"request": {...}, "response": {...}, "meta": {"index": 12, "status": "ok", ...}}
or
{"request": {...}, "meta": {"index": 12, "status": "fail", "error": "..."}}
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests


def _read_jsonl(path: Path):
    with path.open("r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            s = line.strip()
            if not s:
                continue
            try:
                yield i, json.loads(s)
            except Exception as exc:  # noqa: BLE001
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


def _to_payload(req: Dict[str, Any], upstream_model: str, max_tokens_cap: int) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": upstream_model or req.get("model"),
        "messages": req.get("messages", []),
        "stream": False,
    }
    for key in ("temperature", "top_p", "max_tokens", "stop", "repetition_penalty"):
        if key in req:
            payload[key] = req[key]
    if max_tokens_cap > 0:
        old = int(payload.get("max_tokens") or max_tokens_cap)
        payload["max_tokens"] = min(old, max_tokens_cap)
    return payload


def _load_ok_indices(out_path: Path) -> Set[int]:
    out: Set[int] = set()
    if not out_path.exists():
        return out
    for _, row in _read_jsonl(out_path):
        if not isinstance(row, dict):
            continue
        meta = row.get("meta") or {}
        if meta.get("status") == "ok":
            idx = meta.get("index")
            if isinstance(idx, int):
                out.add(idx)
    return out


def _is_tpd_429(resp_text: str) -> bool:
    t = (resp_text or "").lower()
    return "tpd rate limit" in t or ("rate limit" in t and "tpd" in t)


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def main() -> None:
    parser = argparse.ArgumentParser(description="Resilient teacher pair generator")
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--endpoint", required=True)
    parser.add_argument("--model", default="moonshot-v1-8k")
    parser.add_argument("--request-model-default", default="ChiYong-MoE-Novel-18B-A6B")
    parser.add_argument("--api-key", default="")
    parser.add_argument("--api-key-file", default="", help="Read API key from a local text file")
    parser.add_argument("--api-key-env", default="KIMI_API_KEY")
    parser.add_argument("--target-ok", type=int, default=0, help="0 means all requests")
    parser.add_argument("--max-seconds", type=int, default=0, help="0 means no time limit")
    parser.add_argument("--request-timeout-seconds", type=float, default=150.0)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--retry-once-max", type=int, default=2, help="retries per request before marking fail once")
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--tpd-cooldown-seconds", type=int, default=900)
    parser.add_argument("--max-attempts-per-index", type=int, default=10)
    parser.add_argument("--max-tokens-cap", type=int, default=1500)
    parser.add_argument("--status-log-every", type=int, default=20)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    api_key = args.api_key
    if not api_key and args.api_key_file:
        key_path = Path(args.api_key_file)
        if not key_path.is_absolute():
            key_path = Path.cwd() / key_path
        if not key_path.exists():
            raise SystemExit(f"api key file not found: {key_path}")
        api_key = key_path.read_text(encoding="utf-8").strip()
    if not api_key:
        api_key = os.getenv(args.api_key_env, "")
    if not api_key:
        raise SystemExit(f"API key is empty. Set --api-key or env {args.api_key_env}.")

    in_path = Path(args.input)
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows: List[Tuple[int, Dict[str, Any], Dict[str, Any]]] = []
    for idx, rec in _read_jsonl(in_path):
        req = _build_request(rec, default_model=args.request_model_default)
        if req is None:
            continue
        payload = _to_payload(req, upstream_model=args.model, max_tokens_cap=args.max_tokens_cap)
        rows.append((idx, req, payload))
    if not rows:
        raise SystemExit("no valid requests found in input")

    target_ok = args.target_ok if args.target_ok > 0 else len(rows)
    ok_done: Set[int] = _load_ok_indices(out_path) if args.resume else set()
    attempt_map: Dict[int, int] = {}

    start = time.time()
    total = len(rows)
    session = requests.Session()

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    mode = "a" if args.resume and out_path.exists() else "w"
    with out_path.open(mode, encoding="utf-8") as fout:
        cursor = 0
        while len(ok_done) < min(target_ok, total):
            if args.max_seconds > 0 and (time.time() - start) > args.max_seconds:
                print(f"[{_now()}] reach max_seconds, stop.")
                break

            idx, req, payload = rows[cursor]
            cursor = (cursor + 1) % total

            if idx in ok_done:
                continue
            if attempt_map.get(idx, 0) >= args.max_attempts_per_index:
                continue

            attempt_map[idx] = attempt_map.get(idx, 0) + 1

            line: Dict[str, Any]
            success = False
            tpd_hit = False
            err_text = ""

            for at in range(args.retry_once_max + 1):
                try:
                    resp = session.post(
                        args.endpoint,
                        headers=headers,
                        json=payload,
                        timeout=args.request_timeout_seconds,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        line = {
                            "request": req,
                            "response": data,
                            "meta": {
                                "index": idx,
                                "status": "ok",
                                "attempt": attempt_map[idx],
                                "ts": int(time.time()),
                            },
                        }
                        fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                        fout.flush()
                        ok_done.add(idx)
                        success = True
                        break

                    txt = resp.text or ""
                    err_text = f"http_{resp.status_code}: {txt[:600]}"
                    if resp.status_code == 429 and _is_tpd_429(txt):
                        tpd_hit = True
                        break

                    if at < args.retry_once_max:
                        time.sleep(max(0.0, args.retry_backoff_seconds * (2 ** at)))
                        continue
                except Exception as exc:  # noqa: BLE001
                    err_text = f"{type(exc).__name__}: {exc}"
                    if at < args.retry_once_max:
                        time.sleep(max(0.0, args.retry_backoff_seconds * (2 ** at)))
                        continue
                break

            if not success:
                line = {
                    "request": req,
                    "meta": {
                        "index": idx,
                        "status": "fail",
                        "attempt": attempt_map[idx],
                        "error": err_text,
                        "tpd": tpd_hit,
                        "ts": int(time.time()),
                    },
                }
                fout.write(json.dumps(line, ensure_ascii=False) + "\n")
                fout.flush()

                if tpd_hit:
                    print(f"[{_now()}] TPD limit hit; cooldown {args.tpd_cooldown_seconds}s")
                    time.sleep(max(1, args.tpd_cooldown_seconds))
                else:
                    time.sleep(max(0.0, args.sleep_seconds))
            else:
                if len(ok_done) % max(1, args.status_log_every) == 0:
                    elapsed = time.time() - start
                    print(
                        f"[{_now()}] progress ok={len(ok_done)}/{min(target_ok,total)} "
                        f"elapsed={elapsed/60:.1f}m"
                    )
                time.sleep(max(0.0, args.sleep_seconds))

            # If every unfinished index reached attempt cap, stop.
            unfinished = [x for x, _, _ in rows if x not in ok_done]
            if unfinished and all(attempt_map.get(x, 0) >= args.max_attempts_per_index for x in unfinished):
                print(f"[{_now()}] all unfinished indices reached attempt cap; stop.")
                break

    fail_est = total - len(ok_done)
    print(
        f"done total={total} target_ok={min(target_ok,total)} "
        f"ok={len(ok_done)} remaining_est={fail_est} output={out_path}"
    )


if __name__ == "__main__":
    main()
