#!/usr/bin/env bash
# Container entrypoint: wait for PostgreSQL, prepare it, then hand over to the real command.
#
#   RUN_MIGRATIONS   (default true)   apply migrations (under an advisory lock: safe for replicas)
#   SYNC_CATALOG     (default true)   load/refresh the built-in service catalogue (idempotent)
#   SEED_DEMO_DATA   (default false)  create the demo accounts and requests if they are missing
#   DB_WAIT_TIMEOUT  (default 60)     seconds to wait for the database before giving up
#
# Seeding creates accounts with a PUBLICLY KNOWN password (see the README): never switch it on for
# a deployment that holds real data.
set -Eeuo pipefail

truthy() {
  case "${1,,}" in 1 | true | yes | on) return 0 ;; *) return 1 ;; esac
}

python manage.py wait_for_db --timeout "${DB_WAIT_TIMEOUT:-60}"

if truthy "${RUN_MIGRATIONS:-true}"; then
  python manage.py migrate_locked
fi

if truthy "${SYNC_CATALOG:-true}"; then
  python manage.py sync_catalog
fi

if truthy "${SEED_DEMO_DATA:-false}"; then
  python manage.py seed_demo_data
fi

exec "$@"
