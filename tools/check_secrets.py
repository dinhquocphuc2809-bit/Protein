"""Fail if Git-visible files contain supplied secrets. Never print matched values."""

from pathlib import Path
import json
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    values = set()
    for path in ROOT.parent.glob("api-key-*.txt"):
        values.update(line.strip().encode() for line in path.read_text(encoding="utf-8-sig").splitlines() if len(line.strip()) > 15)
    modal = ROOT.parent / "modal.com.txt"
    if modal.exists():
        values.update(x.encode() for x in re.findall(r"\b(?:ak|as)-[A-Za-z0-9_-]+", modal.read_text()))
    for path in (ROOT / '.private').glob('modal-*-proxy.json'):
        data = json.loads(path.read_bytes())
        values.update(value.encode() for value in data.values() if isinstance(value, str) and len(value) > 15)
    environment = ROOT / '.private/deployment/server.env'
    if environment.exists():
        values.update(line.split('=', 1)[1].encode() for line in environment.read_text().splitlines() if line.startswith(('AUVIREL_MASTER_KEY=', 'AUVIREL_ADMIN_TOKEN=')))
    listed = subprocess.check_output(["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT)
    failures = []
    for name in sorted(set(listed.decode().split("\0")) - {""}):
        path = ROOT / name
        if not path.is_file():
            continue
        data = path.read_bytes()
        if any(value in data for value in values) or re.search(rb"-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----|\b(?:ak|as|wk|ws)-[A-Za-z0-9_-]{20,}", data):
            failures.append(name)
    for archive in (ROOT / 'dist').glob('auvirel-*.zip'):
        with zipfile.ZipFile(archive) as package:
            for name in package.namelist():
                data = package.read(name)
                if any(value in data for value in values):
                    failures.append(archive.name + ':' + name)
    if failures:
        raise SystemExit("Sensitive content found in: " + ", ".join(failures))
    print(f"Secret check passed for {len(set(listed.decode().split(chr(0))) - {''})} Git-visible files and built extension archives.")


if __name__ == "__main__":
    main()
