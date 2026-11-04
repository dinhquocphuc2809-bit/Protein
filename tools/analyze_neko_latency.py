"""Aggregate the supplied HAR without exporting transcripts, credentials or audio."""
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def stats(values):
    values=sorted(values)
    if not values:return None
    def percentile(p):
        index=(len(values)-1)*p;low=int(index);high=min(low+1,len(values)-1)
        return round(values[low]+(values[high]-values[low])*(index-low),3)
    return {'min':round(values[0],3),'p50':percentile(.5),'p95':percentile(.95),'max':round(values[-1],3)}


def main():
    entries=json.loads((ROOT.parent/'nekodub.har').read_text(encoding='utf8'))['log']['entries']
    paths=['/api/tts/batch','/api/set-ref-audio','/v1/translate/ai','/v1/transcript','/v1/punctuate/repair']
    report={'source':'Owner-provided nekodub.har','entries':len(entries),
            'scope':'One recorded session; overlap is HTTP requests, not proven GPU parallelism; no seek labels inferred',
            'endpoints':{},'websocket_messages':sum(len(e.get('_webSocketMessages',[])) for e in entries)}
    for path in paths:
        group=[e for e in entries if urlsplit(e['request']['url']).path==path and e['request']['method']=='POST']
        payloads=[]
        for e in group:
            try:payloads.append(json.loads(e['request'].get('postData',{}).get('text','')))
            except (ValueError,TypeError):pass
        events=[]
        for e in group:
            start=datetime.fromisoformat(e['startedDateTime'].replace('Z','+00:00')).timestamp()
            events.extend([(start,1),(start+e['time']/1000,-1)])
        active=peak=0
        for _,change in sorted(events):active+=change;peak=max(peak,active)
        fields=sorted({k for p in payloads if isinstance(p,dict) for k in p})
        result={'count':len(group),'statuses':dict(Counter(e['response']['status'] for e in group)),
                'duration_ms':stats([e['time'] for e in group]),'request_body_bytes':stats([len(e['request'].get('postData',{}).get('text','').encode()) for e in group]),
                'timings_ms':{k:stats([e['timings'][k] for e in group if e.get('timings',{}).get(k,-1)>=0]) for k in ['blocked','dns','connect','send','wait','receive']},
                'json_fields':fields,'peak_overlapping_requests':peak}
        if path=='/api/tts/batch':
            result['items_per_request']=dict(Counter(len(p.get('items',[])) for p in payloads))
            result['diffusion_steps']=dict(Counter(str(p.get('num_step')) for p in payloads))
            result['inline_reference_requests']=sum('ref_audio' in p or 'reference' in p for p in payloads)
            result['uses_voice_id']=sum('voice_id' in p or any('voice_id' in i for i in p.get('items',[])) for p in payloads)
            fingerprints=Counter(hashlib.sha256(json.dumps(p,sort_keys=True).encode()).hexdigest() for p in payloads)
            result['repeated_identical_payloads']=sum(count-1 for count in fingerprints.values())
            durations=[]
            for e in group:
                try:
                    response=json.loads(e['response']['content'].get('text',''))
                    for row in response.get('data',[]):
                        if isinstance(row.get('elapsedMs'),(int,float)):durations.append(row['elapsedMs'])
                except (ValueError,TypeError):pass
            result['server_reported_elapsed_ms']=stats(durations)
        if path=='/v1/translate/ai':
            result['items_per_request']=dict(Counter(len(p.get('items',[])) for p in payloads))
            result['context_items']=stats([len(p.get('contextBefore',[])) for p in payloads])
            result['summary_present']=sum(bool(p.get('videoSummary')) for p in payloads)
            result['punctuation_requested']=sum(p.get('normalizePunctuation') is True for p in payloads)
        report['endpoints'][path]=result
    (ROOT/'research/neko-latency-analysis.json').write_text(json.dumps(report,indent=2),encoding='utf8')
    print(json.dumps(report))


if __name__=='__main__':main()
