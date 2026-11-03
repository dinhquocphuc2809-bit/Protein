"""Remove only obsolete project releases, retaining active plus two rollback releases."""
import os
from pathlib import Path
import re
import shutil
import time


def main():
    root = Path('/opt/auvirel/releases')
    active = Path('/opt/auvirel/current').resolve(strict=True)
    if active.parent != root.resolve(strict=True):
        raise RuntimeError('Unexpected active release path')
    releases = sorted((path for path in root.iterdir() if path.is_dir() and not path.is_symlink()
                       and re.fullmatch(r'\d{8}-\d{6}', path.name) and path.resolve().parent == root.resolve()), reverse=True)
    rollback = [path for path in releases if path != active][:2]
    for path in releases:
        if path != active and path not in rollback and path.stat().st_mtime < time.time()-3600:
            shutil.rmtree(path)


if __name__ == '__main__':
    main()
