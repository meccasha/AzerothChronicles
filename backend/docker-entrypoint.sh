#!/bin/sh
set -e
# Apply migrations before serving; seed the fictional demo group only when DEMO_MODE=true.
if [ "${RUN_MIGRATIONS:-1}" = "1" ]; then
  alembic upgrade head
  python -m app.cli seed-demo --if-missing
fi
exec "$@"
