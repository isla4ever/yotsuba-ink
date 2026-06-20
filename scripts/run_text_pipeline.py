"""
End-to-end text pipeline runner (first or non-first chapter):
1) build request pool
2) generate teacher pairs via upstream API (Kimi)
3) normalize teacher output
4) build SFT dataset
5) resilient SFT training
"""

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


def _count_status(path: Path) -> dict[str, int]:
    stats = {"total": 0, "ok": 0, "fail": 0}
    if not path.exists() or path.stat().st_size == 0:
        return stats
    with path.open("r", encoding="utf-8") as f:
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Run text first/non-first pipeline")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--python-api", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--python-train", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--mode", choices=["first", "non_first"], required=True)
    parser.add_argument("--target-count", type=int, required=True)
    parser.add_argument("--raw-count", type=int, required=True)
    parser.add_argument("--synthetic-count", type=int, default=500)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--force", action="store_true")

    parser.add_argument("--endpoint", default="https://api.moonshot.cn/v1/chat/completions")
    parser.add_argument("--upstream-model", default="kimi-k2-0711-preview")
    parser.add_argument("--api-key-env", default="KIMI_API_KEY")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--sleep-seconds", type=float, default=0.35)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)

    parser.add_argument("--request-max-tokens", type=int, default=3200)
    parser.add_argument("--request-temperature", type=float, default=0.82)
    parser.add_argument("--request-top-p", type=float, default=0.92)
    parser.add_argument("--request-min-output-chars", type=int, default=1600)
    parser.add_argument("--norm-min-chars", type=int, default=1100)
    parser.add_argument("--norm-max-chars", type=int, default=4200)
    parser.add_argument("--sft-min-chars", type=int, default=1100)
    parser.add_argument("--sft-max-chars", type=int, default=4200)
    parser.add_argument("--train-timeout-seconds", type=int, default=14400)
    parser.add_argument("--train-preset", default="rtx3080_qwen35_4b_safe")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    api_py = str((root / args.python_api).resolve()) if str(args.python_api).startswith(".\\") else args.python_api
    train_py = str((root / args.python_train).resolve()) if str(args.python_train).startswith(".\\") else args.python_train

    api_key = os.getenv(args.api_key_env, "").strip()
    if not api_key:
        raise SystemExit(f"{args.api_key_env} is empty. Please set it before running.")

    data_dir = root / "data"
    logs_dir = root / "logs"
    outputs_dir = root / "outputs"

    tag = f"text_{args.mode}_{args.target_count}"
    req_pool = data_dir / f"{tag}_request_pool.jsonl"
    teacher_raw = data_dir / f"{tag}_teacher_raw.jsonl"
    teacher_norm = data_dir / f"{tag}_teacher_norm.jsonl"
    sft_out = data_dir / f"{tag}_sft.jsonl"
    norm_report = logs_dir / f"{tag}_normalize_report.json"
    sft_report = logs_dir / f"{tag}_sft_report.json"
    train_report = logs_dir / f"{tag}_train_report.json"
    train_output_root = outputs_dir / f"{tag}_resilient"
    run_log = logs_dir / f"pipeline_{tag}.log"

    input_paths = [
        data_dir / "novel_task_structured_from_zh_corpus_1500.jsonl",
        data_dir / "novel_task_structured_auto_750.jsonl",
        data_dir / "novel_task_structured_template.jsonl",
    ]
    input_paths = [p for p in input_paths if p.exists()]
    if not input_paths:
        raise SystemExit("No input structured jsonl found for text request pool.")

    resume = bool(args.resume)
    force = bool(args.force)

    # Step1 build request pool
    if force or not (resume and _is_nonempty_file(req_pool)):
        cmd = [
            api_py,
            "scripts/build_text_request_pool.py",
            "--input",
            *[str(p) for p in input_paths],
            "--output",
            str(req_pool),
            "--mode",
            args.mode,
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

    # Step2 teacher generation
    teacher_stats = _count_status(teacher_raw)
    if force or teacher_stats["ok"] < args.raw_count:
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
            "--request-timeout-seconds",
            str(args.timeout_seconds),
            "--sleep-seconds",
            str(args.sleep_seconds),
            "--retry-once-max",
            str(args.max_retries),
            "--retry-backoff-seconds",
            str(args.retry_backoff_seconds),
            "--target-ok",
            str(args.raw_count),
            "--max-attempts-per-index",
            "24",
            "--tpd-cooldown-seconds",
            "1200",
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
            f"text teacher generation incomplete: ok={teacher_stats['ok']} target={args.target_count}"
        )

    # Step3 normalize
    if force or not (resume and _is_nonempty_file(teacher_norm)):
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

    # Step4 build sft
    if force or not (resume and _is_nonempty_file(sft_out)):
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

    # Step5 train
    profile = "first" if args.mode == "first" else "non_first"
    cmd = [
        train_py,
        "scripts/run_text_resilient_train.py",
        "--model-path",
        args.model_path,
        "--data",
        str(sft_out),
        "--output-root",
        str(train_output_root),
        "--report",
        str(train_report),
        "--dtype",
        "float16",
        "--timeout-seconds",
        str(args.train_timeout_seconds),
        "--profile",
        profile,
        "--preset",
        args.train_preset,
        "--seed",
        str(args.seed),
    ]
    _run_cmd(cmd, root, run_log)

    print(f"mode={args.mode}")
    print(f"pipeline_log={run_log}")
    print(f"request_pool={req_pool}")
    print(f"teacher_raw={teacher_raw}")
    print(f"teacher_norm={teacher_norm}")
    print(f"sft_out={sft_out}")
    print(f"sft_report={sft_report}")
    print(f"train_report={train_report}")
    print(f"train_output_root={train_output_root}")


if __name__ == "__main__":
    main()
