"""Read sanitized production usage for the ASR incident and its live reruns."""
import base64
import argparse
import json
from pathlib import Path
import re

from vps import execute

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', default='qwen-incident-live.json')
    parser.add_argument('--report', default='qwen-incident-production-evidence.json')
    args = parser.parse_args()
    for name in [args.live, args.report]:
        if Path(name).name != name or not name.endswith('.json'):
            parser.error('Expected JSON basenames')
    ids = ['775e708607b9752be9700d69c4d02691', 'cc32892f6cd7fe0c44f51964145bbf8c'] if args.live == 'qwen-incident-live.json' else []
    live = ROOT/'research'/args.live
    if live.exists():
        ids.extend(row['job_id'] for row in json.loads(live.read_text())['checks'])
    if not all(re.fullmatch('[a-f0-9]{32}', value) for value in ids):
        raise ValueError('Invalid job ID')
    code = 'ids=' + repr(ids) + '\n' + '''import json,sqlite3,os,shutil,time,wave
c=sqlite3.connect('file:/var/lib/auvirel/auvirel.sqlite3?mode=ro',uri=True);c.row_factory=sqlite3.Row
rows=[]
for job_id in ids:
 r=c.execute('SELECT id,state,stage,error,created,updated FROM jobs WHERE id=?',(job_id,)).fetchone()
 if not r: continue
 d=dict(r);d['events']=[dict(e) for e in c.execute('SELECT provider,event,amount,created FROM usage WHERE job_id=? ORDER BY created',(job_id,))]
 audio='/var/lib/auvirel/spool/'+job_id+'/normalized.wav'
 try:
  with wave.open(audio) as w: d['normalized_audio_seconds']=w.getnframes()/w.getframerate()
 except (FileNotFoundError,EOFError,wave.Error): pass
 rows.append(d)
print(json.dumps({'at_epoch':time.time(),'release':os.path.realpath('/opt/auvirel/current'),'jobs':rows,
 'modal_accounts':[dict(r) for r in c.execute("SELECT label,state,calls FROM api_keys WHERE provider='modal' ORDER BY label")],
 'spool_bytes':sum(os.path.getsize(os.path.join(p,n)) for p,ds,fs in os.walk('/var/lib/auvirel/spool') for n in fs),
 'free_bytes':shutil.disk_usage('/var/lib/auvirel').free}))
'''
    result = execute('printf %s '+base64.b64encode(code.encode()).decode() +
                     ' | base64 -d | sudo python3 -', capture=True)
    if result.returncode:
        raise RuntimeError('Production evidence query failed')
    report = json.loads(result.stdout)
    (ROOT/'research'/args.report).write_text(json.dumps(report, indent=2)+'\n')
    for job in report['jobs']:
        print(json.dumps({'id':job['id'], 'state':job['state'], 'stage':job['stage'],
                          'chunks':sum(e['event']=='qwen_chunk_completed' for e in job['events']),
                          'providers':sorted({e['provider'] for e in job['events']})}))


if __name__ == '__main__':
    main()
