# 003: Next.js proxies only /api/*; one public origin

- **Status:** accepted
- **Date:** 2026-10-22

## Context
The browser needs to call the FastAPI backend. FastAPI also serves things that must not be public: interactive docs and the OpenAPI schema, the `/livez` probe, and dev-only routes like `/dev/trace`. Later, a tunnel will make the app public, and auth (Block 3) will use session cookies.

## Decision
The browser talks **only** to the `web` container. `web/next.config.ts` has one rewrite: `/api/:path*` → `http://api:8000/api/:path*` over the internal Docker network. Nothing else on the api is reachable through the web origin. The api's own port is bound to `127.0.0.1:8000` for local docs only, and only `web` will be exposed by the tunnel.

The reviewer flagged the first version for proxying too much; it was narrowed to `/api/*`. QA verified `/docs`, `/openapi.json` and `/dev/trace` return 404 through port 3000, including path-traversal attempts.

## Alternatives considered
- **Browser calls the api directly (CORS):** two public origins, CORS config to get right, cross-site cookie rules (`SameSite=None; Secure`), and the api's docs and probes exposed unless separately locked down.
- **Proxy everything (`/:path*`):** simple, but exposes docs and dev routes, which is exactly what the reviewer caught.
- **A separate reverse proxy (nginx/Caddy):** clean, but one more service; Next.js already sits in front.

## Tradeoffs and consequences
- **Gain:** one public origin, no CORS, same-origin `HttpOnly` cookies for Block 3 auth, and a clear rule: public routes go under `/api`, everything else is internal.
- **Give up:** an extra hop through Node for every API call; when the api is down the proxy returns a plain-text 500 (the UI handles it); long streaming responses (agent chat, Block 7) must be checked to stream through the rewrite.
- **Revisit if:** proxy latency or streaming becomes a problem, or a real edge proxy is introduced.
