"""Verified Cloudflare binary and a temporary HTTPS acceptance-test tunnel."""
import base64
import json
from pathlib import Path
import re
import shlex
import time
from vps import execute

ROOT = Path(__file__).resolve().parents[1]


def main():
    release = json.loads((ROOT / 'research/cloudflared-release.json').read_text())
    url, digest = release['browser_download_url'], release['digest'].removeprefix('sha256:')
    if not url.startswith('https://github.com/cloudflare/cloudflared/releases/download/') or not re.fullmatch('[a-f0-9]{64}', digest):
        raise ValueError('Unverified Cloudflare release metadata')
    command = f"curl -fLsS --max-time 90 {shlex.quote(url)} -o /tmp/auvirel-cloudflared && echo '{digest}  /tmp/auvirel-cloudflared' | sha256sum -c - && sudo install -m 0755 /tmp/auvirel-cloudflared /usr/local/bin/auvirel-cloudflared"
    result = execute(command, capture=True, timeout=120)
    if result.returncode:
        raise SystemExit('Cloudflare download/checksum verification failed')
    service = '''[Unit]
Description=Auvirel temporary acceptance-test HTTPS tunnel
After=network-online.target auvirel-public.service
[Service]
User=auvirel
ExecStart=/usr/local/bin/auvirel-cloudflared tunnel --no-autoupdate --url http://127.0.0.1:8000
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
PrivateTmp=true
LogNamespace=auvirel
MemoryMax=256M
[Install]
WantedBy=multi-user.target
'''
    encoded = base64.b64encode(service.encode()).decode()
    result = execute('printf %s ' + shlex.quote(encoded) + ' | base64 -d | sudo tee /etc/systemd/system/auvirel-test-tunnel.service >/dev/null && sudo systemctl daemon-reload && sudo systemctl start auvirel-test-tunnel', capture=True)
    if result.returncode:
        raise SystemExit('Temporary tunnel could not start')
    for _ in range(20):
        result = execute('sudo journalctl --namespace=auvirel -u auvirel-test-tunnel -n 40 --no-pager -o cat', capture=True)
        urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', result.stdout)
        if urls:
            endpoint = urls[-1]
            (ROOT / '.private/public-endpoint.json').write_text(json.dumps({'url': endpoint, 'temporary': True}))
            print('Temporary HTTPS test tunnel ready; endpoint saved privately')
            return
        time.sleep(1)
    raise SystemExit('No temporary tunnel URL was returned')


if __name__ == '__main__':
    main()
