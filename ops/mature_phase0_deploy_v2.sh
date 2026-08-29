set -Eeuo pipefail

package="/tmp/jdair-cha-v2-release.tar.gz"
v2_root="/opt/jdair-cha/v2"
release_stamp="$(date +%Y%m%d%H%M%S)"
release_label="${CHA_V2_RELEASE_LABEL:-m2-dashboard-preview}"
release_name="${release_stamp}-${release_label}"
release_dir="${v2_root}/releases/${release_name}"
current_link="${v2_root}/current"
venv_dir="${v2_root}/venv"
service_unit="/etc/systemd/system/jdair-cha-v2.service"
env_dir="/etc/jdair-cha"
env_file="${env_dir}/v2.env"
nginx_site="/etc/nginx/sites-enabled/jdair-cha.conf"
nginx_site_target="$(readlink -f "$nginx_site" 2>/dev/null || printf '%s' "$nginx_site")"
nginx_backup="/tmp/jdair-cha.conf.before-v2-${release_stamp}"
env_backup="/tmp/jdair-cha-v2.env.before-${release_stamp}"
previous_target=""
service_existed="no"
health_base="${CHA_V2_HEALTH_BASE:-http://127.0.0.1:8791}"
health_attempts="${CHA_V2_HEALTH_ATTEMPTS:-12}"
health_retry_seconds="${CHA_V2_HEALTH_RETRY_SECONDS:-0.5}"

case "$health_attempts" in
  ''|*[!0-9]*|0)
    printf 'CHA_V2_HEALTH_ATTEMPTS must be a positive integer\n' >&2
    exit 2
    ;;
esac

wait_for_v2_live() {
  attempt=1
  while [ "$attempt" -le "$health_attempts" ]; do
    service_state="$(systemctl is-active jdair-cha-v2.service 2>/dev/null || true)"
    live_http="$(
      curl -sS -o /dev/null -w '%{http_code}' --max-time 3 \
        "${health_base}/api/v2/health/live" 2>/dev/null || true
    )"
    if [ "$service_state" = "active" ] && [ "$live_http" = "200" ]; then
      printf 'V2_HEALTH_ATTEMPT=%s\n' "$attempt"
      printf 'V2_LIVE_HTTP=%s\n' "$live_http"
      return 0
    fi
    if [ "$attempt" -lt "$health_attempts" ]; then
      sleep "$health_retry_seconds"
    fi
    attempt=$((attempt + 1))
  done
  printf 'V2 service did not become active with live HTTP 200 within bounded retry window\n' >&2
  return 1
}

if [ -L "$current_link" ] || [ -e "$current_link" ]; then
  previous_target="$(readlink -f "$current_link" || true)"
fi
if [ -f "$service_unit" ]; then
  service_existed="yes"
fi

restore_previous() {
  set +e
  if [ -f "$env_backup" ]; then
    install -m 0600 "$env_backup" "$env_file"
  fi
  if [ -f "$nginx_backup" ]; then
    install -m 0644 "$nginx_backup" "$nginx_site_target"
    if [ "$nginx_site" != "$nginx_site_target" ]; then
      ln -sfn "$nginx_site_target" "$nginx_site"
    fi
    nginx -t >/dev/null 2>&1 && systemctl reload nginx >/dev/null 2>&1
  fi
  systemctl stop jdair-cha-v2.service >/dev/null 2>&1
  if [ -n "$previous_target" ] && [ -d "$previous_target" ]; then
    ln -sfn "$previous_target" "$current_link"
    systemctl restart jdair-cha-v2.service >/dev/null 2>&1
    wait_for_v2_live >/dev/null 2>&1 || true
  elif [ "$service_existed" = "no" ]; then
    systemctl disable jdair-cha-v2.service >/dev/null 2>&1
    rm -f "$service_unit"
    systemctl daemon-reload >/dev/null 2>&1
  fi
  rm -rf "$release_dir"
}

on_error() {
  status=$?
  restore_previous
  exit "$status"
}
trap on_error ERR

test -s "$package"
tar -tzf "$package" >/dev/null
package_hash="$(sha256sum "$package" | cut -d' ' -f1)"

install -d -m 0755 -o jdair-demo -g jdair-demo \
  "$v2_root" "$v2_root/releases" "$v2_root/data"
install -d -m 0750 "$env_dir"
cp --dereference --preserve=mode,ownership,timestamps \
  "$nginx_site" "$nginx_backup"
