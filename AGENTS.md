# AGENTS.md: Placewise project context

This is the **single source of truth for any agent or model working in this repo**: Claude Code, Codex, Cursor, or LLM agents inside the app. Read this file first, then `docs/PLAN.md` for current status. `CLAUDE.md` only points here.

## What Placewise is
An **AI layer for recruiting firms that place Architecture, Engineering & Construction (A/E/C) talent**. It sits **on top of** a firm's ATS (Bullhorn, Loxo, etc.); it does **not** replace it. The ATS stays the system of record. Placewise makes that data searchable, explainable and actionable:
resume intake → structured profiles → job-order builder → hybrid search + rerank → evidence-backed candidate scoring → submittals and outreach drafts → human approval → send via n8n.

Full brief: `docs/PROJECT_BRIEF.md`. Build plan and status: `docs/PLAN.md`.

## Context
- Built as a demo for a technical interview (Vertex Solutions, A/E/C recruiting, DFW). Presented as a **personal project built this week**, with no claims of production use.
- **Synthetic data only.** Never add real people's resumes or contact details.

## Working agreement (MUST follow)
1. **One block at a time.** Never implement several blocks at once. Blocks are listed in `docs/PLAN.md`.
2. **Design before code.** For each block: propose the design (user value, data flow, choices, tradeoffs), get the owner's approval, then build.
3. **Check in after each block** before starting the next. "We're short on time" is not approval.
4. **Think from the end user's view.** Every feature must make sense to a recruiter or admin using the portal. No speculative or half-finished features.
5. **Optimized and production-minded:** idempotent operations, bounded retries, timeouts, cost caps, logging, tests. No premature complexity.
6. **A block is done** only when its code is tested and its docs are updated (see "Docs to maintain").
7. **Never change the machine** (installs, databases, deleting files) or **send anything external** (emails, posts) without explicit approval.
8. **Honesty:** the build log records only problems that actually happened. Don't invent metrics or results.

## Team roles and block workflow
Role definitions live in `.claude/agents/`. Other tools can read the same files as plain role prompts.

| Role | File | Job |
|---|---|---|
| **Lead / architect / builder** | (main session) | Proposes each block's design, builds after approval, launches the other roles, talks to the owner |
| **Reviewer** | `reviewer.md` | Independent, read-only code review against the design and this file |
| **QA tester** | `qa-tester.md` | Runs tests, verifies "done when", tries to break it, adds tests |
| **UX reviewer** | `ux-reviewer.md` | Reviews UI blocks from a recruiter's and an admin's view |
| **Docs maintainer** | `docs-maintainer.md` | Keeps module docs, D2 diagrams (rendered SVG), ADRs, build log and prompts in sync with the code |
| **Coordinator** | `coordinator.md` | Session-start status, end-of-block close-out checklist, owns status in `docs/PLAN.md`, flags drift |

Every block follows this sequence:
```
Coordinator status → Lead proposes design → OWNER APPROVES → Lead builds → Reviewer → fixes
→ QA tester → fixes → UX reviewer (UI blocks) → fixes → Docs maintainer → Coordinator close-out
→ open a GitHub PR → CI (tests + web lint/build) + Claude Code review on the PR → fix findings
→ OWNER APPROVES THE PR → merge (--no-ff) + tag block-NN-done → next block
```
- PRs are opened with `gh pr create` and carry: summary, reviewer and QA results, test count, eval numbers, docs links.
- `.github/workflows/ci.yml` runs the test suite in the api image and the web lint and build.
- `.github/workflows/claude-review.yml` posts an automated Claude review on every PR. Mention `@claude` in a PR comment for follow-ups (`claude.yml`).
- Subagents can't launch other agents, so the lead launches each role.
- Run parallel builders only for truly independent pieces, each in its own git worktree, and only with the owner's OK.

