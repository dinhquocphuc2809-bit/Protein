"""Write owner-only connection instructions; the output stays under ignored .private."""
import json
from pathlib import Path
import re

from vps import connection

ROOT = Path(__file__).resolve().parents[1]


def main():
    endpoint = json.loads((ROOT / '.private/public-endpoint.json').read_text())['url']
    ticket = json.loads((ROOT / '.private/owner-ticket.json').read_text())['code']
    env = dict(line.split('=', 1) for line in (ROOT / '.private/deployment/server.env').read_text().splitlines() if '=' in line)
    voice = re.search(r'https://[^\s]+\.modal\.run', (ROOT / '.private/tts-deploy.log').read_text(encoding='utf-16'))[0]
    proxy = json.loads((ROOT / '.private/modal-4-proxy.json').read_text())
    _, destination = connection()
    text = f'''# Private owner handover

Do not publish, commit, forward or include this file in screenshots.

## Backend

Public HTTPS API: {endpoint}
Private admin (connect Tailscale): http://{destination.split('@')[1]}:8001
Admin token: `{env['AUVIREL_ADMIN_TOKEN']}`
Owner ticket: `{ticket}`

The owner ticket was activated during acceptance tests. Its 30-day expiry is shown
in Admin; extend there as needed. Provider keys remain encrypted in the server DB.

## Existing client OmniVoice worker

Endpoint: {voice}
Proxy key: `{proxy['Modal-Key']}`
Proxy secret: `{proxy['Modal-Secret']}`

Use the existing-worker form in Auvirel settings. Deployment ak-/as- credentials are
different; use those only in the local deployment form. The native bridge has also
been tested and registered for Chrome build ID njepcceplllhabnepcaejllfpfhnloil and
Firefox auvirel@protein.local. If Chrome assigns a different ID after moving files,
rerun native/install.py with that actual ID.

## Files

- Chrome unpacked: ../dist/chrome
- Firefox temporary addon: ../dist/firefox/manifest.json
- Local-only ZIPs: ../dist/auvirel-chrome.zip and ../dist/auvirel-firefox.zip
- Operations: ../docs/OPERATIONS.md
- Latest status: ../CHECKPOINT.md

Master key backup: deployment/server.env. Preserve it to recover encrypted provider
credentials and existing tickets. Do not regenerate it on a normal upgrade.
'''
    (ROOT / '.private/HANDOVER.md').write_text(text, encoding='utf-8', newline='\n')
    print('Private owner handover written; no secret values printed')


if __name__ == '__main__':
    main()
