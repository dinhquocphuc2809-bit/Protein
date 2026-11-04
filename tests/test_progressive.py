import asyncio
import secrets

import pytest

from backend.app import build
from backend.config import Settings
from backend.jobs import VideoRequest, WindowRequest
from backend.subtitles import Cue, speech_units


def test_sentence_reflow_preserves_words_and_rejoins_dangling_greeting():
    rows = [Cue(id=0, start=26, end=31, text='of Chongqing for our first stop. Good'),
            Cue(id=1, start=28, end=33, text="morning from Chongqing, China. We've"),
            Cue(id=2, start=30, end=34, text='officially arrived at our first of three'),
            Cue(id=3, start=32, end=37, text='stops. Let us go inside.')]
    units = speech_units(rows)
    assert ' '.join(c.text for c in units).split() == ' '.join(c.text for c in rows).split()
    assert any('Good morning from Chongqing, China.' in c.text for c in units)
    assert any("We've officially arrived at our first of three stops." in c.text for c in units)
    assert all(a.end <= b.start for a, b in zip(units, units[1:]))
    assert all(0 < c.end-c.start <= 14 and len(c.text) <= 600 for c in units)


def test_clause_breaks_and_long_unpunctuated_inputs_are_bounded():
    rows = [Cue(id=0, start=0, end=30, text='word '*150)]
    units = speech_units(rows)
    assert len(units) >= 3
    assert all(c.end-c.start <= 14 and len(c.text) <= 600 for c in units)
    assert sum(len(c.text.split()) for c in units) == 150
    rows = [Cue(id=0, start=0, end=4, text='We spoke with Dr. Smith,'), Cue(id=1, start=4, end=9, text='and reviewed several options,'),
            Cue(id=2, start=9, end=12, text='before choosing a plan.')]
    units = speech_units(rows)
    assert units[0].text.endswith(',') and 'Dr. Smith' in units[0].text


def test_dense_punctuation_in_short_cue_never_inverts_timestamps():
    rows = [Cue(id=0, start=1, end=1.1, text='Hello. '*40)]
    units = speech_units(rows)
    assert all(1 <= c.start < c.end <= 1.1 for c in units)
    assert ' '.join(c.text for c in units).split() == rows[0].text.split()


@pytest.mark.parametrize('position', [-1, float('nan'), float('inf'), 14401])
def test_progressive_position_validation(position):
    with pytest.raises(ValueError):
        VideoRequest(url='https://example.org/video', progressive=True, position=position)
    with pytest.raises(ValueError):
        WindowRequest(video_job_id='a'*32, position=position)


def test_prepare_translates_one_unit_then_seek_windows_reuse_cache_and_keep_ticket_scope(tmp_path):
    async def run():
        app = build(Settings(data_dir=tmp_path, master_key=secrets.token_hex(32), admin_token=secrets.token_hex(32), reserve_free_bytes=0, disk_high_water=.94))
        jobs, security, db = app.state.jobs, app.state.security, app.state.db
        owner = security.create_ticket('owner', 3600)
        security.activate(owner['code'])
        rows = [Cue(id=i, start=i*4, end=i*4+3, text=f'Sentence number {i}.') for i in range(120)]
        called = []
        async def llm(selection, instruction, payload, **kwargs):
            assert 'commas' in instruction and payload['speech_budget_seconds']
            called.extend(payload['requested_ids'])
            return {'items': [{'id': c['id'], 'text': 'Natural complete sentence.'} for c in payload['items']]}
        jobs.providers.llm = llm
        def start(kind, payload, identity):
            result = jobs.submit(owner['id'], kind, payload, identity)
            db.execute("UPDATE jobs SET state='running' WHERE id=?", (result['id'],))
            return db.one('SELECT * FROM jobs WHERE id=?', (result['id'],))
        try:
            payload = {'url': 'https://example.org/progressive', 'progressive': True, 'position': 4,
                       'source_language': 'en', 'cues': [c.model_dump() for c in rows]}
            job = start('video', payload, 'progressive-prepare')
            result = await jobs.video(job, payload)
            assert called == [1] and len(result['cues']) == 120
            assert sum(bool(c['translated']) for c in result['cues']) == 1
            import json
            db.execute("UPDATE jobs SET state='done',result=? WHERE id=?", (json.dumps(result), job['id']))
            seek = {'video_job_id': job['id'], 'position': 240, 'count': 3}
            window = start('window', seek, 'progressive-window')
            translated = await jobs.window(window, seek)
            assert [c['id'] for c in translated['cues']] == [60, 61, 62]
            assert called == [1, 60, 61, 62]
            await jobs.window(window, seek)
            assert called == [1, 60, 61, 62]
            bypass = {**payload, 'already_translated': True}
            bypass_job = start('video', bypass, 'progressive-bypass')
            bypass_result = await jobs.video(bypass_job, bypass)
            assert bypass_result['translation_id'] != result['translation_id']
            assert bypass_result['cues'][1]['translated'] == rows[1].text
            assert called == [1, 60, 61, 62]
            other = security.create_ticket('other', 3600)
            security.activate(other['code'])
            with pytest.raises(ValueError, match='Prepared video not found'):
                await jobs.window({**window, 'ticket_id': other['id']}, seek)
            assert all(row['bytes'] < 5000 for row in db.all("SELECT bytes FROM cache WHERE key LIKE 'speech:%'"))
        finally:
            await jobs.close()
    asyncio.run(run())
