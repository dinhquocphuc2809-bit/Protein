"""Acquire only audio for the authorized long-video benchmark; never log secrets."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.storage import download_public
from verify_providers import records

VIDEO = 'YGi-aPUsZrQ'


def main():
    folder = ROOT/'.private/asr-long-video'
    folder.mkdir(exist_ok=True)
    target = folder/'audio.wav'
    report_path = ROOT/'research/benchmarks/qwen-long-video-input.json'
    if target.exists():
        raise ValueError('Retained input already exists; validate it instead of downloading again')
    def reserve(_=0):
        if shutil.disk_usage(folder).free < 2*1024**3:
            raise ValueError('Less than 2 GiB local free-space reserve')
    reserve()
    report = {'video': VIDEO, 'at': datetime.now(timezone.utc).isoformat(),
              'storage_location': 'local Windows workspace, not VPS', 'passed': False}
    started = time.perf_counter()
    media_file = folder/'media.json'
    media = json.loads(media_file.read_text()) if media_file.exists() else {}
    if media.get('expires', 0) < time.time()+600:
        with httpx.Client(timeout=120) as client:
            for index, key in enumerate(records('tunelio'), 1):
                headers = {'Authorization': 'Bearer '+key}
                credits = client.get('https://tunelio.dev/credits', headers=headers)
                if credits.status_code != 200 or float(credits.json().get('credits', 0)) < 10:
                    continue
                response = client.get('https://tunelio.dev/create', headers=headers,
                                      params={'url': 'https://www.youtube.com/watch?v='+VIDEO, 'quality': 'opus'})
                if response.status_code != 200:
                    continue
                media = response.json()
                if media.get('status') == 'ok' and media.get('url'):
                    media_file.write_text(json.dumps(media), encoding='utf-8')
                    report['tunelio_record'] = index
                    break
            else:
                raise RuntimeError('No Tunelio audio URL obtained')
    source = folder/'audio.opus'
    if not source.exists():
        download_public(media['url'], source, 512*1024**2, deadline_seconds=1200, progress=reserve)
    report['download_seconds'] = time.perf_counter()-started
    report['download_bytes'] = source.stat().st_size
    ffmpeg = shutil.which('ffmpeg')
    if not ffmpeg:
        raise RuntimeError('ffmpeg is required')
    ffprobe = str(Path(ffmpeg).with_name('ffprobe.exe'))
    probe = subprocess.run([ffprobe, '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(source)],
                           capture_output=True, timeout=60, check=True)
    metadata = json.loads(probe.stdout)
    if not metadata['streams'] or any(s['codec_type'] != 'audio' for s in metadata['streams']):
        raise ValueError('Provider did not return audio-only media')
    duration = float(metadata['format']['duration'])
    if not 0 < duration <= 14400:
        raise ValueError('Audio exceeds four-hour experiment limit')
    report['source_duration_seconds'] = duration
    report['source_codecs'] = [s['codec_name'] for s in metadata['streams']]
    reserve()
    started = time.perf_counter()
    partial = folder/'normalized.partial.wav'
    with (folder/'ffmpeg.log').open('wb') as log:
        result = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', str(source), '-map', '0:a:0',
                                 '-vn', '-sn', '-dn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le',
                                 '-fs', str(512*1024**2), str(partial)], stdout=log, stderr=log, timeout=1200)
    if result.returncode:
        raise RuntimeError('Audio normalization failed; inspect private ffmpeg log')
    with wave.open(str(partial)) as wav:
        normalized_duration = wav.getnframes()/wav.getframerate()
        assert (wav.getnchannels(), wav.getsampwidth(), wav.getframerate()) == (1, 2, 16000)
        assert abs(normalized_duration-duration) < 1
    with partial.open('rb') as file:
        digest = hashlib.file_digest(file, 'sha256').hexdigest()
    partial.rename(target)
    report.update(normalization_seconds=time.perf_counter()-started, duration_seconds=normalized_duration,
                  normalized_bytes=target.stat().st_size, audio_sha256=digest, audio_only=True, passed=True)
    source.unlink()
    report['download_source_removed'] = True
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print(json.dumps({'error_type': type(error).__name__}), flush=True)
        raise SystemExit(1)
