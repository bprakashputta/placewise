#!/usr/bin/env sh
# Start (or refresh) the public demo link: Docker stack + quick tunnel, then point the workers.dev
# address (https://placewise.bprakashputta.workers.dev) at the tunnel. Safe to re-run any time, e.g.
# after a restart changed the tunnel's random address. Needs CLOUDFLARE_API_TOKEN in .env.
set -eu
cd "$(dirname "$0")/.."
DC="docker compose -f docker-compose.yml -f docker-compose.public.yml"
if [ "${1:-}" = "--tunnel-only" ]; then
  $DC up -d --force-recreate tunnel     # new tunnel (new random address); the app keeps running
else
  $DC up -d --build
fi
echo "Waiting for the tunnel address..."
URL=""
for _ in $(seq 1 60); do
  URL=$($DC logs --since 2m tunnel 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true)
  [ -n "$URL" ] && break
  sleep 3
done
[ -n "$URL" ] || { echo "No tunnel address found; check: $DC logs tunnel"; exit 1; }
echo "Tunnel: $URL"
CLOUDFLARE_API_TOKEN=$(grep '^CLOUDFLARE_API_TOKEN=' .env | cut -d= -f2- | tr -d '"'"'"' \r\n')
export CLOUDFLARE_API_TOKEN
docker run --rm -e CLOUDFLARE_API_TOKEN -v "$PWD/infra/worker":/w -w /w node:22-alpine \
  sh -c "npx -y wrangler@4.20.0 deploy --var TUNNEL_ORIGIN:$URL" | grep -E 'workers.dev|Uploaded|error' || true
echo "Public link: https://placewise.bprakashputta.workers.dev"
