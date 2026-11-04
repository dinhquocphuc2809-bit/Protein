"""Compare recognition before/after sentence DSP using retained real TTS samples.

This is a bounded audio-quality check, not source-video acquisition or listening QA.
Requires the owner-only output from progressive_live.py and two short Deepgram calls.
"""
import io
import json
from pathlib import Path
import re
import wave

import httpx
import numpy as np

from verify_providers import records

ROOT = Path(__file__).resolve().parents[1]


def distance(a, b):
    previous = list(range(len(b)+1))
    for i, x in enumerate(a, 1):
        current = [i]
        for j, y in enumerate(b, 1):
            current.append(min(current[-1]+1, previous[j]+1, previous[j-1]+(x != y)))
        previous = current
    return previous[-1]


def main():
    folder = ROOT / '.private/progressive-audio'
    samples = np.concatenate([np.fromfile(p, dtype='<f4') for p in sorted(folder.glob('unit-[0-9].f32'))])
    if not 0 < len(samples) <= 24000*60:
        raise ValueError('Expected at most 60 seconds of existing verification samples')
    raw = io.BytesIO()
    with wave.open(raw, 'wb') as output:
        output.setparams((1, 2, 24000, 0, 'NONE', 'not compressed'))
        output.writeframes((np.clip(samples, -1, 1)*32767).astype('<i2').tobytes())
    transcripts = []
    with httpx.Client(timeout=90) as http:
        for data in [raw.getvalue(), (folder/'sentence-comparison-new.wav').read_bytes()]:
            response = http.post('https://api.deepgram.com/v1/listen',
                params={'model': 'nova-3', 'language': 'vi', 'punctuate': 'true'},
                headers={'Authorization': 'Token '+records('deepgram')[0], 'Content-Type': 'audio/wav'}, content=data)
            if response.status_code != 200:
                raise RuntimeError(f'Quality verification returned HTTP {response.status_code}')
            transcripts.append(response.json()['results']['channels'][0]['alternatives'][0])
    (folder/'recognition-comparison.json').write_text(json.dumps(transcripts,ensure_ascii=False,indent=2),encoding='utf8')
    words = [re.findall(r'\w+', t['transcript'].lower()) for t in transcripts]
    edits = distance(*words)
    report = {'scope': 'Independent ASR of real natural and DSP-fitted TTS samples; not subjective listening',
              'model': 'nova-3', 'language': 'vi', 'natural_words': len(words[0]), 'fitted_words': len(words[1]),
              'recognition_edits_after_dsp': edits, 'recognition_change_rate': round(edits/max(1,len(words[0])),4),
              'same_first_five_words': words[0][:5] == words[1][:5], 'same_last_five_words': words[0][-5:] == words[1][-5:]}
    (ROOT/'research/progressive-speech-check.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
