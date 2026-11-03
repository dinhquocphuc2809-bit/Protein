from __future__ import annotations

import html
import math
import re

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def plain_text(text: str) -> str:
    text = html.unescape(re.sub(r"<[^>]*>", "", text))
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class Cue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: int = Field(ge=0)
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(gt=0, allow_inf_nan=False)
    text: str = Field(min_length=1, max_length=4000)
    translated: str | None = Field(default=None, max_length=8000)

    @field_validator("text", "translated")
    @classmethod
    def clean(cls, value):
        if value is None:
            return value
        value = plain_text(value)
        if not value:
            raise ValueError("Empty cue text")
        return value

    @model_validator(mode="after")
    def timings(self):
        if self.end <= self.start or self.end - self.start > 120:
            raise ValueError("Cue duration must be between 0 and 120 seconds")
        return self


def validate_cues(cues: list[Cue], max_seconds=14400) -> list[Cue]:
    if not cues or len(cues) > 20000:
        raise ValueError("Expected 1 to 20000 subtitle cues")
    ids, previous = set(), -1.0
    for cue in cues:
        if cue.id in ids or cue.start < previous or cue.end > max_seconds:
            raise ValueError("Duplicate ID, unsorted timestamp or video too long")
        ids.add(cue.id)
        previous = cue.start
    return cues


TIMING = re.compile(r"^(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,3}):(\d{2}):(\d{2})[,.](\d{3})(?:\s+.*)?$")


def parse_srt(data: bytes) -> list[Cue]:
    if not data or len(data) > 2 * 1024**2:
        raise ValueError("SRT must be between 1 byte and 2 MiB")
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise ValueError("SRT must be UTF-8") from error
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").replace("\r", "\n").strip())
    cues = []
    for block in blocks:
        lines = block.strip().splitlines()
        if lines and lines[0].strip().isdigit():
            lines.pop(0)
        match = TIMING.fullmatch(lines[0].strip()) if lines else None
        if not match or len(lines) < 2:
            raise ValueError(f"Invalid SRT cue {len(cues) + 1}")
        values = list(map(int, match.groups()))
        if any(values[i] >= 60 for i in (1, 2, 5, 6)):
            raise ValueError("Invalid minute/second field")
        start = values[0] * 3600 + values[1] * 60 + values[2] + values[3] / 1000
        end = values[4] * 3600 + values[5] * 60 + values[6] + values[7] / 1000
        cues.append(Cue(id=len(cues), start=start, end=end, text=" ".join(lines[1:])))
    return validate_cues(cues)


def words_to_cues(words: list[dict]) -> list[Cue]:
    cues, pending = [], []
    for word in words:
        text = str(word.get("punctuated_word", word.get("text", word.get("word", "")))).strip()
        start, end = float(word["start"]), float(word["end"])
        if not text:
            continue
        if not all(map(math.isfinite, [start, end])) or end < start:
            raise ValueError("Invalid word timestamps")
        if pending and (start - pending[0][0] > 5 or start - pending[-1][1] > 0.7):
            cues.append(Cue(id=len(cues), start=pending[0][0], end=max(pending[-1][1], pending[0][0] + .01), text=" ".join(w[2] for w in pending)))
            pending = []
        pending.append((start, end, text))
        if re.search(r"[.!?。！？]$", text):
            cues.append(Cue(id=len(cues), start=pending[0][0], end=max(end, pending[0][0] + .01), text=" ".join(w[2] for w in pending)))
            pending = []
    if pending:
        cues.append(Cue(id=len(cues), start=pending[0][0], end=max(pending[-1][1], pending[0][0] + .01), text=" ".join(w[2] for w in pending)))
    return validate_cues(cues)
