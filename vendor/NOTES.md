# Vendor Evaluation Notes

This project follows a reuse-first strategy for the novel workflow rewrite.

## Frontend

- Preferred candidate after product correction: `bytedance/flowgram.ai`.
- Status: shallow clone was attempted but failed with RPC/early EOF network disconnect in this environment. It remains the preferred design reference because its AI workflow editor includes canvas, node forms, variables, and LLM workflow materials that map well to configurable novel stages.
- Backup candidate: `synergycodes/workflowbuilder`.
- Status: retry clone failed with RPC/early EOF network disconnect. Keep as a future evaluation target for schema-driven UI, validation, and execution visualization.
- Current vendored base: `xyflow/vite-react-flow-template`.
- Commit: `303af39d8775ad9a0f96d57fdd790049052b8b4e`.
- License: MIT.
- Intended use: lightweight fallback only. The current `apps/web` UI has been rebuilt as a novel pipeline configuration console rather than a simple free-canvas demo.

### Frontend Decision

Use FlowGram's product direction as the UX target, but do not block on vendoring while network clones fail. The current implementation keeps xyflow/Vite as a local foundation and implements the required pipeline console, stage inspector, provider selector, prompt preview, memory policy, quality policy, and run console in project code.

## Knowledge Graph Components

- Current component: `vasturiano/react-force-graph` via `react-force-graph-2d`.
- License: MIT.
- Why keep it for v1 UI: the current character graph is small, and this component already covers canvas rendering, force layout, zoom/pan, node dragging, hover, click, and custom canvas drawing with a very small integration surface.
- Obsidian plugin list from product reference: do not import these plugins directly. They depend on the Obsidian plugin runtime and are not suitable as web app dependencies. Borrow the product capabilities instead:
  - Dataview-style query views for Wiki, character, foreshadowing, and chapter metadata.
  - Contribution Graph-style heatmaps for chapter output, quality trend, and foreshadowing payoff density.
  - Meta Bind-style metadata forms for stage settings, Wiki pages, and character cards.
  - Kanban-style boards for chapter status and foreshadowing lifecycle.
  - Iconize/File Color/Style Settings-style visual taxonomy for Wiki pages, factions, characters, and volumes.
- Future candidate: `antvis/G6`.
- License: MIT.
- Why consider later: G6 is a fuller graph visualization engine with layout, interaction, animation, theme, and plugin capabilities, which fits larger Wiki knowledge graphs and relation analysis.
- Future candidate: `antvis/Graphin`.
- License: MIT.
- Why consider later: Graphin is a React toolkit built on top of G6 and is better suited to graph analysis modules when the product needs filtering, relation exploration, and richer graph UI.
- Current decision: do not replace the existing character graph in this UI pass. Keep `react-force-graph-2d` and optimize layout, label density, and contrast first.

## Backend

- Candidate: `JoshuaC215/agent-service-toolkit`.
- Commit: `5b3945f48e41a193816d7710b275eb89b90568ee`.
- License: MIT.
- Reused ideas: FastAPI service boundary, Pydantic schemas, streaming endpoint shape, LangGraph-first service organization, testable agent runner.
- Not copied wholesale: Streamlit app, voice modules, multi-provider LangChain stack, heavy optional dependencies.

## License Rule

MIT and Apache-2.0 code may be adapted into the main product. AGPL/GPL projects are reference-only unless the project license strategy changes explicitly.
