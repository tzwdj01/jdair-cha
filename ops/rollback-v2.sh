#!/usr/bin/env bash
set -Eeuo pipefail

root="${CHA_V2_ROOT:-/opt/jdair-cha/v2}"
current="${CHA_V2_CURRENT:-${root}/current}"
target="${CHA_V2_ROLLBACK_TARGET:-}"
env_file="${CHA_V2_ENV_FILE:-}"
env_backup="${CHA_V2_ENV_BACKUP:-}"
dry_run="${CHA_V2_ROLLBACK_DRY_RUN:-false}"
service="${CHA_V2_SERVICE:-}"
health_base="${CHA_V2_HEALTH_BASE:-http://127.0.0.1:8791}"
health_attempts="${CHA_V2_HEALTH_ATTEMPTS:-12}"
health_retry_seconds="${CHA_V2_HEALTH_RETRY_SECONDS:-0.5}"

case "$health_attempts" in
  ''|*[!0-9]*|0)
    printf 'CHA_V2_HEALTH_ATTEMPTS must be a positive integer\n' >&2
    exit 2
    ;;
esac

if [ -z "$target" ]; then
  printf 'CHA_V2_ROLLBACK_TARGET is required\n' >&2
  exit 2
fi

root_resolved="$(readlink -f "$root")"
target_resolved="$(readlink -f "$target")"
case "$target_resolved" in
  "$root_resolved"/releases/*) ;;
  *)
    printf 'rollback target must stay inside %s/releases\n' "$root_resolved" >&2
    exit 2
    ;;
esac

test -d "$target_resolved"
test -f "$target_resolved/VERSION"
test -f "$target_resolved/BUILD"
if [ -n "$env_backup" ]; then
  test -n "$env_file"
  test -f "$env_backup"
fi

if [ "$dry_run" = "true" ]; then
  printf 'DRY_RUN=true\n'
  printf 'CURRENT=%s\n' "$current"
  printf 'TARGET=%s\n' "$target_resolved"
  if [ -n "$env_backup" ]; then
    printf 'ENV_RESTORE=%s -> %s\n' "$env_backup" "$env_file"
  fi
  exit 0
fi

wait_for_live() {
  attempt=1
  while [ "$attempt" -le "$health_attempts" ]; do
    service_state="$(systemctl is-active "$service" 2>/dev/null || true)"
    live_http="$(
      curl -sS -o /dev/null -w '%{http_code}' --max-time 3 \
        "${health_base}/api/v2/health/live" 2>/dev/null || true
    )"
    if [ "$service_state" = "active" ] && [ "$live_http" = "200" ]; then
      printf 'ROLLBACK_HEALTH_ATTEMPT=%s\n' "$attempt"
      printf 'ROLLBACK_LIVE_HTTP=%s\n' "$live_http"
      return 0
    fi
    if [ "$attempt" -lt "$health_attempts" ]; then
      sleep "$health_retry_seconds"
    fi
    attempt=$((attempt + 1))
  done
  printf 'rollback service did not become active with live HTTP 200 within bounded retry window\n' >&2
  return 1
}

install -d -m 0755 "$(dirname "$current")"
ln -sfn "$target_resolved" "$current"
if [ -n "$env_backup" ]; then
  install -d -m 0755 "$(dirname "$env_file")"
  install -m 0600 "$env_backup" "$env_file"
fi

test "$(readlink -f "$current")" = "$target_resolved"
test -s "$current/VERSION"
test -s "$current/BUILD"
if [ -n "$service" ]; then
  systemctl restart "$service"
  wait_for_live
fi

printf 'ROLLBACK=passed\n'
printf 'CURRENT_TARGET=%s\n' "$(readlink -f "$current")"
printf 'VERSION=%s\n' "$(tr -d '\r\n[:space:]' < "$current/VERSION")"
printf 'BUILD=%s\n' "$(tr -d '\r\n[:space:]' < "$current/BUILD")"
printf 'RUNNING_RELEASE=%s\n' "$(basename "$target_resolved")"
printf 'RUNNING_COMMIT=%s\n' "$(
  tr -d '\r\n[:space:]' < "$current/COMMIT" 2>/dev/null || printf 'unknown'
)"
printf 'PACKAGE_HASH=%s\n' "$(
  tr -d '\r\n[:space:]' < "$current/PACKAGE_SHA256" 2>/dev/null || printf 'unknown'
)"
