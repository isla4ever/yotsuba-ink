"""
Run full text pipeline for both:
1) first chapter (target 500)
2) non-first chapter (target 745)
"""

from __future__ import annotations

import argparse
import subprocess
import time
from pathlib import Path
from typing import Sequence


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


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
    parser = argparse.ArgumentParser(description="Run first+non-first text pipelines")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--python-api", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--python-train", default=r".\.venv\Scripts\python.exe")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--endpoint", default="https://api.moonshot.cn/v1/chat/completions")
    parser.add_argument("--upstream-model", default="kimi-k2-0711-preview")
    parser.add_argument("--api-key-env", default="KIMI_API_KEY")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--train-timeout-seconds", type=int, default=14400)
    parser.add_argument("--train-preset", default="rtx3080_qwen35_4b_safe")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    run_log = root / "logs" / "pipeline_text_full.log"

    api_py = str((root / args.python_api).resolve()) if str(args.python_api).startswith(".\\") else args.python_api
    train_py = str((root / args.python_train).resolve()) if str(args.python_train).startswith(".\\") else args.python_train

    common = [
        "--project-root",
        str(root),
        "--python-api",
        api_py,
        "--python-train",
        train_py,
        "--model-path",
        args.model_path,
        "--endpoint",
        args.endpoint,
        "--upstream-model",
        args.upstream_model,
        "--api-key-env",
        args.api_key_env,
        "--seed",
        str(args.seed),
        "--train-timeout-seconds",
        str(args.train_timeout_seconds),
        "--train-preset",
        args.train_preset,
    ]
    if args.force:
        common.append("--force")

    cmd_first = [
        api_py,
        "scripts/run_text_pipeline.py",
        *common,
        "--mode",
        "first",
        "--target-count",
        "500",
        "--raw-count",
        "650",
        "--synthetic-count",
        "700",
        "--request-min-output-chars",
        "1800",
        "--request-max-tokens",
        "3200",
        "--norm-min-chars",
        "900",
        "--norm-max-chars",
        "3800",
        "--sft-min-chars",
        "900",
        "--sft-max-chars",
        "3600",
    ]

    cmd_non = [
        api_py,
        "scripts/run_text_pipeline.py",
        *common,
        "--mode",
        "non_first",
        "--target-count",
        "745",
        "--raw-count",
        "900",
        "--synthetic-count",
        "900",
        "--request-min-output-chars",
        "2200",
        "--request-max-tokens",
        "3600",
        "--norm-min-chars",
        "1100",
        "--norm-max-chars",
        "4600",
        "--sft-min-chars",
        "1100",
        "--sft-max-chars",
        "4200",
    ]

    _run_cmd(cmd_first, root, run_log)
    _run_cmd(cmd_non, root, run_log)
    print(f"done, full_log={run_log}")


if __name__ == "__main__":
    main()
