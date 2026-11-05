"""Validate a video-scoped terminology plan before applying explicit source edits."""
import re
from difflib import SequenceMatcher

from .subtitles import plain_text

VERSION = 2


def plausible_spelling(alias, canonical):
    if alias == canonical:
        return True
    if any(c.isdigit() for c in alias+canonical):
        return False
    negation = r"\b(?:no|not|never)\b|n't\b"
    if bool(re.search(negation, alias, re.I)) != bool(re.search(negation, canonical, re.I)):
        return False
    if re.fullmatch(r'[\u3400-\u9fff]+', alias+canonical):
        from pypinyin import lazy_pinyin
        if len(alias) != len(canonical):
            return False
        a, b = lazy_pinyin(alias), lazy_pinyin(canonical)
        return all(SequenceMatcher(None, x, y).ratio() >= .55 for x,y in zip(a,b)) and (
            SequenceMatcher(None, ' '.join(a), ' '.join(b)).ratio() >= .8)
    return SequenceMatcher(None, alias.casefold(), canonical.casefold()).ratio() >= .75


def evidence_sample(cues, limit=90000):
    total = sum(len(c.text) for c in cues)
    stride = max(1, (total+limit-1)//limit)
    rows, size = [], 0
    for cue in cues[::stride]:
        if size+len(cue.text) > limit:
            break
        rows.append({'id': cue.id, 'text': cue.text})
        size += len(cue.text)
    return rows


def validate_plan(value, cues):
    if not isinstance(value, dict) or not isinstance(value.get('terms'), list) or len(value['terms']) > 64:
        raise ValueError('Invalid video terminology plan')
    by_id = {c.id: c.text for c in cues}
    terms, aliases_used = [], set()
    for term in value['terms']:
        if not isinstance(term, dict) or term.get('confidence') != 'high' or term.get('kind') not in ('name', 'asr'):
            continue
        canonical, target = term.get('canonical'), term.get('translation')
        aliases, evidence = term.get('aliases'), term.get('evidence_ids')
        if (not isinstance(canonical, str) or not 2 <= len(canonical) <= 80
                or not isinstance(target, str) or not 1 <= len(target) <= 120
                or not isinstance(aliases, list) or not 1 <= len(aliases) <= 6
                or not isinstance(evidence, list) or not 2 <= len(set(e for e in evidence if type(e) is int)) <= 128):
            continue
        if any(type(e) is not int or e not in by_id for e in evidence):
            continue
        if canonical != plain_text(canonical) or target != plain_text(target):
            continue
        valid = [a for a in aliases if isinstance(a, str) and 2 <= len(a) <= 80 and a == plain_text(a)
                 and any(a in text for text in (by_id.values() if term['kind'] == 'name' else (by_id[e] for e in evidence)))
                 and plausible_spelling(a, canonical)]
        if not valid or any(a in aliases_used for a in valid):
            continue
        # Proper names must use a spelling already present in this video's evidence.
        # Homophone repairs may introduce a new spelling, but remain visibly audited.
        if term['kind'] == 'name' and not any(canonical in by_id[e] for e in evidence):
            continue
        aliases_used.update(valid)
        terms.append({'kind': term['kind'], 'aliases': valid, 'canonical': canonical,
                      'translation': target, 'evidence_ids': sorted(set(evidence)), 'confidence': 'high'})
    return {'version': VERSION, 'terms': terms}


def apply_plan(cues, plan):
    replacements = {}
    for term in plan.get('terms', []):
        for alias in term['aliases']:
            if alias != term['canonical']:
                replacements[alias] = term
    if not replacements:
        return cues, []
    # One simultaneous pass prevents chained or cyclic alias replacements.
    pattern = re.compile('|'.join(re.escape(a) for a in sorted(replacements, key=len, reverse=True)))
    output, edits = [], []
    for cue in cues:
        def replace(match):
            alias = match.group()
            term = replacements[alias]
            if term['kind'] == 'asr' and cue.id not in term['evidence_ids']:
                return alias
            if alias.isascii() and ((match.start() and cue.text[match.start()-1].isalnum())
                                    or (match.end() < len(cue.text) and cue.text[match.end()].isalnum())):
                return alias
            edits.append({'cue_id': cue.id, 'original': alias, 'replacement': term['canonical'], 'kind': term['kind']})
            return term['canonical']
        text = pattern.sub(replace, cue.text)
        output.append(cue.model_copy(update={'text': text}))
    return output, edits


def required_names(text, plan):
    result = []
    for term in (plan or {}).get('terms', []):
        if term['kind'] != 'name':
            continue
        for alias in set([term['canonical'], *term['aliases']]):
            pattern = r'(?<!\w)'+re.escape(alias)+r'(?!\w)' if alias.isascii() else re.escape(alias)
            if re.search(pattern, text):
                result.append(term['translation'])
                break
    return result
