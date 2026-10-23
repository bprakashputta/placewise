# 008: Answer-key isolation (truth never mounted in the api)

- **Status:** accepted
- **Date:** 2026-10-22

## Context
The synthetic answer key (`data/seed/truth/`: candidate facts, job-order specs, relevance labels) exists to grade the app. If the app being graded could read it, by accident or through a later feature, an eval could leak answers and report fake accuracy. The owner also wanted a live Seed page in the browser, which runs through the api.

## Decision
Keep the answer key out of the running app **by mounts, not by convention**:
- `data/seed/truth` is mounted only into the on-demand `seed` tools container (it mounts `./data`). Evals (Block 9) will be the only other reader.
- The `api` container mounts only `data/seed/public`, `data/seed/resumes` and `outputs/samples`, all **read-only**. `truth/` and `generated/` aren't in its filesystem.
- `seed/public.py` publishes only safe data into `public/`: aggregate counts, the file list (file notes only for dev-split files), job-order notes (structured specs only for dev-split job orders) and up to 12 **dev-split** showcase candidates. Nothing per-candidate from the test split.
- The `/api/dev/seed/*` routes are registered only when `APP_ENV=dev` ([ADR 005](005-app-env-dev-prod-switch.md)), validate candidate ids and block path traversal.
- Writes into `public/` are atomic (temp file + rename) so the page never reads half a file.

## Alternatives considered
- **Mount `./data` into the api and rely on code never reading `truth/`:** one careless import or endpoint would leak answers; hard to prove it doesn't.
- **Store the answer key in the database:** the api can read the database, so isolation would depend on permissions we haven't built yet.
- **No live page, CLI output only:** safer but gives the owner no way to see progress and samples in the browser.

## Tradeoffs and consequences
- **Gain:** the isolation is visible in `docker-compose.yml` and easy to verify; the Seed page works without ever seeing test-split answers.
- **Give up:** a separate `public/` copy that must be republished after each step (done automatically by `facts`, `render` and `job-orders`). The truth files are still committed to git, so this protects the running app, not the repo.
- **Known nit:** candidate ids reveal generation order (targeted candidates start at `C0501`). Harmless while ingest never sees ids; ingest must assign its own.
- **Revisit if:** evals run inside the api or worker, or the Seed page becomes an admin page (Block 3) that needs more than aggregates.
