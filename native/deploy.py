"""Local child process; only deploys the reviewed worker bundled with this repository."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

import modal

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".private/native"


def publish(**data):
    temporary = STATE / "status.tmp"
    temporary.write_text(json.dumps({**data, "updated": time.time()}))
    os.replace(temporary, STATE / "status.json")


def run(args, timeout=1200, private=False):
    result = subprocess.run([sys.executable, "-m", "modal", *args], cwd=ROOT, timeout=timeout,
                            capture_output=private, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    if result.returncode:
        raise RuntimeError("Modal command failed; inspect the private deployment log")
    return result.stdout if private else None


def main():
    try:
        publish(state="running", stage="Caching pinned OmniVoice weights")
        run(["run", "gpu/tts.py"])
        publish(state="running", stage="Deploying authenticated voice endpoint")
        run(["deploy", "gpu/tts.py"], timeout=300)
        endpoint = modal.Function.from_name("auvirel-voice", "api").get_web_url()
        publish(state="running", stage="Creating workspace proxy credential")
        raw = run(["workspace", "proxy-tokens", "create", "--name", "auvirel-native-client", "--json"], timeout=60, private=True)
        proxy = json.loads(raw)
        publish(state="done", endpoint=endpoint, proxy_id=proxy["Modal-Key"], proxy_secret=proxy["Modal-Secret"])
    except Exception as error:
        publish(state="failed", error=str(error) if isinstance(error, RuntimeError) else type(error).__name__)
    finally:
        (STATE / "deployment.lock").unlink(missing_ok=True)


if __name__ == "__main__":
    main()
