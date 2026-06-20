# RTX 3080 Training Notes

This repository is now refit for a local RTX 3080 + Qwen3.5-4B workflow.

## Default assumptions

- Python env: `.venv`
- Base model path: `D:\models\Qwen3.5-4B`
- Training dtype: `float16`
- LoRA default: low-risk CUDA preset with automatic fallback

## Main training entry

Use the generic resilient trainer:

```powershell
.\examples\novel_sft_windows.ps1 `
  -Task summary `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -TrainData "data\summary_sft_deepseek_1000_hq_correction_v5_mix1000.jsonl"
```

Supported tasks:

- `info_recommend`
- `summary`
- `outline`
- `detail_outline`
- `text_first`
- `text_nonfirst`

## Auto fallback behavior

The new resilient trainer will automatically retry with smaller configs when a run fails.

Fallback order includes:

- lower `max_seq_len`
- lower `lora_r`
- fewer `lora_target` modules
- longer cooldown between attempts

It does not silently overwrite older successful outputs. Each attempt gets a timestamped output directory.

## Logs and reports

For each run:

- main report: `logs/train_<task>_resilient_report.json`
- per-attempt log index: `logs/train_<task>_rtx3080_qwen35_4b_safe_attempts.jsonl`
- stdout/stderr per attempt: `logs/train_<attempt_name>.out.log` and `logs/train_<attempt_name>.err.log`
- selected successful run pointer: `outputs/<task>_resilient/latest_selected_run.json`

Inside each training output directory:

- trainer log: `training_log.jsonl`
- final adapter: `final\`

## Server defaults

The local OpenAI-compatible server is now aligned to RTX 3080 defaults:

- `dtype=float16`
- `max_new_tokens=1664`
- PowerShell startup script no longer uses the reserved `$Host` variable

Run:

```powershell
.\examples\run_local_openai_server_windows.ps1 `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -AdapterPath "outputs\summary_resilient\summary_len224_r8_qv__<timestamp>\final"
```

## Recommended workflow

1. Rebuild `.venv` on the 3080 machine with CUDA-capable PyTorch.
2. Copy `data\`, `scripts\`, `examples\`, `deploy\`, and the final selected `outputs\...`.
3. Run `.\examples\novel_sft_windows.ps1 -DryRun` first to inspect the attempt ladder.
4. Run the real training job.
5. Use `latest_selected_run.json` to know which adapter path should be served.
