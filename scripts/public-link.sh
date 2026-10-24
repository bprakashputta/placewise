#!/usr/bin/env sh
# Start (or refresh) the public demo link: Docker stack + two quick tunnels, then point the workers.dev
# address (https://placewise.bprakashputta.workers.dev) at both. The Worker fails over between them, so
# one tunnel dropping never takes the link down. Safe to re-run any time. Needs CLOUDFLARE_API_TOKEN in .env.
#   ./scripts/public-link.sh                    full stack + both tunnels
#   ./scripts/public-link.sh --tunnel-only      recreate both tunnels (app keeps running)
#   ./scripts/public-link.sh --replace tunnel2  recreate just one tunnel, keep the other serving
#   ./scripts/public-link.sh --repoint          only redeploy the Worker for the running tunnels
set -eu
cd "$(dirname "$0")/.."
DC="docker compose -f docker-compose.yml -f docker-compose.public.yml"
envval() { grep "^$1=" .env 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' \r\n'; }
DIRECT_HOST=$(envval PUBLIC_DIRECT_HOST)   # set only on the cloud server
[ -n "$DIRECT_HOST" ] && DC="$DC -f docker-compose.server.yml"
mkdir -p logs
STATE=logs/tunnel-origins   # "service url" per line, read by the watchdog

case "${1:-}" in
  --tunnel-only) $DC up -d --force-recreate tunnel tunnel2; FRESH="tunnel tunnel2" ;;
  --replace)     $DC up -d --force-recreate "$2"; FRESH="$2" ;;
  --repoint)     FRESH="" ;;   # no container changes: redeploy the Worker for the running tunnels (used by deploy.sh)
  *)             $DC up -d --build; FRESH="tunnel tunnel2" ;;
esac

url_of() {  # latest trycloudflare address printed by one tunnel service
  $DC logs "$1" 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1 || true
}
echo "Waiting for the tunnel addresses..."
for svc in $FRESH; do
  for _ in $(seq 1 60); do
    # only accept an address printed by the fresh container, not an old one from the log history
    [ -n "$($DC logs --since 3m "$svc" 2>&1 | grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' | tail -1)" ] && break
    sleep 3
  done
done
U1=$(url_of tunnel); U2=$(url_of tunnel2)
[ -n "$U1$U2" ] || { echo "No tunnel address found; check: $DC logs tunnel tunnel2"; exit 1; }
printf 'tunnel %s\ntunnel2 %s\n' "$U1" "$U2" > "$STATE"
ORIGINS=$(printf '%s,%s' "$U1" "$U2" | sed 's/^,//; s/,$//')
[ -n "$DIRECT_HOST" ] && ORIGINS="https://$DIRECT_HOST,$ORIGINS"   # direct route first, tunnels as backup
echo "Tunnels: $ORIGINS"
CLOUDFLARE_API_TOKEN=$(envval CLOUDFLARE_API_TOKEN)
export CLOUDFLARE_API_TOKEN
docker run --rm -e CLOUDFLARE_API_TOKEN -v "$PWD/infra/worker":/w -w /w node:22-alpine \
  sh -c "npx -y wrangler@4.20.0 deploy --var TUNNEL_ORIGINS:$ORIGINS" 2>&1 | grep -E 'workers.dev|Uploaded|rror' || true
echo "Public link: https://placewise.bprakashputta.workers.dev"
