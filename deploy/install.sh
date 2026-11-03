#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
test "$(uname -m)" = aarch64
release=$(cd -- "$(dirname -- "$0")/.." && pwd)
case "$release" in /opt/auvirel/releases/*) ;; *) echo 'Invalid release location' >&2; exit 1;; esac
previous=$(readlink -f /opt/auvirel/current 2>/dev/null || true)
rollback() {
  if test -n "$previous" && test "$previous" != "$release" && test -d "$previous"; then
    case "$previous" in /opt/auvirel/releases/*)
      ln -sfn "$previous" /opt/auvirel/current
      systemctl restart auvirel-public auvirel-admin || true
      echo 'Application code rolled back; persistent database retained' >&2
    ;; esac
  fi
}
trap rollback ERR
tail_ip=$(tailscale ip -4)
case "$tail_ip" in 100.*) ;; *) echo 'Tailscale is required' >&2; exit 1;; esac
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv ffmpeg
id auvirel >/dev/null 2>&1 || useradd --system --home-dir /var/lib/auvirel --shell /usr/sbin/nologin auvirel
install -d -m 0750 -o auvirel -g auvirel /var/lib/auvirel
install -d -m 0700 /etc/auvirel
if test -f "$release/.private/server.env"; then
  if test -f /etc/auvirel/server.env; then
    echo 'Keeping existing server environment'
  else
    install -m 0600 "$release/.private/server.env" /etc/auvirel/server.env
  fi
fi
sed -i 's/\r$//' /etc/auvirel/server.env
python3 -m venv "$release/.venv"
"$release/.venv/bin/pip" install --no-cache-dir "$release" > "$release/install.log" 2>&1
set -a
source /etc/auvirel/server.env
set +a
cd "$release"
"$release/.venv/bin/python" tools/bootstrap_backend.py --credentials "$release/.private/backend-keys.json"
chown -R auvirel:auvirel /var/lib/auvirel
chmod 0750 /var/lib/auvirel
ln -sfn "$release" /opt/auvirel/current
for role in public admin; do
  if test "$role" = public; then address=127.0.0.1; port=8000; else address=$tail_ip; port=8001; fi
  cat > "/etc/systemd/system/auvirel-$role.service" <<EOF
[Unit]
Description=Auvirel $role service
After=network-online.target tailscaled.service
Wants=network-online.target
[Service]
Type=simple
User=auvirel
Group=auvirel
WorkingDirectory=/opt/auvirel/current
EnvironmentFile=/etc/auvirel/server.env
Environment=PYTHONDONTWRITEBYTECODE=1
ExecStart=/opt/auvirel/current/.venv/bin/uvicorn backend.app:create_${role}_app --factory --host $address --port $port --workers 1 --no-access-log --proxy-headers --forwarded-allow-ips=127.0.0.1 --limit-concurrency 48 --timeout-keep-alive 5
Restart=on-failure
RestartSec=5
TimeoutStopSec=45
UMask=0077
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/auvirel
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
LockPersonality=true
CapabilityBoundingSet=
MemoryMax=6G
TasksMax=128
LogNamespace=auvirel
[Install]
WantedBy=multi-user.target
EOF
done
install -d -m 0755 /etc/systemd/journald@auvirel.conf.d
cat > /etc/systemd/journald@auvirel.conf.d/limits.conf <<'EOF'
[Journal]
SystemMaxUse=512M
RuntimeMaxUse=64M
MaxRetentionSec=7day
RateLimitIntervalSec=30s
RateLimitBurst=1000
EOF
systemctl daemon-reload
systemctl enable --now auvirel-public auvirel-admin
systemctl restart auvirel-public auvirel-admin
cat > /etc/systemd/system/auvirel-release-cleanup.service <<'EOF'
[Unit]
Description=Bound Auvirel rollback release storage
[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/auvirel/current/deploy/storage_cleanup.py
NoNewPrivileges=true
ProtectHome=true
EOF
cat > /etc/systemd/system/auvirel-release-cleanup.timer <<'EOF'
[Unit]
Description=Daily Auvirel release retention
[Timer]
OnCalendar=daily
Persistent=true
RandomizedDelaySec=600
[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemctl enable --now auvirel-release-cleanup.timer
for attempt in $(seq 1 20); do
  if curl --fail --silent http://127.0.0.1:8000/healthz >/dev/null; then break; fi
  sleep 1
done
curl --fail --silent http://127.0.0.1:8000/healthz
curl --fail --silent "http://$tail_ip:8001/healthz"
# Imported keys are encrypted in SQLite. Remove only this release's staging secrets.
rm -f -- "$release/.private/backend-keys.json" "$release/.private/server.env"
echo 'Auvirel services installed; public HTTPS and SSH binding are separate verified steps.'
trap - ERR
