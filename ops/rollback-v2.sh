#!/usr/bin/env bash
set -Eeuo pipefail

root="${CHA_V2_ROOT:-/opt/jdair-cha/v2}"
current="${CHA_V2_CURRENT:-${root}/current}"
target="${CHA_V2_ROLLBACK_TARGET:-}"
env_file="${CHA_V2_ENV_FILE:-}"
env_backup="${CHA_V2_ENV_BACKUP:-}"
dry_run="${CHA_V2_ROLLBACK_DRY_RUN:-false}"

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

install -d -m 0755 "$(dirname "$current")"
ln -sfn "$target_resolved" "$current"
if [ -n "$env_backup" ]; then
  install -d -m 0755 "$(dirname "$env_file")"
  install -m 0600 "$env_backup" "$env_file"
fi

test "$(readlink -f "$current")" = "$target_resolved"
test -s "$current/VERSION"
test -s "$current/BUILD"

printf 'ROLLBACK=passed\n'
printf 'CURRENT_TARGET=%s\n' "$(readlink -f "$current")"
printf 'VERSION=%s\n' "$(tr -d '\r\n[:space:]' < "$current/VERSION")"
printf 'BUILD=%s\n' "$(tr -d '\r\n[:space:]' < "$current/BUILD")"
