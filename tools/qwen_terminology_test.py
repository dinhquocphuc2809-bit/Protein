"""Real contextual repair/translation of retained Qwen output; no ASR rerun."""
import asyncio
import argparse
import hashlib
import json
from pathlib import Path
import secrets
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.config import Settings
from backend.database import Database
from backend.providers import KeyPool, Providers
from backend.security import Security
from backend.subtitles import words_to_cues, speech_units
from backend.terminology import apply_plan


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--full-source', action='store_true')
    args = parser.parse_args()
    private = ROOT/'.private/qwen-improvement'
    words = json.loads((private/('full-words-final.json' if args.full_source else 'merged-baseline.json')).read_text(encoding='utf-8'))
    cues = words_to_cues(words, ensure_punctuation=True)
    title = json.loads((ROOT/'.private/translation-audit/source.json').read_text(encoding='utf-8'))['metadata']['title']
    report = {'scope': 'Real Gemini terminology and sampled translations of retained Chinese Qwen output', 'passed': False}
    with tempfile.TemporaryDirectory(dir=ROOT/'.private', prefix='terminology-') as folder:
        settings = Settings(data_dir=Path(folder), master_key=secrets.token_hex(32), admin_token=secrets.token_hex(32))
        db = Database(Path(folder)/'test.sqlite3')
        pool = KeyPool(db, Security(db, settings))
        pool.add('gemini', (ROOT.parent/'api-key-gemini.txt').read_text(encoding='utf-8-sig').splitlines()[0].strip())
        provider = Providers(pool, settings)
        original_llm = provider.llm
        async def capture(*args, **kwargs):
            value = await original_llm(*args, **kwargs)
            if isinstance(value, dict) and 'terms' in value:
                with (private/'terminology-responses.jsonl').open('a',encoding='utf-8') as output:
                    output.write(json.dumps(value,ensure_ascii=False)+'\n')
            return value
        provider.llm = capture
        async def progress(stage):
            pass
        try:
            start = time.perf_counter()
            plan_path = private/'terminology-plan.json'
            fingerprint = hashlib.sha256(json.dumps([c.model_dump() for c in cues],sort_keys=True).encode()).hexdigest()
            identity_path = private/'terminology-source-hash.txt'
            if plan_path.exists() and identity_path.exists() and identity_path.read_text() == fingerprint:
                plan = json.loads(plan_path.read_text(encoding='utf-8'))
            else:
                plan = await provider.terminology(cues, 'zh', 'vi', 'basic', title)
                plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding='utf-8')
                identity_path.write_text(fingerprint)
            report['plan_seconds'] = time.perf_counter()-start
            corrected, edits = apply_plan(cues, plan)
            (private/'source-repairs.json').write_text(json.dumps(edits, ensure_ascii=False, indent=2), encoding='utf-8')
            report.update(terms=len(plan['terms']), edits=len(edits), checks=[])
            corrected = speech_units(corrected)
            raw_units = speech_units(cues)
            translations = []
            for timestamp in [4352, 4493, 4512, 4804, 4807, 4814, 4822, 6888]:
                index = next(i for i,c in enumerate(corrected) if c.end > timestamp)
                cue = corrected[index]
                translated = (await provider.translate([cue], 'zh', 'vi', 'basic', title, progress, speech=True,
                    surrounding_before=[c.text for c in corrected[max(0,index-6):index]],
                    surrounding_after=[c.text for c in corrected[index+1:index+7]], terminology=plan))[0]
                assert (cue.id, cue.start, cue.end) == (translated.id, translated.start, translated.end)
                original = next((c.text for c in raw_units if c.start <= timestamp < c.end), '')
                translations.append({'timestamp': timestamp, 'raw': original, **translated.model_dump()})
                report['checks'].append({'timestamp': timestamp, 'cue_id': cue.id, 'source_changed': cue.text != original,
                                         'timestamps_preserved': True, 'translated': bool(translated.translated)})
                print(json.dumps(report['checks'][-1]), flush=True)
            (private/'translations.json').write_text(json.dumps(translations, ensure_ascii=False, indent=2), encoding='utf-8')
            by_time = {r['timestamp']: r for r in translations}
            names = [t for t in plan['terms'] if t['kind'] == 'name']
            for timestamps, aliases in [([4512,4814], ['\u591a\u91cc','\u591a\u5229']),
                                        ([4814,4822], ['\u6234\u4e9a','\u6b79\u4e9a'])]:
                term = next(t for t in names if any(a in t['aliases'] for a in aliases))
                assert all(term['translation'].casefold() in by_time[t]['translated'].casefold() for t in timestamps)
            assert '\u9e1f' in by_time[6888]['raw']
            assert 'chim' not in by_time[6888]['translated'].casefold()
            assert 'voi' in by_time[4804]['translated'].casefold()
            assert 'cu li' in by_time[4352]['translated'].casefold()
            report['known_error_regressions'] = {'two_names_consistent': True, 'bird_mistranslation_absent': True,
                                                'elephant_context_retained': True, 'loris_not_owl': True}
            report.update(passed=True, seconds=time.perf_counter()-start, calls=db.one('SELECT calls FROM api_keys')['calls'])
        finally:
            await provider.close()
            (ROOT/'research/qwen-terminology-live.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')


if __name__ == '__main__':
    asyncio.run(main())
