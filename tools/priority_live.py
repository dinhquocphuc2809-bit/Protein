"""Live caption/UI checks in the owner's authorized Chrome, with no provider jobs.

Only tabs created by this process are navigated or closed. Reports omit captions,
cookies, signed resource URLs and page text. Historical evidence is not overwritten.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
from pathlib import Path
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from ui_acceptance import shadow_eval

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = [
    'https://www.udemy.com/course/ccna-complete/learn/lecture/9538164?start=0#overview',
    'https://www.bilibili.com/video/BV1WqYV6cEwq/',
    'https://www.youtube.com/watch?v=3BndvjrGwyE',
]
ALLOWED = {'www.udemy.com', 'www.youtube.com', 'www.bilibili.com',
           'www.bilibili.tv', 'www.douyin.com'}
ACQUIRE = """async()=>{
  const M=globalThis.VeloaMedia,v=M?.videos()[0];
  if(!v)return {state:'no-player'};
  const id=M.youtubeId(location.href);
  const r=id?await globalThis.__veloaYoutubeCaptions?.acquire(id):
    await globalThis.__veloaSiteCaptions?.acquire({href:location.href,src:M.source(v)});
  const cues=r?.cues||[];
  const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(cues)));
  return {state:r?.state||'no-bridge',reason:r?.reason,diagnostic:r?.diagnostic,
    cues:cues.length,language:r?.language,first:cues[0]?.start,last:cues.at(-1)?.end,
    duration:Number.isFinite(v.duration)?v.duration:null,mediaError:v.error?.code||null,
    validTimes:cues.length>0&&cues.every(c=>Number.isFinite(c.start)&&Number.isFinite(c.end)&&
      c.start>=0&&c.end>c.start&&(!Number.isFinite(v.duration)||c.end<=v.duration+1)),
    hash:[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join(''),
    playerButton:!!document.querySelector('.vocalm-player-button'),
    rules:M.rules(location.href).map(r=>r.site),trackCount:v.textTracks.length};
}"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--urls', nargs='+')
    parser.add_argument('--report', default='priority-live.json')
    parser.add_argument('--lifecycle', action='store_true', help='Pause/seek and switch available Bilibili parts/episodes in test-created tabs')
    parser.add_argument('--pointer', action='store_true', help='Require a real pointer click on the Vocalm button')
    args = parser.parse_args()
    if Path(args.report).name != args.report or not args.report.endswith('.json'):
        parser.error('Report must be a JSON filename')
    urls = args.urls or DEFAULTS
    if any(urlsplit(u).scheme != 'https' or urlsplit(u).hostname not in ALLOWED for u in urls):
        parser.error('Only the five requested platforms are allowed')
    lines = (Path(os.environ['LOCALAPPDATA']) /
             'Google/Chrome/User Data/DevToolsActivePort').read_text().splitlines()
    report = {'at': datetime.now(timezone.utc).isoformat(),
              'scope': 'Live owner Chrome, installed Vocalm; caption acquisition and quick menu only; no Dubbing/ASR/translation/TTS invocation',
              'pages': []}
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp('ws://127.0.0.1:'+lines[0]+lines[1], timeout=25000)
        session = browser.new_browser_cdp_session()
        installed = [e for e in session.send('Extensions.getExtensions').get('extensions', [])
                     if Path(e.get('path', '')) == ROOT/'dist/chrome' and e.get('enabled')]
        session.detach()
        if len(installed) != 1:
            raise RuntimeError('Current local Vocalm package is not enabled')
        report['extension'] = {k: installed[0][k] for k in ['id', 'name', 'version']}
        report['package_sha256'] = hashlib.sha256(b''.join(
            file.relative_to(ROOT/'dist/chrome').as_posix().encode()+file.read_bytes()
            for file in sorted((ROOT/'dist/chrome').rglob('*.js')))).hexdigest()
        for url in urls:
            page = browser.contexts[0].new_page()
            row = {'url': url, 'checks': []}
            report['pages'].append(row)
            try:
                page.bring_to_front()
                response = page.goto(url, wait_until='domcontentloaded', timeout=40000)
                row['http_status'] = response.status if response else None
                page.wait_for_timeout(12000)
                if urlsplit(url).hostname == 'www.youtube.com':
                    # An advertisement is a different media timeline, never caption evidence.
                    deadline = time.monotonic() + 75
                    while time.monotonic() < deadline and page.locator('.ad-showing, .ad-interrupting').count():
                        skip = page.locator('.ytp-skip-ad-button, .ytp-ad-skip-button-modern')
                        if skip.count() and skip.first.is_visible():
                            skip.first.click(timeout=2000)
                        page.wait_for_timeout(1000)
                    row['adStillShowing'] = bool(page.locator('.ad-showing, .ad-interrupting').count())
                row['destination'] = urlsplit(page.url).hostname + urlsplit(page.url).path
                for label in ['initial', 'repeat']:
                    started = time.monotonic()
                    result = page.evaluate(ACQUIRE)
                    row['checks'].append({'name': label, 'seconds': round(time.monotonic()-started, 3), **result})
                    if result['state'] in ('no-player', 'no-bridge'):
                        break
                if args.lifecycle and row['checks'][-1].get('state') == 'ready':
                    previous = row['checks'][-1]['hash']
                    original = page.evaluate('''()=>{const v=VeloaMedia.videos()[0];
                      const state={time:v.currentTime,paused:v.paused};v.pause();
                      v.currentTime=Math.min(120,v.duration/2);return state}''')
                    page.wait_for_timeout(1200)
                    result = page.evaluate(ACQUIRE)
                    row['seekStable'] = result.get('state') == 'ready' and result.get('hash') == previous
                    page.evaluate('''s=>{const v=VeloaMedia.videos()[0];v.currentTime=s.time;
                      if(!s.paused)v.play().catch(()=>{})}''', original)
                    if urlsplit(url).hostname == 'www.bilibili.com':
                        parts = page.locator('.video-pod__list.multip .video-pod__item')
                        active = next((i for i in range(parts.count())
                            if 'active' in (parts.nth(i).get_attribute('class') or '').split()), None)
                        if parts.count() > 1 and active is not None:
                            target = 1 if active == 0 else 0
                            parts.nth(target).click(timeout=5000)
                            page.wait_for_timeout(8000)
                            changed = page.evaluate(ACQUIRE)
                            selected = page.evaluate('VeloaMedia.biliRoute(location.href).page')
                            row['partSwitch'] = {
                                'page': selected,
                                'passed': selected == target+1 and changed.get('state') == 'ready'
                                    and changed.get('validTimes') and changed.get('hash') != previous,
                                **changed,
                            }
                            parts.nth(active).click(timeout=5000)
                            page.wait_for_timeout(8000)
                            restored = page.evaluate(ACQUIRE)
                            row['partReturn'] = {
                                'passed': restored.get('state') == 'ready' and restored.get('hash') == previous,
                                **restored,
                            }
                    if urlsplit(url).hostname == 'www.bilibili.tv':
                        links = page.locator('a.ep-item[href]')
                        target = None
                        for i in range(min(links.count(), 5)):
                            link = links.nth(i)
                            if 'ep-item--active' not in (link.get_attribute('class') or ''):
                                target = link
                                break
                        if target is not None:
                            target.click(timeout=5000)
                            page.wait_for_timeout(8000)
                            changed = page.evaluate(ACQUIRE)
                            row['episodeSwitch'] = {
                                'path': urlsplit(page.url).path,
                                'passed': changed.get('state') == 'ready' and changed.get('validTimes') and changed.get('hash') != previous,
                                **changed,
                            }
                button = page.locator('.vocalm-player-button')
                if button.count() == 1:
                    if args.pointer:
                        rect = page.locator('video').first.bounding_box()
                        if rect:
                            # Real players overlay the video with controls; move the pointer
                            # into its box without requiring the video itself to receive it.
                            page.mouse.move(rect['x'] + rect['width']/2, rect['y'] + rect['height']/2)
                            page.wait_for_timeout(300)
                        button.click(timeout=5000)
                        row['pointerClick'] = True
                    else:
                        # Distinguish handler integration from hit-target acceptance.
                        button.evaluate('e=>e.click()')
                        row['pointerClick'] = False
                    try:
                        panel = shadow_eval(page, 'auvirel-surface')
                        row['quickMenu'] = panel('function(){return !this.querySelector(".quick-menu").hidden}')
                        panel('function(){this.querySelector(".quick-close").click()}')
                    except Exception as error:
                        row['uiErrorType'] = type(error).__name__
                row['captionsPassed'] = len(row['checks']) == 2 and all(
                    c.get('state') == 'ready' and c.get('validTimes') for c in row['checks'])
                row['stable'] = len(row['checks']) == 2 and row['checks'][0].get('hash') == row['checks'][1].get('hash')
                row['samplePassed'] = bool(row['captionsPassed'] and row['stable'] and row.get('quickMenu')
                    and row.get('seekStable', True) and row.get('episodeSwitch', {}).get('passed', True)
                    and row.get('partSwitch', {}).get('passed', True) and row.get('partReturn', {}).get('passed', True))
            except Exception as error:
                # Playwright exceptions can contain signed request URLs; save only the category.
                row['errorType'] = type(error).__name__
                row['errorSummary'] = re.sub(r'https?://\S+', '[URL omitted]', str(error).splitlines()[0])[:180]
                row['samplePassed'] = False
            finally:
                page.close()
                (ROOT/'research'/args.report).write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
                print(json.dumps(row), flush=True)
    return 0 if all(row.get('samplePassed') for row in report['pages']) else 1


if __name__ == '__main__':
    raise SystemExit(main())
