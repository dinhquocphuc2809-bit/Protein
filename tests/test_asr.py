import asyncio
import secrets

import pytest

from backend.app import build
from backend.config import Settings
from backend.jobs import VideoRequest
from backend.subtitles import Cue


def setup(tmp_path):
    app = build(Settings(data_dir=tmp_path, master_key=secrets.token_hex(32),
                         admin_token=secrets.token_hex(32), reserve_free_bytes=0, disk_high_water=.94))
    ticket = app.state.security.create_ticket('ASR regression', 3600)
    app.state.security.activate(ticket['code'])
    return app, ticket


@pytest.mark.parametrize('mode,failed', [('fast', False), ('quality', False), ('quality', True)])
def test_asr_routing_never_substitutes_deepgram_for_qwen(tmp_path, monkeypatch, mode, failed):
    import backend.jobs as module
    app, ticket = setup(tmp_path)
    jobs, db = app.state.jobs, app.state.db
    calls = []
    async def resolve(url):
        return 'https://media.example.test/audio'
    async def download(*args):
        calls.append('download')
    async def deepgram(**kwargs):
        calls.append('deepgram')
        assert kwargs['url'] == 'https://media.example.test/audio'
        return [Cue(id=0, start=0, end=1, text='Deepgram output.')]
    async def qwen(*args):
        calls.append('qwen')
        if failed:
            raise ValueError('Invalid model alignment')
        return [Cue(id=0, start=0, end=1, text='Qwen output.')]
    monkeypatch.setattr(module, 'public_addresses', lambda url: ['203.0.113.1'])
    monkeypatch.setattr(module, 'download_owned', download)
    monkeypatch.setattr(jobs.providers, 'tunelio', resolve)
    monkeypatch.setattr(jobs.providers, 'deepgram', deepgram)
    monkeypatch.setattr(jobs, 'modal_asr', qwen)
    async def run():
        job = jobs.submit(ticket['id'], 'video', {}, secrets.token_hex(16))
        db.execute("UPDATE jobs SET state='running' WHERE id=?", (job['id'],))
        row = db.one('SELECT * FROM jobs WHERE id=?', (job['id'],))
        try:
            request = VideoRequest(url='https://www.youtube.com/watch?v=f6YA_OvKbhY', asr=mode)
            if failed:
                with pytest.raises(ValueError, match='Invalid model alignment'):
                    await jobs.acquire(row, request)
            else:
                assert await jobs.acquire(row, request)
            assert calls == (['deepgram'] if mode == 'fast' else ['download', 'qwen'])
            events = db.all('SELECT provider,event FROM usage WHERE job_id=?', (job['id'],))
            assert any(e['event'] == ('nova3_started' if mode == 'fast' else 'qwen3_asr_1_7b_started') for e in events)
            if mode == 'quality':
                assert all(e['provider'] != 'deepgram' for e in events)
        finally:
            await jobs.close()
    asyncio.run(run())


def test_source_cache_is_separate_for_qwen_and_deepgram(tmp_path, monkeypatch):
    app, ticket = setup(tmp_path)
    jobs, db = app.state.jobs, app.state.db
    calls = []
    async def acquire(job, request):
        calls.append(request.asr)
        return [Cue(id=0, start=0, end=2, text=request.asr + ' output.')]
    monkeypatch.setattr(jobs, 'acquire', acquire)
    async def run():
        try:
            for mode in ['fast', 'quality', 'quality', 'fast']:
                payload = {'url': 'https://www.youtube.com/watch?v=f6YA_OvKbhY', 'asr': mode,
                           'source_language': 'en', 'target_language': 'en'}
                job = jobs.submit(ticket['id'], 'video', payload, secrets.token_hex(16))
                db.execute("UPDATE jobs SET state='running' WHERE id=?", (job['id'],))
                row = db.one('SELECT * FROM jobs WHERE id=?', (job['id'],))
                result = await jobs.video(row, payload)
                assert result['cues'][0]['text'] == mode + ' output.'
                db.execute("UPDATE jobs SET state='done' WHERE id=?", (job['id'],))
            assert calls == ['fast', 'quality']
        finally:
            await jobs.close()
    asyncio.run(run())
