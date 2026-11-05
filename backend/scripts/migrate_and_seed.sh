#!/usr/bin/env bash
set -e
echo '[migrate_and_seed] Running alembic upgrade head...'
alembic upgrade head
echo '[migrate_and_seed] Migration complete.'
if [ "${SEED_DATA:-false}" = "true" ]; then
  echo '[migrate_and_seed] SEED_DATA=true, running JSON import...'
  python scripts/import_json_to_db.py
  echo '[migrate_and_seed] Import complete.'
fi
echo '[migrate_and_seed] Done.'
