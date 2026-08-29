#!/usr/bin/env bash
set -Eeuo pipefail

# Local-only rehearsal for the Phase 6 rollback health wait. It uses a
# disposable filesystem and fake systemctl/curl commands; it never contacts a
# server, service manager, database, or production path.

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
rollback_script="${repo_root}/ops/rollback-v2.sh"
work_root="$(mktemp -d -t cha-m4-phase6-rollback-XXXXXX)"
trap 'rm -rf "$work_root"' EXIT

test -x "$rollback_script" || test -f "$rollback_script"

v2_root="${work_root}/v2"
releases="${v2_root}/releases"
stable="${releases}/stable"
candidate="${releases}/candidate"
current="${v2_root}/current"
env_file="${work_root}/etc/v2.env"
env_backup="${work_root}/backup/v2.env"
fake_bin="${work_root}/fake-bin"
health_count="${work_root}/health-count"
systemctl_log="${work_root}/systemctl.log"
output="${work_root}/rollback.out"

mkdir -p "$stable" "$candidate" "$(dirname "$env_file")" \
  "$(dirname "$env_backup")" "$fake_bin"
printf '0.8.0\n' > "${stable}/VERSION"
printf 'phase6-stable\n' > "${stable}/BUILD"
printf '0123456789abcdef0123456789abcdef01234567\n' > "${stable}/COMMIT"
printf 'test-package-hash\n' > "${stable}/PACKAGE_SHA256"
printf '0.8.0\n' > "${candidate}/VERSION"
printf 'phase6-candidate\n' > "${candidate}/BUILD"
printf 'CANDIDATE=1\n' > "$env_file"
printf 'STABLE=1\n' > "$env_backup"
ln -s "$candidate" "$current"

cat > "${fake_bin}/systemctl" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "${FAKE_SYSTEMCTL_LOG:?}"
case "${1:-}" in
  restart)
    exit 0
    ;;
  is-active)
    printf 'active\n'
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
SH

cat > "${fake_bin}/curl" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
count=0
if [ -f "${FAKE_HEALTH_COUNT:?}" ]; then
  count="$(cat "${FAKE_HEALTH_COUNT}")"
fi
count=$((count + 1))
printf '%s\n' "$count" > "${FAKE_HEALTH_COUNT}"
if [ "$count" -eq 1 ]; then
  printf '000'
  exit 7
fi
printf '200'
SH

chmod 700 "${fake_bin}/systemctl" "${fake_bin}/curl"

PATH="${fake_bin}:${PATH}" \
FAKE_SYSTEMCTL_LOG="$systemctl_log" \
FAKE_HEALTH_COUNT="$health_count" \
CHA_V2_ROOT="$v2_root" \
CHA_V2_CURRENT="$current" \
CHA_V2_ROLLBACK_TARGET="$stable" \
CHA_V2_ENV_FILE="$env_file" \
CHA_V2_ENV_BACKUP="$env_backup" \
CHA_V2_SERVICE="isolated-v2.service" \
CHA_V2_HEALTH_ATTEMPTS=3 \
CHA_V2_HEALTH_RETRY_SECONDS=0 \
  bash "$rollback_script" > "$output"

test "$(readlink -f "$current")" = "$stable"
grep -qx 'STABLE=1' "$env_file"
grep -qx 'restart isolated-v2.service' "$systemctl_log"
test "$(cat "$health_count")" = "2"
grep -qx 'ROLLBACK_HEALTH_ATTEMPT=2' "$output"
grep -qx 'ROLLBACK_LIVE_HTTP=200' "$output"
grep -qx 'ROLLBACK=passed' "$output"
grep -qx 'RUNNING_RELEASE=stable' "$output"
grep -qx 'RUNNING_COMMIT=0123456789abcdef0123456789abcdef01234567' "$output"
grep -qx 'PACKAGE_HASH=test-package-hash' "$output"

printf 'M4_PHASE6_ROLLBACK_REHEARSAL=passed\n'
