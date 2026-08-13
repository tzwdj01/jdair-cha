set -Eeuo pipefail

stamp="$(date +%Y%m%d-%H%M%S)"
backup_root="/opt/jdair-cha/backups"
backup_name="${stamp}-before-m1-legacy-adapter"
backup_base="${backup_root}/${backup_name}"
backup_archive="${backup_root}/jdair-cha-before-m1-legacy-adapter-${stamp}.tar.gz"
legacy_target="$(readlink -f /opt/jdair-cha/current)"
v2_target="$(readlink -f /opt/jdair-cha/v2/current)"
nginx_site="/etc/nginx/sites-enabled/jdair-cha.conf"
nginx_target="$(readlink -f "$nginx_site" 2>/dev/null || printf '%s' "$nginx_site")"
v2_was_active="$(systemctl is-active jdair-cha-v2.service || true)"

restore_v2() {
  if [ "$v2_was_active" = "active" ]; then
    systemctl start jdair-cha-v2.service >/dev/null 2>&1 || true
  fi
}
trap restore_v2 EXIT

test "$legacy_target" = "/opt/jdair-cha/releases/20260812212342-layout-redesign-phase5"
test -d "$v2_target"
test "$(systemctl is-active jdair-cha.service)" = "active"
nginx -t

systemctl stop jdair-cha-v2.service

mkdir -p \
  "$backup_base/v2" \
  "$backup_base/etc/systemd" \
  "$backup_base/etc/nginx" \
  "$backup_base/etc/jdair-cha" \
  "$backup_base/meta"

cp -a /opt/jdair-cha/v2/releases "$backup_base/v2/"
cp -a /opt/jdair-cha/v2/current "$backup_base/v2/current"
cp --dereference --preserve=mode,ownership,timestamps \
  /etc/systemd/system/jdair-cha-v2.service \
  "$backup_base/etc/systemd/jdair-cha-v2.service"
cp --dereference --preserve=mode,ownership,timestamps \
  "$nginx_site" \
  "$backup_base/etc/nginx/jdair-cha.conf"
cp --dereference --preserve=mode,ownership,timestamps \
  /etc/jdair-cha/v2.env \
  "$backup_base/etc/jdair-cha/v2.env"

{
  printf 'created_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'legacy_target=%s\n' "$legacy_target"
  printf 'v2_target=%s\n' "$v2_target"
  printf 'v2_version=%s\n' "$(curl -sS http://127.0.0.1:8791/api/v2/system/version 2>/dev/null || true)"
  printf 'nginx_target=%s\n' "$nginx_target"
  printf 'nginx_sha256=%s\n' "$(sha256sum "$nginx_site" | cut -d' ' -f1)"
  printf 'v2_env_sha256=%s\n' "$(sha256sum /etc/jdair-cha/v2.env | cut -d' ' -f1)"
} > "$backup_base/meta/manifest.txt"

cat > "$backup_base/rollback-v2.sh" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail
backup_base="${backup_base}"
v2_target="${v2_target}"
nginx_site="${nginx_site}"
nginx_target="${nginx_target}"

test -d "\$v2_target"
test -f "\$backup_base/etc/systemd/jdair-cha-v2.service"
test -f "\$backup_base/etc/nginx/jdair-cha.conf"
test -f "\$backup_base/etc/jdair-cha/v2.env"

systemctl stop jdair-cha-v2.service >/dev/null 2>&1 || true
cp -a "\$backup_base/v2/releases/." /opt/jdair-cha/v2/releases/
ln -sfn "\$v2_target" /opt/jdair-cha/v2/current
install -m 0644 "\$backup_base/etc/systemd/jdair-cha-v2.service" /etc/systemd/system/jdair-cha-v2.service
install -m 0600 "\$backup_base/etc/jdair-cha/v2.env" /etc/jdair-cha/v2.env
install -m 0644 "\$backup_base/etc/nginx/jdair-cha.conf" "\$nginx_target"
if [ "\$nginx_site" != "\$nginx_target" ]; then
  ln -sfn "\$nginx_target" "\$nginx_site"
fi

systemctl daemon-reload
nginx -t
systemctl reload nginx
systemctl restart jdair-cha-v2.service
sleep 3

test "\$(systemctl is-active jdair-cha.service)" = "active"
test "\$(systemctl is-active jdair-cha-v2.service)" = "active"
test "\$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8790/)" = "200"
test "\$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8791/api/v2/health)" = "200"

printf 'V2_ROLLBACK_TARGET=%s\n' "\$(readlink -f /opt/jdair-cha/v2/current)"
printf 'LEGACY_SERVICE=%s\n' "\$(systemctl is-active jdair-cha.service)"
printf 'V2_SERVICE=%s\n' "\$(systemctl is-active jdair-cha-v2.service)"
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

test "$(systemctl is-active jdair-cha.service)" = "active"
test "$(systemctl is-active jdair-cha-v2.service)" = "active"
test "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8790/)" = "200"
test "$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8791/api/v2/health)" = "200"
test ! -L "$backup_base/etc/nginx/jdair-cha.conf"
test ! -L "$backup_base/etc/jdair-cha/v2.env"
tar -tzf "$backup_archive" >/dev/null
(cd / && sha256sum -c "${backup_archive}.sha256")

printf 'BACKUP_NAME=%s\n' "$backup_name"
printf 'BACKUP_BASE=%s\n' "$backup_base"
printf 'BACKUP_ARCHIVE=%s\n' "$backup_archive"
printf 'ARCHIVE_SHA256=%s\n' "$(cut -d' ' -f1 "${backup_archive}.sha256")"
printf 'ARCHIVE_SIZE=%s\n' "$(stat -c '%s' "$backup_archive")"
printf 'ARCHIVE_ENTRIES=%s\n' "$(wc -l < "${backup_archive}.contents.txt")"
printf 'LEGACY_TARGET=%s\n' "$legacy_target"
printf 'V2_TARGET=%s\n' "$v2_target"
printf 'ROLLBACK_SCRIPT=%s\n' "$backup_base/rollback-v2.sh"
printf 'LEGACY_SERVICE=%s\n' "$(systemctl is-active jdair-cha.service)"
printf 'V2_SERVICE=%s\n' "$(systemctl is-active jdair-cha-v2.service)"
