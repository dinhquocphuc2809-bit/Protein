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
    """Project separators only at matched token edges; never replace aligned words."""
    output = [dict(word) for word in words]
    source, separators = [], {}
    for char in unicodedata.normalize('NFKC', transcript):
        if char.isalnum():
            source.extend(char.casefold())
        elif char in ',.;:!?\u3002\u3001':
            separators[len(source)-1] = separators.get(len(source)-1, '') + char
    target = ''.join(lexical(w['text']) for w in output)
    mapping = {}
    for match in SequenceMatcher(None, ''.join(source), target, autojunk=False).get_matching_blocks():
        mapping.update((match.b+i, match.a+i) for i in range(match.size))
    cursor = 0
    for word in output:
        count = len(lexical(word['text']))
        edge = mapping.get(cursor+count-1)
        punctuation = separators.get(edge, '')
        if count and punctuation and not re.search(r'[,.;:!?\u3002\u3001]$', word['text']):
            word['text'] += punctuation
        cursor += count
    return output
