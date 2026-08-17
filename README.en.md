# Yotsuba Ink

[简体中文](README.md) | [English](README.en.md)

<p align="center">
  <img src="docs/assets/branding/yotsuba-ink-logo.png" alt="Yotsuba Ink trademark" width="156" />
</p>

<p align="center"><strong>Turn ideas into a deliverable long-form novel.</strong><br />A staged writing and delivery workbench for long-form fiction</p>

<p align="center">
  <img src="https://img.shields.io/badge/CI-passing-3f8f68" alt="CI passing" />
  <img src="https://img.shields.io/badge/version-1.0.0%20Demo-68717a" alt="version 1.0.0 Demo" />
  <img src="https://img.shields.io/badge/license-Apache--2.0-68717a" alt="Apache 2.0 license" />
</p>

<p align="center"><a href="README.md">中文</a> · <a href="README.en.md">English</a></p>

<p align="center"><img src="docs/assets/branding/yotsuba-ink-banner.png" alt="Yotsuba Ink long-form writing workbench banner" width="100%" /></p>

> Brand assets: the trademark is `2048×2048` and the banner is `1600×720`. The local demo does not depend on cover image generation; the Cover stage still preserves the complete visual metadata.

Yotsuba Ink is an open-source workbench for long-form fiction. Instead of generating an entire book from one prompt, it organizes story information, synopsis, volume outline, chapter blueprint, prose, cover, and export into an editable, reviewable, traceable, and recoverable production pipeline.

> Current version: `1.0.0 Demo`. This release completes one real balanced-mode long-form run above 100,000 characters and presents completed projects through a static terminal projection instead of replaying historical SSE. Live-model literary quality still requires ongoing human cold reads.

## Highlights

- **Eight-stage Artifact workflow**: Brief, Spine, Cast, Volumes, Detail, Text, Cover metadata, and Export.
- **Three creation modes**: Fast, Balanced, and Deep, each with a different cost, approval, and automation policy.
- **Artifact-first semantics**: current drafts, approved artifacts, and formal writeback are separate; candidates never update Story Bible or Canon prematurely.
- **Long-form continuity**: character relationships, worldbuilding, foreshadowing, Wiki/Canon, and chapter context constrain cross-chapter generation.
- **Review and revision**: quality reports, fact writeback, selection revisions, version history, and stable checkpoints form a recoverable loop.
- **Terminal browsing**: completed projects open on the final workbench with all committed artifacts, accepted chapter versions, and immutable export receipts; historical execution is not replayed.
- **Single-row bookshelf**: the library keeps one horizontal row of book spines with arrow controls, touchpad/touch scrolling, and a selected-book reading desk.
- **Parallel delivery**: after Detail is approved, Text and Cover can proceed in parallel; Export waits for both branches and validates the package. Cover image generation can be disabled per Run without losing Cover metadata.
- **Explicit Provider boundary**: production code uses OpenAI-compatible text and image Providers; Fake Providers exist only in tests.

## Workflow

```text
Planning
  -> Brief
  -> Spine
  -> Cast
  -> Volumes
  -> Detail
  -> [Text || Cover metadata]
  -> Export
```

All modes share the same Artifact and writeback contracts:

| Mode | User control | Default flow |
| --- | --- | --- |
| Fast | Minimal intervention | Runs the full pipeline after setup |
| Balanced | Approve the Brief | Continues automatically after Brief; comparison is user-triggered |
| Deep | Stage-by-stage review | Regenerate, edit, and approve each text stage before continuing |

Cover and Export keep their own candidate, approval, and delivery decisions instead of copying the three-column text comparison UI.

## Stack

- Frontend: React, TypeScript, Vite, GSAP, Motion, Radix UI, Three.js
- Backend: Python, FastAPI, Pydantic, SSE
- Model integration: OpenAI-compatible text/image APIs, Provider templates, and fallback routing
- Persistence: projects, run history, stable snapshots, Provider profiles, Wiki, knowledge base, and export receipts

## Repository Layout

```text
apps/web/                    React creation workbench
src/novel_workflow/          Python domain logic and FastAPI adapters
runtime/novel_workflow/      Local runtime configuration and data
tests/                       Backend contract, orchestration, quality, and prompt regression tests
docs/                        Product, stage contract, and architecture documentation
```

The frontend uses one directory system under `features/pipeline`: `layout/`, `planning/`, `brief/`, `running/`, `settings/`, `state/`, `services/`, `contracts/`, and `lib/`. The backend `api/` package is an HTTP/SSE adapter only; orchestration, quality, and persistence rules live in domain packages.

