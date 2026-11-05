"""Choose one text/time seam between overlapping independently aligned windows."""
from difflib import SequenceMatcher
import math

from .asr_text import lexical


def _atoms(words, boundary):
    atoms = []
    for i, word in enumerate(words):
        if word['end'] < boundary-3 or word['start'] > boundary+3:
            continue
        text = lexical(word['text'])
        for j, char in enumerate(text):
            middle = word['start'] + (word['end']-word['start'])*(j+.5)/len(text)
            atoms.append((char, i, middle, j == len(text)-1))
    return atoms


class WindowMerger:
    def __init__(self):
        self.words = []
        self.previous_offset = None
        self.seams = []

    def append(self, words, offset, duration):
        if self.previous_offset is not None and offset <= self.previous_offset:
            raise ValueError('ASR windows must arrive in increasing order')
        incoming = []
        for word in words:
            start, end = float(word['start']), float(word['end'])
            if not all(map(math.isfinite, (start, end))) or not 0 <= start <= end <= duration+.001:
                raise ValueError('Invalid ASR word bounds')
            if incoming and start+offset < incoming[-1]['start']-.001:
                raise ValueError('Unsorted ASR window')
            incoming.append({**word, 'start': start+offset, 'end': end+offset})
        if self.previous_offset is None:
            self.words = incoming
        else:
            boundary = offset+2
            left, right = _atoms(self.words, boundary), _atoms(incoming, boundary)
            candidates = []
            for match in SequenceMatcher(None, ''.join(a[0] for a in left), ''.join(a[0] for a in right), autojunk=False).get_matching_blocks():
                if match.size < 2:
                    continue
                for n in range(match.size):
                    a, b = left[match.a+n], right[match.b+n]
                    # Cut only at whole-token edges, supported by adjacent matching
                    # text and nearby audio. Never collapse repeated words globally.
                    if a[3] and b[3] and abs(a[2]-b[2]) <= .65:
                        candidates.append((abs((a[2]+b[2])/2-boundary), a[1], b[1]))
            if candidates:
                _, a, b = min(candidates)
                proposed = self.words[:a+1] + incoming[b+1:]
                baseline = [w for w in self.words if (w['start']+w['end'])/2 < boundary]
                baseline += [w for w in incoming if (w['start']+w['end'])/2 >= boundary]
                old_text = ''.join(lexical(w['text']) for w in baseline if w['end'] >= boundary-4)
                new_text = ''.join(lexical(w['text']) for w in proposed if w['end'] >= boundary-4)
                changes = SequenceMatcher(None, old_text, new_text, autojunk=False).get_opcodes()
                # A seam can remove/recover boundary copies, not pick a different
                # acoustic hypothesis just because its alignment is a little closer.
                if any(op == 'replace' for op, *_ in changes):
                    self.words = baseline
                    mode = 'temporal_conflicting_text'
                else:
                    self.words = proposed
                    mode = 'text_time_anchor'
            else:
                self.words = [w for w in self.words if (w['start']+w['end'])/2 < boundary]
                self.words.extend(w for w in incoming if (w['start']+w['end'])/2 >= boundary)
                mode = 'temporal_unresolved' if left and right else 'silence_boundary'
            self.seams.append({'offset': offset, 'mode': mode})
        self.previous_offset = offset
        self.words.sort(key=lambda w: w['start'])
        return self.words
