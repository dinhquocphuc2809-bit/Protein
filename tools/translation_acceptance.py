"""Bounded real Gemini translation and checkpoint-reuse probe; no ASR/TTS calls."""
import asyncio
import json
from pathlib import Path
import secrets
import tempfile
import time

from backend.config import Settings
from backend.database import Database
from backend.providers import KeyPool, Providers
from backend.security import Security
from backend.subtitles import Cue

ROOT = Path(__file__).resolve().parents[1]


async def main():
    report = {'scope': 'Real Gemini basic, 12 labelled restaurant subtitle cues; no ASR/TTS', 'passed': False}
    lines = ['This buffet costs two dollars per person.', 'The price includes rice and vegetables.',
             'We will compare it with a more expensive restaurant.', 'First, let us try the soup.',
             'It tastes lighter than I expected.', 'The noodles are made fresh every morning.',
             'There are several sauces on the table.', 'You can choose how spicy you want it.',
             'Now we are visiting the second restaurant.', 'Here the buffet costs seventy-five dollars.',
             'The seafood selection is much larger.', 'But the best choice depends on what you enjoy eating.']
    cues = [Cue(id=240+i, start=500+i*4, end=503+i*4, text=line) for i, line in enumerate(lines)]
    with tempfile.TemporaryDirectory(dir=ROOT / '.private', prefix='translation-check-') as folder:
        settings = Settings(data_dir=Path(folder), master_key=secrets.token_hex(32), admin_token=secrets.token_hex(32))
        db = Database(Path(folder) / 'test.sqlite3')
        pool = KeyPool(db, Security(db, settings))
        pool.add('gemini', (ROOT.parent / 'api-key-gemini.txt').read_text(encoding='utf-8-sig').strip())
        provider = Providers(pool, settings)
        checkpoint = {}
        async def progress(stage):
            pass
        def load(batch):
            return checkpoint.get(batch[0].id)
        def save(batch, value):
            checkpoint[batch[0].id] = value
        try:
            start = time.monotonic()
            result = await provider.translate(cues, 'en', 'vi', 'basic', 'Restaurant comparison', progress,
                                              load_batch=load, save_batch=save)
            assert [(c.id, c.start, c.end) for c in result] == [(c.id, c.start, c.end) for c in cues]
            assert all(c.translated for c in result)
            calls = db.one('SELECT calls FROM api_keys')['calls']
            again = await provider.translate(cues, 'en', 'vi', 'basic', 'Restaurant comparison', progress,
                                             load_batch=load, save_batch=save)
            assert again == result and db.one('SELECT calls FROM api_keys')['calls'] == calls
            report.update(passed=True, cues=len(result), provider_calls=calls, elapsed_seconds=round(time.monotonic()-start, 3),
                          timestamps_preserved=True, checkpoint_repeat_provider_calls=0)
        except Exception as error:
            report['error'] = type(error).__name__
            raise
        finally:
            await provider.close()
            (ROOT / 'research/translation-recovery.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            print(json.dumps(report))


if __name__ == '__main__':
    asyncio.run(main())
