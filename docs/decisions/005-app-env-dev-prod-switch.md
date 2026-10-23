# 005: APP_ENV dev/prod switch with prod as the code default

- **Status:** accepted
- **Date:** 2026-10-22

## Context
During development we want interactive API docs and a test-trace endpoint. In the shared demo (public through a tunnel), those must not exist, and health responses shouldn't leak versions, project names or exception types.

## Decision
`APP_ENV` accepts only `dev` or `prod` (`Literal["dev","prod"]` in `config.py`; anything else fails at startup).
- **Code default is `prod`.** If the variable is missing, dev-only routes stay off.
- In `dev`: `/docs`, `/openapi.json` and `POST /dev/trace` are registered; `/api/health` shows full details.
- In `prod`: those routes are **not registered at all** (404), and health details are reduced to "connected"/"unavailable".
- `docker-compose.yml` sets `APP_ENV=${APP_ENV:-dev}` for local work; the shared demo sets `APP_ENV=prod` in `.env`.

Tests cover both modes, the prod default and rejection of invalid values.

## Alternatives considered
- **Default to `dev` in code:** convenient, but one missing variable would expose docs and dev routes publicly.
- **Keep routes registered but guard them with auth:** more code and more ways to get it wrong; not registering them is simpler and verifiable.
- **More environments (staging, test):** no need yet; tests set `APP_ENV` directly.

## Tradeoffs and consequences
- **Gain:** safe by default; a small, testable switch.
- **Give up:** compose and code have different defaults (`dev` vs `prod`), which can surprise someone running the image outside compose; `DEV` is computed at import time, so changing `APP_ENV` needs a restart (tests reload the module).
- **Revisit if:** we need per-feature flags rather than one environment switch.
