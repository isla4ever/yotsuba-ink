"""
Simple background monitor for training progress JSONL.

It periodically reads the latest training log entry and appends a compact
progress line to an output log, including a rough ETA from observed speed.
"""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple


def _read_last_json_line(path: Path) -> Optional[dict]:
    if not path.exists() or path.stat().st_size == 0:
        return None
    # Lightweight tail read.
    with path.open("rb") as f:
        f.seek(0, 2)
        size = f.tell()
        block = 4096
        data = b""
        while size > 0:
            step = min(block, size)
            size -= step
            f.seek(size)
            data = f.read(step) + data
            lines = data.splitlines()
            if len(lines) >= 2:
                break
    lines = [x for x in data.splitlines() if x.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1].decode("utf-8"))
    except Exception:
        return None


def _fmt_eta(seconds: float) -> str:
    if seconds < 0:
        seconds = 0
    td = timedelta(seconds=int(seconds))
    return str(td)


def _append(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(text + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor training progress from training_log.jsonl")
    parser.add_argument("--training-log", type=str, required=True)
    parser.add_argument("--output-log", type=str, required=True)
    parser.add_argument("--total-steps", type=int, required=True)
    parser.add_argument("--final-checkpoint", type=str, required=True)
    parser.add_argument("--interval-seconds", type=int, default=300)
    parser.add_argument("--max-hours", type=float, default=8.0)
    args = parser.parse_args()

    training_log = Path(args.training_log)
    output_log = Path(args.output_log)
    final_ckpt = Path(args.final_checkpoint)

    start_wall = time.time()
    first_obs: Optional[Tuple[int, float]] = None
    last_step = -1

    _append(output_log, f"[{datetime.now().isoformat(timespec='seconds')}] monitor_start total_steps={args.total_steps}")

    while True:
        if final_ckpt.exists():
            _append(output_log, f"[{datetime.now().isoformat(timespec='seconds')}] training_finished checkpoint={final_ckpt}")
            break

        elapsed_h = (time.time() - start_wall) / 3600.0
        if elapsed_h >= args.max_hours:
            _append(output_log, f"[{datetime.now().isoformat(timespec='seconds')}] monitor_timeout hours={elapsed_h:.2f}")
            break

        rec = _read_last_json_line(training_log)
        now = time.time()
        if rec and "step" in rec and isinstance(rec.get("step"), int):
            step = int(rec["step"])
            if step > 0:
                if first_obs is None:
                    first_obs = (step, now)
                if step != last_step:
                    last_step = step
                    eta_str = "unknown"
                    if first_obs is not None and step > first_obs[0]:
                        delta_steps = step - first_obs[0]
                        delta_sec = now - first_obs[1]
                        sec_per_step = delta_sec / delta_steps if delta_steps > 0 else 0
                        remain_steps = max(0, args.total_steps - step)
                        eta_str = _fmt_eta(sec_per_step * remain_steps)
                    _append(
                        output_log,
                        (
                            f"[{datetime.now().isoformat(timespec='seconds')}] "
                            f"step={step}/{args.total_steps} "
                            f"epoch={rec.get('train/epoch', rec.get('epoch', 'n/a'))} "
                            f"loss={rec.get('train/loss', rec.get('epoch/train_loss', 'n/a'))} "
                            f"eta={eta_str}"
                        ),
                    )
        else:
            _append(output_log, f"[{datetime.now().isoformat(timespec='seconds')}] waiting_for_training_log")

        time.sleep(max(10, args.interval_seconds))


if __name__ == "__main__":
    main()

