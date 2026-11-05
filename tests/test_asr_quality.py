import re
import json
from pathlib import Path

import pytest

from backend.asr_merge import WindowMerger
from backend.asr_text import join_text, lexical, restore_punctuation
from backend.subtitles import words_to_cues, speech_units


def words(text, start=24, step=.16):
    return [{'text': c, 'start': start+i*step, 'end': start+(i+1)*step} for i, c in enumerate(text)]


@pytest.mark.parametrize('text', ['\u5fc5\u987b\u6210\u4e3a\u5f3a\u8005', '\u5988\u5988\u90fd\u4f1a', 'go go home', '\u5f88\u4e0d\u6ee1\u4ed6\u4eec'])
@pytest.mark.parametrize('jitter', [-.12, -.04, .04, .12])
def test_context_seam_preserves_true_repetitions(text, jitter):
    first = words(text, start=25.5)
    second = [{**w, 'start': w['start']-24+jitter, 'end': w['end']-24+jitter} for w in first]
    merger = WindowMerger()
    merger.append(first, 0, 28)
    merger.append(second, 24, 28)
    assert ''.join(w['text'] for w in merger.words) == text
    assert merger.seams[-1]['mode'] == 'text_time_anchor'


def test_punctuation_and_tokenization_change_at_seam():
    merger = WindowMerger()
    merger.append(words('\u6210\u4e3a\u5f3a\u8005', start=25.6), 0, 28)
    merger.append([{'text': '\u6210\u4e3a', 'start': 1.58, 'end': 1.94},
                   {'text': '\u5f3a\u8005\u3002', 'start': 1.94, 'end': 2.25}], 24, 28)
    assert lexical(''.join(w['text'] for w in merger.words)) == '\u6210\u4e3a\u5f3a\u8005'


def test_silence_and_invalid_bounds():
    merger = WindowMerger()
    merger.append(words('abc', 1), 0, 28)
    merger.append([], 24, 28)
    assert ''.join(w['text'] for w in merger.words) == 'abc'
    with pytest.raises(ValueError):
        merger.append(words('x', -1), 48, 28)


def test_punctuation_projection_never_changes_lexical_content_or_time():
    original = words('\u5988\u5988\u6765\u4e86\u6211\u5f88\u9ad8\u5174', 0)
    output = restore_punctuation(original, '\u5988\u5988\u6765\u4e86\uff0c\u6211\u5f88\u9ad8\u5174\u3002')
    assert [(w['start'], w['end']) for w in output] == [(w['start'], w['end']) for w in original]
    assert lexical(join_text(w['text'] for w in output)) == lexical(join_text(w['text'] for w in original))
    assert output[3]['text'].endswith(',') and output[-1]['text'].endswith('\u3002')


def test_cjk_spacing_and_latin_words():
    assert join_text(['\u4e2d', '\u534e', '\u79cb', '\u6c99', '\u9e2d']) == '\u4e2d\u534e\u79cb\u6c99\u9e2d'
    assert join_text(['Hello', 'world', '!']) == 'Hello world!'
    assert join_text(['Xin', 'chao', 'ban.']) == 'Xin chao ban.'


def test_source_cues_have_bounded_times_punctuation_and_no_cjk_spaces():
    original = words('\u4e2d\u534e\u79cb\u6c99\u9e2d'*20, 0)
    cues = words_to_cues(original, ensure_punctuation=True)
    assert all(re.search(r'[,.;!?\u3002\uff0c]$', c.text) for c in cues)
    assert all(not re.search(r'[\u4e00-\u9fff] [\u4e00-\u9fff]', c.text) for c in cues)
    assert lexical(''.join(c.text for c in cues)) == lexical(''.join(w['text'] for w in original))
    assert speech_units(cues)


@pytest.mark.parametrize('case', json.loads((Path(__file__).parent/'fixtures/qwen_boundary_regressions.json').read_text()))
def test_real_qwen_window_boundaries(case):
    merger = WindowMerger()
    for window in case['windows']:
        merger.append(window['words'], window['offset'], 28)
    text = lexical(''.join(w['text'] for w in merger.words))
    assert case['expected'] in text
    for rejected in ['\u4e3a\u4e3a', '\u4e00\u4e00', '\u4e0d\u4e0d', '\u8fbd\u8fbd']:
        assert rejected not in text
