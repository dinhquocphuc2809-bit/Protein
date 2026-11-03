"""Small real HTTP synthesis test, with private credentials and bounded polling."""
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets
import time

import httpx

ROOT = Path(__file__).resolve().parents[1]


def main():
    session = httpx.Client(transport=httpx.HTTPTransport(retries=2))
    log = (ROOT / ".private/tts-deploy.log").read_text(encoding="utf-16")
    endpoint = re.search(r"https://[^\s]+\.modal\.run", log)[0]
    proxy = json.loads((ROOT / ".private/modal-4-proxy.json").read_bytes())
    headers = {k: proxy[k] for k in ("Modal-Key", "Modal-Secret")}
    unauthorized = session.get(endpoint + "/v1/health", timeout=30)
    health = session.get(endpoint + "/v1/health", headers=headers, timeout=30)
    health.raise_for_status()
    presets = json.loads((ROOT / "assets/imported/presets.json").read_text(encoding="utf-8"))
    preset = next(p for p in presets if p["id"] == "vi-dang-khoa")
    reference = (ROOT / "assets/imported" / preset["path"]).read_bytes()
    payload = {"text": "Xin chao. Hom nay chung ta cung tim hieu mot y tuong moi.", "reference": base64.b64encode(reference).decode(),
               "reference_text": preset["transcript"], "language": "vi", "duration": 5.0}
    headers["Idempotency-Key"] = hashlib.sha256(secrets.token_bytes(32)).hexdigest()
    started = time.monotonic()
    response = session.post(endpoint + "/v1/synthesize", headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    identity = response.json()["id"]
    duplicate = session.post(endpoint + "/v1/synthesize", headers=headers, json=payload, timeout=30)
    duplicate.raise_for_status()
    result = None
    try:
        while time.monotonic()-started < 240:
            response = session.get(endpoint + "/v1/results/" + identity, headers=headers, timeout=30)
            if response.status_code == 200:
                result = response.json()
                break
            response.raise_for_status()
            time.sleep(1)
    finally:
        if result is None:
            session.delete(endpoint + "/v1/results/" + identity, headers=headers, timeout=30)
    report = {"unauthorized_status": unauthorized.status_code, "health": health.json(), "duplicate_same_id": duplicate.json()["id"] == identity,
              "elapsed_seconds": time.monotonic()-started, "completed": result is not None}
    if result:
        audio = base64.b64decode(result["audio"], validate=True)
        (ROOT / ".private/benchmark-audio/production-voice.ogg").write_bytes(audio)
        report.update(duration=result["duration"], audio_bytes=len(audio), audio_sha256=hashlib.sha256(audio).hexdigest())
    (ROOT / "research/benchmarks/production-voice.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    if not result:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
