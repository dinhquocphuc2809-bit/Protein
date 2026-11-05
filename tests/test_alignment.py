import pytest

from gpu.alignment import bounded_alignment, whisper_alignment_language


def test_incident_80ms_tail_overrun_retains_text_without_extending_audio():
    rows = [{'text': 'first', 'start': 2.88, 'end': 3.20},
            {'text': 'last', 'start': 3.44, 'end': 3.52}]
    result = bounded_alignment(rows, 3.44)
    assert result == [{'text': 'first last', 'start': 2.88, 'end': 3.20}]
    assert rows[-1]['end'] == 3.52


def test_small_edge_overshoot_is_clipped_and_zero_tokens_are_retained():
    rows = [{'text': 'prefix', 'start': 0, 'end': 0},
            {'text': 'word', 'start': 0, 'end': 1.08}]
    assert bounded_alignment(rows, 1) == [{'text': 'prefix word', 'start': 0.0, 'end': 1}]


@pytest.mark.parametrize('start,end', [(0, 1.2), (-.2, .5), (.6, .5),
                                      (float('nan'), 1), (0, float('inf')), (1, 1)])
def test_large_or_unusable_alignment_is_not_hidden(start, end):
    with pytest.raises(ValueError):
        bounded_alignment([{'text': 'word', 'start': start, 'end': end}], 1)


def test_nonmonotonic_alignment_requires_real_realigning():
    with pytest.raises(ValueError):
        bounded_alignment([{'text': 'one', 'start': .5, 'end': .7},
                           {'text': 'two', 'start': .2, 'end': .4}], 1)


def test_cantonese_fallback_on_99_language_whisper_uses_chinese_tokenizer():
    assert whisper_alignment_language('yue', ('en','zh','vi','tl')) == 'zh'
    assert whisper_alignment_language('yue', ('en','zh','yue')) == 'yue'


@pytest.mark.parametrize('code,expected', [('fil','tl'),('zh-CN','zh'),('vi','vi'),('en','en')])
def test_fallback_language_aliases_and_supported_languages(code,expected):
    assert whisper_alignment_language(code, ('en','zh','vi','tl')) == expected


@pytest.mark.parametrize('code', ['auto','unknown','yue'])
def test_unsupported_language_has_clear_error_not_tokenizer_index_failure(code):
    with pytest.raises(ValueError,match='unsupported by the fallback aligner'):
        whisper_alignment_language(code, ('en',))
