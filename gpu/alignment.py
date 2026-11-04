"""Validate model timestamps, allowing bounded quantization at audio edges."""
import math


def bounded_alignment(words, duration, tolerance=0.12):
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("Invalid alignment audio duration")
    output, pending = [], []
    previous = -math.inf
    for word in words:
        text = str(word['text']).strip()
        if not text:
            continue
        start, end = float(word['start']), float(word['end'])
        if (not math.isfinite(start) or not math.isfinite(end) or end < start
                or start < -tolerance or end > duration + tolerance or start < previous - 0.001):
            raise ValueError("Alignment produced invalid timestamps")
        previous = max(previous, start)
        start, end = min(duration, max(0.0, start)), min(duration, max(0.0, end))
        if start == end:
            # Quantized edge tokens have no measurable interval. Retain their
            # text in an adjacent aligned word instead of inventing more audio.
            if output:
                output[-1]['text'] += ' ' + text
            else:
                pending.append(text)
            continue
        output.append({'text': ' '.join([*pending, text]), 'start': start, 'end': end})
        pending.clear()
    if pending or not output:
        raise ValueError("Alignment has no measurable word intervals")
    return output
