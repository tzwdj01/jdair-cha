#!/usr/bin/env bash
set -Eeuo pipefail

stamp="$(date +%Y%m%d-%H%M%S)"
backup_root="${CHA_BACKUP_ROOT:-/opt/jdair-cha/backups}"
backup_name="${stamp}-before-m3-realtime"
backup_base="${backup_root}/${backup_name}"
backup_archive="${backup_root}/jdair-cha-before-m3-realtime-${stamp}.tar.gz"
legacy_current="${CHA_LEGACY_CURRENT:-/opt/jdair-cha/current}"
v2_current="${CHA_V2_CURRENT:-/opt/jdair-cha/v2/current}"
legacy_target="$(readlink -f "$legacy_current")"
v2_target="$(readlink -f "$v2_current")"
nginx_site="${CHA_NGINX_SITE:-/etc/nginx/sites-enabled/jdair-cha.conf}"
nginx_target="$(readlink -f "$nginx_site" 2>/dev/null || printf '%s' "$nginx_site")"
v2_env="${CHA_V2_ENV_FILE:-/etc/jdair-cha/v2.env}"
legacy_service="${CHA_LEGACY_SERVICE:-jdair-cha.service}"
v2_service="${CHA_V2_SERVICE:-jdair-cha-v2.service}"
v2_was_active="$(systemctl is-active "$v2_service" || true)"

restore_v2() {
  if [ "$v2_was_active" = "active" ]; then
    systemctl start "$v2_service" >/dev/null 2>&1 || true
  fi
}
trap restore_v2 EXIT

test -d "$legacy_target"
test -d "$v2_target"
test -f "$v2_target/VERSION"
test -f "$v2_target/BUILD"
test -f "$nginx_site"
test -f "$v2_env"
test "$(systemctl is-active "$legacy_service")" = "active"
test "$(systemctl is-active "$v2_service")" = "active"
nginx -t

systemctl stop "$v2_service"

mkdir -p \
  "$backup_base/legacy" \
  "$backup_base/v2" \
  "$backup_base/etc/systemd" \
  "$backup_base/etc/nginx" \
  "$backup_base/etc/jdair-cha" \
  "$backup_base/meta"

cp -a "$legacy_target" "$backup_base/legacy/current-release"
cp -a "$legacy_current" "$backup_base/legacy/current"
cp -a /opt/jdair-cha/v2/releases "$backup_base/v2/"
cp -a "$v2_current" "$backup_base/v2/current"
if [ -d /opt/jdair-cha/v2/data ]; then
  cp -a /opt/jdair-cha/v2/data "$backup_base/v2/"
fi
cp --dereference --preserve=mode,ownership,timestamps \
  "/etc/systemd/system/${legacy_service}" \
  "$backup_base/etc/systemd/${legacy_service}"
cp --dereference --preserve=mode,ownership,timestamps \
  "/etc/systemd/system/${v2_service}" \
  "$backup_base/etc/systemd/${v2_service}"
cp --dereference --preserve=mode,ownership,timestamps \
  "$nginx_site" \
  "$backup_base/etc/nginx/jdair-cha.conf"
cp --dereference --preserve=mode,ownership,timestamps \
  "$v2_env" \
  "$backup_base/etc/jdair-cha/v2.env"

{
  printf 'created_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'purpose=before-m3-realtime\n'
  printf 'legacy_target=%s\n' "$legacy_target"
  printf 'v2_target=%s\n' "$v2_target"
  printf 'v2_version=%s\n' "$(tr -d '\r\n[:space:]' < "$v2_target/VERSION")"
  printf 'v2_build=%s\n' "$(tr -d '\r\n[:space:]' < "$v2_target/BUILD")"
  printf 'nginx_target=%s\n' "$nginx_target"
  printf 'nginx_sha256=%s\n' "$(sha256sum "$nginx_site" | cut -d' ' -f1)"
  printf 'v2_env_sha256=%s\n' "$(sha256sum "$v2_env" | cut -d' ' -f1)"
  printf 'v2_data_bytes=%s\n' \
    "$(du -sb /opt/jdair-cha/v2/data 2>/dev/null | awk '{print $1}' || printf '0')"
} > "$backup_base/meta/manifest.txt"

cat > "$backup_base/rollback-v2.sh" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
backup_base="${backup_base}"
legacy_target="${legacy_target}"
v2_target="${v2_target}"
nginx_site="${nginx_site}"
nginx_target="${nginx_target}"
v2_env="${v2_env}"
legacy_service="${legacy_service}"
v2_service="${v2_service}"

test -d "\$legacy_target"
test -d "\$v2_target"
test -f "\$backup_base/etc/nginx/jdair-cha.conf"
test -f "\$backup_base/etc/jdair-cha/v2.env"

systemctl stop "\$v2_service" >/dev/null 2>&1 || true
cp -a "\$backup_base/v2/releases/." /opt/jdair-cha/v2/releases/
if [ -d "\$backup_base/v2/data" ]; then
  install -d -m 0755 /opt/jdair-cha/v2/data
  cp -a "\$backup_base/v2/data/." /opt/jdair-cha/v2/data/
fi
ln -sfn "\$legacy_target" "${legacy_current}"
ln -sfn "\$v2_target" "${v2_current}"
install -m 0644 \
  "\$backup_base/etc/systemd/\$legacy_service" \
  "/etc/systemd/system/\$legacy_service"
install -m 0644 \
  "\$backup_base/etc/systemd/\$v2_service" \
  "/etc/systemd/system/\$v2_service"
install -m 0600 "\$backup_base/etc/jdair-cha/v2.env" "\$v2_env"
install -m 0644 "\$backup_base/etc/nginx/jdair-cha.conf" "\$nginx_target"
if [ "\$nginx_site" != "\$nginx_target" ]; then
  ln -sfn "\$nginx_target" "\$nginx_site"
fi

systemctl daemon-reload
nginx -t
systemctl reload nginx
systemctl restart "\$legacy_service"
systemctl restart "\$v2_service"
EOF
chmod 700 "$backup_base/rollback-v2.sh"

find "$backup_base" -type f ! -path "$backup_base/meta/files.sha256" -print0 \
  | sort -z | xargs -0 sha256sum > "$backup_base/meta/files.sha256"
tar --numeric-owner -C / -czf "$backup_archive" "${backup_base#/}"
tar -tzf "$backup_archive" > "${backup_archive}.contents.txt"
sha256sum "$backup_archive" > "${backup_archive}.sha256"
chmod 600 "$backup_archive" "${backup_archive}.sha256" "${backup_archive}.contents.txt"

restore_v2
trap - EXIT
sleep 3

test "$(systemctl is-active "$legacy_service")" = "active"
test "$(systemctl is-active "$v2_service")" = "active"
tar -tzf "$backup_archive" >/dev/null
(cd / && sha256sum -c "${backup_archive}.sha256")

printf 'BACKUP_NAME=%s\n' "$backup_name"
printf 'BACKUP_BASE=%s\n' "$backup_base"
printf 'BACKUP_ARCHIVE=%s\n' "$backup_archive"
printf 'ARCHIVE_SHA256=%s\n' "$(cut -d' ' -f1 "${backup_archive}.sha256")"
printf 'ARCHIVE_SIZE=%s\n' "$(stat -c '%s' "$backup_archive")"
printf 'ROLLBACK_SCRIPT=%s\n' "$backup_base/rollback-v2.sh"
