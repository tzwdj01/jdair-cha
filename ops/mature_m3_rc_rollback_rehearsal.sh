#!/usr/bin/env bash
set -Eeuo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rollback_script="${script_dir}/rollback-v2.sh"
result_path="${1:-m3-rc-rollback-result.json}"
work_root="$(mktemp -d -t cha-m3-rollback-XXXXXX)"
trap 'rm -rf "$work_root"' EXIT

v2_root="${work_root}/v2"
releases="${v2_root}/releases"
current="${v2_root}/current"
env_file="${work_root}/etc/v2.env"
env_backup="${work_root}/backup/v2.env"
previous="${releases}/0.6.0-m3-four-grid-realtime"
candidate="${releases}/0.7.0-m3-realtime-rc"

mkdir -p "$previous" "$candidate" "$(dirname "$env_file")" \
  "$(dirname "$env_backup")"
printf '0.6.0\n' > "$previous/VERSION"
printf 'm3-four-grid-realtime\n' > "$previous/BUILD"
printf 'CHA_V2_FEATURE_REALTIME_READONLY=false\nSTABLE=1\n' > "$env_file"
cp "$env_file" "$env_backup"
printf '0.7.0\n' > "$candidate/VERSION"
printf 'm3-realtime-rc\n' > "$candidate/BUILD"
printf 'CHA_V2_FEATURE_REALTIME_READONLY=false\nRC=1\n' \
  > "${work_root}/candidate.env"

ln -s "$previous" "$current"
before_target="$(readlink -f "$current")"
before_env_sha="$(sha256sum "$env_file" | cut -d' ' -f1)"

ln -sfn "$candidate" "$current"
install -m 0600 "${work_root}/candidate.env" "$env_file"
test "$(tr -d '\r\n[:space:]' < "$current/VERSION")" = "0.7.0"
test "$(tr -d '\r\n[:space:]' < "$current/BUILD")" = "m3-realtime-rc"
grep -q '^CHA_V2_FEATURE_REALTIME_READONLY=false$' "$env_file"

CHA_V2_ROOT="$v2_root" \
CHA_V2_CURRENT="$current" \
CHA_V2_ROLLBACK_TARGET="$previous" \
CHA_V2_ENV_FILE="$env_file" \
CHA_V2_ENV_BACKUP="$env_backup" \
  "$rollback_script" >/dev/null

after_target="$(readlink -f "$current")"
after_env_sha="$(sha256sum "$env_file" | cut -d' ' -f1)"
version="$(tr -d '\r\n[:space:]' < "$current/VERSION")"
build="$(tr -d '\r\n[:space:]' < "$current/BUILD")"

test "$after_target" = "$before_target"
test "$after_env_sha" = "$before_env_sha"
test "$version" = "0.6.0"
test "$build" = "m3-four-grid-realtime"
grep -q '^CHA_V2_FEATURE_REALTIME_READONLY=false$' "$env_file"

python3 - "$result_path" "$before_target" "$after_target" \
  "$before_env_sha" "$after_env_sha" "$version" "$build" <<'PY'
import json
import sys
from pathlib import Path

path, before, after, before_sha, after_sha, version, build = sys.argv[1:]
Path(path).write_text(
    json.dumps(
        {
            "status": "PASS",
            "previous_target": before,
            "restored_target": after,
            "environment_sha256_before": before_sha,
            "environment_sha256_after": after_sha,
            "version": version,
            "build": build,
            "realtime_enabled": False,
        },
        ensure_ascii=False,
        indent=2,
    ),
    encoding="utf-8",
)
PY

printf 'ROLLBACK_REHEARSAL=PASS\n'
printf 'RESULT=%s\n' "$result_path"
