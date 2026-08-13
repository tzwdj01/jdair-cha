set -Eeuo pipefail

legacy_target="$(readlink -f /opt/jdair-cha/current)"
v2_target="$(readlink -f /opt/jdair-cha/v2/current)"

test "$(systemctl is-active jdair-cha.service)" = "active"
test "$(systemctl is-active jdair-cha-v2.service)" = "active"
test -d "$legacy_target"
test -d "$v2_target"
nginx -t >/dev/null

legacy_http="$(curl -sS -o /tmp/jdair-cha-m2-legacy.html -w '%{http_code}' \
  --max-time 15 http://127.0.0.1:8790/)"
v2_http="$(curl -sS -o /tmp/jdair-cha-m2-v2-health.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1:8791/api/v2/health)"
proxied_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-m2-v2-proxy.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/api/v2/health)"
feature_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-m2-features.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/api/v2/system/features)"

test "$legacy_http" = "200"
test "$v2_http" = "200"
test "$proxied_http" = "200"
test "$feature_http" = "200"

printf 'LEGACY_TARGET=%s\n' "$legacy_target"
printf 'V2_TARGET=%s\n' "$v2_target"
printf 'LEGACY_SERVICE=%s\n' "$(systemctl is-active jdair-cha.service)"
printf 'V2_SERVICE=%s\n' "$(systemctl is-active jdair-cha-v2.service)"
printf 'LEGACY_HTTP=%s\n' "$legacy_http"
printf 'V2_HTTP=%s\n' "$v2_http"
printf 'PROXIED_HTTP=%s\n' "$proxied_http"
printf 'FEATURE_HTTP=%s\n' "$feature_http"
printf 'VERSION=%s\n' "$(tr -d '\r\n[:space:]' < "$v2_target/VERSION")"
printf 'BUILD=%s\n' "$(tr -d '\r\n[:space:]' < "$v2_target/BUILD")"
printf 'FEATURES=%s\n' "$(cat /tmp/jdair-cha-m2-features.json)"
printf 'NGINX_SHA256=%s\n' "$(sha256sum /etc/nginx/sites-enabled/jdair-cha.conf | cut -d' ' -f1)"
printf 'ENV_SHA256=%s\n' "$(sha256sum /etc/jdair-cha/v2.env | cut -d' ' -f1)"
