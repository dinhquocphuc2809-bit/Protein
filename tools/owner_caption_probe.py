"""Probe owner-supplied course URLs in the authorized Chrome session.

Uses new tabs only, closes only those tabs; no cookie export or paid operations.
Source probe is labelled separately from packaged-extension live acceptance.
"""
import json
import os
from pathlib import Path
from datetime import datetime, timezone
from playwright.sync_api import sync_playwright
from udemy_attached import SCRIPTS

ROOT=Path(__file__).resolve().parents[1]
URLS=[
    'https://www.skillshare.com/en/classes/how-to-draw-a-beginners-guide-part-1-of-the-drawing-laboratory/1607370408',
    'https://platzi.com/cursos/computacion-basica/computacion-basica-para-principiantes-en/',
    'https://www.skool.com/claudecodeclub/about',
]

def main():
    report={'at':datetime.now(timezone.utc).isoformat(),'scope':'Authorized owner Chrome session, new tabs only; caption source probe; no ASR or GPU calls','pages':[]}
    try:
        port=(Path(os.environ['LOCALAPPDATA'])/'Google/Chrome/User Data/DevToolsActivePort').read_text().splitlines()
        with sync_playwright() as p:
            browser=p.chromium.connect_over_cdp('ws://127.0.0.1:'+port[0]+port[1],timeout=20000)
            context=browser.contexts[0]
            for url in URLS:
                page=context.new_page()
                row={'url':url};report['pages'].append(row)
                try:
                    response=page.goto(url,wait_until='domcontentloaded',timeout=25000)
                    row['http_status']=response.status if response else None
                    page.wait_for_timeout(5000)
                    row['frames']=[]
                    for frame in page.frames:
                        from urllib.parse import urlsplit
                        host=urlsplit(frame.url).hostname or ''
                        if host not in ['www.skillshare.com','platzi.com','www.skool.com','www.loom.com']:
                            continue
                        loaded=frame.evaluate('()=>!!globalThis.__veloaSiteCaptions')
                        if not loaded:
                            for script in SCRIPTS:
                                frame.evaluate((ROOT/'extension'/script).read_text(encoding='utf-8'))
                        result=frame.evaluate('''async()=>{
                          const video=VeloaMedia.videos()[0];if(!video)return {host:location.hostname,state:'no-player'};
                          const r=await __veloaSiteCaptions.acquire({href:location.href,src:VeloaMedia.source(video)});
                          return {host:location.hostname,state:r.state,reason:r.reason,cues:r.cues?.length,language:r.language,
                            first:r.cues?.[0]?.start,last:r.cues?.at(-1)?.end,duration:Number.isFinite(video.duration)?video.duration:null,
                            mediaError:video.error?.code||null};
                        }''')
                        result['existingBridge']=loaded
                        row['frames'].append(result)
                except Exception as error:
                    row['error']=type(error).__name__+': '+str(error)[:300]
                finally:
                    page.close()
            # Do not close the owner browser or its existing context/tabs.
    except Exception as error:
        report['connection_error']=type(error).__name__+': '+str(error).splitlines()[0][:180]
    (ROOT/'research/owner-attached-samples.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':
    main()
