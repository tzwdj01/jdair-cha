#!/usr/bin/env bash
set -Eeuo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
release_script="${repo_root}/ops/mature_m3_final_release.sh"
result_path="${1:-${repo_root}/m3-release-fix-rehearsal-result.json}"
work_root="$(mktemp -d -t cha-m3-release-rehearsal-XXXXXX)"
trap 'rm -rf "$work_root"' EXIT

fixture="${work_root}/fixture"
package="${work_root}/candidate.tar.gz"
mkdir -p "$fixture/app" "$fixture/tests"
printf '0.8.0\n' > "$fixture/VERSION"
printf 'm3-final-rc\n' > "$fixture/BUILD"
cat > "$fixture/FEATURES.env" <<'EOF'
CHA_V2_FEATURE_REALTIME_READONLY=false
CHA_V2_FEATURE_REALTIME_AUDIO=false
CHA_V2_FEATURE_REALTIME_CONTROL=false
CHA_V2_FEATURE_ACCOUNT_POOL_V2=false
EOF
printf '' > "$fixture/app/__init__.py"
cat > "$fixture/tests/test_smoke.py" <<'PY'
import unittest


class SmokeTest(unittest.TestCase):
    def test_release_fixture(self):
        self.assertTrue(True)
PY
tar -C "$fixture" -czf "$package" .
package_sha="$(sha256sum "$package" | cut -d' ' -f1)"

fake_bin="${work_root}/fake-bin"
mkdir -p "$fake_bin"
cat > "$fake_bin/systemctl" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
case "${1:-}" in
  restart)
    printf 'restart %s\n' "${2:-}" >> "$FAKE_SYSTEMCTL_LOG"
    ;;
  is-active)
    printf 'active\n'
    ;;
  *)
    printf 'unexpected systemctl command: %s\n' "$*" >&2
    exit 2
    ;;
esac
SH
cat > "$fake_bin/curl" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s' "${FAKE_HEALTH_STATUS:-200}"
SH
cat > "$fake_bin/sleep" <<'SH'
#!/usr/bin/env bash
exit 0
SH
chmod 755 "$fake_bin/systemctl" "$fake_bin/curl" "$fake_bin/sleep"

prepare_scenario() {
  scenario="$1"
  scenario_root="${work_root}/${scenario}/v2"
  previous="${scenario_root}/releases/previous"
  current="${scenario_root}/current"
  venv_python="${scenario_root}/venv/bin/python"
  mkdir -p "$previous" "$(dirname "$venv_python")"
  printf '0.3.0\n' > "$previous/VERSION"
  printf 'm2-dashboard-preview\n' > "$previous/BUILD"
  ln -s "$previous" "$current"
  printf 'verified\n' > "${work_root}/${scenario}/backup.proof"
  : > "${work_root}/${scenario}/systemctl.log"
  : > "${work_root}/${scenario}/python.log"
  cat > "$venv_python" <<'SH'
#!/usr/bin/env bash
set -Eeuo pipefail
printf '%s\n' "$*" >> "$FAKE_PYTHON_LOG"
if [ "${FAKE_EXPECT_TEST_ENV_SANITIZED:-false}" = "true" ] \
  && printf '%s\n' "$*" | grep -q -- '-m unittest'; then
  test -z "${CHA_PG_HOST:-}"
  test -z "${CHA_V2_AEE_USERNAME:-}"
  test -z "${PGGSSENCMODE:-}"
fi
if [ "${FAKE_TEST_FAILURE:-false}" = "true" ] \
  && printf '%s\n' "$*" | grep -q -- '-m unittest'; then
  exit 42
fi
exec /usr/bin/python3 "$@"
SH
  chmod 755 "$venv_python"
}

run_release() {
  scenario="$1"
  release_name="$2"
  set +e
  PATH="${fake_bin}:$PATH" \
  FAKE_SYSTEMCTL_LOG="${work_root}/${scenario}/systemctl.log" \
  FAKE_PYTHON_LOG="${work_root}/${scenario}/python.log" \
  FAKE_TEST_FAILURE="${FAKE_TEST_FAILURE:-false}" \
  FAKE_EXPECT_TEST_ENV_SANITIZED=true \
  FAKE_HEALTH_STATUS="${FAKE_HEALTH_STATUS:-200}" \
  CHA_PG_HOST="release-test-must-not-leak" \
  CHA_V2_AEE_USERNAME="release-test-must-not-leak" \
  PGGSSENCMODE=disable \
  CHA_M3_PACKAGE="$package" \
  CHA_M3_PACKAGE_SHA256="$package_sha" \
  CHA_V2_ROOT="${work_root}/${scenario}/v2" \
  CHA_V2_CURRENT="${work_root}/${scenario}/v2/current" \
  CHA_V2_VENV_PYTHON="${work_root}/${scenario}/v2/venv/bin/python" \
  CHA_V2_SERVICE="isolated-v2.service" \
  CHA_M3_RELEASE_NAME="$release_name" \
  CHA_M3_BACKUP_PROOF="${work_root}/${scenario}/backup.proof" \
  CHA_M3_RELEASE_DRY_RUN=false \
  CHA_M3_RELEASE_APPROVED=true \
  CHA_M3_STARTUP_WAIT_SECONDS=0 \
  CHA_M3_HEALTH_BASE="http://127.0.0.1:18791" \
    bash "$release_script" \
    >"${work_root}/${scenario}/stdout.log" \
    2>"${work_root}/${scenario}/stderr.log"
  scenario_rc=$?
  set -e
}

prepare_scenario success
FAKE_TEST_FAILURE=false FAKE_HEALTH_STATUS=200 \
  run_release success candidate-success
if [ "$scenario_rc" -ne 0 ]; then
  cat "${work_root}/success/stdout.log"
  cat "${work_root}/success/stderr.log" >&2
  exit "$scenario_rc"
fi
test "$scenario_rc" -eq 0
test "$(readlink -f "${work_root}/success/v2/current")" = \
  "${work_root}/success/v2/releases/candidate-success"
test "$(wc -l < "${work_root}/success/systemctl.log")" -eq 1
grep -q -- '-m unittest discover -s tests -v' \
  "${work_root}/success/python.log"

prepare_scenario test-failure
FAKE_TEST_FAILURE=true FAKE_HEALTH_STATUS=200 \
  run_release test-failure candidate-test-failure
test "$scenario_rc" -ne 0
test "$(readlink -f "${work_root}/test-failure/v2/current")" = \
  "${work_root}/test-failure/v2/releases/previous"
test ! -e \
  "${work_root}/test-failure/v2/releases/candidate-test-failure"
test ! -s "${work_root}/test-failure/systemctl.log"

prepare_scenario health-failure
FAKE_TEST_FAILURE=false FAKE_HEALTH_STATUS=503 \
  run_release health-failure candidate-health-failure
test "$scenario_rc" -ne 0
test "$(readlink -f "${work_root}/health-failure/v2/current")" = \
  "${work_root}/health-failure/v2/releases/previous"
test "$(wc -l < "${work_root}/health-failure/systemctl.log")" -eq 2

python3 - "$result_path" <<'PY'
import json
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "status": "PASS",
            "production_venv_python": "PASS",
            "test_failure_fail_fast": "PASS",
            "test_failure_service_restarts": 0,
            "health_failure_single_rollback": "PASS",
            "health_failure_total_restarts": 2,
            "production_paths_touched": False,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
PY

printf 'M3_FINAL_RELEASE_REHEARSAL=PASS\n'
printf 'RESULT=%s\n' "$result_path"
