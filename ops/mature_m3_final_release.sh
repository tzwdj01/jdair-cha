#!/usr/bin/env bash
set -Eeuo pipefail

# M3 Final guarded release helper. It is intentionally dry-run by default.
# Actual production execution requires both an approval flag and a verified
# backup proof created by the separately reviewed backup procedure.

package="${CHA_M3_PACKAGE:-mature-modernization/jdair-cha-v2-m3-final-rc.tar.gz}"
expected_sha="${CHA_M3_PACKAGE_SHA256:-}"
root="${CHA_V2_ROOT:-/opt/jdair-cha/v2}"
current="${CHA_V2_CURRENT:-${root}/current}"
service="${CHA_V2_SERVICE:-jdair-cha-v2.service}"
release_name="${CHA_M3_RELEASE_NAME:-0.8.0-m3-final-rc-release-fix}"
release_dir="${root}/releases/${release_name}"
backup_proof="${CHA_M3_BACKUP_PROOF:-}"
dry_run="${CHA_M3_RELEASE_DRY_RUN:-true}"
approved="${CHA_M3_RELEASE_APPROVED:-false}"
health_base="${CHA_M3_HEALTH_BASE:-http://127.0.0.1:8791}"
venv_python="${CHA_V2_VENV_PYTHON:-${root}/venv/bin/python}"
startup_wait_seconds="${CHA_M3_STARTUP_WAIT_SECONDS:-3}"

test -s "$package"
test -x "$venv_python"
tar -tzf "$package" >/dev/null
actual_sha="$(sha256sum "$package" | cut -d' ' -f1)"
if [ -n "$expected_sha" ] && [ "$actual_sha" != "$expected_sha" ]; then
  printf 'package checksum mismatch\n' >&2
  exit 2
fi

work_root="$(mktemp -d -t cha-m3-final-release-XXXXXX)"
trap 'rm -rf "$work_root"' EXIT
tar -xzf "$package" -C "$work_root"
version="$(tr -d '\r\n[:space:]' < "$work_root/VERSION")"
build="$(tr -d '\r\n[:space:]' < "$work_root/BUILD")"
test "$version" = "0.8.0"
test "$build" = "m3-final-rc"
grep -q '^CHA_V2_FEATURE_REALTIME_READONLY=false$' "$work_root/FEATURES.env"
grep -q '^CHA_V2_FEATURE_REALTIME_AUDIO=false$' "$work_root/FEATURES.env"
grep -q '^CHA_V2_FEATURE_REALTIME_CONTROL=false$' "$work_root/FEATURES.env"
grep -q '^CHA_V2_FEATURE_ACCOUNT_POOL_V2=false$' "$work_root/FEATURES.env"
"$venv_python" -m compileall -q "$work_root/app"

root_resolved="$(readlink -m "$root")"
release_resolved="$(readlink -m "$release_dir")"
case "$release_resolved" in
  "$root_resolved"/releases/*) ;;
  *)
    printf 'release target must stay inside %s/releases\n' "$root_resolved" >&2
    exit 2
    ;;
esac

printf 'M3_FINAL_RELEASE_PLAN=validated\n'
printf 'DRY_RUN=%s\n' "$dry_run"
printf 'PACKAGE=%s\n' "$package"
printf 'PACKAGE_SHA256=%s\n' "$actual_sha"
printf 'VERSION=%s\n' "$version"
printf 'BUILD=%s\n' "$build"
printf 'CURRENT=%s\n' "$current"
printf 'RELEASE_DIR=%s\n' "$release_dir"
printf 'SERVICE=%s\n' "$service"
printf 'HEALTH_BASE=%s\n' "$health_base"
printf 'VENV_PYTHON=%s\n' "$venv_python"
printf 'FEATURES_DEFAULT_CLOSED=true\n'

if [ "$dry_run" = "true" ]; then
  exit 0
fi

if [ "$approved" != "true" ]; then
  printf 'CHA_M3_RELEASE_APPROVED=true is required for a non-dry-run\n' >&2
  exit 2
fi
if [ -z "$backup_proof" ] || [ ! -s "$backup_proof" ]; then
  printf 'a verified CHA_M3_BACKUP_PROOF file is required\n' >&2
  exit 2
fi

previous_target=""
if [ -L "$current" ] || [ -e "$current" ]; then
  previous_target="$(readlink -f "$current" || true)"
fi
test -n "$previous_target"
test -d "$previous_target"

switched_current=false
rollback_attempted=false

rollback_on_error() {
  rc=$?
  trap - ERR
  set +e
  if [ "$switched_current" = "true" ] \
    && [ "$rollback_attempted" = "false" ] \
    && [ -d "$previous_target" ]; then
    rollback_attempted=true
    ln -sfn "$previous_target" "$current"
    systemctl restart "$service"
  fi
  exit "$rc"
}
trap 'rollback_on_error' ERR

run_candidate_tests() {
  # The production EnvironmentFile is intentionally rich in CHA/AEE/MCS8 and
  # PostgreSQL settings.  The package test suite must run against its own
  # defaults, rather than inheriting those live settings and turning a
  # deterministic release check into a production-configuration check.
  #
  # Preserve PATH and generic test controls (used by the isolated rehearsal),
  # but remove every supported runtime-configuration namespace in this
  # subshell.  Nothing is changed in the parent deployment environment.
  local test_home="${work_root}/.release-test-home"
  install -d -m 0700 "$test_home"
  (
    while IFS='=' read -r variable_name _; do
      case "$variable_name" in
        CHA_*|PG*|DATABASE_URL|MCS8_*|AEE_*)
          unset "$variable_name"
          ;;
      esac
    done < <(env)
    export HOME="$test_home"
    "$venv_python" -m unittest discover -s tests -v
  )
}

# Validate the extracted candidate with the exact interpreter used by the
# production service. A test failure occurs before current is switched and
# therefore must not restart the service.  This is deliberately isolated from
# protected production runtime configuration.
(cd "$work_root" && run_candidate_tests)

test ! -e "$release_dir"
install -d -m 0755 "$(dirname "$release_dir")"
mkdir "$release_dir"
tar -xzf "$package" -C "$release_dir"
"$venv_python" -m compileall -q "$release_dir/app"

ln -sfn "$release_dir" "$current"
switched_current=true
systemctl restart "$service"
sleep "$startup_wait_seconds"
test "$(systemctl is-active "$service")" = "active"
test "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
  "${health_base}/api/v2/health/live")" = "200"
test "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 \
  "${health_base}/api/v2/health/ready")" = "200"

trap - ERR
printf 'M3_FINAL_RELEASE=passed\n'
printf 'CURRENT_TARGET=%s\n' "$(readlink -f "$current")"
