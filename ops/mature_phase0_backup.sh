set -Eeuo pipefail

stamp="$(date +%Y%m%d-%H%M%S)"
backup_name="${stamp}-before-mature-modernization"
backup_root="/opt/jdair-cha/backups"
backup_base="${backup_root}/${backup_name}"
backup_archive="${backup_root}/jdair-cha-before-mature-modernization-${stamp}.tar.gz"
service_was_active="$(systemctl is-active jdair-cha.service || true)"
current_target="$(readlink -f /opt/jdair-cha/current)"
current_hash="$(sha256sum "${current_target}/mcs8_web_panel.py" | cut -d' ' -f1)"
nginx_site="/etc/nginx/sites-enabled/jdair-cha.conf"
nginx_site_target="$(readlink -f "$nginx_site" 2>/dev/null || printf '%s' "$nginx_site")"

restore_service() {
  if [ "$service_was_active" = "active" ]; then
    systemctl start jdair-cha.service >/dev/null 2>&1 || true
  fi
}
trap restore_service EXIT

mkdir -p "$backup_root"
chmod 700 "$backup_root"

nginx -t
systemctl stop jdair-cha.service

mkdir -p \
  "$backup_base/app" \
  "$backup_base/etc/systemd" \
  "$backup_base/etc/nginx" \
  "$backup_base/meta"

cp -a /opt/jdair-cha/releases "$backup_base/app/"
cp -a /opt/jdair-cha/current "$backup_base/app/current"
if [ -e /opt/jdair-cha/venv ] || [ -L /opt/jdair-cha/venv ]; then
  cp -a /opt/jdair-cha/venv "$backup_base/app/venv"
fi
if [ -d /opt/jdair-cha/.git ]; then
  cp -a /opt/jdair-cha/.git "$backup_base/app/"
fi
if [ -f /opt/jdair-cha/.gitignore ]; then
  cp -a /opt/jdair-cha/.gitignore "$backup_base/app/"
fi

cp --dereference --preserve=mode,ownership,timestamps \
  /etc/systemd/system/jdair-cha.service \
  "$backup_base/etc/systemd/jdair-cha.service"
cp --dereference --preserve=mode,ownership,timestamps \
  "$nginx_site" \
  "$backup_base/etc/nginx/jdair-cha.conf"
if [ -f /etc/default/jdair-cha ]; then
  cp -a /etc/default/jdair-cha "$backup_base/etc/"
fi
if [ -d /etc/jdair-cha ]; then
  cp -a /etc/jdair-cha "$backup_base/etc/"
fi

{
  printf 'created_at=%s\n' "$(date --iso-8601=seconds)"
  printf 'hostname=%s\n' "$(hostname)"
  printf 'backup_name=%s\n' "$backup_name"
  printf 'backup_base=%s\n' "$backup_base"
  printf 'backup_archive=%s\n' "$backup_archive"
  printf 'current_target=%s\n' "$current_target"
  printf 'current_program_sha256=%s\n' "$current_hash"
  printf 'service_before_backup=%s\n' "$service_was_active"
  printf 'nginx_site=%s\n' "$nginx_site"
  printf 'nginx_site_target=%s\n' "$nginx_site_target"
  printf 'nginx_site_sha256=%s\n' "$(sha256sum "$nginx_site" | cut -d' ' -f1)"
  printf 'python=%s\n' "$(python3 --version 2>&1)"
  printf 'nginx=%s\n' "$(nginx -v 2>&1)"
} > "$backup_base/meta/manifest.txt"

systemctl show jdair-cha.service > "$backup_base/meta/jdair-cha-service-show.txt"
systemctl cat jdair-cha.service > "$backup_base/meta/jdair-cha-service-unit.txt"
nginx -T > "$backup_base/meta/nginx-full-config.txt" 2>&1
ss -lntp > "$backup_base/meta/listeners.txt"
df -h > "$backup_base/meta/disk-usage.txt"
find /opt/jdair-cha -mindepth 1 -maxdepth 3 \
  -path '/opt/jdair-cha/backups' -prune -o \
  -printf '%y|%p|%s|%u:%g|%m|%TY-%Tm-%TdT%TH:%TM:%TS\n' \
  > "$backup_base/meta/source-inventory.txt"

