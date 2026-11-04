"""Run a temporary benchmark app on backend account 1; never change production."""
import argparse
import os
from pathlib import Path
import subprocess
import sys

from operate_modal import environment


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--gpu', required=True, choices=['T4', 'L4'])
    parser.add_argument('--region', choices=['us-east', 'us-central', 'us-west'])
    parser.add_argument('--account', type=int, choices=[1, 2, 3], default=1)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    env = environment(args.account)
    env['VOCALM_COMPARE_GPU'] = args.gpu
    env['VOCALM_COMPARE_ACCOUNT'] = str(args.account)
    if args.region:
        env['VOCALM_COMPARE_REGION'] = args.region
    env['PYTHONPATH'] = str(root) + os.pathsep + env.get('PYTHONPATH', '')
    result = subprocess.run([sys.executable, '-m', 'modal', 'run', 'gpu/asr_comparison.py'],
                            cwd=root, env=env, timeout=1800)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
