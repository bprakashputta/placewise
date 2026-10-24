#!/usr/bin/env sh
# Read-only look at the Placewise database, for screen-sharing. Runs psql inside the db container
# (nothing is exposed), with every transaction forced read-only.
#   ./scripts/db-tour.sh          → runs the tour (scripts/sql/db-tour.sql)
#   ./scripts/db-tour.sh shell    → interactive read-only psql (\dt lists tables, \q quits)
cd "$(dirname "$0")/.."
RO='-c default_transaction_read_only=on'
if [ "${1:-}" = "shell" ]; then
  exec docker compose exec -e PGOPTIONS="$RO" db psql -U placewise -d placewise
fi
docker compose exec -T -e PGOPTIONS="$RO" db psql -U placewise -d placewise -X -q < scripts/sql/db-tour.sql
