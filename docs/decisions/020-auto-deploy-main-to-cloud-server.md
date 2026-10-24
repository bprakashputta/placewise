# 020: Auto-deploy main to the cloud server (build on the server, verify, roll back)

- **Status:** accepted (owner asked for it 2026-10-23: "a workflow that updates the docker image with latest pull from the main branch ... triggered whenever there's a push to main or merge into main")
- **Date:** 2026-10-23

## Context
The demo runs on one Google Cloud VM with the same Docker Compose stack as local development. Updating it by hand (copying files from a laptop) can drift from `main` and skips review. The owner wants every push or merge to `main` to reach the server automatically, and the live site must keep working.

## Decision
- **Trigger:** `.github/workflows/deploy.yml` runs when the CI workflow succeeds for a push to `main` (merges are pushes), plus a manual "Run workflow" button. It deploys exactly the commit CI tested. One deploy at a time; a running deploy is never cancelled.
- **Build on the server** from the same Dockerfiles (`scripts/deploy.sh`), while the old containers keep serving; then recreate only `api`, `worker` and `web`. Tunnels and the database are untouched unless their config changed. The Worker is redeployed from the same commit.
- **Verify before calling it done:** api healthy (migrations run on start), `/api/health` ok, admin login + a data query, the web app through Caddy, no container restarts for 20 s, and the public link. The workflow then checks the public link again from GitHub.
- **Docs-only changes** (`docs/`, `*.md`) update the server's checkout and re-run the checks without restarting anything.
- **Roll back automatically** to the previous commit (rebuild + verify) if any check fails; the workflow run goes red.
- **Access:** a dedicated SSH key whose only permitted command is `/usr/local/bin/placewise-deploy` (accepts a 40-character SHA on `origin/main`; no shell, no port forwarding). The server's host key is pinned in the workflow secrets. `.env` never leaves the server.

## Alternatives considered
- **Build images in GitHub Actions and push to a registry (GHCR / Artifact Registry), server pulls:** faster swaps and no build load on the server, but adds a registry, registry credentials on the server, and a second way images get built. Worth it with several servers.
- **Copy files by hand / `git pull` by hand:** no automation, easy to forget, drifts from `main`.
- **Blue-green (two app copies behind Caddy):** no restart blip, but double the memory and more moving parts for a demo.

## Tradeoffs and consequences
- **Gain:** the server always runs the latest reviewed `main`, with a health gate and rollback.
- **Give up:** a ~10–20 s restart blip per deploy (visitors see the self-reloading "Reconnecting…" page), and a few minutes of build load on the server.
- **Rollback limit:** migrations are forward-only; rolling back code after an additive migration is safe, a destructive one is not. Keep migrations additive.
- **Revisit if:** more than one server, deploys become frequent during use, or zero-downtime matters.
