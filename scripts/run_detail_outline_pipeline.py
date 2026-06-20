"""
End-to-end detail-outline pipeline runner:
1) Build detail-outline request pool
2) Generate teacher pairs via DeepSeek
3) Normalize teacher responses
4) Build HQ detail-outline SFT dataset
5) Run resilient SFT training

Supports resume: existing non-empty output files will be skipped by default.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path
from typing import List, Sequence


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def _is_nonempty_file(path: Path) -> bool:
    return path.exists() and path.is_file() and path.stat().st_size > 0


def _run_cmd(cmd: Sequence[str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as fout:
        fout.write(f"\n[{_now()}] CMD: {' '.join(cmd)}\n")
        fout.flush()
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=fout, stderr=fout)
        code = proc.wait()
        fout.write(f"[{_now()}] EXIT: {code}\n")
    if code != 0:
        raise RuntimeError(f"step_failed: {' '.join(cmd)} (exit={code})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run detail-outline data+training pipeline")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--python-api", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--python-train", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--input", nargs="*", default=[])
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--synthetic-count", type=int, default=1200)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--endpoint", default="https://api.deepseek.com/v1/chat/completions")
    parser.add_argument("--upstream-model", default="deepseek-chat")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--sleep-seconds", type=float, default=0.08)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--run-tag", default="detail_outline1000")
    parser.add_argument("--train-preset", default="rtx3080_qwen35_4b_safe")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    api_py = str((root / args.python_api).resolve()) if str(args.python_api).startswith(".\\") else args.python_api
    train_py = str((root / args.python_train).resolve()) if str(args.python_train).startswith(".\\") else args.python_train

    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key:
        raise SystemExit("DEEPSEEK_API_KEY is empty. Please set env var before running pipeline.")

    data_dir = root / "data"
    logs_dir = root / "logs"
    outputs_dir = root / "outputs"

    req_pool = data_dir / f"detail_outline_request_pool_{args.target_count}.jsonl"
    teacher_raw = data_dir / f"detail_outline_teacher_pairs_deepseek_{args.target_count}.jsonl"
    teacher_norm = data_dir / f"detail_outline_teacher_pairs_deepseek_{args.target_count}_norm.jsonl"
    sft_out = data_dir / f"detail_outline_sft_deepseek_{args.target_count}_hq.jsonl"
    sft_report = logs_dir / f"detail_outline_hq_correction_report_{args.target_count}.json"
    train_report = logs_dir / f"train_detail_outline_hqcorr_resilient_{args.run_tag}_report.json"
    train_output_root = outputs_dir / f"detail_outline_hqcorr_resilient_{args.run_tag}"
    run_log = logs_dir / f"pipeline_detail_outline_{args.run_tag}.log"

    default_inputs = [
        data_dir / "novel_task_structured_from_zh_corpus_1500.jsonl",
        data_dir / "novel_task_structured_auto_750.jsonl",
    ]
    if args.input:
        base_inputs = [Path(x) if Path(x).is_absolute() else (root / x) for x in args.input]
    else:
        base_inputs = [p for p in default_inputs if p.exists()]

    if not base_inputs:
        raise SystemExit("No valid input files found for detail-outline request pool.")

    force = bool(args.force)
    resume = bool(args.resume)

    # Step 1: request pool
    if force or not (resume and _is_nonempty_file(req_pool)):
        cmd = [
            api_py,
            "scripts/build_detail_outline_request_pool.py",
            "--input",
            *[str(p) for p in base_inputs],
            "--output",
            str(req_pool),
            "--target-count",
            str(args.target_count),
            "--synthetic-count",
            str(args.synthetic_count),
            "--seed",
            str(args.seed),
        ]
        _run_cmd(cmd, root, run_log)

    # Step 2: teacher generation
    if force or not (resume and _is_nonempty_file(teacher_raw)):
        cmd = [
            api_py,
            "scripts/generate_teacher_pairs_via_api.py",
            "--input",
            str(req_pool),
            "--output",
            str(teacher_raw),
            "--endpoint",
            args.endpoint,
            "--model",
            args.upstream_model,
            "--api-key-env",
            "DEEPSEEK_API_KEY",
            "--timeout-seconds",
            str(args.timeout_seconds),
            "--concurrency",
            str(args.concurrency),
            "--sleep-seconds",
            str(args.sleep_seconds),
            "--max-retries",
            "2",
            "--retry-backoff-seconds",
            "1.8",
            "--max-requests",
            str(args.target_count),
        ]
        _run_cmd(cmd, root, run_log)

    # Step 3: normalize
    if force or not (resume and _is_nonempty_file(teacher_norm)):
        cmd = [
            api_py,
            "scripts/normalize_detail_outline_teacher_pairs.py",
            "--input",
            str(teacher_raw),
            "--output",
            str(teacher_norm),
        ]
        _run_cmd(cmd, root, run_log)

    # Step 4: build sft
    if force or not (resume and _is_nonempty_file(sft_out)):
        cmd = [
            api_py,
            "scripts/build_detail_outline_hq_correction_sft.py",
            "--input",
            str(teacher_norm),
            "--output",
            str(sft_out),
            "--report",
            str(sft_report),
            "--target-count",
            str(args.target_count),
            "--min-chapters",
            "3",
            "--max-chapters",
            "12",
            "--min-chapter-chars",
            "420",
            "--seed",
            str(args.seed),
        ]
        _run_cmd(cmd, root, run_log)

    # Step 5: train
    cmd = [
        train_py,
        "scripts/run_detail_outline_resilient_train.py",
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
        "--attempt-timeout-seconds",
        "9000",
        "--preset",
        args.train_preset,
    ]
    _run_cmd(cmd, root, run_log)

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
