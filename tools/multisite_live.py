"""Public-page caption probes using the actual extension, without backend/GPU calls."""
import json
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    'https://developer.apple.com/videos/play/wwdc2024/10140/',
    'https://ahrefs.com/academy/seo-training-course/lesson-1-1',
    'https://iandevlin.github.io/mdn/video-player-with-captions/',
]


def main():
    output = ROOT / '.private/multisite-live'
    output.mkdir(exist_ok=True)
    report = {'scope': 'Public live pages; acquisition only; no backend or GPU requests', 'pages': []}
    with sync_playwright() as p:
        extension = ROOT / 'dist/chrome'
        profile = tempfile.TemporaryDirectory(prefix='profile-', dir=output)
        context = p.chromium.launch_persistent_context(profile.name, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'], viewport={'width': 1440, 'height': 1000})
        try:
            worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
            for url in PAGES:
                page = context.new_page()
                row = {'url': url}
                report['pages'].append(row)
                try:
                    response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    row['http_status'] = response.status if response else None
                    page.wait_for_timeout(5000)
                    tab = worker.evaluate('''async url=>(await chrome.tabs.query({})).find(t=>t.url===url)?.id''', page.url)
                    results = worker.evaluate('''async tab=>await chrome.scripting.executeScript({target:{tabId:tab,allFrames:true},world:'MAIN',func:async()=>{
                        const v=globalThis.VeloaMedia?.videos()[0];if(!v)return {state:'no-player'};
                        const id=VeloaMedia.youtubeId(location.href);
                        const result=id?await globalThis.__veloaYoutubeCaptions?.acquire(id):await globalThis.__veloaSiteCaptions?.acquire({href:location.href,src:VeloaMedia.source(v)});
                        return {host:location.hostname,engine:id?'youtube':'multisite',state:result?.state||'no-bridge',reason:result?.reason,cues:result?.cues?.length,language:result?.language,
                            first:result?.cues?.[0]?.start,last:result?.cues?.at(-1)?.end,trackCount:v.textTracks.length};
                    }})''', tab)
                    row['frames'] = [result['result'] for result in results]
                    row['acquired'] = any(result['result'].get('state') == 'ready' for result in results)
                except Exception as error:
                    row['error'] = str(error)[:400]
                page.close()
        finally:
            context.close()
            profile.cleanup()
            (ROOT / 'research/multisite-live.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