## Architecture (agreed)
- **Docker Compose** services: `web` (Next.js App Router + Tailwind + shadcn/ui, light/dark), `api` (FastAPI, stateless), `worker` (runs LangGraph jobs from a Postgres `SKIP LOCKED` queue, scales horizontally), `db` (Postgres 17 + pgvector), `n8n`, `mailpit` (local test inbox), and optional `tunnel` (Cloudflare quick tunnel for a temporary public link).
- **LangChain** for model wrappers, structured output, prompts, embeddings and the PGVector store and retrievers.
- **LangGraph** for the ingest graph, the match graph (parallel fan-out scoring, approval `interrupt`) and the recruiter agent. The checkpointer is in Postgres.
- **LangSmith** for tracing every run, datasets, evaluators and prompt versions.
- **Models:** Claude Sonnet 5.5 (main), Claude Opus 5.5 (agent). Use Haiku 5.5 only where evals show equal quality. Embeddings: Voyage `voyage-4-large`. Reranker: Voyage `rerank-3`. All model names live in config.
- **Retrieval:** hard SQL filters → hybrid (pgvector HNSW + Postgres full-text) → RRF fusion → rerank.
- **Trust rules:** the LLM judges each requirement and must quote the resume; **code verifies that quotes exist** and **code computes the score**. **Blind scoring** strips name, address and graduation years before the LLM scores. **Nothing auto-sends**: outreach waits for human approval.
- **n8n handles triggers, integrations and notifications. Placewise code handles all AI logic.**
- **Auth:** simple username/password with hashed passwords and session cookies. Roles: `admin` and `recruiter`.

## Repo layout
```
AGENTS.md / CLAUDE.md      agent context (this file is canonical)
docs/                      PROJECT_BRIEF, PLAN, architecture, modules/, diagrams/ (D2 sources + SVGs),
                           decisions/ (ADRs), build-log, evals, cost-and-performance, roadmap, demo-script
prompts/                   versioned prompt files (name, version, model, schema, changelog)
src/                       Python backend (api, graphs, worker)
web/                       Next.js portal
n8n/                       workflow JSON exports
data/                      synthetic data generator outputs
evals/                     LangSmith datasets and evaluators
outputs/                   sample outputs, eval reports, screenshots
```

## Docs to maintain (update with every block)
- `docs/PLAN.md`: block status
- `docs/modules/<module>.md`: purpose, graph diagram, inputs/outputs, prompts, failure modes, tests
- `docs/decisions/NNN-*.md`: one ADR per significant choice (context, decision, alternatives, tradeoffs)
- `docs/build-log.md`: dated, real problems: symptom → cause → fix
- `prompts/*.yaml`: never hardcode prompts in code
- `docs/diagrams/`: D2 diagrams (sources in `docs/diagrams/src/`, rendered SVGs; see its README), never Mermaid

## Git branching (MUST follow)
- **`main` always works.** Only finished, reviewed, owner-approved blocks are merged into it.
- **One branch per block or workflow:** `block/NN-short-name` (e.g. `block/00-foundation`, `block/02-ingest`). Branch from the latest `main`.
- Commit often on the block branch and push it to GitHub.
- **Merge only after the owner's check-in**: `git merge --no-ff block/NN-...` into `main`, then tag `block-NN-done`. The tag is a known-good restore point if a later block breaks something.
- Fixes to an already-merged block go on a new branch: `fix/NN-short-name`.
- Never force-push `main`. Never merge a block whose tests fail.
- Docs, prompts and diagrams for a block go on that block's branch, so code and docs merge together.

## Everything runs in Docker (MUST follow)
- **All services run as containers:** db (Postgres + pgvector, data in a named Docker volume), api, worker, web, n8n, mailpit, tunnel.
- **Never use the host machine's Postgres, Python, Node or packages.** Run installs, tests, migrations and scripts inside containers (`docker compose exec api ...`, `docker compose run --rm ...`).
- The host only needs Docker Desktop, git and an editor.
- The container db is **not published on 5432** (the host has its own Postgres there). Publish it on **5433** only for debugging.

## Conventions
- Python 3.12, managed with `uv` inside the containers. Pydantic for every LLM output schema.
- Secrets live only in `.env` (gitignored). Never commit keys. `.env.example` lists the variable names.
- Commit after each block with a clear message.
