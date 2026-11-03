"""Select the authorized account without exposing its token in the process arguments."""

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("role", choices=["asr", "tts"])
    parser.add_argument("--gpu", choices=["T4", "L4"], default="T4")
    args = parser.parse_args()
    lines = [x for x in (ROOT.parent / "modal.com.txt").read_text().splitlines() if x.strip()]
    line = lines[0 if args.role == "asr" else 3]
    token_id = re.search(r"--token-id\s+([A-Za-z0-9_-]+)", line)
    token_secret = re.search(r"--token-secret\s+([A-Za-z0-9_-]+)", line)
    if not token_id or not token_secret:
        raise SystemExit("Invalid Modal credential record")
    env = os.environ.copy()
    env.update(MODAL_TOKEN_ID=token_id[1], MODAL_TOKEN_SECRET=token_secret[1],
               AUVIREL_BENCH_ROLE=args.role, AUVIREL_BENCH_GPU=args.gpu, PYTHONIOENCODING="utf-8")
    result = subprocess.run([sys.executable, "-m", "modal", "run", "gpu/benchmark.py"], cwd=ROOT, env=env)
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
