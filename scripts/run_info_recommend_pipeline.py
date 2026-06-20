from __future__ import annotations

import argparse
import os
import subprocess
import time
from pathlib import Path
from typing import Sequence


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
    parser = argparse.ArgumentParser(description="Run info-recommend data+training pipeline")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--python-api", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--python-train", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--target-count", type=int, default=1000)
    parser.add_argument("--synthetic-count", type=int, default=1400)
    parser.add_argument("--resume", action="store_true", default=True)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--endpoint", default="https://api.deepseek.com/v1/chat/completions")
    parser.add_argument("--upstream-model", default="deepseek-chat")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--sleep-seconds", type=float, default=0.35)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--run-tag", default="info_recommend1000")
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

    req_pool = data_dir / f"info_recommend_request_pool_{args.target_count}.jsonl"
    teacher_raw = data_dir / f"info_recommend_teacher_pairs_deepseek_{args.target_count}.jsonl"
    teacher_norm = data_dir / f"info_recommend_teacher_pairs_deepseek_{args.target_count}_normalized_rtx3080.jsonl"
    sft_out = data_dir / f"info_recommend_sft_deepseek_{args.target_count}_rtx3080.jsonl"
    train_report = logs_dir / f"train_info_recommend_resilient_{args.run_tag}_report.json"
    train_output_root = outputs_dir / f"info_recommend_resilient_{args.run_tag}"
    run_log = logs_dir / f"pipeline_info_recommend_{args.run_tag}.log"

    base_inputs = [
        data_dir / "novel_task_structured_from_zh_corpus_1500.jsonl",
        data_dir / "novel_task_structured_auto_750.jsonl",
        data_dir / "novel_task_structured_template.jsonl",
    ]
    base_inputs = [p for p in base_inputs if p.exists()]
    if not base_inputs:
        raise SystemExit("No input structured jsonl found for info_recommend request pool.")

    force = bool(args.force)
    resume = bool(args.resume)

    if force or not (resume and _is_nonempty_file(req_pool)):
        cmd = [
            api_py,
            "scripts/build_info_recommend_request_pool.py",
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
            "--max-tokens",
            "1200",
        ]
        _run_cmd(cmd, root, run_log)

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
            "3",
            "--retry-backoff-seconds",
            "2.0",
            "--max-requests",
            str(args.target_count),
        ]
        _run_cmd(cmd, root, run_log)

    if force or not (resume and _is_nonempty_file(teacher_norm)):
        cmd = [
            api_py,
            "scripts/normalize_info_teacher_pairs.py",
            "--input",
            str(teacher_raw),
            "--output",
            str(teacher_norm),
        ]
        _run_cmd(cmd, root, run_log)

    if force or not (resume and _is_nonempty_file(sft_out)):
        cmd = [
            api_py,
            "scripts/build_novel_sft_dataset.py",
            "--input",
            str(teacher_norm),
            "--output",
            str(sft_out),
            "--dedupe",
            "--min-assistant-chars",
            "320",
        ]
        _run_cmd(cmd, root, run_log)

    cmd = [
        train_py,
        "scripts/run_info_recommend_resilient_train.py",
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
        "--preset",
        args.train_preset,
    ]
    _run_cmd(cmd, root, run_log)

    print(f"pipeline_log={run_log}")
    print(f"request_pool={req_pool}")
    print(f"teacher_raw={teacher_raw}")
    print(f"teacher_norm={teacher_norm}")
    print(f"sft_out={sft_out}")
    print(f"train_report={train_report}")
    print(f"train_output_root={train_output_root}")


if __name__ == "__main__":
    main()
