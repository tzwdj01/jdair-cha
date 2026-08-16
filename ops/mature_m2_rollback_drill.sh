set -Eeuo pipefail

backup_base="/opt/jdair-cha/backups/20260813-223030-before-m2-dashboard"
rollback_script="${backup_base}/rollback-v2.sh"

test -x "$rollback_script"
test "$(tr -d '\r\n[:space:]' < /opt/jdair-cha/v2/current/VERSION)" = "0.3.0"
test "$(systemctl is-active jdair-cha.service)" = "active"
test "$(systemctl is-active jdair-cha-v2.service)" = "active"

"$rollback_script"
sleep 2

legacy_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-m2-drill-legacy.html -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/)"
v2_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-m2-drill-v2.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/api/v2/health)"
feature_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-m2-drill-features.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/api/v2/system/features)"
dashboard_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-m2-drill-dashboard.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/api/v2/dashboard/overview)"

test "$legacy_http" = "200"
test "$v2_http" = "200"
test "$feature_http" = "200"
test "$dashboard_http" = "404"
grep -q '"version":"0.2.0"' <(curl -sS --max-time 15 http://127.0.0.1:8791/api/v2/system/version)
grep -q '"dashboard_v2":false' /tmp/jdair-cha-m2-drill-features.json

printf 'ROLLBACK_DRILL=passed\n'
printf 'CURRENT_TARGET=%s\n' "$(readlink -f /opt/jdair-cha/v2/current)"
printf 'VERSION=%s\n' "$(tr -d '\r\n[:space:]' < /opt/jdair-cha/v2/current/VERSION)"
printf 'BUILD=%s\n' "$(tr -d '\r\n[:space:]' < /opt/jdair-cha/v2/current/BUILD)"
printf 'LEGACY_SERVICE=%s\n' "$(systemctl is-active jdair-cha.service)"
printf 'V2_SERVICE=%s\n' "$(systemctl is-active jdair-cha-v2.service)"
printf 'LEGACY_HTTP=%s\n' "$legacy_http"
printf 'V2_HTTP=%s\n' "$v2_http"
printf 'FEATURE_HTTP=%s\n' "$feature_http"
printf 'DASHBOARD_HTTP=%s\n' "$dashboard_http"
