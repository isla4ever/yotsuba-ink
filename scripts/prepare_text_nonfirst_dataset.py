from __future__ import annotations

import argparse
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Sequence


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _is_nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", errors="replace") as f:
        return sum(1 for line in f if line.strip())


def _count_status(path: Path) -> dict[str, int]:
    stats = {"total": 0, "ok": 0, "fail": 0}
    if not path.exists() or path.stat().st_size == 0:
        return stats
    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line in f:
            s = line.strip()
            if not s:
                continue
            stats["total"] += 1
            try:
                obj = json.loads(s)
            except Exception:
                continue
            meta = obj.get("meta") if isinstance(obj, dict) else None
            status = meta.get("status") if isinstance(meta, dict) else None
            if status == "ok":
                stats["ok"] += 1
            elif status == "fail":
                stats["fail"] += 1
    return stats


def _run_cmd(cmd: Sequence[str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n[{_now()}] CMD: {' '.join(cmd)}\n")
        f.flush()
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=f, stderr=f)
        code = proc.wait()
        f.write(f"[{_now()}] EXIT: {code}\n")
    if code != 0:
        raise RuntimeError(f"step_failed: {' '.join(cmd)} (exit={code})")


def _iter_jsonl(path: Path):
    with path.open("r", encoding="utf-8", errors="replace") as f:
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


def _extract_user_prefix(obj: dict) -> str:
    req = obj.get("request")
    if not isinstance(req, dict):
        return ""
    messages = req.get("messages")
    if not isinstance(messages, list):
        return ""
    for msg in messages:
        if isinstance(msg, dict) and msg.get("role") == "user":
            return str(msg.get("content", "") or "").replace("\ufffd", "").strip()[:300]
    return ""


def _source_is_newer(src_paths: list[Path], out_path: Path) -> bool:
    if not out_path.exists():
        return True
    out_mtime = out_path.stat().st_mtime
    return any(src.exists() and src.stat().st_mtime > out_mtime for src in src_paths)


def _merge_local_teacher_sources(src_paths: list[Path], out_path: Path) -> dict[str, int]:
    stats = {"input_total": 0, "ok_rows": 0, "written": 0, "deduped": 0}
    seen_user = set()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as fout:
        for src in src_paths:
            for obj in _iter_jsonl(src):
                stats["input_total"] += 1
                meta = obj.get("meta")
                if not isinstance(meta, dict) or meta.get("status") != "ok":
                    continue
                if not isinstance(obj.get("request"), dict) or not isinstance(obj.get("response"), dict):
                    continue
                stats["ok_rows"] += 1
                user_key = _extract_user_prefix(obj)
                if user_key and user_key in seen_user:
                    stats["deduped"] += 1
                    continue
                if user_key:
                    seen_user.add(user_key)
                fout.write(json.dumps(obj, ensure_ascii=False) + "\n")
                stats["written"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare Kimi-based non-first chapter SFT dataset")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--python-api", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--target-count", type=int, default=960)
    parser.add_argument("--raw-count", type=int, default=1280)
    parser.add_argument("--synthetic-count", type=int, default=1280)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--endpoint", default="https://api.moonshot.cn/v1/chat/completions")
    parser.add_argument("--upstream-model", default="kimi-k2-0711-preview")
    parser.add_argument("--api-key-env", default="KIMI_API_KEY")
    parser.add_argument("--timeout-seconds", type=float, default=150.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.45)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--request-max-tokens", type=int, default=3600)
    parser.add_argument("--request-temperature", type=float, default=0.82)
    parser.add_argument("--request-top-p", type=float, default=0.92)
    parser.add_argument("--request-min-output-chars", type=int, default=2400)
    parser.add_argument("--norm-min-chars", type=int, default=1300)
    parser.add_argument("--norm-max-chars", type=int, default=4600)
    parser.add_argument("--sft-min-chars", type=int, default=1300)
    parser.add_argument("--sft-max-chars", type=int, default=4200)
    parser.add_argument("--ignore-local-teacher-sources", action="store_true")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    api_py = str((root / args.python_api).resolve()) if str(args.python_api).startswith(".\\") else args.python_api

    data_dir = root / "data"
    logs_dir = root / "logs"
    run_log = logs_dir / f"prepare_text_non_first_{args.target_count}.log"

    req_pool = data_dir / f"text_non_first_{args.target_count}_request_pool.jsonl"
    teacher_raw = data_dir / f"text_non_first_{args.target_count}_teacher_raw.jsonl"
    teacher_norm = data_dir / f"text_non_first_{args.target_count}_teacher_norm.jsonl"
    sft_out = data_dir / f"text_non_first_{args.target_count}_sft.jsonl"
    norm_report = logs_dir / f"text_non_first_{args.target_count}_normalize_report.json"
    sft_report = logs_dir / f"text_non_first_{args.target_count}_sft_report.json"
    local_teacher_sources = [
        data_dir / "text_non_first_489_800_hq_temp.jsonl",
        data_dir / "text_non_first_500_teacher_raw_kimi_k2.jsonl",
    ]
    local_teacher_sources = [p for p in local_teacher_sources if p.exists()]
    if args.ignore_local_teacher_sources:
        local_teacher_sources = []

    upstream_changed = False
    if local_teacher_sources:
        if args.force or _source_is_newer(local_teacher_sources, teacher_raw):
            merge_stats = _merge_local_teacher_sources(local_teacher_sources, teacher_raw)
            upstream_changed = True
            with run_log.open("a", encoding="utf-8") as f:
                f.write(f"\n[{_now()}] merged local teacher sources -> {teacher_raw}\n")
                f.write(json.dumps({"local_sources": [str(p) for p in local_teacher_sources], **merge_stats}, ensure_ascii=False) + "\n")
        teacher_stats = _count_status(teacher_raw)
    else:
        if not os.getenv(args.api_key_env, "").strip():
            raise SystemExit(f"{args.api_key_env} is empty. Cannot prepare non-first dataset.")

        input_paths = [
            data_dir / "novel_task_structured_from_zh_corpus_1500.jsonl",
            data_dir / "novel_task_structured_auto_750.jsonl",
            data_dir / "novel_task_structured_template.jsonl",
        ]
        input_paths = [p for p in input_paths if p.exists()]
        if not input_paths:
            raise SystemExit("No input structured jsonl found for non-first request pool.")

        if args.force or not (args.resume and _is_nonempty_file(req_pool)):
            cmd = [
                api_py,
                "scripts/build_text_request_pool.py",
                "--input",
                *[str(p) for p in input_paths],
                "--output",
                str(req_pool),
                "--mode",
                "non_first",
                "--target-count",
                str(args.raw_count),
                "--synthetic-count",
                str(args.synthetic_count),
                "--seed",
                str(args.seed),
                "--max-tokens",
                str(args.request_max_tokens),
                "--temperature",
                str(args.request_temperature),
                "--top-p",
                str(args.request_top_p),
                "--min-output-chars",
                str(args.request_min_output_chars),
            ]
            _run_cmd(cmd, root, run_log)

        teacher_stats = _count_status(teacher_raw)
        if args.force or teacher_stats["ok"] < args.raw_count:
            cmd = [
                api_py,
                "scripts/generate_teacher_pairs_resilient.py",
                "--input",
                str(req_pool),
                "--output",
                str(teacher_raw),
                "--endpoint",
                args.endpoint,
                "--model",
                args.upstream_model,
                "--api-key-env",
                args.api_key_env,
                "--target-ok",
                str(args.raw_count),
                "--request-timeout-seconds",
                str(args.timeout_seconds),
                "--sleep-seconds",
                str(args.sleep_seconds),
                "--retry-once-max",
                str(args.max_retries),
                "--retry-backoff-seconds",
                str(args.retry_backoff_seconds),
                "--tpd-cooldown-seconds",
                "1200",
                "--max-attempts-per-index",
                "24",
                "--max-tokens-cap",
                str(args.request_max_tokens),
                "--status-log-every",
                "10",
                "--resume",
            ]
            _run_cmd(cmd, root, run_log)
            teacher_stats = _count_status(teacher_raw)

    if teacher_stats["ok"] < args.target_count:
        raise RuntimeError(
            f"non-first teacher generation incomplete: ok={teacher_stats['ok']} target={args.target_count}"
        )

    if args.force or upstream_changed or not (args.resume and _is_nonempty_file(teacher_norm)):
        cmd = [
            api_py,
            "scripts/normalize_text_teacher_pairs.py",
            "--input",
            str(teacher_raw),
            "--output",
            str(teacher_norm),
            "--report",
            str(norm_report),
            "--min-chars",
            str(args.norm_min_chars),
            "--max-chars",
            str(args.norm_max_chars),
            "--drop-too-short",
        ]
        _run_cmd(cmd, root, run_log)

    if args.force or upstream_changed or not (args.resume and _is_nonempty_file(sft_out)):
        cmd = [
            api_py,
            "scripts/build_text_sft_from_teacher.py",
            "--input",
            str(teacher_norm),
            "--output",
            str(sft_out),
            "--report",
            str(sft_report),
            "--target-count",
            str(args.target_count),
            "--min-assistant-chars",
            str(args.sft_min_chars),
            "--max-assistant-chars",
            str(args.sft_max_chars),
            "--drop-duplicate-user",
        ]
        _run_cmd(cmd, root, run_log)

    final_count = _count_lines(sft_out)
    if final_count < args.target_count:
        raise RuntimeError(f"non-first SFT dataset too small: count={final_count} target={args.target_count}")

    print(f"request_pool={req_pool}")
    print(f"teacher_raw={teacher_raw}")
    print(f"teacher_ok={teacher_stats['ok']}")
    print(f"teacher_norm={teacher_norm}")
    print(f"sft_out={sft_out}")
    print(f"sft_count={final_count}")
    print(f"run_log={run_log}")


if __name__ == "__main__":
    main()
