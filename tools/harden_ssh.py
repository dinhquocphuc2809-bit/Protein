"""Verify a fresh Tailscale connection before and after changing SSH listeners."""
import base64
import json
from pathlib import Path
import shlex
import time
from vps import execute, connection

ROOT = Path(__file__).resolve().parents[1]


def main():
    _, destination = connection()
    host = destination.split('@', 1)[1]
    if not host.startswith('100.'):
        raise SystemExit('The SSH input must already target the Tailscale address')
    before = execute('echo verified_second_connection; tailscale ip -4', capture=True)
    if before.returncode or 'verified_second_connection' not in before.stdout or host not in before.stdout:
        raise SystemExit('Independent Tailscale verification failed')
    payload = base64.b64encode((ROOT / 'deploy/harden_ssh.sh').read_bytes()).decode()
    result = execute('printf %s ' + shlex.quote(payload) + ' | base64 -d | sudo bash', capture=True)
    if result.returncode:
        raise SystemExit('SSH hardening did not complete; rollback remains armed if it was scheduled')
    verified = False
    for _ in range(8):
        try:
            check = execute("sudo ss -Hlnpt 'sport = :22'; sudo sshd -T | grep '^listenaddress'", capture=True, timeout=20)
            if check.returncode == 0 and host + ':22' in check.stdout and '0.0.0.0:22' not in check.stdout and '[::]:22' not in check.stdout:
                verified = True
                break
        except Exception:
            pass
        time.sleep(2)
    if not verified:
        raise SystemExit('Fresh SSH verification failed; scheduled rollback will restore previous listeners')
    cancel = execute('sudo systemctl stop auvirel-ssh-rollback.timer', capture=True)
    if cancel.returncode:
        raise SystemExit('Binding verified but rollback timer could not be cancelled')
    report = {'tailscale_only': True, 'independent_reconnect': True, 'rollback_cancelled': True}
    (ROOT / 'research/ssh-hardening.json').write_text(json.dumps(report, indent=2))
    print('SSH listens only on Tailscale; independent reconnect passed; rollback timer cancelled')


if __name__ == '__main__':
    main()
