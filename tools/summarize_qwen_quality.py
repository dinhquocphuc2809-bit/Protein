"""Offline structural audit of retained benchmark output; no provider calls."""
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import wave

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.subtitles import speech_units, words_to_cues


def main():
    folder = ROOT / '.private/asr-long-video'
    source = folder / 'T4-retained-words.json'
    words = json.loads(source.read_text(encoding='utf-8'))
    cues = words_to_cues(words)
    raw = [json.loads(line) for line in (folder / 'T4-words.jsonl').read_text(encoding='utf-8').splitlines()]
    with wave.open(str(folder / 'audio.wav')) as audio:
        assert (audio.getnchannels(), audio.getsampwidth(), audio.getframerate()) == (1, 2, 16000)
        duration = audio.getnframes() / audio.getframerate()
        audio.setpos(374 * 24 * 16000)
        tail = audio.readframes(28 * 16000)

    # A repeated token alone is not an error (e.g. the Chinese word for mother).
    candidates = []
    for i, first in enumerate(words):
        for second in words[i+1:]:
            if second['start'] >= first['end']:
                break
            overlap = min(first['end'], second['end']) - max(first['start'], second['start'])
            if first['text'] != second['text'] or overlap <= 0:
                continue
            center = (first['start'] + second['start']) / 2
            boundary = round((center - 2) / 24) * 24 + 2
            indices = [(boundary - 2) // 24 - 1, (boundary - 2) // 24]
            contexts = []
            for index in indices:
                row = raw[index]
                contexts.append({'index': index, 'text': ''.join(w['text'] for w in row['words']
                    if boundary-3 < w['start']+row['offset'] < boundary+3)})
            candidates.append({'first': first, 'second': second,
                'overlap_seconds': round(overlap, 6), 'nearest_ownership_boundary': boundary,
                'raw_window_contexts': contexts,
                'retained_context': ''.join(w['text'] for w in words if boundary-3 < w['start'] < boundary+3)})

    punctuation = r'[,.;:!?\u3002\uff0c\uff1b\uff1a\uff01\uff1f\u3001]'
    report = {
        'video': 'YGi-aPUsZrQ', 'duration_seconds': duration,
        'scope': 'Full retained T4 structural audit and sampled blinded audio references; no human ground truth',
        'retained_sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
        'words': len(words), 'cues': len(cues), 'speech_units': len(speech_units(cues)),
        'all_word_times_finite_in_bounds': all(math.isfinite(w['start']) and math.isfinite(w['end'])
            and 0 <= w['start'] <= w['end'] <= duration for w in words),
        'cues_with_punctuation': sum(bool(re.search(punctuation, c.text)) for c in cues),
        'cues_ending_in_punctuation': sum(bool(re.search(punctuation+'$', c.text)) for c in cues),
        'cues_with_spaces_between_cjk': sum(bool(re.search(r'[\u4e00-\u9fff] [\u4e00-\u9fff]', c.text)) for c in cues),
        'overlapping_identical_token_candidates': candidates,
        'candidate_interpretation': 'Four duplicated single occurrences at 1154, 2594, 4370, 8210; 1922 is legitimate mama, not a proven duplication.',
        'silent_tail_reference_rejection': {
            'index': 374, 'offset': 8976, 'duration_seconds': len(tail)/32000,
            'all_pcm_bytes_zero': bool(tail) and not any(tail),
            'conclusion': 'Gemini speech on this digital-silent clip is a false positive; Qwen and Deepgram return empty.'},
        'references': {}, 'production_changed': False,
        'accuracy_score': None, 'accuracy_score_reason': 'No manually verified reference transcript; model disagreements are not CER/WER.'}
    for engine in ('gemini', 'deepgram'):
        reference = json.loads((ROOT / f'research/qwen-quality-{engine}.json').read_text(encoding='utf-8'))
        assert reference['completed']
        report['references'][engine] = {'model': reference['reference_model'],
            'windows': len(reference['samples']), 'sample_audio_seconds': reference['sample_audio_seconds'],
            'indices': [r['index'] for r in reference['samples']]}
    path = ROOT / 'research/qwen-quality-summary.json'
    path.write_text(json.dumps(report, ensure_ascii=True, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ('words', 'cues', 'speech_units', 'all_word_times_finite_in_bounds',
        'cues_with_punctuation', 'cues_with_spaces_between_cjk')}, indent=2))
    print('Overlapping identical-token candidates:', len(candidates))


if __name__ == '__main__':
    main()
