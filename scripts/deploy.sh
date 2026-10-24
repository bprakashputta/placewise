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

say() {  # to the log, and to the caller if it's still connected (never fail if it isn't)
  line="$(date -u '+%F %T') $*"
  echo "$line" >> "$LOG"
  echo "$line" 2>/dev/null || true
}
envval() { grep "^$1=" .env 2>/dev/null | cut -d= -f2- | tr -d '"'"'"' \r\n'; }
rawval() {  # value as written (keeps spaces and symbols), minus one pair of surrounding quotes
  grep "^$1=" .env 2>/dev/null | head -1 | cut -d= -f2- | sed 's/\r$//; s/^"\(.*\)"$/\1/; s/^'"'"'\(.*\)'"'"'$/\1/'
}

# A deploy must finish once started: an SSH drop or a closed pipe must not stop it halfway.
trap '' HUP PIPE

# one deploy at a time
exec 9>logs/deploy.lock
flock -w 900 9 || { say "another deploy is still running; giving up"; exit 1; }

[ -f .env ] || { say "no .env on the server"; exit 1; }
git fetch -q origin
TARGET=$(git rev-parse "${1:-$REF}^{commit}")
if [ -n "${1:-}" ] && ! git merge-base --is-ancestor "$TARGET" "$REF"; then
  say "refusing $TARGET: not on $REF"; exit 1
fi
# Roll back to the last VERIFIED commit, not whatever HEAD is (an interrupted deploy could leave HEAD
# on an unverified commit).
PREV=$(cat logs/deployed-sha 2>/dev/null || true)
git cat-file -e "${PREV:-x}^{commit}" 2>/dev/null || PREV=$(git rev-parse HEAD)
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
  # JSON-escape the password and send the body on stdin (never in curl's argv)
  pw=$(rawval PLACEWISE_DEMO_ADMIN_PASSWORD | sed 's/\\/\\\\/g; s/"/\\"/g')
  ck=$(printf '{"username":"admin","password":"%s"}' "$pw" | curl -s --max-time 15 -D - -o /dev/null \
       -H 'content-type: application/json' --data-binary @- http://127.0.0.1:8000/api/auth/login \
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
  # 5. no crash loop for 20 s: the recreated app containers have never restarted; the rest are running
  #    (db and caddy aren't recreated, so an old restart of theirs says nothing about this deploy)
  sleep 20
  for svc in $APP db caddy; do
    [ -n "$($DC ps -aq "$svc")" ] || { echo "$svc has no container"; return 1; }
    for id in $($DC ps -aq "$svc"); do
      st=$(docker inspect -f '{{.State.Status}} {{.RestartCount}}' "$id")
      case " $APP " in *" $svc "*) want="running 0" ;; *) want="running" ; st=${st%% *} ;; esac
      [ "$st" = "$want" ] || { echo "$svc is '$st'"; return 1; }
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

# Docs-only change (docs/ or *.md): update the checkout, check the site, no restart.
if [ "$PREV" != "$TARGET" ] && git diff --quiet "$PREV" "$TARGET" -- . ':(exclude)docs' ':(exclude)*.md'; then
  git -c advice.detachedHead=false checkout -q --force "$TARGET" || { say "git checkout $TARGET failed"; exit 1; }
  if out=$(verify); then
    echo "$TARGET" > logs/deployed-sha
    say "OK: $TARGET is live (docs only, no restart)"
    exit 0
  fi
  say "docs-only update, but the running site failed its checks: $out"
  exit 1
fi

say "deploy $TARGET (running: $PREV)"
if out=$(roll_out "$TARGET" && verify); then
  echo "$TARGET" > logs/deployed-sha
  # keep the forced command and the watchdog service in step with the repo
  if ! cmp -s infra/server/placewise-deploy /usr/local/bin/placewise-deploy; then
    sudo -n install -m 755 -o root -g root infra/server/placewise-deploy /usr/local/bin/placewise-deploy \
      && say "updated /usr/local/bin/placewise-deploy" || say "WARNING: could not update placewise-deploy"
  fi
  if ! git diff --quiet "$PREV" "$TARGET" -- scripts/watch-public-link.sh infra/server/placewise-watch.service; then
    sudo -n cp infra/server/placewise-watch.service /etc/systemd/system/ && sudo -n systemctl daemon-reload \
      && sudo -n systemctl restart placewise-watch && say "restarted the watchdog" || say "WARNING: could not restart the watchdog"
  fi
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
