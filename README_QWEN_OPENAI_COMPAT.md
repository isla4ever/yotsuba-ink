# Qwen3.5-4B OpenAI-Compatible Service + SFT Workflow

This repository now includes a local OpenAI-compatible chat API that can keep your Spring Boot logic unchanged (`POST /v1/chat/completions`, `stream=true/false`).

## 1) Install dependencies

```powershell
pip install -r requirements.txt
```

## 2) Start local API server

PowerShell:

```powershell
.\examples\run_local_openai_server_windows.ps1 `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -ServedModelName "ChiYong-MoE-Novel-18B-A6B" `
  -Port 54862
```

Direct Python:

```powershell
python deploy/openai_compat_server.py `
  --model-path "D:\models\Qwen3.5-4B" `
  --served-model-name "ChiYong-MoE-Novel-18B-A6B" `
  --host 0.0.0.0 --port 54862
```

### Optional: route non-stream tasks to DeepSeek (upstream fallback)

Set API key in env (do not hardcode in source):

```powershell
$env:DEEPSEEK_API_KEY="your_real_key"
```

Run with upstream routing enabled:

```powershell
python deploy/openai_compat_server.py `
  --model-path "D:\models\Qwen3.5-4B" `
  --served-model-name "ChiYong-MoE-Novel-18B-A6B" `
  --host 0.0.0.0 --port 54862 `
  --upstream-endpoint "https://api.deepseek.com/v1/chat/completions" `
  --upstream-model "deepseek-chat" `
  --upstream-api-key-env "DEEPSEEK_API_KEY" `
  --upstream-nonstream-tasks "info_recommend,summary,outline,detail_outline"
```

Notes:
- Stream requests still go local by default.
- For `info_recommend`, response `content` is normalized to fixed sections:
  `**人物信息**` / `**故事背景**` / `**简介**` and ends with `<|im_end|>`.

### API contract

- Endpoint: `POST /v1/chat/completions`
- Input fields supported:
  - `model`, `messages`, `stream`
  - `max_tokens`, `temperature`, `top_p`, `repetition_penalty`, `stop`
- Output format:
  - non-stream: OpenAI chat completion JSON
  - stream: SSE chunks with `chat.completion.chunk` and `delta`

## 3) Keep Spring backend unchanged

Your existing Java code can continue to call:

```java
.uri("/v1/chat/completions")
```

Only ensure `baseUrl` points to your local service, for example:

```java
.baseUrl("http://127.0.0.1:54862")
```

You can still send the old model name (`ChiYong-MoE-Novel-18B-A6B`); the server accepts it and serves Qwen locally.

## 4) Build SFT data from teacher request/response logs

Prepare input JSONL with one pair per line, for example:

```json
{"request": {...}, "response": {...}}
```

or:

```json
{"request_body":"{...}", "stream_response":"data: {...}\n\ndata: [DONE]"}
```

Convert:

```powershell
python scripts/build_novel_sft_dataset.py `
  --input data\teacher_pairs.jsonl `
  --output data\novel_sft_train.jsonl `
  --dedupe
```

Output format is compatible with `scripts/sft.py`:

```json
{"messages":[{"role":"user","content":"..."},{"role":"assistant","content":"..."}]}
```

### 4.0) Generate teacher pairs directly via DeepSeek API

```powershell
$env:DEEPSEEK_API_KEY="your_real_key"

python scripts/generate_teacher_pairs_via_api.py `
  --input data\teacher_request_only.jsonl `
  --output data\teacher_pairs_deepseek.jsonl `
  --endpoint "https://api.deepseek.com/v1/chat/completions" `
  --model "deepseek-chat" `
  --api-key-env "DEEPSEEK_API_KEY" `
  --concurrency 8 `
  --max-retries 3
```

Then convert generated pairs to SFT JSONL:

```powershell
python scripts/build_novel_sft_dataset.py `
  --input data\teacher_pairs_deepseek.jsonl `
  --output data\novel_sft_train_from_deepseek.jsonl `
  --dedupe
