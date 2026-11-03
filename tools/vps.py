"""Read credentials without echoing them; run explicit commands over pinned SSH."""
import argparse
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def connection():
    text = (ROOT.parent / 'ssh.txt').read_text(encoding='utf-8-sig')
    key = re.search(r'-i\s+"([^"]+)"', text)
    destination = re.search(r'\b([A-Za-z0-9_-]+@[A-Za-z0-9.:-]+)', text)
    if not key or not destination:
        raise ValueError('Invalid SSH input format')
    return key[1], destination[1]


def execute(command, capture=False, timeout=120):
    key, destination = connection()
    return subprocess.run(['ssh', '-i', key, '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15', destination, command],
                          capture_output=capture, timeout=timeout, text=True, encoding='utf-8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('command')
    args = parser.parse_args()
    raise SystemExit(execute(args.command, timeout=1800).returncode)


if __name__ == '__main__':
    main()