if [ -f "$env_file" ]; then
  cp --dereference --preserve=mode,ownership,timestamps \
    "$env_file" "$env_backup"
fi

mkdir -p "$release_dir"
tar -xzf "$package" -C "$release_dir"
chown -R jdair-demo:jdair-demo "$release_dir"
printf '%s\n' "$package_hash" > "$release_dir/PACKAGE_SHA256"
chown jdair-demo:jdair-demo "$release_dir/PACKAGE_SHA256"

python3 -m compileall -q "$release_dir/app"
release_version="$(tr -d '\r\n[:space:]' < "$release_dir/VERSION")"
release_build="$(tr -d '\r\n[:space:]' < "$release_dir/BUILD" 2>/dev/null || printf 'unknown')"
test -n "$release_version"
test -n "$release_build"
test -s "$release_dir/COMMIT"
test -x "$release_dir/ops/rollback-v2.sh"

if [ ! -x "$venv_dir/bin/python" ]; then
  python3 -m venv "$venv_dir"
fi
pip_args=(
  --disable-pip-version-check
  --no-input
  --no-index
)
if [ -d "$release_dir/wheelhouse" ]; then
  pip_args+=(--find-links "$release_dir/wheelhouse")
fi
"$venv_dir/bin/python" -m pip install \
  "${pip_args[@]}" \
  -r "$release_dir/requirements.lock"
"$venv_dir/bin/python" -m pip check
(cd "$release_dir" && "$venv_dir/bin/python" -m unittest discover -s tests -v)

if [ ! -f "$env_file" ]; then
  cat > "$env_file" <<EOF
CHA_V2_SERVICE_NAME=jdair-cha-v2
CHA_V2_ENVIRONMENT=production
CHA_V2_ALLOWED_HOSTS=cha.jdair.top,127.0.0.1,localhost
CHA_V2_LEGACY_BASE_URL=http://127.0.0.1:8790
CHA_V2_LEGACY_TIMEOUT_SECONDS=20
CHA_V2_DASHBOARD_DEVICE_TTL_SECONDS=15
CHA_V2_DASHBOARD_VIDEO_TTL_SECONDS=180
CHA_V2_DASHBOARD_FLIGHT_TTL_SECONDS=60
CHA_V2_DASHBOARD_ROUTINE_TTL_SECONDS=300
CHA_V2_DASHBOARD_TREND_TTL_SECONDS=300
CHA_V2_DASHBOARD_STALE_SECONDS=3600
CHA_V2_DASHBOARD_INITIAL_WAIT_SECONDS=1.5
CHA_V2_DASHBOARD_STATE_DIR=/opt/jdair-cha/v2/data
CHA_V2_FEATURE_DASHBOARD_V2=false
CHA_V2_FEATURE_REALTIME_READONLY=false
CHA_V2_FEATURE_REALTIME_AUDIO=false
CHA_V2_FEATURE_REALTIME_CONTROL=false
CHA_V2_FEATURE_ACCOUNT_POOL_V2=false
CHA_V2_FEATURE_RECORDS_V2=false
EOF
  chmod 600 "$env_file"
else
  python3 - "$env_file" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
updates = {
    "CHA_V2_LEGACY_BASE_URL": "http://127.0.0.1:8790",
    "CHA_V2_LEGACY_TIMEOUT_SECONDS": "20",
    "CHA_V2_DASHBOARD_DEVICE_TTL_SECONDS": "15",
    "CHA_V2_DASHBOARD_VIDEO_TTL_SECONDS": "180",
    "CHA_V2_DASHBOARD_FLIGHT_TTL_SECONDS": "60",
    "CHA_V2_DASHBOARD_ROUTINE_TTL_SECONDS": "300",
    "CHA_V2_DASHBOARD_TREND_TTL_SECONDS": "300",
    "CHA_V2_DASHBOARD_STALE_SECONDS": "3600",
    "CHA_V2_DASHBOARD_INITIAL_WAIT_SECONDS": "1.5",
    "CHA_V2_DASHBOARD_STATE_DIR": "/opt/jdair-cha/v2/data",
}
lines = path.read_text(encoding="utf-8").splitlines()
seen = set()
output = []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if key in {"CHA_V2_VERSION", "CHA_V2_BUILD"}:
        continue
    if key in updates:
        output.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(f"{key}={value}")
path.write_text("\n".join(output) + "\n", encoding="utf-8")
PY
  chmod 600 "$env_file"
