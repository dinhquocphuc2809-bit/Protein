import asyncio

from backend.subtitles import Cue
from backend.terminology import apply_plan, validate_plan, plausible_spelling
from backend.providers import Providers


def sample():
    return [Cue(id=0, start=0, end=2, text='Daya greets Deya.'),
            Cue(id=1, start=2, end=4, text='Deya belongs to the elephant herd.'),
            Cue(id=2, start=4, end=6, text='Today Deya left.')]


def term(**kwargs):
    return dict({'kind': 'name', 'canonical': 'Daya', 'translation': 'Daya', 'aliases': ['Deya'],
                 'evidence_ids': [0, 1], 'confidence': 'high'}, **kwargs)


def test_name_plan_preserves_times_and_audits_edits():
    cues = sample()
    plan = validate_plan({'terms': [term()]}, cues)
    output, edits = apply_plan(cues, plan)
    assert all('Deya' not in c.text for c in output)
    assert len(edits) == 3
    assert [(c.id, c.start, c.end) for c in output] == [(c.id, c.start, c.end) for c in cues]
    assert 'Deya' in cues[0].text


def test_uncertain_unattested_names_or_foreign_evidence_are_not_applied():
    for change in [{'confidence': 'low'}, {'canonical': 'Invented'}, {'evidence_ids': [0, 99]},
                   {'aliases': ['absent']}, {'evidence_ids': [0]}, {'canonical': '<b>Daya</b>'}]:
        assert not validate_plan({'terms': [term(**change)]}, sample())['terms']


def test_asr_repairs_scoped_to_cited_cues_not_global_replacement():
    plan = validate_plan({'terms': [term(kind='asr')]}, sample())
    output, edits = apply_plan(sample(), plan)
    assert 'Deya' in output[2].text and len(edits) == 2


def test_translation_receives_immutable_plan_when_seeking():
    plan = validate_plan({'terms': [term()]}, sample())
    payloads = []
    async def llm(selection, instruction, payload, **kwargs):
        payloads.append(payload)
        assert 'homophone' in instruction
        return {'items': [{'id': c['id'], 'text': 'Daya.'} for c in payload['items']]}
    async def progress(stage):
        pass
    provider = object.__new__(Providers)
    provider.llm = llm
    for index in [2, 0, 1]:
        asyncio.run(provider.translate([sample()[index]], 'en', 'vi', 'basic', '', progress, terminology=plan))
    assert all(p['video_terminology'] == plan['terms'] for p in payloads)


def test_homophone_guard_rejects_species_substitution_and_modifier_loss():
    assert plausible_spelling('\u5c01\u4faf', '\u8702\u7334')
    assert plausible_spelling('\u5934\u9e1f', '\u5934\u725b')
    assert not plausible_spelling('\u5c01\u4faf', '\u957f\u81c2\u733f')
    assert not plausible_spelling('\u96cc\u7389', '\u53cd\u5634\u9e6c')


def test_missing_required_name_is_repaired_instead_of_silently_accepted():
    calls = []
    async def llm(selection, instruction, payload, **kwargs):
        calls.append(payload)
        return {'items': [{'id': 0, 'text': 'Deya.' if len(calls) == 1 else 'Daya.'}]}
    async def progress(stage):
        pass
    provider = object.__new__(Providers)
    provider.llm = llm
    plan = validate_plan({'terms': [term()]}, sample())
    result = asyncio.run(provider.translate([sample()[0]], 'en', 'vi', 'basic', '', progress, terminology=plan))
    assert result[0].translated == 'Daya.' and len(calls) == 2


def test_many_valid_evidence_citations_do_not_drop_an_important_name():
    cues = [Cue(id=i, start=i*2, end=i*2+1, text='Daya and Deya.') for i in range(25)]
    assert validate_plan({'terms': [term(evidence_ids=list(range(25)))]}, cues)['terms']


def test_only_disputed_basic_cue_uses_advanced_model():
    selections = []
    async def llm(selection, instruction, payload, **kwargs):
        selections.append((selection, kwargs.get('thinking_level')))
        return {'items': [{'id': c['id'], 'text': 'Translation.'} for c in payload['items']]}
    async def progress(stage):
        pass
    provider = object.__new__(Providers)
    provider.llm = llm
    plan = validate_plan({'terms': [term(kind='asr')]}, sample())
    asyncio.run(provider.translate([sample()[0]], 'en', 'vi', 'basic', '', progress, terminology=plan))
    asyncio.run(provider.translate([sample()[0]], 'en', 'vi', 'basic', '', progress))
    assert selections == [('advanced','LOW'), ('basic',None)]


def test_numbers_and_negation_are_not_spelling_repairs():
    assert not plausible_spelling('24 birds', '25 birds')
    assert not plausible_spelling('not ready', 'now ready')
