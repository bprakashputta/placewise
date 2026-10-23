#!/usr/bin/env sh
# Keeps the public demo link alive. Every 20 s it checks each tunnel directly; after 2 failed checks in
# a row it recreates only that tunnel and re-points the Worker, while the other tunnel keeps serving.
# Also keeps the Mac awake while it runs (caffeinate). Log: logs/public-link-watch.log
#   start: nohup ./scripts/watch-public-link.sh >/dev/null 2>&1 &
#   stop:  pkill -f watch-public-link.sh
cd "$(dirname "$0")/.."
mkdir -p logs
LOG=logs/public-link-watch.log
STATE=logs/tunnel-origins
PUBLIC=https://placewise.bprakashputta.workers.dev/api/health
command -v caffeinate >/dev/null && caffeinate -dims -w $$ &   # Mac only: no sleep while this runs
f1=0; f2=0
say() { echo "$(date '+%F %T') $*" >> "$LOG"; }
check() { curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$1/api/health" || echo 000; }
say "watcher started (pid $$), two-tunnel mode"
while true; do
  u1=$(awk '$1=="tunnel"{print $2}' "$STATE" 2>/dev/null)
  u2=$(awk '$1=="tunnel2"{print $2}' "$STATE" 2>/dev/null)
  for svc in tunnel tunnel2; do
    if [ "$svc" = tunnel ]; then u=$u1; f=$f1; else u=$u2; f=$f2; fi
    code=000; [ -n "$u" ] && code=$(check "$u")
    if [ "$code" = "200" ]; then
      [ "$f" -gt 0 ] && say "$svc healthy again"
      f=0
    else
      f=$((f + 1)); say "$svc check failed ($code), strike $f"
      if [ "$f" -ge 2 ]; then
        say "replacing $svc (the other tunnel keeps serving)"
        ./scripts/public-link.sh --replace "$svc" >> "$LOG" 2>&1 || say "replace $svc failed"
        f=0
      fi
    fi
    if [ "$svc" = tunnel ]; then f1=$f; else f2=$f; fi
  done
  pc=$(curl -s -o /dev/null -w '%{http_code}' --max-time 20 "$PUBLIC" || echo 000)
  [ "$pc" = "200" ] || say "PUBLIC link check failed ($pc)"
  sleep 20
done
