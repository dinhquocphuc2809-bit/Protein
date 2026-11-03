"""Register the local Native Messaging host for this user's Chrome and Firefox."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--chrome-id", required=True)
    args = parser.parse_args()
    if not re.fullmatch(r"[a-p]{32}", args.chrome_id):
        raise SystemExit("Invalid Chrome extension ID")
    if os.name != "nt":
        raise SystemExit("This installer targets the supplied Windows workspace")
    import winreg
    directory = ROOT / ".private/native"
    directory.mkdir(parents=True, exist_ok=True)
    launcher = directory / "host.cmd"
    launcher.write_text(f'@echo off\r\n"{sys.executable}" "{ROOT / "native/host.py"}"\r\n', encoding="utf-8")
    common = {"name": "com.auvirel.modal", "description": "Auvirel local Modal deployment", "path": str(launcher), "type": "stdio"}
    for browser, key, allowed in [
        ("chrome", r"Software\Google\Chrome\NativeMessagingHosts\com.auvirel.modal", {"allowed_origins": [f"chrome-extension://{args.chrome_id}/"]}),
        ("firefox", r"Software\Mozilla\NativeMessagingHosts\com.auvirel.modal", {"allowed_extensions": ["auvirel@protein.local"]}),
    ]:
        manifest = directory / (browser + ".json")
        manifest.write_text(json.dumps({**common, **allowed}, indent=2))
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as registry:
            winreg.SetValueEx(registry, "", 0, winreg.REG_SZ, str(manifest))
    print("Native Messaging host registered for the current Windows user")


if __name__ == "__main__":
    main()
