import asyncio
import json
import secrets

import httpx
import pytest

from backend.config import Settings
from backend.app import build
from backend.database import Database
from backend.providers import KeyPool, ProviderFailure, Providers
from backend.security import Security
from backend.subtitles import Cue


def cues(count=12):
    return [Cue(id=100+i*2, start=i*3, end=i*3+2, text=f"Sentence {i}.") for i in range(count)]


async def progress(stage):
    assert stage == "translating"


def instance(call):
    provider = object.__new__(Providers)
    provider.llm = call
    return provider


def test_reordered_partial_response_only_repairs_missing_ids():
    requested = []
    async def llm(selection, instruction, payload, **kwargs):
        assert kwargs['schema']['properties']['items']['items']['properties']['id']['type'] == 'integer'
        ids = payload['requested_ids']
        requested.append(ids)
        if len(requested) == 1:
            ids = ids[:-2]
        return {'items': [{'id': identity, 'text': f'Translation {identity}'} for identity in reversed(ids)]}
    original = cues()
    result = asyncio.run(instance(llm).translate(original, 'en', 'vi', 'basic', 'test', progress))
    assert requested[1] == [original[-2].id, original[-1].id]
    assert [(c.id, c.start, c.end, c.text) for c in result] == [(c.id, c.start, c.end, c.text) for c in original]
    assert all(c.translated == f'Translation {c.id}' for c in result)


def test_invalid_duplicate_and_foreign_ids_never_replace_source_ids():
    rows = {'items': [{'id': 100, 'text': 'First'}, {'id': 100, 'text': 'Conflict'},
                     {'id': '102', 'text': 'Wrong type'}, {'id': True, 'text': 'Boolean'},
                     {'id': 999, 'text': 'Foreign'}, {'id': 104, 'text': '<b></b>'},
                     {'id': 106, 'text': 'x'*8001}, {'id': 108, 'text': 'Valid'}]}
    assert Providers.translation_items(rows, cues()) == {108: 'Valid'}


def test_split_recovers_repeated_malformed_batch_responses():
    sizes = []
    async def llm(selection, instruction, payload, **kwargs):
        sizes.append(len(payload['items']))
        if len(payload['items']) > 3:
            raise ProviderFailure('gemini', 502, 'invalid_json')
        return {'items': [{'id': item['id'], 'text': 'Translated'} for item in payload['items']]}
    result = asyncio.run(instance(llm).translate(cues(), 'en', 'vi', 'basic', 'test', progress))
    assert len(result) == 12 and sizes == [12, 12, 6, 6, 3, 3, 6, 6, 3, 3]


def test_unrecoverable_translation_has_bounded_retries_and_no_fake_success():
    calls = []
    async def llm(*args, **kwargs):
        calls.append(1)
        return {'items': []}
    with pytest.raises(ProviderFailure, match='incomplete_cue_coverage'):
        asyncio.run(instance(llm).translate(cues(), 'en', 'vi', 'basic', 'test', progress))
    assert len(calls) <= 10


def test_partial_checkpoint_survives_failure_and_reuses_valid_translations():
    cache, requested = {}, []
    async def failing(selection, instruction, payload, **kwargs):
        if not cache:
            return {'items': [{'id': payload['items'][0]['id'], 'text': 'Saved translation'}]}
        raise ProviderFailure('gemini', 503, 'network_unavailable')
    def save(batch, value):
        cache[batch[0].id] = value
    def load(batch):
        return cache.get(batch[0].id)
    with pytest.raises(ProviderFailure):
        asyncio.run(instance(failing).translate(cues(3), 'en', 'vi', 'basic', 'test', progress, load_batch=load, save_batch=save))
    async def recovery(selection, instruction, payload, **kwargs):
        requested.extend(payload['requested_ids'])
        return {'items': [{'id': item['id'], 'text': 'Recovered'} for item in payload['items']]}
    result = asyncio.run(instance(recovery).translate(cues(3), 'en', 'vi', 'basic', 'test', progress, load_batch=load, save_batch=save))
    assert requested == [102, 104] and result[0].translated == 'Saved translation'


