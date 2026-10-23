# Diagram sources (D2)

Diagrams are written in [D2](https://d2lang.com) and rendered to SVG in Docker (nothing installed on the host):

```
docker run --rm -u $(id -u):$(id -g) -v "$PWD/docs/diagrams":/home/debian/src -w /home/debian/src \
  terrastruct/d2:v0.7.1 --layout elk src/<name>.d2 <name>.svg
```

Color key: blue = Placewise services, green = data or plain code steps, orange = external AI / LLM steps,
red = needs attention, dashed gray = planned or asynchronous.

Check every render visually before committing (for example `qlmanage -t -s 1400 -o <tmpdir> ../<name>.svg` on macOS). Why D2: [ADR 016](../../decisions/016-d2-for-diagrams.md).

| Source | Shows | Embedded in |
|---|---|---|
| `architecture.d2` | Containers, data and external services | `../architecture.md`, `README.md` |
| `deployment.d2` | Compose services, ports, volumes | `../deployment.md` |
| `ingest-graph.d2` | The LangGraph ingest graph | `docs/modules/ingest.md`, `README.md` |
| `queue-lifecycle.d2` | `ingest_jobs` states and transitions | `docs/modules/ingest.md` |
| `data-model.d2` | Ingest tables and views | `docs/modules/ingest.md` |
| `sequence-health-check.d2` | System status health check | `../sequence-health-check.md` |
| `sequence-seed-pipeline.d2` | Synthetic data pipeline (sequence) | `../sequence-seed-pipeline.md` |
| `synthetic-data-flow.d2` | Synthetic data steps (flow) | `docs/modules/synthetic-data.md` |
| `rag-graph.d2` | The Ask (RAG) LangGraph as built | `docs/modules/rag.md` |
| `ask-conversation.d2` | Planned conversational Ask: routing + memory (ADR 018) | `docs/modules/rag.md` |
