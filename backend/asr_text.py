"""Lossless punctuation projection and script-aware display joining."""
from difflib import SequenceMatcher
import re
import unicodedata

CJK = r'\u3400-\u9fff\uf900-\ufaff\u3040-\u30ff'


def join_text(parts):
    text = ' '.join(str(part).strip() for part in parts if str(part).strip())
    text = re.sub(fr'(?<=[{CJK}])\s+(?=[{CJK}])', '', text)
    text = re.sub(r'\s+([,.;:!?\u3002\uff0c\uff01\uff1f\uff1b\uff1a\u3001])', r'\1', text)
    text = re.sub(fr'([\u3002\uff0c\uff01\uff1f\uff1b\uff1a\u3001])\s+(?=[{CJK}])', r'\1', text)
    text = re.sub(fr'(?<=[{CJK}])([,.;:!?])\s+(?=[{CJK}])', r'\1', text)
    return text


def lexical(text):
    return ''.join(c.casefold() for c in unicodedata.normalize('NFKC', text) if c.isalnum())


def restore_punctuation(words, transcript):
    """Retain matched numeric separators and token-edge sentence punctuation."""
    output = [dict(word) for word in words]
    transcript = unicodedata.normalize('NFKC', transcript)
    source, separators = [], {}
    for position, char in enumerate(transcript):
        if char.isalnum():
            source.extend(char.casefold())
        elif char in ',.;:!?\u3002\u3001':
            if (char in '.,' and 0 < position < len(transcript)-1
                    and transcript[position-1].isdigit() and transcript[position+1].isdigit()):
                continue
            separators[len(source)-1] = separators.get(len(source)-1, '') + char
    target = ''.join(lexical(w['text']) for w in output)
    mapping = {}
    for match in SequenceMatcher(None, ''.join(source), target, autojunk=False).get_matching_blocks():
        mapping.update((match.b+i, match.a+i) for i in range(match.size))
    # Forced aligners may return 193 for a correctly recognized 1.93. Match the
    # complete digit run before restoring it, including across word boundaries;
    # never guess a decimal position from numeric plausibility or an LLM.
    inverse = {source_index: target_index for target_index, source_index in mapping.items()}
    numeric_spans = []
    # If lexical coverage differs, a repeated digit run can map to the wrong
    # occurrence (e.g. 1.93 ... 193 with one occurrence missing). Do not guess.
    numbers = re.finditer(r'\d+(?:[.,]\d+)+', transcript) if ''.join(source) == target else ()
    for number in numbers:
        begin = len(lexical(transcript[:number.start()]))
        size = len(lexical(number.group()))
        first = inverse.get(begin)
        if first is not None and all(mapping.get(first+i) == begin+i for i in range(size)):
            numeric_spans.append((first, first+size, number.group()))
    cursor, indexed = 0, []
    for word in output:
        size = len(lexical(word['text']))
        indexed.append((cursor, cursor+size, word))
        cursor += size
    # Whole aligned numeric tokens can be joined without inventing internal
    # timestamps. Other token shapes remain untouched instead of rewriting text.
    for begin, end, number in reversed(numeric_spans):
        selected = [i for i, (a, b, _) in enumerate(indexed) if a < end and b > begin]
        if not selected:
            continue
        first, last = selected[0], selected[-1]
        group = indexed[first:last+1]
        if group[0][0] != begin or group[-1][1] != end:
            continue
        if any(not re.fullmatch(r'[\d.,\s]+', item['text']) for _, _, item in group):
            continue
        restored = {**group[0][2], 'text': number,
                    'end': max(item['end'] for _, _, item in group)}
        indexed[first:last+1] = [(begin, end, restored)]
    output = [item for _, _, item in indexed]
    cursor = 0
    for word in output:
        count = len(lexical(word['text']))
        edge = mapping.get(cursor+count-1)
        punctuation = separators.get(edge, '')
        if count and punctuation and not re.search(r'[,.;:!?\u3002\u3001]$', word['text']):
            word['text'] += punctuation
        cursor += count
    return output
