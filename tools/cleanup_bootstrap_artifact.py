"""Remove the exact CR-suffixed directory created by the early bootstrap CRLF bug."""
import base64
from pathlib import Path
import shlex
from vps import execute

script = '''from pathlib import Path
import shutil
target = Path('/var/lib') / ('auvirel' + chr(13))
if target.exists():
    assert not target.is_symlink()
    assert target.resolve().parent == Path('/var/lib')
    assert target.name == 'auvirel' + chr(13)
    assert all(p.name in {'auvirel.sqlite3', 'auvirel.sqlite3-wal', 'auvirel.sqlite3-shm', 'initial-ticket.json'} for p in target.iterdir())
    shutil.rmtree(target)
print('Owned CRLF bootstrap artifact absent')
'''
encoded = base64.b64encode(script.encode()).decode()
result = execute('printf %s ' + shlex.quote(encoded) + ' | base64 -d | sudo python3', capture=True)
if result.returncode:
    raise SystemExit('Cleanup validation failed; no broad deletion attempted')
print(result.stdout.strip())