## Local Development

### 1. Requirements

- Python 3.12 or later
- Node.js and npm

### 2. Install the backend

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e ".[dev]"
```

### 3. Start the backend

```bash
.venv/bin/python -m uvicorn novel_workflow.api.app:app \
  --host 127.0.0.1 \
  --port 8787 \
  --reload
```

### 4. Start the frontend

```bash
cd apps/web
npm install
npm run dev
```

Open [http://127.0.0.1:5173](http://127.0.0.1:5173). Vite proxies `/api` to `http://127.0.0.1:8787` by default; set `NOVEL_API_PROXY` to override it.

## Provider Configuration

The recommended path is **Settings -> Model Providers** in the application: select a Provider template, enter the API key and default model, then run **Save and check**. Secrets are stored in local runtime storage and must not be committed.

Generic OpenAI-compatible Providers can also be supplied through environment variables:

```bash
export NOVEL_LLM_BASE_URL="https://your-text-provider.example/v1"
export NOVEL_LLM_API_KEY="your-text-api-key"
export NOVEL_LLM_MODEL="your-text-model"

export NOVEL_IMAGE_BASE_URL="https://your-image-provider.example/v1"
export NOVEL_IMAGE_API_KEY="your-image-api-key"
export NOVEL_IMAGE_MODEL="your-image-model"
```

No key is required to inspect setup, projects, or history. Live generation requires the Provider readiness check to pass. Never commit `.env` files, API keys, run history, or user manuscripts to a public repository.

## v1.0 Demo acceptance

The official `official-deepseek-balanced` template completed one real long-form Run:

- Work: `明日来电`; Project `proj-e1007717ad`; Run `balanced-110k-v1-demo-20260817-040033`
- `8/8` stages complete, 44 chapters, 107,613 non-whitespace characters; chapter range 1,710–3,692, average 2,445.75, P90 2,962
- Volume distribution: 14/14/16 chapters; 100% title completeness; downloadable ZIP export
- Provider: 314 operations, 311 successful, 3 failed and recovered; 1,760,252 total tokens
- Cover image generation was disabled for this Run; Cover metadata and Export still closed successfully

See the [v1.0 balanced long-form acceptance report](docs/engineering/yotsuba-ink-v1-balanced-110k-acceptance.md) for hard gates, continuity sampling, Provider receipts, warnings, and browser screenshots. Historical findings are listed in the [v1.0 follow-up record](docs/engineering/yotsuba-ink-v1-open-findings.md).

## Verification

```bash
# Full backend suite (use the repository virtual environment)
.venv/bin/pytest -q

# Frontend tests, production build, and CSS gates
cd apps/web
npm test
npm run build
npm run audit:css
npm run check:css-split
```

Run the automated suites, production build, CSS gates, and browser checks before publishing. Passing automation proves local contracts and UI projections; live Provider literary quality, AI flavor, and full human cold-read acceptance remain evidence-based release work.

## Documentation

- [Product and architecture overview](docs/architecture/overview.md)
- [Stage Artifact contract](docs/architecture/stage-artifact-contract.md)
- [Production workflow](docs/architecture/product-production-workflow.md)
- [Story Bible, Wiki, and quality boundaries](docs/architecture/story-bible-quality.md)
- [Human preference calibration protocol](docs/architecture/preference-calibration-protocol.md)
- [Phase 27 frontend/backend handoff](docs/architecture/phase-27-frontend-backend-handoff.md)
- [DeepSeek Harness adoption review](docs/architecture/deepseek-harness-adoption-review.md)
- [v1.0 balanced long-form acceptance](docs/engineering/yotsuba-ink-v1-balanced-110k-acceptance.md)
- [v1.0 follow-up record](docs/engineering/yotsuba-ink-v1-open-findings.md)
- [Worktree cleanup record](docs/architecture/worktree-cleanup-2026-08-15.md)
- [Repository contribution rules](AGENTS.md)

## Roadmap

- Validate cross-volume and cross-chapter continuity with an explicitly authorized live text Provider.
- Validate cover generation, retry, candidate approval, and export packaging with a live image Provider.
- Complete release security checks, deployment documentation, and observability baselines.
- Reconsider the open-source/core and hosted/enhanced split at `v1.0`; keep one repository until then.

## License

Yotsuba Ink is released under the [Apache License 2.0](LICENSE). Third-party dependencies remain subject to their respective licenses.

Repository: [github.com/isla4ever/yotsuba-ink](https://github.com/isla4ever/yotsuba-ink)
