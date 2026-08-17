#!/usr/bin/env bash
# M4 P3.2 — CHA cha_m4 PostgreSQL daily backup (local short-term).
#
# Produces a custom-format pg_dump with SHA256 + readability verification,
# kept under /opt/jdair-cha/backups/pg with retention.
#
# This is a LOCAL short-term backup on the same host's disk. A REMOTE / off-host
# copy is required before "PRODUCTION BACKUP COMPLETE" can be declared; that
# destination is OWNER ACTION (object storage or another controlled server).
#
# Run manually or via systemd timer (see ops/cha_m4_pg_backup.timer).
set -Eeuo pipefail

SECRET_FILE="${CHA_PG_SECRET_FILE:-/etc/cha-pg-secrets}"
BACKUP_DIR="${CHA_PG_BACKUP_DIR:-/opt/jdair-cha/backups/pg}"
RETENTION_DAYS="${CHA_PG_BACKUP_RETENTION_DAYS:-14}"

test -r "$SECRET_FILE"
mkdir -p "$BACKUP_DIR"

# shellcheck disable=SC1090
set -a; source "$SECRET_FILE"; set +a
export PGPASSWORD="$CHA_PG_PASSWORD"

STAMP="$(date +%Y%m%d-%H%M%S)"
DUMP="${BACKUP_DIR}/cha_m4-${STAMP}.dump"

pg_dump -h "$CHA_PG_HOST" -p "$CHA_PG_PORT" -U "$CHA_PG_USER" \
  -d "$CHA_PG_DATABASE" -Fc --no-owner --no-privileges -f "$DUMP"

sha256sum "$DUMP" > "${DUMP}.sha256"

# verify readability: pg_restore -l must succeed and show the schema tables
pg_restore -l "$DUMP" >/dev/null 2>&1 || {
  echo "BACKUP_VERIFY_FAIL $DUMP" >&2
  rm -f "$DUMP" "${DUMP}.sha256"
  exit 1
}

# retention: remove dumps older than RETENTION_DAYS (keep .sha256 alongside)
find "$BACKUP_DIR" -name "cha_m4-*.dump" -mtime "+${RETENTION_DAYS}" -print \
  | while IFS= read -r old; do
      rm -f "$old" "${old}.sha256"
    done

echo "BACKUP_OK $DUMP"
echo "BACKUP_SHA $(cat "${DUMP}.sha256")"