```

### 4.0.1) Info-recommend specialized data pipeline (recommended)

Build a request-only pool (high-format constraints, long-form output):

```powershell
python scripts/build_info_recommend_request_pool.py `
  --input data\novel_task_structured_from_zh_corpus_1500.jsonl data\novel_task_structured_auto_750.jsonl `
  --output data\info_recommend_request_pool_1800.jsonl `
  --target-count 1800 `
  --synthetic-count 1800
```

Generate 1000 DeepSeek teacher pairs:

```powershell
python scripts/generate_teacher_pairs_via_api.py `
  --input data\info_recommend_request_pool_1800.jsonl `
  --output data\info_recommend_teacher_pairs_deepseek_1000.jsonl `
  --endpoint "https://api.deepseek.com/v1/chat/completions" `
  --model "deepseek-chat" `
  --api-key-env "DEEPSEEK_API_KEY" `
  --max-requests 1000 `
  --concurrency 8 `
  --max-retries 3
```

Normalize output style to fixed `人物信息/故事背景/简介` format and train:

```powershell
python scripts/normalize_info_teacher_pairs.py `
  --input data\info_recommend_teacher_pairs_deepseek_1000.jsonl `
  --output data\info_recommend_teacher_pairs_deepseek_1000_normalized.jsonl

python scripts/build_novel_sft_dataset.py `
  --input data\info_recommend_teacher_pairs_deepseek_1000_normalized.jsonl `
  --output data\info_recommend_sft_deepseek_1000_norm_clean.jsonl `
  --dedupe `
  --min-assistant-chars 240

.\.venv\Scripts\python.exe scripts/sft.py `
  --model-path "D:\models\Qwen3.5-4B" `
  --data data\info_recommend_sft_deepseek_1000_norm_clean.jsonl `
  --output-dir outputs\info_recommend_deepseek_sft_1000_xpu_v2 `
  --num-epochs 1 `
  --lr 2e-5 `
  --batch-size 1 `
  --grad-accum 32 `
  --max-seq-len 32 `
  --truncate-side tail `
  --lora-r 8 `
  --lora-alpha 16 `
  --lora-target q_proj k_proj v_proj o_proj `
  --dtype float16 `
  --swanlab-mode disabled
```

### 4.0.2) Summary (梗概) specialized DeepSeek pipeline (stable schema)

Build request-only pool for summary task:

```powershell
python scripts/build_summary_request_pool.py `
  --input data\novel_task_structured_from_zh_corpus_1500.jsonl data\novel_task_structured_auto_750.jsonl `
  --output data\summary_request_pool_2000.jsonl `
  --target-count 2000 `
  --synthetic-count 2000
```

Generate 1200 DeepSeek teacher pairs:

```powershell
python scripts/generate_teacher_pairs_via_api.py `
  --input data\summary_request_pool_2000.jsonl `
  --output data\summary_teacher_pairs_deepseek_1200.jsonl `
  --endpoint "https://api.deepseek.com/v1/chat/completions" `
  --model "deepseek-chat" `
  --api-key-env "DEEPSEEK_API_KEY" `
  --max-requests 1200 `
  --concurrency 8 `
  --max-retries 3
```

Normalize to fixed summary schema:
`[{'主要人物和他们的行为': {...}, '内容': '...'}]`

```powershell
python scripts/normalize_summary_teacher_pairs.py `
  --input data\summary_teacher_pairs_deepseek_1200.jsonl `
  --output data\summary_teacher_pairs_deepseek_1200_norm.jsonl

python scripts/build_novel_sft_dataset.py `
  --input data\summary_teacher_pairs_deepseek_1200_norm.jsonl `
  --output data\summary_sft_deepseek_1200_norm.jsonl `
  --dedupe `
  --min-assistant-chars 180
