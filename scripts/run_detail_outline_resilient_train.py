from __future__ import annotations

import argparse
import json
import sys

from resilient_train_core import run_task_profile


def main() -> None:
    parser = argparse.ArgumentParser(description="Resilient detail-outline trainer for RTX 3080")
    parser.add_argument("--model-path", required=True)
    parser.add_argument("--data", nargs="+", required=True)
    parser.add_argument("--output-root", default="outputs/detail_outline_hqcorr_resilient")
    parser.add_argument("--logs-dir", default="logs")
    parser.add_argument("--report", default="logs/train_detail_outline_hqcorr_resilient_report.json")
    parser.add_argument("--dtype", default=None, choices=[None, "float16", "bfloat16", "float32"])
    parser.add_argument("--max-acceptable-oom-skips", type=int, default=None)
    parser.add_argument("--attempt-timeout-seconds", type=int, default=None)
    parser.add_argument("--preset", default="rtx3080_qwen35_4b_safe")
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--num-epochs", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    report = run_task_profile(
        task="detail_outline",
        preset=args.preset,
        python_exe=sys.executable,
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
