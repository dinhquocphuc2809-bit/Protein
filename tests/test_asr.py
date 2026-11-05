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


def test_long_operation_cancellation_is_propagated_and_locks_renew(tmp_path):
    import time
    from backend.jobs import JobCancelled
    app, ticket = setup(tmp_path)
    jobs, db = app.state.jobs, app.state.db
    async def run():
        submitted = jobs.submit(ticket['id'], 'video', {}, secrets.token_hex(16))
        db.execute("UPDATE jobs SET state='running' WHERE id=?", (submitted['id'],))
        row = db.one('SELECT * FROM jobs WHERE id=?', (submitted['id'],))
        db.execute('INSERT INTO cache_locks VALUES(?,?,?)', ('long-source', row['id'], time.time()+1))
        await jobs.progress(row, 'aligning')
        assert db.one('SELECT expires FROM cache_locks')['expires'] > time.time()+1700
        cancelled = asyncio.Event()
        started = asyncio.Event()
        async def remote():
            started.set()
            try:
                await asyncio.Event().wait()
            finally:
                cancelled.set()
        task = asyncio.create_task(jobs.leased(row, 'aligning', remote()))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cancelled.is_set()
        db.execute("UPDATE jobs SET state='cancelled' WHERE id=?", (row['id'],))
        async def finished():
            return []
        with pytest.raises(JobCancelled):
            await jobs.leased(row, 'aligning', finished())
        await jobs.close()
    asyncio.run(run())


def test_qwen_terminology_and_translations_reused_on_retry_and_seek(tmp_path, monkeypatch):
    app, ticket = setup(tmp_path)
    jobs, db = app.state.jobs, app.state.db
    calls = {'asr':0, 'plan':0, 'translation':0}
    async def acquire(job, request):
        calls['asr'] += 1
        return [Cue(id=0,start=0,end=3,text='Daya arrives.'), Cue(id=1,start=20,end=23,text='Deya leaves.')]
    async def plan(*args):
        calls['plan'] += 1
        return {'version':2,'terms':[{'kind':'name','canonical':'Daya','aliases':['Deya'],
            'translation':'Daya','evidence_ids':[0,1],'confidence':'high'}]}
    async def llm(selection, instruction, payload, **kwargs):
        calls['translation'] += 1
        assert payload['video_terminology'][0]['canonical'] == 'Daya'
        return {'items':[{'id':i,'text':'Daya.'} for i in payload['requested_ids']]}
    monkeypatch.setattr(jobs,'acquire',acquire)
    monkeypatch.setattr(jobs.providers,'terminology',plan)
    monkeypatch.setattr(jobs.providers,'llm',llm)
    async def run():
        payload={'url':'https://example.org/cache-test','asr':'quality','source_language':'en','target_language':'vi','progressive':True}
        try:
            for _ in range(2):
                job=jobs.submit(ticket['id'],'video',payload,secrets.token_hex(16))
                db.execute("UPDATE jobs SET state='running' WHERE id=?",(job['id'],))
                row=db.one('SELECT * FROM jobs WHERE id=?',(job['id'],))
                result=await jobs.video(row,payload)
                assert result['source_repairs'] and result['cues'][1]['text']=='Daya leaves.'
                for position in [20,0,20]:
                    await jobs.translate_window(row,result,position,1)
                db.execute("UPDATE jobs SET state='done' WHERE id=?",(job['id'],))
            assert calls=={'asr':1,'plan':1,'translation':2}
        finally:
            await jobs.close()
    asyncio.run(run())


def test_modal_capacity_timeout_rotates_account_without_marking_depleted(tmp_path):
    from backend.providers import ProviderFailure
    app, _ = setup(tmp_path)
    pool = app.state.jobs.providers.pool
    pool.preflight = None
    pool.add('modal','fixture-account-one-0000','one')
    pool.add('modal','fixture-account-two-0000','two')
    calls, affinity = [], {}
    async def operation(key):
        calls.append(key)
        if len(calls) == 1:
            raise ProviderFailure('modal',503,'cooling_down',retry_after=60)
        return 'completed'
    async def run():
        try:
            assert await pool.run('modal',operation,affinity=affinity) == 'completed'
            assert len(set(calls)) == 2 and affinity['modal']
            assert {r['state'] for r in pool.db.all('SELECT state FROM api_keys')} == {'cooling_down','available'}
        finally:
            await app.state.jobs.close()
    asyncio.run(run())
