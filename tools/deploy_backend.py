"""Upload an explicit source allowlist and private server-only credentials over SSH."""
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import tarfile
import time

from vps import connection, execute

ROOT = Path(__file__).resolve().parents[1]


def main():
    staging = ROOT / '.private/deployment'
    staging.mkdir(parents=True, exist_ok=True)
    env = staging / 'server.env'
    if not env.exists():
        env.write_text('AUVIREL_MASTER_KEY=' + secrets.token_hex(32) + '\nAUVIREL_ADMIN_TOKEN=' + secrets.token_hex(32) + '\nAUVIREL_DATA_DIR=/var/lib/auvirel\n', encoding='utf-8', newline='\n')
    records = {}
    for provider in ('tunelio', 'apify', 'deepgram', 'gemini', 'deepseek'):
        records[provider] = [line.strip() for line in (ROOT.parent / f'api-key-{provider}.txt').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    lines = [line for line in (ROOT.parent / 'modal.com.txt').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
    records['modal'] = [json.dumps({'token_id': re.search(r'--token-id\s+([A-Za-z0-9_-]+)', line)[1], 'token_secret': re.search(r'--token-secret\s+([A-Za-z0-9_-]+)', line)[1]}) for line in lines[:3]]
    keys = staging / 'backend-keys.json'
    keys.write_text(json.dumps(records))
    archive = staging / 'release.tar.gz'
    version = time.strftime('%Y%m%d-%H%M%S', time.gmtime())
    remote = '/opt/auvirel/releases/' + version
    with tarfile.open(archive, 'w:gz') as bundle:
        for directory in ('backend', 'deploy'):
            for path in (ROOT / directory).rglob('*'):
                if path.is_file() and '__pycache__' not in path.parts:
                    bundle.add(path, arcname=path.relative_to(ROOT))
        for name in ('pyproject.toml', 'tools/bootstrap_backend.py'):
            bundle.add(ROOT / name, arcname=name)
        bundle.add(env, arcname='.private/server.env')
        bundle.add(keys, arcname='.private/backend-keys.json')
    key, destination = connection()
    subprocess.run(['scp', '-i', key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', str(archive), destination + ':auvirel-release.tar.gz'], check=True, timeout=60)
    result = execute(f'sudo install -d -m 0755 {remote} && sudo tar -xzf ~/auvirel-release.tar.gz -C {remote} && sudo chmod 700 {remote}/.private && sudo bash {remote}/deploy/install.sh', capture=True, timeout=1200)
    (staging / 'install.log').write_text(result.stdout + result.stderr, encoding='utf-8')
    if result.returncode:
        raise SystemExit('Installation failed; inspect .private/deployment/install.log')
    execute('rm -f -- ~/auvirel-release.tar.gz', capture=True)
    print('Backend installed; public and Tailscale admin health checks passed')
    (staging / 'release.json').write_text(json.dumps({'path': remote, 'version': version}))


if __name__ == '__main__':
    main()
