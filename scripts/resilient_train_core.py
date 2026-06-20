from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from copy import deepcopy
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, Optional


@dataclass
class AttemptConfig:
    name: str
    max_seq_len: int
    grad_accum: int
    lora_r: int
    lora_alpha: int
    lora_target: list[str]
    batch_size: int = 1
    lr: float = 2e-5


@dataclass
class TaskProfile:
    task: str
    preset: str
    dtype: str
    attempt_timeout_seconds: int
    max_acceptable_oom_skips: int
    cooldown_seconds: int
    num_epochs: int = 1
    save_every_epoch: bool = False
    attempts: list[AttemptConfig] = field(default_factory=list)


RTX3080_QWEN35_4B_SAFE: dict[str, TaskProfile] = {
    "info_recommend": TaskProfile(
        task="info_recommend",
        preset="rtx3080_qwen35_4b_safe",
        dtype="float16",
        attempt_timeout_seconds=7200,
        max_acceptable_oom_skips=12,
        cooldown_seconds=12,
        attempts=[
            AttemptConfig("info_recommend_len1024_r8_qv", 1024, 10, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("info_recommend_len896_r8_qv", 896, 10, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("info_recommend_len768_r8_qv", 768, 12, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("info_recommend_len640_r4_qv", 640, 12, 4, 8, ["q_proj", "v_proj"]),
            AttemptConfig("info_recommend_len512_r4_q", 512, 16, 4, 8, ["q_proj"]),
        ],
    ),
    "summary": TaskProfile(
        task="summary",
        preset="rtx3080_qwen35_4b_safe",
        dtype="float16",
        attempt_timeout_seconds=9000,
        max_acceptable_oom_skips=12,
        cooldown_seconds=12,
        attempts=[
            AttemptConfig("summary_len1280_r8_qv", 1280, 10, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("summary_len1152_r8_qv", 1152, 10, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("summary_len1024_r8_qv", 1024, 12, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("summary_len896_r4_qv", 896, 12, 4, 8, ["q_proj", "v_proj"]),
            AttemptConfig("summary_len768_r4_q", 768, 16, 4, 8, ["q_proj"]),
        ],
    ),
    "outline": TaskProfile(
        task="outline",
        preset="rtx3080_qwen35_4b_safe",
        dtype="float16",
        attempt_timeout_seconds=18000,
        max_acceptable_oom_skips=16,
        cooldown_seconds=15,
        attempts=[
            AttemptConfig("outline_len2048_r8_qv", 2048, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("outline_len1792_r8_qv", 1792, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("outline_len1536_r8_qv", 1536, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("outline_len1280_r4_qv", 1280, 10, 4, 8, ["q_proj", "v_proj"]),
            AttemptConfig("outline_len1024_r4_q", 1024, 12, 4, 8, ["q_proj"]),
        ],
    ),
    "detail_outline": TaskProfile(
        task="detail_outline",
        preset="rtx3080_qwen35_4b_safe",
        dtype="float16",
        attempt_timeout_seconds=18000,
        max_acceptable_oom_skips=16,
        cooldown_seconds=15,
        attempts=[
            AttemptConfig("detail_outline_len2048_r8_qv", 2048, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("detail_outline_len1792_r8_qv", 1792, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("detail_outline_len1536_r8_qv", 1536, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("detail_outline_len1280_r4_qv", 1280, 10, 4, 8, ["q_proj", "v_proj"]),
            AttemptConfig("detail_outline_len1024_r4_q", 1024, 12, 4, 8, ["q_proj"]),
        ],
    ),
    "text_first": TaskProfile(
        task="text_first",
        preset="rtx3080_qwen35_4b_safe",
        dtype="float16",
        attempt_timeout_seconds=14400,
        max_acceptable_oom_skips=16,
        cooldown_seconds=15,
        attempts=[
            AttemptConfig("text_first_len2048_r8_qv", 2048, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("text_first_len1792_r8_qv", 1792, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("text_first_len1536_r8_qv", 1536, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("text_first_len1280_r4_qv", 1280, 10, 4, 8, ["q_proj", "v_proj"]),
            AttemptConfig("text_first_len1024_r4_q", 1024, 12, 4, 8, ["q_proj"]),
        ],
    ),
    "text_nonfirst": TaskProfile(
        task="text_nonfirst",
        preset="rtx3080_qwen35_4b_safe",
        dtype="float16",
        attempt_timeout_seconds=18000,
        max_acceptable_oom_skips=16,
        cooldown_seconds=15,
        attempts=[
            AttemptConfig("text_nonfirst_len2048_r8_qv", 2048, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("text_nonfirst_len1792_r8_qv", 1792, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("text_nonfirst_len1536_r8_qv", 1536, 8, 8, 16, ["q_proj", "v_proj"]),
            AttemptConfig("text_nonfirst_len1280_r4_qv", 1280, 10, 4, 8, ["q_proj", "v_proj"]),
            AttemptConfig("text_nonfirst_len1024_r4_q", 1024, 12, 4, 8, ["q_proj"]),
        ],
    ),
}


RTX3080_QWEN35_4B_TEXT_HQ: dict[str, TaskProfile] = {
    "text_first": TaskProfile(
        task="text_first",
        preset="rtx3080_qwen35_4b_text_hq",
        dtype="float16",
        attempt_timeout_seconds=28800,
        max_acceptable_oom_skips=4,
        cooldown_seconds=20,
        num_epochs=1,
        save_every_epoch=True,
        attempts=[
            AttemptConfig("text_first_len2816_r16_qkvo", 2816, 8, 16, 32, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.5e-5),
            AttemptConfig("text_first_len2560_r12_qkvo", 2560, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.5e-5),
            AttemptConfig("text_first_len2304_r8_qkvo", 2304, 10, 8, 16, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.75e-5),
            AttemptConfig("text_first_len2048_r8_qv", 2048, 10, 8, 16, ["q_proj", "v_proj"], lr=2e-5),
        ],
    ),
    "text_nonfirst": TaskProfile(
        task="text_nonfirst",
        preset="rtx3080_qwen35_4b_text_hq",
        dtype="float16",
        attempt_timeout_seconds=36000,
        max_acceptable_oom_skips=4,
        cooldown_seconds=20,
        num_epochs=1,
        save_every_epoch=True,
        attempts=[
            AttemptConfig("text_nonfirst_len2816_r16_qkvo", 2816, 8, 16, 32, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.5e-5),
            AttemptConfig("text_nonfirst_len2560_r12_qkvo", 2560, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.5e-5),
            AttemptConfig("text_nonfirst_len2304_r8_qkvo", 2304, 10, 8, 16, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.75e-5),
            AttemptConfig("text_nonfirst_len2048_r8_qv", 2048, 10, 8, 16, ["q_proj", "v_proj"], lr=2e-5),
        ],
    ),
}


RTX3080_QWEN35_4B_STORY_HQ: dict[str, TaskProfile] = {
    "summary": TaskProfile(
        task="summary",
        preset="rtx3080_qwen35_4b_story_hq",
        dtype="float16",
        attempt_timeout_seconds=10800,
        max_acceptable_oom_skips=10,
        cooldown_seconds=15,
        attempts=[
            AttemptConfig("summary_len1536_r12_qkvo", 1536, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.4e-5),
            AttemptConfig("summary_len1408_r12_qkvo", 1408, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.4e-5),
            AttemptConfig("summary_len1280_r8_qkvo", 1280, 10, 8, 16, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.6e-5),
            AttemptConfig("summary_len1152_r8_qv", 1152, 10, 8, 16, ["q_proj", "v_proj"], lr=1.75e-5),
            AttemptConfig("summary_len1024_r4_qv", 1024, 12, 4, 8, ["q_proj", "v_proj"], lr=2e-5),
        ],
    ),
    "outline": TaskProfile(
        task="outline",
        preset="rtx3080_qwen35_4b_story_hq",
        dtype="float16",
        attempt_timeout_seconds=21600,
        max_acceptable_oom_skips=12,
        cooldown_seconds=18,
        attempts=[
            AttemptConfig("outline_len2304_r12_qkvo", 2304, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.4e-5),
            AttemptConfig("outline_len2048_r12_qkvo", 2048, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.4e-5),
            AttemptConfig("outline_len1792_r8_qkvo", 1792, 8, 8, 16, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.6e-5),
            AttemptConfig("outline_len1536_r8_qv", 1536, 10, 8, 16, ["q_proj", "v_proj"], lr=1.75e-5),
            AttemptConfig("outline_len1280_r4_qv", 1280, 12, 4, 8, ["q_proj", "v_proj"], lr=2e-5),
        ],
    ),
    "detail_outline": TaskProfile(
        task="detail_outline",
        preset="rtx3080_qwen35_4b_story_hq",
        dtype="float16",
        attempt_timeout_seconds=21600,
        max_acceptable_oom_skips=12,
        cooldown_seconds=18,
        attempts=[
            AttemptConfig("detail_outline_len2304_r12_qkvo", 2304, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.4e-5),
            AttemptConfig("detail_outline_len2048_r12_qkvo", 2048, 8, 12, 24, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.4e-5),
            AttemptConfig("detail_outline_len1792_r8_qkvo", 1792, 8, 8, 16, ["q_proj", "k_proj", "v_proj", "o_proj"], lr=1.6e-5),
            AttemptConfig("detail_outline_len1536_r8_qv", 1536, 10, 8, 16, ["q_proj", "v_proj"], lr=1.75e-5),
            AttemptConfig("detail_outline_len1280_r4_qv", 1280, 12, 4, 8, ["q_proj", "v_proj"], lr=2e-5),
        ],
    ),
}


PRESETS: dict[str, dict[str, TaskProfile]] = {
    "rtx3080_qwen35_4b_safe": RTX3080_QWEN35_4B_SAFE,
    "rtx3080_qwen35_4b_text_hq": RTX3080_QWEN35_4B_TEXT_HQ,
    "rtx3080_qwen35_4b_story_hq": RTX3080_QWEN35_4B_STORY_HQ,
}


OOM_PATTERNS = [
    "out of memory",
    "cuda out of memory",
    "cuda error: out of memory",
    "allocation on device",
    "cublas_status_alloc_failed",
    "oom skipped batches",
]

DEVICE_PATTERNS = [
    "device-side assert",
    "illegal memory access",
    "cuda error",
    "device lost",
    "driver shutting down",
    "unspecified launch failure",
]

DATA_PATTERNS = [
    "jsondecodeerror",
    "expecting value",
    "tokenizer",
    "indexerror",
    "keyerror",
]


def available_presets() -> list[str]:
    return sorted(PRESETS.keys())


def available_tasks(preset: str) -> list[str]:
    if preset not in PRESETS:
        raise KeyError(f"unknown preset: {preset}")
    return sorted(PRESETS[preset].keys())


def get_profile(task: str, preset: str) -> TaskProfile:
    if preset not in PRESETS:
        raise KeyError(f"unknown preset: {preset}")
    if task not in PRESETS[preset]:
        raise KeyError(f"unknown task: {task} for preset={preset}")
    return deepcopy(PRESETS[preset][task])


def _safe_read(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def _parse_oom_skipped(text: str) -> Optional[int]:
    match = re.search(r"OOM skipped batches:\s+(\d+)", text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except Exception:
        return None


def _is_complete(text: str) -> bool:
    return ("Training complete!" in text) or ("Training complete" in text and "Training Report" in text)


def _classify_failure(out_text: str, err_text: str, *, return_code: int, timed_out: bool, final_dir_exists: bool) -> str:
    text = f"{out_text}\n{err_text}".lower()
    if timed_out:
        return "timeout"
    if final_dir_exists and return_code == 0:
        return "success_like_but_incomplete"
    if any(p in text for p in OOM_PATTERNS):
        return "oom"
    if any(p in text for p in DEVICE_PATTERNS):
        return "device_failure"
    if any(p in text for p in DATA_PATTERNS):
        return "data_or_format_error"
    if "keyboardinterrupt" in text:
        return "interrupted"
    if "modulenotfounderror" in text or "importerror" in text:
        return "environment_error"
    if return_code == 0:
        return "missing_completion_marker"
    return "unknown_failure"


def _read_last_training_record(training_log_path: Path) -> Optional[dict[str, Any]]:
    if not training_log_path.exists() or training_log_path.stat().st_size == 0:
        return None
    try:
        with training_log_path.open("rb") as f:
            f.seek(0, 2)
            size = f.tell()
            block = 8192
            data = b""
            while size > 0:
                step = min(block, size)
                size -= step
                f.seek(size)
                data = f.read(step) + data
                if data.count(b"\n") >= 2:
                    break
        lines = [line for line in data.splitlines() if line.strip()]
        if not lines:
            return None
        return json.loads(lines[-1].decode("utf-8"))
    except Exception:
        return None


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _build_sft_command(
    *,
    python_exe: str,
    cfg: AttemptConfig,
    model_path: str,
    data_paths: Iterable[str],
    output_dir: Path,
    dtype: str,
    seed: int,
    num_epochs: int,
    save_every_epoch: bool,
) -> list[str]:
    cmd = [
        python_exe,
        "scripts/sft.py",
        "--model-path",
        model_path,
        "--data",
        *list(data_paths),
        "--output-dir",
        str(output_dir),
        "--num-epochs",
        str(num_epochs),
        "--batch-size",
        str(cfg.batch_size),
        "--grad-accum",
        str(cfg.grad_accum),
        "--max-seq-len",
        str(cfg.max_seq_len),
        "--truncate-side",
        "tail",
        "--lr",
        str(cfg.lr),
        "--lora-r",
        str(cfg.lora_r),
        "--lora-alpha",
        str(cfg.lora_alpha),
        "--lora-target",
        *cfg.lora_target,
        "--dtype",
        dtype,
        "--attn-implementation",
        "sdpa",
        "--seed",
        str(seed),
        "--swanlab-mode",
        "disabled",
    ]
    if save_every_epoch:
        cmd.append("--save-every-epoch")
    else:
        cmd.append("--no-save-every-epoch")
    return cmd


def run_task_profile(
    *,
    task: str,
    preset: str,
    python_exe: str,
    model_path: str,
    data_paths: list[str],
    output_root: str,
    logs_dir: str,
    report_path: str,
    seed: int,
    dry_run: bool = False,
    dtype_override: Optional[str] = None,
    timeout_override: Optional[int] = None,
    max_acceptable_oom_skips_override: Optional[int] = None,
    num_epochs_override: Optional[int] = None,
) -> dict[str, Any]:
    profile = get_profile(task, preset)
    if dtype_override:
        profile.dtype = dtype_override
    if timeout_override is not None:
        profile.attempt_timeout_seconds = timeout_override
    if max_acceptable_oom_skips_override is not None:
        profile.max_acceptable_oom_skips = max_acceptable_oom_skips_override
    if num_epochs_override is not None:
        profile.num_epochs = num_epochs_override

    output_root_path = Path(output_root)
    logs_dir_path = Path(logs_dir)
    report_file = Path(report_path)
    attempts_jsonl = logs_dir_path / f"train_{task}_{preset}_attempts.jsonl"

    report: dict[str, Any] = {
        "timestamp": int(time.time()),
        "task": task,
        "preset": preset,
        "model_path": model_path,
        "data": data_paths,
        "dtype": profile.dtype,
        "attempt_timeout_seconds": profile.attempt_timeout_seconds,
        "max_acceptable_oom_skips": profile.max_acceptable_oom_skips,
        "cooldown_seconds": profile.cooldown_seconds,
        "num_epochs": profile.num_epochs,
        "dry_run": dry_run,
        "attempt_plan": [asdict(a) for a in profile.attempts],
        "selected": None,
        "attempts": [],
    }

    if dry_run:
        report_file.parent.mkdir(parents=True, exist_ok=True)
        report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    selected: Optional[dict[str, Any]] = None
    logs_dir_path.mkdir(parents=True, exist_ok=True)
    output_root_path.mkdir(parents=True, exist_ok=True)

    for idx, cfg in enumerate(profile.attempts, start=1):
        ts = int(time.time())
        attempt_name = f"{cfg.name}__{ts}"
        out_dir = output_root_path / attempt_name
        out_log = logs_dir_path / f"train_{attempt_name}.out.log"
        err_log = logs_dir_path / f"train_{attempt_name}.err.log"
        training_log_path = out_dir / "training_log.jsonl"
        final_dir = out_dir / "final"
        cmd = _build_sft_command(
            python_exe=python_exe,
            cfg=cfg,
            model_path=model_path,
            data_paths=data_paths,
            output_dir=out_dir,
            dtype=profile.dtype,
            seed=seed,
            num_epochs=profile.num_epochs,
            save_every_epoch=profile.save_every_epoch,
        )

        start_time = time.time()
        timed_out = False
        with out_log.open("w", encoding="utf-8") as fout, err_log.open("w", encoding="utf-8") as ferr:
            proc = subprocess.Popen(cmd, cwd=str(Path(__file__).resolve().parents[1]), stdout=fout, stderr=ferr)
            try:
                return_code = proc.wait(timeout=max(1, int(profile.attempt_timeout_seconds)))
            except subprocess.TimeoutExpired:
                timed_out = True
                return_code = -9
                try:
                    if os.name == "nt":
                        subprocess.run(
                            ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                            check=False,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                    else:
                        proc.kill()
                except Exception:
                    pass

        out_text = _safe_read(out_log)
        err_text = _safe_read(err_log)
        complete = _is_complete(out_text)
        oom_skipped = _parse_oom_skipped(out_text)
        success = (return_code == 0) and complete and final_dir.exists()
        failure_type = "success" if success else _classify_failure(
            out_text,
            err_text,
            return_code=return_code,
            timed_out=timed_out,
            final_dir_exists=final_dir.exists(),
        )
        last_training_record = _read_last_training_record(training_log_path)
        elapsed_seconds = round(time.time() - start_time, 2)

        record = {
            "attempt_index": idx,
            "started_at": int(start_time),
            "finished_at": int(time.time()),
            "elapsed_seconds": elapsed_seconds,
            "config": asdict(cfg),
            "command": cmd,
            "return_code": return_code,
            "timed_out": timed_out,
            "complete_marker": complete,
            "oom_skipped_batches": oom_skipped,
            "success": success,
            "failure_type": failure_type,
            "output_dir": str(out_dir),
            "final_dir_exists": final_dir.exists(),
            "out_log": str(out_log),
            "err_log": str(err_log),
            "training_log": str(training_log_path),
            "last_training_record": last_training_record,
            "out_tail": out_text[-1600:],
            "err_tail": err_text[-1600:],
        }
        report["attempts"].append(record)
        _append_jsonl(attempts_jsonl, record)

        if success:
            oom = record.get("oom_skipped_batches")
            if oom is None or oom <= profile.max_acceptable_oom_skips:
                selected = record
                break

        if idx < len(profile.attempts) and profile.cooldown_seconds > 0:
            time.sleep(profile.cooldown_seconds)

    report["selected"] = selected
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if selected is not None:
        latest_selected = output_root_path / "latest_selected_run.json"
        latest_selected.write_text(json.dumps(selected, ensure_ascii=False, indent=2), encoding="utf-8")
        return report

    raise SystemExit(1)
