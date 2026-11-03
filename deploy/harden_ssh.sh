#!/usr/bin/env bash
set -euo pipefail
test "$(id -u)" = 0
tail_ip=$(tailscale ip -4)
case "$tail_ip" in 100.*) ;; *) exit 1;; esac
backup=/root/auvirel-ssh-backup
install -d -m 0700 "$backup"
sshd_file=/etc/ssh/sshd_config.d/00-auvirel-tailscale.conf
socket_file=/etc/systemd/system/ssh.socket.d/10-auvirel-tailscale.conf
for path in "$sshd_file" "$socket_file"; do
  if test -f "$path"; then echo 'SSH binding already configured; inspect before replacing' >&2; exit 1; fi
done
cp -a /etc/ssh/sshd_config "$backup/sshd_config"
cat > "$backup/rollback.sh" <<'EOF'
#!/usr/bin/env bash
set -e
rm -f -- /etc/ssh/sshd_config.d/00-auvirel-tailscale.conf /etc/systemd/system/ssh.socket.d/10-auvirel-tailscale.conf
systemctl daemon-reload
systemctl stop ssh.service ssh.socket
systemctl start ssh.socket ssh.service
EOF
chmod 0700 "$backup/rollback.sh"
systemd-run --unit=auvirel-ssh-rollback --on-active=120s /bin/bash "$backup/rollback.sh"
printf 'ListenAddress %s\n' "$tail_ip" > "$sshd_file"
install -d /etc/systemd/system/ssh.socket.d
cat > "$socket_file" <<EOF
[Unit]
After=tailscaled.service
Wants=tailscaled.service
[Socket]
ListenStream=
ListenStream=$tail_ip:22
FreeBind=yes
EOF
sshd -t
systemctl daemon-reload
systemctl stop ssh.service ssh.socket
systemctl start ssh.socket ssh.service
echo 'Binding changed. Rollback remains armed until independent verification.'