def test_job_retry_uses_ticket_scoped_persistent_translation_checkpoint(tmp_path):
    async def run():
        settings = Settings(data_dir=tmp_path, master_key=secrets.token_hex(32), admin_token=secrets.token_hex(32),
                            reserve_free_bytes=0, disk_high_water=.94)
        app = build(settings)
        jobs, security, db = app.state.jobs, app.state.security, app.state.db
        ticket = security.create_ticket('recovery', 3600)
        security.activate(ticket['code'])
        payload = {'url': 'https://example.org/translation-recovery', 'source_language': 'en',
                   'cues': [c.model_dump() for c in cues(3)]}
        requested = []
        async def llm(selection, instruction, data, **kwargs):
            requested.append(data['requested_ids'])
            if len(requested) == 1:
                return {'items': [{'id': 100, 'text': 'Saved'}]}
            if len(requested) == 2:
                raise ProviderFailure('gemini', 503, 'network_unavailable')
            return {'items': [{'id': item['id'], 'text': 'Recovered'} for item in data['items']]}
        jobs.providers.llm = llm
        def job(identity):
            submitted = jobs.submit(ticket['id'], 'video', payload, identity)
            db.execute("UPDATE jobs SET state='running' WHERE id=?", (submitted['id'],))
            return db.one('SELECT * FROM jobs WHERE id=?', (submitted['id'],))
        try:
            first = job('translation-attempt-1')
            with pytest.raises(ProviderFailure):
                await jobs.video(first, payload)
            db.execute("UPDATE jobs SET state='failed' WHERE id=?", (first['id'],))
            second = job('translation-attempt-2')
            result = await jobs.video(second, payload)
            assert requested[-1] == [102, 104] and result['cues'][0]['translated'] == 'Saved'
            cached = await jobs.video(second, payload)
            assert cached == result and len(requested) == 3
            rows = db.all("SELECT key FROM cache WHERE kind='translation_batch'")
            assert rows and all(ticket['id'] in row['key'] for row in rows)
        finally:
            await jobs.close()
    asyncio.run(run())


def test_large_cues_are_batched_by_text_size_and_cancellation_stops_calls():
    sizes = []
    async def llm(selection, instruction, payload, **kwargs):
        sizes.append(sum(len(item['text']) for item in payload['items']))
        return {'items': [{'id': item['id'], 'text': 'Translated'} for item in payload['items']]}
    original = [c.model_copy(update={'text': 'word '*700}) for c in cues(3)]
    asyncio.run(instance(llm).translate(original, 'en', 'vi', 'basic', 'test', progress))
    assert sizes == [3500]*3
    async def cancel(stage):
        raise asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(instance(llm).translate(cues(), 'en', 'vi', 'basic', 'test', cancel))
    assert sizes == [3500]*3


@pytest.mark.parametrize('selection', ['basic', 'deepseek'])
def test_malformed_model_json_does_not_cool_down_healthy_credential(tmp_path, selection):
    async def run():
        settings = Settings(data_dir=tmp_path, master_key=secrets.token_hex(32), admin_token=secrets.token_hex(32))
        db = Database(tmp_path / 'test.sqlite3')
        pool = KeyPool(db, Security(db, settings))
        provider_name = 'deepseek' if selection == 'deepseek' else 'gemini'
        pool.add(provider_name, 'fixture-key-00000000')
        provider = Providers(pool, settings)
        pool.preflight = None
        await provider.http.aclose()
        calls = []
        def respond(request):
            calls.append(json.loads(request.content))
            text = '{bad' if len(calls) == 1 else '{"items":[{"id":100,"text":"Valid"}]}'
            body = {'choices': [{'message': {'content': text}, 'finish_reason': 'stop'}]} if selection == 'deepseek' else {
                'candidates': [{'content': {'parts': [{'text': text}]}, 'finishReason': 'STOP'}]}
            return httpx.Response(200, json=body)
        provider.http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        try:
            result = await provider.translate(cues(1), 'en', 'vi', selection, 'test', progress)
            assert result[0].translated == 'Valid'
            row = db.one('SELECT state,calls FROM api_keys')
            assert row == {'state': 'available', 'calls': 2}
            if selection == 'basic':
                assert 'responseJsonSchema' in calls[0]['generationConfig']
        finally:
            await provider.close()
    asyncio.run(run())
