from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from resilient_train_core import run_task_profile


TASK_ORDER = [
    "info_recommend",
    "summary",
    "outline",
    "detail_outline",
    "text_first",
    "text_nonfirst",
]


TASK_SPECS: dict[str, dict[str, Any]] = {
    "info_recommend": {"data": "data/info_recommend_sft_deepseek_1000.jsonl", "min_count": 1000},
    "summary": {"data": "data/summary_sft_deepseek_1000_hq_correction_v5_mix1000.jsonl", "min_count": 1000},
    "outline": {"data": "data/outline_sft_deepseek_1000_hq_long_v2.jsonl", "min_count": 1000},
    "detail_outline": {"data": "data/detail_outline_sft_deepseek_1000_hq.jsonl", "min_count": 1000},
    "text_first": {"data": "data/text_first_500_sft.jsonl", "min_count": 500},
    "text_nonfirst": {
        "data": "data/text_non_first_clean_v2_sft.jsonl",
        "min_count": 300,
    },
}


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as f:
        return sum(1 for line in f if line.strip())


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(payload, ensure_ascii=False) + "\n")


def _run_cmd(cmd: list[str], cwd: Path, log_path: Path) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] CMD: {' '.join(cmd)}\n")
        f.flush()
        proc = subprocess.Popen(cmd, cwd=str(cwd), stdout=f, stderr=f)
        code = proc.wait()
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] EXIT: {code}\n")
    if code != 0:
        raise RuntimeError(f"step_failed: {' '.join(cmd)} (exit={code})")


def _resolve_dataset(root: Path, task: str, python_exe: str, log_path: Path) -> Path:
    spec = TASK_SPECS[task]
    dataset_path = root / spec["data"]
    if task == "text_nonfirst" and _count_lines(dataset_path) < spec["min_count"]:
        cmd = [
            python_exe,
            spec["prepare_script"],
            "--project-root",
            str(root),
            "--python-api",
            python_exe,
        ]
        _run_cmd(cmd, root, log_path)
    return dataset_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Managed sequential trainer for the six novel tasks")
    parser.add_argument("--project-root", default=".")
    parser.add_argument("--model-path", default=r"D:\models\Qwen3.5-4B")
    parser.add_argument("--preset", default="rtx3080_qwen35_4b_safe")
    parser.add_argument("--dtype", default="float16", choices=["float16", "bfloat16", "float32"])
    parser.add_argument("--seed", type=int, default=2026)
    parser.add_argument("--num-epochs", type=int, default=1)
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--start-from", choices=TASK_ORDER, default=TASK_ORDER[0])
    parser.add_argument("--status-file", default="logs/managed_novel_training_status.json")
    parser.add_argument("--history-file", default="logs/managed_novel_training_history.jsonl")
    parser.add_argument("--supervisor-log", default="logs/managed_novel_training_supervisor.log")
    args = parser.parse_args()

    root = Path(args.project_root).resolve()
    model_path = Path(args.model_path)
    if not model_path.exists():
        raise SystemExit(f"model path not found: {model_path}")

    status_path = root / args.status_file
    history_path = root / args.history_file
    supervisor_log = root / args.supervisor_log

    state = _load_json(status_path) or {"tasks": {}}
    state["status"] = "running"
    state["current_task"] = args.start_from
    state["updated_at"] = int(time.time())
    state["model_path"] = str(model_path)
    state["preset"] = args.preset
    state["dtype"] = args.dtype
    state.pop("pause_reason", None)
    state.pop("stopped_after_task", None)
    state.pop("last_error", None)
    _write_json(status_path, state)

    start_index = TASK_ORDER.index(args.start_from)
    for task in TASK_ORDER[start_index:]:
        state = _load_json(status_path) or {"tasks": {}}
        if state.get("tasks", {}).get(task, {}).get("status") == "completed":
            continue

        dataset_path = _resolve_dataset(root, task, args.python_exe, supervisor_log)
        dataset_count = _count_lines(dataset_path)
        min_count = TASK_SPECS[task]["min_count"]
        if dataset_count < min_count:
            raise RuntimeError(f"{task} dataset not ready: {dataset_path} count={dataset_count} min={min_count}")

        output_root = root / "outputs" / f"managed_{task}_resilient"
        report_path = root / "logs" / f"managed_train_{task}_report.json"

        state["current_task"] = task
        state["updated_at"] = int(time.time())
        state.setdefault("tasks", {})[task] = {
            "status": "running",
            "dataset": str(dataset_path),
            "dataset_count": dataset_count,
            "started_at": int(time.time()),
        }
        _write_json(status_path, state)
        _append_jsonl(history_path, {"ts": int(time.time()), "task": task, "event": "started", "dataset": str(dataset_path), "dataset_count": dataset_count})

        report = run_task_profile(
            task=task,
            preset=args.preset,
            python_exe=args.python_exe,
            model_path=str(model_path),
            data_paths=[str(dataset_path)],
            output_root=str(output_root),
            logs_dir=str(root / "logs"),
            report_path=str(report_path),
            seed=args.seed,
            dtype_override=args.dtype,
            num_epochs_override=args.num_epochs,
        )

        selected = report.get("selected")
        if not selected:
            raise RuntimeError(f"{task} training finished without a selected run")

        state = _load_json(status_path) or {"tasks": {}}
        state.setdefault("tasks", {})[task] = {
            "status": "completed",
            "dataset": str(dataset_path),
            "dataset_count": dataset_count,
            "completed_at": int(time.time()),
            "selected_output_dir": selected.get("output_dir"),
            "selected_final_dir": str(Path(selected["output_dir"]) / "final"),
            "report_path": str(report_path),
        }
        state["updated_at"] = int(time.time())
        _write_json(status_path, state)
        _append_jsonl(history_path, {"ts": int(time.time()), "task": task, "event": "completed", "selected_output_dir": selected.get("output_dir")})

    state = _load_json(status_path) or {"tasks": {}}
    state["status"] = "completed"
    state["current_task"] = None
    state["updated_at"] = int(time.time())
    _write_json(status_path, state)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        root = Path(".").resolve()
        status_path = root / "logs/managed_novel_training_status.json"
        state = _load_json(status_path) or {"tasks": {}}
        state["status"] = "blocked"
        state["updated_at"] = int(time.time())
        state["last_error"] = str(exc)
        _write_json(status_path, state)
        raise