```

Train LoRA on this specialized summary dataset:

```powershell
.\.venv\Scripts\python.exe scripts/sft.py `
  --model-path "D:\models\Qwen3.5-4B" `
  --data data\summary_sft_deepseek_1200_norm.jsonl `
  --output-dir outputs\summary_deepseek_sft_1200_xpu_v1 `
  --num-epochs 1 `
  --lr 2e-5 `
  --batch-size 1 `
  --grad-accum 32 `
  --max-seq-len 32 `
  --truncate-side tail `
  --lora-r 8 `
  --lora-alpha 16 `
  --lora-target q_proj k_proj v_proj o_proj `
  --dtype float16 `
  --swanlab-mode disabled
```

## 4.1) Build templated SFT data for 5 novel tasks (recommended)

For higher style-replication quality, use structured task records and generate multiple prompt templates per record.

Supported tasks:
- `info_recommend` (信息推荐)
- `summary` (梗概)
- `outline` (大纲)
- `detail_outline` (细纲)
- `text` (正文)

Template input example:

```text
data\novel_task_structured_template.jsonl
```

Generate templated dataset:

```powershell
python scripts/build_novel_templated_sft.py `
  --input data\novel_task_structured.jsonl `
  --output data\novel_sft_templated_train.jsonl `
  --variants-per-record 3 `
  --dedupe
```

Or with helper script:

```powershell
.\examples\build_novel_templated_sft_windows.ps1 `
  -Input "data\novel_task_structured.jsonl" `
  -Output "data\novel_sft_templated_train.jsonl" `
  -VariantsPerRecord 3
```

Then train with the generated file:

```powershell
.\examples\novel_sft_windows.ps1 `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -TrainData "data\novel_sft_templated_train.jsonl" `
  -OutputDir "outputs\novel_sft"
```

## 4.2) Collect legal fiction corpus at scale (public-domain source)

If you need large-scale novel-style text, avoid scraping copyrighted web novels.
Use legal/public-domain sources first.

This repo provides a collector for Project Gutenberg:

```powershell
python scripts/collect_legal_fiction_gutenberg.py `
  --output-corpus data\legal_fiction_corpus.jsonl `
  --output-sft data\legal_fiction_sft.jsonl `
  --max-books 300 `
  --languages en
```

Windows helper:

```powershell
.\examples\collect_legal_fiction_windows.ps1 `
  -OutputCorpus "data\legal_fiction_corpus.jsonl" `
  -OutputSft "data\legal_fiction_sft.jsonl" `
  -MaxBooks 300
```

Notes:
- `legal_fiction_corpus.jsonl` stores full text + source metadata.
- `legal_fiction_sft.jsonl` stores continuation-style SFT pairs and can be used directly by `scripts/sft.py`.

## 4.3) Collect legal Chinese fiction corpus (zh.wikisource)

To build a Chinese fiction-style dataset (instead of English), use the Chinese Wikisource collector:

```powershell
python scripts/collect_legal_fiction_zh_wikisource.py `
  --output-corpus data\legal_fiction_zh_corpus.jsonl `
  --output-sft data\legal_fiction_zh_sft_1000.jsonl `
  --target-sft 1000
```

Windows helper:

```powershell
.\examples\collect_legal_fiction_zh_windows.ps1 `
  -OutputCorpus "data\legal_fiction_zh_corpus.jsonl" `
  -OutputSft "data\legal_fiction_zh_sft_1000.jsonl" `
  -TargetSft 1000
```

## 4.4) Probe Intel iGPU (XPU) and switch backend automatically

Use this script to:
- inspect local GPU/torch backend
- optionally install Intel XPU stack into a dedicated venv
- run training with `xpu` when available, otherwise fallback to `cpu`

Probe only:

```powershell
.\examples\probe_intel_xpu_and_train_windows.ps1 `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -TrainData "data\legal_fiction_zh_sft_1000.jsonl" `
  -CheckOnly
