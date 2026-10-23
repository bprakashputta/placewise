#!/usr/bin/env sh
# Keeps the public demo link alive: every 30 s it checks https://placewise.bprakashputta.workers.dev;
# after 2 failed checks in a row it recreates the tunnel and re-points the Worker (public-link.sh
# --tunnel-only). Also keeps the Mac awake while it runs (caffeinate). Log: logs/public-link-watch.log
#   start: nohup ./scripts/watch-public-link.sh >/dev/null 2>&1 &
#   stop:  pkill -f watch-public-link.sh
cd "$(dirname "$0")/.."
mkdir -p logs
LOG=logs/public-link-watch.log
URL=https://placewise.bprakashputta.workers.dev/api/health
caffeinate -dims -w $$ &          # no display/idle/disk/system sleep while this script is alive
fails=0
echo "$(date '+%F %T') watcher started (pid $$)" >> "$LOG"
while true; do
  code=$(curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$URL" || echo 000)
  if [ "$code" = "200" ]; then
    [ "$fails" -gt 0 ] && echo "$(date '+%F %T') healthy again" >> "$LOG"
    fails=0
  else
    fails=$((fails + 1))
    echo "$(date '+%F %T') check failed ($code), strike $fails" >> "$LOG"
    if [ "$fails" -ge 2 ]; then
      echo "$(date '+%F %T') repairing: new tunnel + re-point Worker" >> "$LOG"
      ./scripts/public-link.sh --tunnel-only >> "$LOG" 2>&1 || echo "$(date '+%F %T') repair failed" >> "$LOG"
      fails=0
      sleep 60
      continue
    fi
  fi
  sleep 30
done
