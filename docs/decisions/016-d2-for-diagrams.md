# 016: D2 for diagrams (replacing Mermaid)

- **Status:** accepted
- **Date:** 2026-10-22

## Context
Diagrams are how the owner explains the system in a technical interview. The owner reviewed the Mermaid diagrams and found them not presentable: default styling, cramped layouts and little control over grouping or color.

## Decision
Write diagrams in **[D2](https://d2lang.com)** and commit both the source and the rendered SVG:
- sources in `docs/diagrams/src/*.d2`, SVGs in `docs/diagrams/*.svg`, embedded in Markdown as images;
- rendered in Docker with the pinned image `terrastruct/d2:v0.7.1` and the ELK layout (nothing installed on the host; command in `docs/diagrams/src/README.md`);
- a shared look through D2 `classes`: blue = Placewise services, green = data or plain code steps, orange = external AI / LLM steps, red = needs attention, dashed gray = planned or asynchronous; grouped containers for boundaries;
- `shape: sequence_diagram` for sequences, `sql_table` for the data model.

## Alternatives considered
- **Mermaid:** renders inline on GitHub with no build step, but the owner rejected the look.
- **PlantUML:** strong UML support, dated look, needs Java or a server.
- **Excalidraw / draw.io:** nice visuals but hand-drawn, so they drift from the code and are hard to diff.
- **Structurizr / C4:** good for architecture only.

## Tradeoffs and consequences
- **Gain:** consistent, readable diagrams; text sources that diff in git; class-based styling reused across diagrams.
- **Give up:** a render step. An SVG can go stale if someone edits the `.d2` without re-rendering, so docs updates must re-render. GitHub doesn't render `.d2` itself, so the SVG is what readers see.
- **Revisit if:** GitHub renders D2 natively, or the render step becomes a burden (then render in CI).
