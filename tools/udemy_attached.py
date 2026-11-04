"""Probe only the authorized Udemy lecture in an already-open Chrome session.

Connects through Chrome's user-approved DevTools endpoint. No cookie export,
profile copying, navigation, playback changes or backend/provider calls.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ['lib/captions.js', 'lib/sites.js', 'lib/media.js', 'lib/subtitle-formats.js',
           'lib/bilibili.js', 'lib/platform-captions.js', 'multisite-main.js']


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--lecture', default='9538164')
    parser.add_argument('--require-packaged', action='store_true')
    args = parser.parse_args()
    if not args.lecture.isdigit():
        parser.error('Lecture must be numeric')
    lines = (Path(os.environ['LOCALAPPDATA']) / 'Google/Chrome/User Data/DevToolsActivePort').read_text().splitlines()
    report = {'at': datetime.now(timezone.utc).isoformat(), 'scope': 'Live authorized Chrome session; source acquisition probe, not full packaged UI/translation acceptance', 'lecture': args.lecture, 'checks': []}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('ws://127.0.0.1:'+lines[0]+lines[1], timeout=45000)
        pages = [page for ctx in browser.contexts for page in ctx.pages
                 if urlsplit(page.url).hostname == 'www.udemy.com' and
                 urlsplit(page.url).path.endswith('/learn/lecture/'+args.lecture)]
        if len(pages) != 1:
            raise RuntimeError('Expected exactly one authorized lecture tab')
        page = pages[0]
        if args.require_packaged:
            session=browser.new_browser_cdp_session()
            extensions=session.send('Extensions.getExtensions').get('extensions',[])
            session.detach()
            installed=[e for e in extensions if Path(e.get('path',''))==ROOT/'dist/chrome' and e.get('enabled')]
            if len(installed)!=1:
                raise RuntimeError('Current local Vocalm package is not enabled')
            report['scope']='Live authorized Udemy session; installed local Vocalm MV3 caption acquisition; no translation, ASR or GPU requests'
            report['extension']={key:installed[0][key] for key in ['id','name','version']}
            report['package_source_sha256']=hashlib.sha256('\n;\n'.join(
                (ROOT/'dist/chrome'/name).read_text(encoding='utf-8') for name in SCRIPTS).encode()).hexdigest()
        report['before'] = page.evaluate('''()=>({bridge:!!globalThis.__veloaSiteCaptions,
          button:!!document.querySelector('.vocalm-player-button'),
          videos:[...document.querySelectorAll('video')].map(v=>({duration:v.duration,time:v.currentTime,paused:v.paused,tracks:v.textTracks.length}))})''')
        if not report['before']['bridge']:
            if args.require_packaged:
                raise RuntimeError('Installed extension acquisition bridge is missing')
            # Inject the exact repository acquisition sources into this tab only.
            sources = [(ROOT/'extension'/name).read_text(encoding='utf-8') for name in SCRIPTS]
            report['source_sha256'] = hashlib.sha256('\n;\n'.join(sources).encode()).hexdigest()
            page.evaluate('\n;\n'.join(sources))
        for label in ['initial', 'repeat']:
            started = time.monotonic()
            result = page.evaluate('''async()=>{
              const v=globalThis.VeloaMedia?.videos()[0];if(!v)return {state:'no-player'};
              const r=await __veloaSiteCaptions.acquire({href:location.href,src:VeloaMedia.source(v)});
              const cues=r.cues||[];
              const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(cues)));
              return {state:r.state,reason:r.reason,cues:cues.length,language:r.language,
                first:cues[0]?.start,last:cues.at(-1)?.end,duration:v.duration,
                hash:[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join(''),
                validTimes:cues.every(c=>Number.isFinite(c.start)&&Number.isFinite(c.end)&&c.start>=0&&c.end>c.start&&c.end<=v.duration+1),
                totalCharacters:cues.reduce((n,c)=>n+c.text.length,0)};
            }''')
            report['checks'].append({'name':label,'seconds':round(time.monotonic()-started,3),**result})
        report['passed'] = all(row['state']=='ready' and row['cues']>0 and row['validTimes'] for row in report['checks'])
        report['stable'] = bool(report['checks'][0].get('hash')) and report['checks'][0].get('hash')==report['checks'][1].get('hash')
        # Leaving Playwright disconnects; do not close the user's browser/context/page.
    (ROOT/'research/udemy-attached-live.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return 0 if report['passed'] and report['stable'] else 1


if __name__=='__main__':
    raise SystemExit(main())