```

Probe + try install XPU stack + train:

```powershell
.\examples\probe_intel_xpu_and_train_windows.ps1 `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -TrainData "data\legal_fiction_zh_sft_1000.jsonl" `
  -TryInstallXpu
```

Notes:
- On integrated Intel XPU, this script auto-caps `max_seq_len` to `128` for Qwen3.5-4B to avoid OOM.
- It also defaults to `--truncate-side tail` so assistant tokens are preserved when sequence length is small.

## 5) Fine-tune LoRA on Qwen3.5-4B

```powershell
.\examples\novel_sft_windows.ps1 `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -TrainData "data\novel_sft_train.jsonl" `
  -OutputDir "outputs\novel_sft"
```

Default final adapter path:

```text
outputs\novel_sft\final
```

## 6) Serve model + LoRA

```powershell
.\examples\run_local_openai_server_windows.ps1 `
  -ModelPath "D:\models\Qwen3.5-4B" `
  -AdapterPath "outputs\novel_sft\final" `
  -ServedModelName "ChiYong-MoE-Novel-18B-A6B"
```

## 7) Quick check

```powershell
curl http://127.0.0.1:54862/v1/chat/completions `
  -H "Content-Type: application/json" `
  -d "{\"model\":\"ChiYong-MoE-Novel-18B-A6B\",\"messages\":[{\"role\":\"user\",\"content\":\"你好\"}],\"stream\":false}"
```

If the response contains `choices[0].message.content`, your Spring side can consume it directly.

## 8) Detail-outline schema upgrade (new stable chapter JSON list)

Normalized assistant schema for `detail_outline`:

```text
[{'章节标题': '...', '细纲内容': '...'}, ...]
```

Server normalization now supports legacy formats (`|||`, markdown headings) and rewrites to the schema above.

### Build request pool

```powershell
python scripts/build_detail_outline_request_pool.py `
  --input data\novel_task_structured_from_zh_corpus_1500.jsonl data\novel_task_structured_auto_750.jsonl `
  --output data\detail_outline_request_pool_1000.jsonl `
  --target-count 1000 `
  --synthetic-count 1200
```

### Generate teacher pairs via DeepSeek

```powershell
python scripts/generate_teacher_pairs_via_api.py `
  --input data\detail_outline_request_pool_1000.jsonl `
  --output data\detail_outline_teacher_pairs_deepseek_1000.jsonl `
  --endpoint "https://api.deepseek.com/v1/chat/completions" `
  --model "deepseek-chat" `
  --api-key-env "DEEPSEEK_API_KEY" `
  --max-requests 1000 `
  --concurrency 2 `
  --max-retries 2
```

### Normalize + build HQ SFT

```powershell
python scripts/normalize_detail_outline_teacher_pairs.py `
  --input data\detail_outline_teacher_pairs_deepseek_1000.jsonl `
  --output data\detail_outline_teacher_pairs_deepseek_1000_norm.jsonl

python scripts/build_detail_outline_hq_correction_sft.py `
  --input data\detail_outline_teacher_pairs_deepseek_1000_norm.jsonl `
  --output data\detail_outline_sft_deepseek_1000_hq.jsonl `
  --report logs\detail_outline_hq_correction_report_1000.json `
  --target-count 1000 `
  --min-chapters 3 `
  --max-chapters 12 `
  --min-chapter-chars 320
```

### Resilient training

```powershell
.\.venv\Scripts\python.exe scripts/run_detail_outline_resilient_train.py `
  --model-path "D:\models\Qwen3.5-4B" `
  --data data\detail_outline_sft_deepseek_1000_hq.jsonl `
  --output-root outputs\detail_outline_hqcorr_resilient_detail_outline1000 `
  --report logs\train_detail_outline_hqcorr_resilient_detail_outline1000_report.json `
  --dtype float16
```

### One-shot full pipeline

```powershell
python scripts/run_detail_outline_pipeline.py `
  --model-path "D:\models\Qwen3.5-4B" `
  --target-count 1000 `
  --run-tag detail_outline1000
```