cat > "$backup_base/rollback.sh" <<EOF
#!/usr/bin/env bash
set -Eeuo pipefail

backup_base="${backup_base}"
target_release="${current_target}"
nginx_site="${nginx_site}"
nginx_site_target="${nginx_site_target}"

test -d "\$backup_base/app/releases"
test -d "\$target_release"
test -f "\$backup_base/etc/systemd/jdair-cha.service"
test -f "\$backup_base/etc/nginx/jdair-cha.conf"

systemctl stop jdair-cha-v2.service >/dev/null 2>&1 || true
systemctl disable jdair-cha-v2.service >/dev/null 2>&1 || true
systemctl stop jdair-cha.service

cp -a "\$backup_base/app/releases/." /opt/jdair-cha/releases/
ln -sfn "\$target_release" /opt/jdair-cha/current
install -m 0644 "\$backup_base/etc/systemd/jdair-cha.service" /etc/systemd/system/jdair-cha.service
install -m 0644 "\$backup_base/etc/nginx/jdair-cha.conf" "\$nginx_site_target"
if [ "\$nginx_site" != "\$nginx_site_target" ]; then
  ln -sfn "\$nginx_site_target" "\$nginx_site"
fi

systemctl daemon-reload
nginx -t
systemctl restart nginx
systemctl restart jdair-cha.service
sleep 3

test "\$(systemctl is-active jdair-cha.service)" = "active"
test "\$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8790/)" = "200"
test "\$(sha256sum "\$nginx_site" | cut -d' ' -f1)" = "\$(sha256sum "\$backup_base/etc/nginx/jdair-cha.conf" | cut -d' ' -f1)"

printf 'ROLLBACK_TARGET=%s\n' "\$(readlink -f /opt/jdair-cha/current)"
printf 'SERVICE=%s\n' "\$(systemctl is-active jdair-cha.service)"
printf 'ROOT_HTTP=%s\n' "\$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8790/)"
EOF
chmod 700 "$backup_base/rollback.sh"

find "$backup_base" -type f ! -path "$backup_base/meta/files.sha256" -print0 \
  | sort -z \
  | xargs -0 sha256sum > "$backup_base/meta/files.sha256"

tar --numeric-owner -C / -czf "$backup_archive" "${backup_base#/}"
tar -tzf "$backup_archive" > "${backup_archive}.contents.txt"
sha256sum "$backup_archive" > "${backup_archive}.sha256"
chmod 600 "$backup_archive" "${backup_archive}.sha256" "${backup_archive}.contents.txt"

restore_service
trap - EXIT
sleep 3

service_state="$(systemctl is-active jdair-cha.service || true)"
root_http="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 15 http://127.0.0.1:8790/ || true)"
archive_hash="$(cut -d' ' -f1 "${backup_archive}.sha256")"
archive_size="$(stat -c '%s' "$backup_archive")"
archive_entries="$(wc -l < "${backup_archive}.contents.txt")"

test "$service_state" = "active"
test "$root_http" = "200"

printf 'BACKUP_NAME=%s\n' "$backup_name"
printf 'BACKUP_BASE=%s\n' "$backup_base"
printf 'BACKUP_ARCHIVE=%s\n' "$backup_archive"
printf 'ARCHIVE_SHA256=%s\n' "$archive_hash"
printf 'ARCHIVE_SIZE=%s\n' "$archive_size"
printf 'ARCHIVE_ENTRIES=%s\n' "$archive_entries"
printf 'CURRENT_TARGET=%s\n' "$current_target"
printf 'CURRENT_PROGRAM_SHA256=%s\n' "$current_hash"
printf 'ROLLBACK_SCRIPT=%s\n' "$backup_base/rollback.sh"
printf 'SERVICE=%s\n' "$service_state"
printf 'ROOT_HTTP=%s\n' "$root_http"
