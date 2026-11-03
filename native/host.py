"""Native Messaging host. Fixed Modal deploy only; credentials never go to the VPS."""
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".private/native"
STATE.mkdir(parents=True, exist_ok=True)


def read_message():
    header = sys.stdin.buffer.read(4)
    if len(header) != 4:
        raise ValueError("Missing native frame")
    length = struct.unpack("<I", header)[0]
    if not 1 <= length <= 16384:
        raise ValueError("Native request exceeds limit")
    data = sys.stdin.buffer.read(length)
    if len(data) != length:
        raise ValueError("Incomplete native frame")
    return json.loads(data)


def write_message(value):
    encoded = json.dumps(value).encode()
    sys.stdout.buffer.write(struct.pack("<I", len(encoded)) + encoded)
    sys.stdout.buffer.flush()


def status():
    path = STATE / "status.json"
    if not path.exists():
        return {"state": "idle"}
    result = json.loads(path.read_text())
    if result.get("state") == "running" and time.time()-result["updated"] > 1800:
        return {"state": "failed", "error": "Deployment deadline exceeded. Inspect the private native log."}
    return result


def handle(message):
    if not isinstance(message, dict):
        raise ValueError("Invalid native message")
    if message.get("operation") == "status" and set(message) == {"operation"}:
        return status()
    if message.get("operation") != "start" or set(message) != {"operation", "credentials", "gpu"}:
        raise ValueError("Unsupported native operation")
    credentials = message["credentials"]
    if not isinstance(credentials, dict) or set(credentials) != {"token_id", "token_secret"}:
        raise ValueError("Invalid credentials")
    if not re.fullmatch(r"ak-[A-Za-z0-9_-]+", credentials["token_id"]) or not re.fullmatch(r"as-[A-Za-z0-9_-]+", credentials["token_secret"]) or message["gpu"] not in {"T4", "L4"}:
        raise ValueError("Invalid credentials or GPU")
    lock = STATE / "deployment.lock"
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        os.close(descriptor)
    except FileExistsError:
        return {"state": "running", "stage": "A deployment is already in progress"}
    env = os.environ.copy()
    env.update(MODAL_TOKEN_ID=credentials["token_id"], MODAL_TOKEN_SECRET=credentials["token_secret"],
               AUVIREL_GPU=message["gpu"], PYTHONIOENCODING="utf-8")
    flags = subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS if os.name == "nt" else 0
    try:
        (STATE / "status.json").write_text(json.dumps({"state": "running", "stage": "Starting deployment", "updated": time.time()}))
        with (STATE / "deployment.log").open("ab") as log:
            subprocess.Popen([sys.executable, str(ROOT / "native/deploy.py")], cwd=ROOT, env=env,
                             stdin=subprocess.DEVNULL, stdout=log, stderr=log, creationflags=flags,
                             start_new_session=os.name != "nt", close_fds=True)
    except BaseException:
        lock.unlink(missing_ok=True)
        raise
    return {"state": "running", "stage": "Starting deployment"}


if __name__ == "__main__":
    try:
        write_message(handle(read_message()))
    except Exception as error:
        write_message({"state": "failed", "error": str(error) if isinstance(error, ValueError) else type(error).__name__})
