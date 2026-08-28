#!/usr/bin/env bash
# M4 P3.2 — CHA cha_m4 PostgreSQL daily backup (local + off-host).
#
# Produces a custom-format pg_dump with SHA256 + readability verification
# on the CHA host, then pulls a second independent copy (also pg_dump'd on the
# Aliyun host) over the Tailscale private network into
# /opt/jdair-cha/backups/remote-pg. The two backups live on different hosts.
#
# Run manually or via systemd timer (see ops/cha_m4_pg_backup.timer).
set -Eeuo pipefail

SECRET_FILE="${CHA_PG_SECRET_FILE:-/etc/cha-pg-secrets}"
BACKUP_DIR="${CHA_PG_BACKUP_DIR:-/opt/jdair-cha/backups/pg}"
REMOTE_DIR="${CHA_PG_REMOTE_BACKUP_DIR:-/opt/jdair-cha/backups/remote-pg}"
ALIYUN_HOST="${CHA_PG_ALIYUN_HOST:-}"
ALIYUN_LOCAL_DIR="${CHA_PG_ALIYUN_LOCAL_DIR:-/opt/jdair-cha/backups/pg-local}"
ALIYUN_SECRET_FILE="${CHA_PG_ALIYUN_SECRET_FILE:-/etc/cha_pg_secrets_cha_m4}"
RETENTION_DAYS="${CHA_PG_BACKUP_RETENTION_DAYS:-14}"
REMOTE_RETENTION_DAYS="${CHA_PG_REMOTE_BACKUP_RETENTION_DAYS:-14}"

test -r "$SECRET_FILE"
test -n "$ALIYUN_HOST" || {
  echo "CHA_PG_ALIYUN_HOST is required for off-host backup" >&2
  exit 1
}
mkdir -p "$BACKUP_DIR"
mkdir -p "$REMOTE_DIR"

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

# ---- off-host copy ----
# 1) Ensure the Aliyun host has a fresh local dump.
ssh -o BatchMode=yes -o ConnectTimeout=10 "root@${ALIYUN_HOST}" \
  "ALIYUN_SECRET_FILE=${ALIYUN_SECRET_FILE} bash -s" <<'REMOTE'
set -e
APP_PW=$(python3 -c "import re;raw=open('${ALIYUN_SECRET_FILE}').read();m=re.search(r'CHA_PG_APP_PASSWORD=(.+)',raw);print(m.group(1).strip())")
mkdir -p /opt/jdair-cha/backups/pg-local
chmod 700 /opt/jdair-cha/backups/pg-local
STAMP=$(date +%Y%m%d-%H%M%S)
DUMP=/opt/jdair-cha/backups/pg-local/cha_m4-${STAMP}.dump
PGPASSWORD="$APP_PW" pg_dump -h 127.0.0.1 -p 5432 -U cha_m4_app -d cha_m4 \
  -Fc --no-owner --no-privileges -f "$DUMP"
chmod 600 "$DUMP"
sha256sum "$DUMP" > "$DUMP.sha256"
chmod 600 "$DUMP.sha256"
echo "ALIYUN_LOCAL_DUMP=$DUMP"
REMOTE

# 2) Pull the latest Aliyun dump to CHA remote-pg.
ALIYUN_LATEST=$(ssh -o BatchMode=yes -o ConnectTimeout=10 \
  "root@${ALIYUN_HOST}" \
  "ls -t /opt/jdair-cha/backups/pg-local/cha_m4-*.dump 2>/dev/null | head -1")
if [ -n "$ALIYUN_LATEST" ]; then
  BASE=$(basename "$ALIYUN_LATEST")
  scp -o BatchMode=yes "root@${ALIYUN_HOST}:${ALIYUN_LATEST}" \
    "${REMOTE_DIR}/${BASE}"
  scp -o BatchMode=yes "root@${ALIYUN_HOST}:${ALIYUN_LATEST}.sha256" \
    "${REMOTE_DIR}/${BASE}.sha256"
  chmod 600 "${REMOTE_DIR}/${BASE}" "${REMOTE_DIR}/${BASE}.sha256"
  # verify remote copy readable
  pg_restore -l "${REMOTE_DIR}/${BASE}" >/dev/null 2>&1 || {
    echo "REMOTE_BACKUP_VERIFY_FAIL $BASE" >&2
    rm -f "${REMOTE_DIR}/${BASE}" "${REMOTE_DIR}/${BASE}.sha256"
    exit 1
  }
  echo "REMOTE_BACKUP_OK ${REMOTE_DIR}/${BASE}"
  echo "REMOTE_BACKUP_SHA $(cat "${REMOTE_DIR}/${BASE}.sha256")"
else
  echo "REMOTE_BACKUP_NO_DUMP on ${ALIYUN_HOST}" >&2
fi

# 3) retention on the remote-pg directory (CHA side)
find "$REMOTE_DIR" -name "cha_m4-*.dump" -mtime "+${REMOTE_RETENTION_DAYS}" \
  -print | while IFS= read -r old; do
    rm -f "$old" "${old}.sha256"
  done
