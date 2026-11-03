"""Bounded operations on explicitly selected project accounts; never print tokens."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def environment(account):
    lines = [line for line in (ROOT.parent / "modal.com.txt").read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    record = lines[account-1]
    env = os.environ.copy()
    for variable, flag in [("MODAL_TOKEN_ID", "token-id"), ("MODAL_TOKEN_SECRET", "token-secret")]:
        match = re.search(r"--"+flag+r"\s+([A-Za-z0-9_-]+)", record)
        if not match:
            raise ValueError("Invalid credential record")
        env[variable] = match[1]
    env["PYTHONIOENCODING"] = "utf-8"
    return env


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["status", "deploy", "prepare", "proxy"])
    parser.add_argument("--account", type=int, choices=range(1, 5), required=True)
    args = parser.parse_args()
    env = environment(args.account)
    role = "tts" if args.account == 4 else "asr"
    command = {"status": ["app", "list", "--json"], "deploy": ["deploy", f"gpu/{role}.py"],
               "prepare": ["run", f"gpu/{role}.py"],
               "proxy": ["workspace", "proxy-tokens", "create", "--name", "auvirel-private-client", "--json"]}[args.action]
    if args.action in {"status", "proxy"}:
        result = subprocess.run([sys.executable, "-m", "modal", *command], env=env, cwd=ROOT, capture_output=True, timeout=60)
        if result.returncode:
            raise SystemExit("Modal operation failed; no credential output emitted")
        path = ROOT / ".private" / f"modal-{args.account}-{args.action}.json"
        path.write_bytes(result.stdout)
        if args.action == "status":
            rows = json.loads(result.stdout)
            for row in rows:
                if "auvirel" in str(row).lower():
                    print(json.dumps(row))
        else:
            print("Proxy credentials saved to ignored private file")
    else:
        result = subprocess.run([sys.executable, "-m", "modal", *command], env=env, cwd=ROOT, timeout=1800)
        raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