fi

if [ -f "$release_dir/FEATURES.env" ]; then
  python3 - "$env_file" "$release_dir/FEATURES.env" <<'PY'
from pathlib import Path
import sys

env_path = Path(sys.argv[1])
feature_path = Path(sys.argv[2])
allowed = {
    "CHA_V2_FEATURE_DASHBOARD_V2",
    "CHA_V2_FEATURE_REALTIME_READONLY",
    "CHA_V2_FEATURE_REALTIME_AUDIO",
    "CHA_V2_FEATURE_REALTIME_CONTROL",
    "CHA_V2_FEATURE_ACCOUNT_POOL_V2",
    "CHA_V2_FEATURE_RECORDS_V2",
}
updates = {}
for line in feature_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    if "=" not in line:
        raise SystemExit(f"Invalid feature line: {line}")
    key, value = (part.strip() for part in line.split("=", 1))
    if key not in allowed:
        raise SystemExit(f"Unsupported feature key: {key}")
    if value.lower() not in {"true", "false"}:
        raise SystemExit(f"Feature value must be true or false: {key}")
    updates[key] = value.lower()

lines = env_path.read_text(encoding="utf-8").splitlines()
seen = set()
output = []
for line in lines:
    key = line.split("=", 1)[0].strip() if "=" in line else ""
    if key in updates:
        output.append(f"{key}={updates[key]}")
        seen.add(key)
    else:
        output.append(line)
for key, value in updates.items():
    if key not in seen:
        output.append(f"{key}={value}")
env_path.write_text("\n".join(output) + "\n", encoding="utf-8")
PY
  chmod 600 "$env_file"
fi

cat > "$service_unit" <<EOF
[Unit]
Description=JD Air CHA modular API v2
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=jdair-demo
Group=jdair-demo
WorkingDirectory=/opt/jdair-cha/v2/current
EnvironmentFile=/etc/jdair-cha/v2.env
ExecStart=/opt/jdair-cha/v2/venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8791 --proxy-headers --forwarded-allow-ips=127.0.0.1
Restart=always
RestartSec=3
TimeoutStopSec=15
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=full
ProtectHome=true
ReadWritePaths=/opt/jdair-cha/v2

[Install]
WantedBy=multi-user.target
EOF
chmod 644 "$service_unit"

ln -sfn "$release_dir" "$current_link"
chown -h jdair-demo:jdair-demo "$current_link"

if [ -n "$previous_target" ] && [ -d "$previous_target" ]; then
  previous_env_backup="$release_dir/previous-v2.env"
  if [ -f "$env_backup" ]; then
    install -m 0600 "$env_backup" "$previous_env_backup"
  else
    install -m 0600 "$env_file" "$previous_env_backup"
  fi
  cat > "$release_dir/rollback-to-previous.sh" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
CHA_V2_ROOT="/opt/jdair-cha/v2" \\
CHA_V2_CURRENT="/opt/jdair-cha/v2/current" \\
CHA_V2_ROLLBACK_TARGET="${previous_target}" \\
CHA_V2_ENV_FILE="/etc/jdair-cha/v2.env" \\
CHA_V2_ENV_BACKUP="${previous_env_backup}" \\
CHA_V2_SERVICE="jdair-cha-v2.service" \\
CHA_V2_HEALTH_BASE="${health_base}" \\
exec "\$(dirname "\$0")/ops/rollback-v2.sh"
EOF
  chmod 700 "$release_dir/rollback-to-previous.sh"
  chown jdair-demo:jdair-demo "$release_dir/rollback-to-previous.sh"
fi

systemctl daemon-reload
systemctl enable jdair-cha-v2.service
systemctl restart jdair-cha-v2.service
wait_for_v2_live

test "$(systemctl is-active jdair-cha-v2.service)" = "active"
direct_http="$(curl -sS -o /tmp/jdair-cha-v2-direct.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1:8791/api/v2/health)"
test "$direct_http" = "200"
grep -q '"status":"ok"' /tmp/jdair-cha-v2-direct.json

python3 - "$nginx_site" <<'PY'
from pathlib import Path
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
marker = "# BEGIN CHA V2 MANAGED"
if marker not in text:
    block = r'''
    # BEGIN CHA V2 MANAGED
    location ^~ /api/v2/ {
        proxy_pass http://127.0.0.1:8791;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }

    location ^~ /ws/v2/ {
        proxy_pass http://127.0.0.1:8791;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 3600s;
        proxy_send_timeout 3600s;
    }
    # END CHA V2 MANAGED

'''
    anchor = "    location / {"
    if anchor not in text:
        raise SystemExit("Could not find the legacy location anchor")
    text = text.replace(anchor, block + anchor, 1)
    path.write_text(text, encoding="utf-8")
