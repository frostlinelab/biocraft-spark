#!/bin/sh
# Biocraft-Spark container entrypoint.
#
# Runs database migrations on every start (idempotent) before handing off to
# the CMD. This guarantees the SQLite schema exists even when the host's
# bind-mounted db.sqlite3 is a fresh empty file — the default install path,
# where install.sh creates it via `touch`. Without this, every DB-backed API
# endpoint (/api/dashboard-stats/, /api/marketplace/catalog/, ...) would 500
# with "no such table" on a brand-new install, while the non-DB health pings
# stayed green.
#
# `migrate --noinput` is safe to run repeatedly: Django skips already-applied
# migrations, so this is a no-op on subsequent starts.
set -e

echo "[biocraft] Applying database migrations..."
python manage.py migrate --noinput

echo "[biocraft] Starting server..."
exec "$@"
