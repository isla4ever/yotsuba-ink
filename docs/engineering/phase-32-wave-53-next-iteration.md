# Phase 32 Wave 53 — Next Iteration Runbook

## Objective

Close the remaining canonical text-route gate without entering image acceptance. The target is a reproducible, process-restart-safe text pipeline for all three official modes:

```text
official.screenplay_sample  -> completed
official.short_novel        -> image_deferred (export locked)
official.long_novel         -> image_deferred (export locked)
```

`image_deferred` is a successful text-stage terminal state for this wave. It is not a provider failure and must not be converted into an export-ready state.

## Current baseline

- Screenplay canonical r3 is transport-closed: 11/11 provider operations succeeded, zero pending, terminal `completed`; one initial writeback binding failure was recovered from the persisted read-model decision. Fountain Export is readable; repeated storm/rain imagery remains a literary warning.
- Short-novel canonical r7 remains the historical recovery baseline; fresh canonical r8 is now closed after writeback hardening: 11/11 provider operations succeeded, zero first-pass contract rejects, terminal `image_deferred`, zero pending operations and zero image operations. Promise refs and Cast/text naming constraints passed the cold-read sample.
- Long-novel canonical r8 remains the historical naming baseline; fresh canonical r9 is transport-closed after writeback hardening: 10/10 receipts succeeded, zero first-pass contract rejects, zero pending, terminal `image_deferred`; 45 monotonic SSE events, 37,674 tokens, estimated cost `$0.06923928`, image operations 0. Both chapters pass the explicit-name gate and contain no `林晚`; the two-chapter bounded smoke is still not a formal long-novel quality pass.
- The three earlier findings are fixed in code: canonical model split, canonical stage budgets, and nested long-detail schema examples.
- The current candidate boundary also has a narrow explicit-name gate. It rejects high-signal markers such as `姓名：X`, `名字是X`, `叫作X`, and `输入“X”` when `X` is outside the active frozen Cast; it deliberately does not attempt general Chinese NER.

## Execution order

### 1. Restore a writable runtime

The smoke runner must be able to create and read:

- `runtime/novel_workflow/phase32_runtime/runs/<run_id>/definition.json`
- provider-operation receipts and lock files
- event append logs

Before spending provider budget, perform a local write/read probe in the same runtime directory. If it fails, move the runtime data directory to a clean writable location or restart the desktop workspace with its project permission restored. Do not weaken lock semantics or silently ignore `PermissionError`.

### 2. Fresh long-novel smoke

The naming-gate run `release-smoke-canonical-long_novel-20260827-r8` is now complete. Keep the existing bounded release-smoke cap for repeatability, and use a new run id only when testing a prompt/writeback change or a larger continuity sample; use the canonical route with `provider-deepseek-text` / `deepseek-v4-pro`.

Acceptance assertions:

1. Decisions complete in order: `brief`, `book_architecture`, `volumes`, `rolling_detail`.
2. At least the configured text units complete and write back to the canonical artifact chain.
3. Cover brief completes without an image execution binding.
4. Terminal status is `image_deferred`.
5. Export is locked with the explicit deferred-image reason.
6. Provider operation receipts are complete, redacted, and contract-valid; no pending lock remains.
7. `image_ops == 0` and no image provider/model is called.

### 3. Cold-read and recovery continuity

After the fresh run reaches its terminal state:

- restart the API/runtime process;
- read the run exclusively from persisted definition, artifact, receipt, and event files;
- verify the terminal status, stage statuses, artifact references, writebacks, and export lock are unchanged;
- replay the SSE stream from the persisted event log and verify monotonic sequence numbers and a single terminal event.

For a controlled failure drill, interrupt only after a text operation has persisted its receipt, restart, and verify that the run can resume or project a deterministic failure without duplicating the provider operation.

### 4. Quality and continuity sample

Transport closure is necessary but not sufficient. For each route, retain a redacted sample of the final text and score:

- artifact-schema validity;
- causal continuity from brief to outline/beat plan to prose;
- character/entity consistency;
- unresolved placeholders or meta commentary;
- section/chapter boundary quality;
- cold-read readability by a human reviewer.

Record scores separately from provider latency and cost. A passing transport run with weak literary continuity remains a quality failure.

The prompt hardening slice now covers three boundaries: the writeback prompt repeats a compact format gate after the full frozen context; Story Map/Section Plan prompts require explicit Promise references; and Cast/Text prompts freeze registered names and forbid ad-hoc names for unregistered actors. The writeback recovery path also reuses the same pending operation and immutable input snapshot, so a successful recovery cannot leave an orphan `pending` receipt. r7 still recorded one first-pass writeback contract rejection, which remains visible as a quality metric rather than being hidden by the final status.

Wave 54 adds a writeback-specific hardening: because DeepSeek `json_object` does not enforce nested
`span_ids.maxLength`, the 1/2/3 cardinality rule is repeated after the full source context. The correction prompt
now repairs only the offending claim and explicitly preserves valid claims. Fresh Short r8 and Long r9 both show
zero first-pass writeback contract rejects and zero empty-claims corrections.

The r7 long-novel cold read is retained as the regression fixture: the prompt alone did not stop the model
from introducing `林晚`, and the new gate reproduces that failure on both committed chapters without
rewriting history. The fresh r9 run then passed both naming and writeback gates by keeping registered Cast labels
and selecting no more than three evidence spans per claim. The remaining long-route blocker is the bounded
two-chapter scale; neither that limitation nor any literary warning may be hidden by the `image_deferred` terminal state.

## Stop conditions

Stop and diagnose if any of the following occurs:

- a canonical route resolves to a legacy source stage or generic model/budget fallback;
- a provider response is structurally invalid, truncated, or has unredacted receipt content;
- a run reports `completed` while export is still blocked, or reports export-ready before image acceptance is enabled;
- a process restart changes persisted state or duplicates an operation;
- a recovered writeback leaves any Provider operation in `pending` or produces an unknown terminal cost;
- any image provider operation is observed during this wave.

## Exit criteria

Wave 53 transport/recovery evidence is now fresh for all three route rows: Short r8, Screenplay r3 and Long r9.
Wave 54 writeback evidence is fresh for Short/Long with zero first-pass contract rejects. The overall work is not a
formal literary-quality pass until the three human cold-read records are reviewed and Long receives a standard
multi-chapter/accepted-prefix sample. Next implementation waves are Wave 55 text export, Wave 56 frontend/browser
observability, and Wave 57 image re-entry.