PY

nginx -t
systemctl reload nginx
sleep 2

proxied_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-v2-proxied.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/api/v2/health)"
legacy_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-legacy-root.html -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/)"
feature_http="$(curl -sS -H 'Host: cha.jdair.top' \
  -o /tmp/jdair-cha-v2-features.json -w '%{http_code}' \
  --max-time 15 http://127.0.0.1/api/v2/system/features)"

test "$proxied_http" = "200"
test "$legacy_http" = "200"
test "$feature_http" = "200"
grep -q '"status":"ok"' /tmp/jdair-cha-v2-proxied.json
expected_dashboard="false"
if [ -f "$release_dir/FEATURES.env" ]; then
  expected_dashboard="$(awk -F= '$1=="CHA_V2_FEATURE_DASHBOARD_V2"{print tolower($2)}' "$release_dir/FEATURES.env" | tail -n1)"
fi
test -n "$expected_dashboard"
grep -q "\"dashboard_v2\":${expected_dashboard}" /tmp/jdair-cha-v2-features.json
grep -q '"realtime_readonly":false' /tmp/jdair-cha-v2-features.json

dashboard_page_http="not-enabled"
dashboard_api_http="not-enabled"
if [ "$expected_dashboard" = "true" ]; then
  dashboard_page_http="$(curl -sS -H 'Host: cha.jdair.top' \
    -o /tmp/jdair-cha-v2-dashboard.html -w '%{http_code}' \
    --max-time 15 http://127.0.0.1/api/v2/dashboard)"
  dashboard_api_http="$(curl -sS -H 'Host: cha.jdair.top' \
    -o /tmp/jdair-cha-v2-dashboard-api.json -w '%{http_code}' \
    --max-time 15 http://127.0.0.1/api/v2/dashboard/overview)"
  test "$dashboard_page_http" = "200"
  test "$dashboard_api_http" = "401"
  grep -q 'CHA 态势总览' /tmp/jdair-cha-v2-dashboard.html
  grep -q '"authentication_required"' /tmp/jdair-cha-v2-dashboard-api.json
fi

release_hash="$(find "$release_dir" -type f -print0 | sort -z | xargs -0 sha256sum | sha256sum | cut -d' ' -f1)"

printf 'RELEASE_NAME=%s\n' "$release_name"
printf 'RELEASE_DIR=%s\n' "$release_dir"
printf 'PREVIOUS_TARGET=%s\n' "$previous_target"
printf 'CURRENT_TARGET=%s\n' "$(readlink -f "$current_link")"
printf 'RUNNING_RELEASE=%s\n' "$(basename "$(readlink -f "$current_link")")"
printf 'RUNNING_COMMIT=%s\n' "$(tr -d '\r\n[:space:]' < "$release_dir/COMMIT")"
printf 'PACKAGE_SHA256=%s\n' "$package_hash"
printf 'PACKAGE_HASH=%s\n' "$(tr -d '\r\n[:space:]' < "$release_dir/PACKAGE_SHA256")"
printf 'RELEASE_TREE_SHA256=%s\n' "$release_hash"
printf 'V2_SERVICE=%s\n' "$(systemctl is-active jdair-cha-v2.service)"
printf 'LEGACY_SERVICE=%s\n' "$(systemctl is-active jdair-cha.service)"
printf 'DIRECT_HTTP=%s\n' "$direct_http"
printf 'PROXIED_HTTP=%s\n' "$proxied_http"
printf 'FEATURE_HTTP=%s\n' "$feature_http"
printf 'DASHBOARD_PAGE_HTTP=%s\n' "$dashboard_page_http"
printf 'DASHBOARD_API_HTTP=%s\n' "$dashboard_api_http"
printf 'LEGACY_HTTP=%s\n' "$legacy_http"
printf 'DASHBOARD_V2=%s\n' "$expected_dashboard"
printf 'VERSION=%s\n' "$release_version"
printf 'BUILD=%s\n' "$release_build"
printf 'ROLLBACK_TO_PREVIOUS=%s\n' "$release_dir/rollback-to-previous.sh"

trap - ERR
