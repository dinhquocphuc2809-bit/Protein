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


def speech_units(cues: list[Cue]) -> list[Cue]:
    """Reflow display fragments without dropping words or inventing word alignment."""
    validate_cues(cues)
    pieces = []
    abbreviations = {"mr", "mrs", "ms", "dr", "prof", "st", "vs", "etc", "e.g", "i.e"}
    merged = []
    for cue in cues:
        if merged and cue.start == merged[-1].start:
            previous = merged[-1]
            merged[-1] = Cue(id=previous.id, start=previous.start, end=max(previous.end, cue.end), text=previous.text+' '+cue.text)
        else:
            merged.append(cue)
    for index, original in enumerate(merged):
        # YouTube rolling display lifetimes overlap. Speech ownership ends when
        # the next caption begins, not when the previous visual caption disappears.
        cue = original.model_copy(update={"end": min(original.end, merged[index+1].start) if index+1 < len(merged) else original.end})
        text = cue.text
        cuts = []
        for match in re.finditer(r'[.!?,;:\u3002\uff01\uff1f\uff0c](?:["\u201d\u2019\')\]]*)(?=\s|$)', text):
            before = text[:match.start()].rsplit(' ', 1)[-1].lower()
            if text[match.start()] == '.' and (before in abbreviations or len(before) == 1):
                continue
            cuts.append(match.end())
        cuts.append(len(text))
        offset, start = 0, cue.start
        boundaries = sorted(set(cuts))
        epsilon = min(.02, (cue.end-cue.start)/(len(boundaries)+1))
        for number, cut in enumerate(boundaries):
            part = text[offset:cut].strip()
            if not part:
                continue
            estimated = cue.start + (cue.end-cue.start)*cut/len(text)
            anchor = cue.start if cut/len(text) < .5 else cue.end
            upper = cue.end-epsilon*(len(boundaries)-number-1)
            end = cue.end if cut == len(text) else min(upper, max(start+epsilon, min(anchor+.75, max(anchor-.75, estimated))))
            pieces.append((start, end, part))
            start, offset = end, cut
    units, pending = [], []
    def flush():
        if pending:
            units.append(Cue(id=len(units), start=pending[0][0], end=pending[-1][1],
                             text=' '.join(p[2] for p in pending)))
            pending.clear()
    for start, end, text in pieces:
        if pending and (start-pending[-1][1] > .8 or end-pending[0][0] > 14 or sum(len(p[2])+1 for p in pending)+len(text) > 600):
            flush()
        # Very long unpunctuated imported cues still need bounded TTS inputs.
        words = text.split()
        while len(' '.join(words)) > 600 or end-start > 14:
            count = max(1, min(len(words)-1, int(len(words)*min(12/max(.01, end-start), 500/max(1,len(' '.join(words)))))))
            if len(words) < 2:
                raise ValueError('Subtitle contains an unsplittable speech unit')
            head = ' '.join(words[:count])
            boundary = start+(end-start)*len(head)/max(1,len(' '.join(words)))
            pending.append((start,boundary,head))
            flush()
            start, words = boundary, words[count:]
        pending.append((start,end,' '.join(words)))
        duration = end-pending[0][0]
        if re.search(r'[.!?\u3002\uff01\uff1f]["\u201d\u2019\')\]]*$', text) or (duration >= 7 and re.search(r'[,;:\uff0c]["\u201d\u2019\')\]]*$', text)):
            flush()
    flush()
    combined = []
    for unit in units:
        previous = combined[-1] if combined else None
        if (previous and unit.start-previous.end <= .35 and unit.end-previous.start <= 10
                and len(previous.text)+len(unit.text) < 550
                and (previous.end-previous.start < 2.5 or unit.end-unit.start < 1)):
            combined[-1] = Cue(id=previous.id, start=previous.start, end=unit.end, text=previous.text+' '+unit.text)
        else:
            combined.append(unit.model_copy(update={"id": len(combined)}))
    return validate_cues(combined)
