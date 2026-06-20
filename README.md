# Novel Workflow

Open-source long-form fiction orchestration for teams that want more than a one-shot “AI novel generator”.

Novel Workflow turns novel creation into a controllable production line:

- `Story Brief approval` before the pipeline commits
- `Story Bible / Wiki` as a runtime fact layer
- `quality gates` that can pass, revise, or block
- `provider-agnostic orchestration` across planning and writing stages
- `token-aware runtime surfaces` for usage visibility

The repo still contains legacy training and evaluation assets, but the main product is now the Novel Workflow application in `apps/web` + `src/novel_workflow`.

## Product Path

```text
配置准备
  -> 创作立项定稿
  -> 全书梗概
  -> 分卷大纲
  -> 全书章节细纲
  -> 正文分章生成
  -> 封面 / 导出
```

Key product decisions:

- Only the Story Brief stage is a default human approval gate.
- Wiki is not a cosmetic panel; it is the continuity and fact layer.
- Quality is not “just a score”; it is an execution decision system.
- Full-book detail outline must be complete before正文 starts.

## Repository Structure

```text
apps/web/                     React workbench UI
src/novel_workflow/
  api/                        FastAPI app + route groups
  orchestration/              Run coordination and stage flow
  quality/                    Quality checks and revision engine
  usage/                      Token / usage estimation scaffolding
  output_contracts/           Stage output schema contracts
  knowledge/                  Knowledge-base ingest and search
  references/                 Web/reference retrieval
  workflows/                  Workflow schemas, templates, compiler
docs/
  engineering/                Repo rules and architecture notes
tests/                        Workflow-level backend regression tests
```

## Local Development

### Backend

```bash
.venv/bin/python -m uvicorn novel_workflow.api.app:app --host 127.0.0.1 --port 8787 --reload
```

### Frontend

```bash
cd apps/web
npm install
npm run dev
```

Frontend default URL: [http://127.0.0.1:5173](http://127.0.0.1:5173)

## Quality Philosophy

We are not trying to build a vague “literary score dashboard”.

We optimize for the failure modes that break long-form fiction production:

- character continuity loss
- world-rule conflicts
- missing or dropped foreshadows
- broken chapter handoff
- incomplete detail outline coverage
- wasteful full rewrites when a local revision would fix the issue

## Engineering Direction

This repository follows Ponytail-inspired engineering rules at the repo level:

- keep files small
- split mixed responsibilities early
- reuse local primitives before adding dependencies
- prefer explicit contracts over stringly coupled behavior

See [docs/engineering/ponytail.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/docs/engineering/ponytail.md) and [AGENTS.md](/Users/isla/Desktop/project/multi-stage-creation-model-end/AGENTS.md).

## Verification

```bash
cd apps/web && npm run build
.venv/bin/python -m pytest tests/test_workflow_runner.py -q
```

## Roadmap

Near-term priorities:

1. Stronger structured outputs for core stages
2. Richer token/cost accounting and stage summary overlays
3. Provider-native caching + semantic cache where it saves money safely
4. Story Bible conflict detection and eval datasets for regression
5. Cleaner open-source extension points for provider adapters and stage contracts
