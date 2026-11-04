"""Public-page caption probes using the actual extension, without backend/GPU calls."""
import json
import argparse
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
PAGES = [
    'https://www.bilibili.com/video/BV1WqYV6cEwq/',
    'https://developer.apple.com/videos/play/wwdc2024/10140/',
    'https://ahrefs.com/academy/seo-training-course/lesson-1-1',
    'https://iandevlin.github.io/mdn/video-player-with-captions/',
]
PLATFORM_PAGES = [
    'https://www.ted.com/talks/ken_robinson_do_schools_kill_creativity',
    'https://www.feynmanlectures.caltech.edu/fml.html',
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--bilibili', action='store_true')
    parser.add_argument('--platforms', action='store_true')
    parser.add_argument('--urls', nargs='+', help='Public sample URLs for this acquisition run')
    parser.add_argument('--report', default=None, help='Report filename within research (JSON)')
    parser.add_argument('--activate-player', action='store_true', help='Click an observed public video play button in the isolated profile')
    parser.add_argument('--next-video', action='store_true', help='After activation, test Al Jazeera Next video carousel control')
    args = parser.parse_args()
    if args.report and (Path(args.report).name != args.report or not args.report.endswith('.json')):
        parser.error('--report must be a JSON filename')
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
            for url in args.urls or (PLATFORM_PAGES if args.platforms else PAGES[:1] if args.bilibili else PAGES):
                page = context.new_page()
                row = {'url': url}
                report['pages'].append(row)
                try:
                    response = page.goto(url, wait_until='domcontentloaded', timeout=30000)
                    row['http_status'] = response.status if response else None
                    page.wait_for_timeout(10000 if 'bilibili.com' in url else 5000)
                    if args.activate_player and url.startswith('https://www.aljazeera.com/video/'):
                        play=page.get_by_role('button',name='Play video',exact=True)
                        if play.count()==1:
                            play.click(timeout=8000)
                            row['activation']='Clicked public Play video button'
                            page.wait_for_timeout(5000)
                            if args.next_video:
                                page.get_by_role('button',name='Next video',exact=True).click(timeout=8000)
                                row['navigation']='Clicked Next video in the public carousel'
                                page.wait_for_timeout(5000)
                    if args.activate_player:
                        for frame in page.frames:
                            if frame.url.startswith('https://www.loom.com/embed/'):
                                play=frame.get_by_role('button',name='Play the video, keyboard shortcut K',exact=True)
                                if play.count():
                                    play.first.click(timeout=8000)
                                    row['activation']='Clicked embedded Loom Play video button'
                                    page.wait_for_timeout(3000)
                    tab = worker.evaluate('''async url=>(await chrome.tabs.query({})).find(t=>t.url===url)?.id''', page.url)
                    results = worker.evaluate('''async tab=>await chrome.scripting.executeScript({target:{tabId:tab,allFrames:true},world:'MAIN',func:async()=>{
                        const v=globalThis.VeloaMedia?.videos()[0];if(!v)return {state:'no-player'};
                        const id=VeloaMedia.youtubeId(location.href);
                        const result=id?await globalThis.__veloaYoutubeCaptions?.acquire(id):await globalThis.__veloaSiteCaptions?.acquire({href:location.href,src:VeloaMedia.source(v)});
                        return {host:location.hostname,engine:id?'youtube':'multisite',state:result?.state||'no-bridge',reason:result?.reason,diagnostic:result?.diagnostic,cues:result?.cues?.length,language:result?.language,
                            playerButton:Boolean(VeloaMedia.query('.vocalm-player-button').length), duration:Number.isFinite(v.duration)?v.duration:null,mediaError:v.error?.code||null,
                            path:location.pathname, rules:VeloaMedia.rules(location.href).map(r=>r.site),
                            videos:VeloaMedia.videos().map(v=>({parent:v.parentElement?.className,width:v.getBoundingClientRect().width,height:v.getBoundingClientRect().height})),
                            first:result?.cues?.[0]?.start,last:result?.cues?.at(-1)?.end,trackCount:v.textTracks.length};
                    }})''', tab)
                    row['frames'] = [result.get('result') or {'state':'frame-unavailable'} for result in results]
                    row['acquired'] = any(frame.get('state') == 'ready' for frame in row['frames'])
                except Exception as error:
                    row['error'] = str(error)[:400]
                page.close()
        finally:
            context.close()
            profile.cleanup()
            (ROOT / 'research' / (args.report or ('platform-live.json' if args.platforms else 'bilibili-live.json' if args.bilibili else 'multisite-live.json'))).write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report))


if __name__ == '__main__':
    main()
