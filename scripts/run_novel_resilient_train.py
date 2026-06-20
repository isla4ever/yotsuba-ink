from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from resilient_train_core import available_presets, available_tasks, run_task_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Generic resilient LoRA trainer for novel tasks")
    parser.add_argument("--task", required=True)
    parser.add_argument("--preset", default="rtx3080_qwen35_4b_safe", choices=available_presets())
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--data", nargs="+", required=True)
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument("--report", required=True)
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--dtype", default=None, choices=[None, "float16", "bfloat16", "float32"])
    parser.add_argument("--attempt-timeout-seconds", type=int, default=None)
    parser.add_argument("--max-acceptable-oom-skips", type=int, default=None)
    parser.add_argument("--num-epochs", type=int, default=None)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    valid_tasks = available_tasks(args.preset)
    if args.task not in valid_tasks:
        raise SystemExit(f"task={args.task} is not supported by preset={args.preset}; valid={valid_tasks}")

    report = run_task_profile(
        task=args.task,
        preset=args.preset,
        python_exe=args.python_exe,
        model_path=args.model_path,
        data_paths=args.data,
        output_root=args.output_root,
        logs_dir=args.logs_dir,
        report_path=args.report,
        seed=args.seed,
        dry_run=bool(args.dry_run),
        dtype_override=args.dtype,
        timeout_override=args.attempt_timeout_seconds,
        max_acceptable_oom_skips_override=args.max_acceptable_oom_skips,
        num_epochs_override=args.num_epochs,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
