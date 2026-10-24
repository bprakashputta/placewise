#!/usr/bin/env sh
# Deploy the latest main to the cloud server (or roll back if it doesn't come up healthy).
# Run on the server, normally by the GitHub "Deploy" workflow through the restricted deploy key:
#   scripts/deploy.sh <commit-sha>        deploy that commit (must be on origin/main)
#   scripts/deploy.sh                     deploy the tip of origin/main
#   DEPLOY_REF=origin/some-branch scripts/deploy.sh   manual test of a branch (not reachable via the deploy key)
#
# Steps: build new images while the old containers keep serving → recreate only api, worker, web →
# verify (containers stable, API health, login + data, the web app, the public link) → on failure,
# check out the previous commit, rebuild and verify again. Log: logs/deploy.log
set -eu
cd "${PLACEWISE_DIR:-$(dirname "$0")/..}"   # the deploy key runs a temp copy of this script, with PLACEWISE_DIR set
mkdir -p logs
LOG=logs/deploy.log
DC="docker compose -f docker-compose.yml -f docker-compose.public.yml -f docker-compose.server.yml"
APP="api worker web"
REF=${DEPLOY_REF:-origin/main}

say() { echo "$(date -u '+%F %T') $*" | tee -a "$LOG"; }
envval() { grep "^$1=" .env 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' \r\n'; }

# one deploy at a time
exec 9>logs/deploy.lock
flock -w 900 9 || { say "another deploy is still running; giving up"; exit 1; }

[ -f .env ] || { say "no .env on the server"; exit 1; }
git fetch -q origin
TARGET=$(git rev-parse "${1:-$REF}^{commit}")
if [ -n "${1:-}" ] && ! git merge-base --is-ancestor "$TARGET" "$REF"; then
  say "refusing $TARGET: not on $REF"; exit 1
fi
PREV=$(git rev-parse HEAD)
if [ "$PREV" != "$TARGET" ] && git merge-base --is-ancestor "$TARGET" "$PREV"; then
  say "skip: $TARGET is older than the running $PREV"; exit 0
fi

# disk space: keep at least 4 GB free for builds
free_gb=$(df -BG --output=avail / | tail -1 | tr -dc 0-9)
if [ "$free_gb" -lt 4 ]; then
  say "low disk (${free_gb} GB): pruning old images and build cache"
  docker image prune -af --filter "until=24h" >/dev/null 2>&1 || true
  docker builder prune -af --filter "until=24h" >/dev/null 2>&1 || true
fi

verify() {  # all checks must pass; prints the first failure
  # 1. api reports healthy (it runs migrations on start)
  # fail fast: a crash, restart or "unhealthy" means the new version is broken, no need to wait it out
  i=0
  while :; do
    st=$(docker inspect -f '{{.State.Status}} {{.RestartCount}} {{.State.Health.Status}}' "$($DC ps -aq api)" 2>/dev/null || echo "missing 0 none")
    case "$st" in
      "running 0 healthy") break ;;
      "running 0 starting") ;;
      *) echo "api is not starting cleanly ($st): $($DC logs --tail 3 api 2>&1 | tr '\n' ' ' | cut -c1-300)"; return 1 ;;
    esac
    i=$((i + 1)); [ $i -gt 60 ] && { echo "api never became healthy"; return 1; }; sleep 3
  done
  # 2. health endpoint: api + database ok
  h=$(curl -s --max-time 10 http://127.0.0.1:8000/api/health || true)
  echo "$h" | grep -q '"ok":true' || { echo "api health not ok: $(echo "$h" | cut -c1-200)"; return 1; }
  # 3. login works and data is readable (no AI calls, no cost)
  pw=$(envval PLACEWISE_DEMO_ADMIN_PASSWORD)
  ck=$(curl -s --max-time 15 -D - -o /dev/null -H 'content-type: application/json' \
       -d "{\"username\":\"admin\",\"password\":\"$pw\"}" http://127.0.0.1:8000/api/auth/login \
       | tr -d '\r' | sed -n 's/^[Ss]et-[Cc]ookie: \(pw_session=[^;]*\).*/\1/p')
  [ -n "$ck" ] || { echo "admin login failed"; return 1; }
  s=$(curl -s --max-time 15 -H "Cookie: $ck" http://127.0.0.1:8000/api/stats || true)
  echo "$s" | grep -q '"candidates"' || { echo "stats API failed: $(echo "$s" | cut -c1-200)"; return 1; }
  # 4. the web app renders through Caddy (direct route)
  host=$(envval PUBLIC_DIRECT_HOST); sec=$(envval ORIGIN_SHARED_SECRET)
  for p in /login /api/health; do
    c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 --resolve "$host:443:127.0.0.1" \
        -H "X-Placewise-Origin: $sec" "https://$host$p" || echo 000)
    [ "$c" = 200 ] || { echo "web $p returned $c"; return 1; }
  done
  # 5. containers stay up (no crash loop) for 20 s
  sleep 20
  for svc in api worker web db caddy; do
    for id in $($DC ps -q "$svc"); do
      st=$(docker inspect -f '{{.State.Status}} {{.RestartCount}}' "$id")
      [ "$st" = "running 0" ] || { echo "$svc is '$st'"; return 1; }
    done
  done
  # 6. the public link answers
  c=$(curl -s -o /dev/null -w '%{http_code}' --max-time 30 https://placewise.bprakashputta.workers.dev/api/health || echo 000)
  [ "$c" = 200 ] || { echo "public link returned $c"; return 1; }
  return 0
}

dc_retry() {  # docker can still be removing a container from the previous step: retry a few times
  n=0
  until $DC "$@" >> "$LOG" 2>&1; do
    n=$((n + 1)); [ $n -ge 3 ] && return 1; sleep 5
  done
}

roll_out() {  # $1 = commit; build first (old containers keep serving), then swap the app containers
  git -c advice.detachedHead=false checkout -q --force "$1" || { echo "git checkout $1 failed"; return 1; }
  $DC build $APP >> "$LOG" 2>&1 || { echo "image build failed (see $LOG)"; return 1; }
  dc_retry up -d --no-deps --force-recreate $APP || { echo "starting app containers failed"; return 1; }
  dc_retry up -d || { echo "compose up failed"; return 1; }   # others only if their config changed (tunnels stay)
  ./scripts/public-link.sh --repoint >> "$LOG" 2>&1 || { echo "Worker deploy failed"; return 1; }   # Worker code from this commit
}

say "deploy $TARGET (running: $PREV)"
if out=$(roll_out "$TARGET" && verify); then
  echo "$TARGET" > logs/deployed-sha
  docker image prune -f >/dev/null 2>&1 || true
  say "OK: $TARGET is live"
  exit 0
fi
say "FAILED: $out"
say "rolling back to $PREV"
sleep 5   # let docker finish removing the failed containers
if out2=$(roll_out "$PREV" && verify); then
  echo "$PREV" > logs/deployed-sha
  say "rolled back: $PREV is live again"
else
  say "ROLLBACK FAILED: $out2  (manual check needed)"
fi
exit 1
