"""Import the supplied local media with provenance; no execution of reference JS."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import wave
from pathlib import Path

import json5

ROOT = Path(__file__).resolve().parents[1]


def object_literal(source: str, start: int) -> str:
    depth, quote, escaped = 0, None, False
    for index in range(start, len(source)):
        char = source[index]
        if quote:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                quote = None
        elif char in "\"'":
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return source[start:index + 1]
    raise ValueError("Unterminated reference metadata object")


def main():
    reference = ROOT.parent / "Neko Dub"
    source = (reference / "background.js").read_text(encoding="utf-8")
    marker = re.search(r"\{\s*version\s*:\s*2\s*,\s*updatedAt\s*:", source)
    if marker is None:
        raise ValueError("Reference metadata format changed; inspect before importing")
    catalog = json5.loads(object_literal(source, marker.start()))
    output = ROOT / "assets" / "imported"
    entries = []
    presets = []
    for language, voices in catalog["voices"].items():
        for voice in voices:
            presets.append({"id": voice["id"], "name": voice["name"], "language": language,
                            "path": voice["audioUrl"], "transcript": voice["transcript"]})
            for emotion, variant in voice.get("emotions", {}).items():
                presets.append({"id": voice["id"] + "-" + emotion, "name": voice["name"] + " / " + emotion,
                                "language": language, "path": variant["audioUrl"], "transcript": variant["transcript"]})
    for folder in ("presets", "bgm"):
        for path in sorted((reference / folder).rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(reference)
            target = output / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest() != digest:
                raise ValueError(f"Refusing to overwrite modified imported asset: {relative}")
            if not target.exists():
                shutil.copy2(path, target)
            entry = {"path": relative.as_posix(), "bytes": path.stat().st_size, "sha256": digest}
            if path.suffix.lower() == ".wav":
                with wave.open(str(path), "rb") as audio:
                    entry.update(sample_rate=audio.getframerate(), channels=audio.getnchannels(),
                                 duration_seconds=audio.getnframes() / audio.getframerate())
            entries.append(entry)
    missing = [item["path"] for item in presets if not (output / item["path"]).is_file()]
    if missing:
        raise ValueError(f"Missing preset assets: {missing}")
    (output / "presets.json").write_text(json.dumps(presets, ensure_ascii=False, indent=2), encoding="utf-8")
    manifest = {"source": "User-supplied Neko Dub 1.2.3", "redistribution_license": "not_found",
                "single_voice_per_session": True, "presets": len(presets), "assets": entries}
    (ROOT / "research" / "asset-manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Imported {len(entries)} assets; {len(presets)} selectable references; hashes verified.")


if __name__ == "__main__":
    main()
