"""Inspect only our synthetic summary input/output; no provider credentials in logs."""
import json
from pathlib import Path
import httpx

ROOT = Path(__file__).resolve().parents[1]
key = (ROOT.parent / 'api-key-gemini.txt').read_text(encoding='utf-8-sig').strip()
instruction = 'Summarize this video in Vietnamese. Return JSON {"sections":[{"start":0,"title":"...","text":"..."}]}. Use only supplied timestamps and at least one section.'
schema = {'type': 'object', 'required': ['sections'], 'properties': {'sections': {'type': 'array', 'items': {'type': 'object', 'required': ['start', 'title', 'text'], 'properties': {'start': {'type': 'number'}, 'title': {'type': 'string'}, 'text': {'type': 'string'}}}}}}
payload = {'systemInstruction': {'parts': [{'text': instruction}]}, 'contents': [{'role': 'user', 'parts': [{'text': json.dumps({'title': 'Caching explained', 'transcript': [{'start': 0, 'text': 'A cache stores results for reuse.'}]})}]}], 'generationConfig': {'temperature': .2, 'maxOutputTokens': 8192, 'responseMimeType': 'application/json'}}
schema['properties']['sections'].update(minItems=1, maxItems=100)
for mode in ['none', 'responseJsonSchema', 'responseSchema']:
    body = json.loads(json.dumps(payload))
    if mode != 'none':
        body['generationConfig'][mode] = schema
    response = httpx.post('https://generativelanguage.googleapis.com/v1beta/models/gemini-3.5-flash-lite:generateContent', headers={'x-goog-api-key': key}, json=body, timeout=90)
    result = response.json()
    (ROOT / '.private' / ('summary-'+mode+'.json')).write_text(json.dumps(result, indent=2, ensure_ascii=True))
    print(mode, response.status_code, result.get('error', {}).get('message', '')[:700])
