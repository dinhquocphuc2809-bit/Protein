"""Packaged MV3 tests of specific platform metadata chains, with labelled fixtures."""
import html
import json
from pathlib import Path
import tempfile

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
VTT = 'WEBVTT\n\n00:01.000 --> 00:03.000\nExisting caption.\n\n00:04.000 --> 00:06.000\nCorrect lesson.'
CAPTION = 'https://captions.fixture.test/full.vtt'


def scenarios():
    video = '<video id="v" style="width:800px;height:450px"></video>'
    from reader_fixtures import scenarios as reader_scenarios
    yield from reader_scenarios(video, CAPTION, VTT)
    from priority_fixtures import scenarios as priority_scenarios
    yield from priority_scenarios(video, CAPTION, VTT)
    def case(name, url, script='', body=video, resources=None, ready=True):
        return dict(name=name, url=url, script=script, body=body, resources=resources or {}, ready=ready)
    def next_data(data):
        return '<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props': {'pageProps': data}})+'</script>'+video
    yield case('egghead', 'https://egghead.io/lessons/lesson', body=next_data({'post': {'fields': {'slug': 'lesson'}}, 'videoResource': {'fields': {'srt': VTT}}}))
    yield case('egghead_stale', 'https://egghead.io/lessons/new', body=next_data({'post': {'fields': {'slug': 'old'}}, 'videoResource': {'fields': {'srt': VTT}}}), ready=False)
    metadata = {'transcriptLanguages': {'en': 'English'}, 'transcriptTranslationUrl': '/transcript/__lang__'}
    yield case('edx', 'https://courses.edx.org/courseware/test', body='<div class="video" data-metadata="'+html.escape(json.dumps(metadata), quote=True)+'">'+video+'</div>', resources={'/transcript/en': {'start': [1000, 4000], 'end': [3000, 6000], 'text': ['Existing caption.', 'Correct lesson.']}})
    yield case('datacamp', 'https://projector.datacamp.com/?projector_key=course_42_intro', resources={'/production/course_42/subtitles/course_42_intro.vtt': VTT})
    yield case('ted', 'https://www.ted.com/talks/lesson', body=next_data({'videoData': {'playerData': json.dumps({'slug': 'lesson', 'resources': {'hls': {'metadata': 'https://captions.fixture.test/ted.json'}}})}}), resources={'/ted.json': {'subtitles': [{'code': 'en', 'webvtt': CAPTION}]}})
    yield case('naver', 'https://tv.naver.com/v/123', body=next_data({'vodInfo': {'clip': {'clipNo': 123, 'videoId': 'vid'}, 'play': {'inKey': 'fixture-only'}}}), resources={'/rmcnmv/rmcnmv/vod/play/v2.0/vid': {'captions': {'list': [{'source': CAPTION, 'locale': 'en'}]}}})
    yield case('rutube', 'https://rutube.ru/video/abc/', resources={'/api/play/options/abc/': {'captions': [{'file': CAPTION, 'language': 'en'}]}})
    yield case('substack', 'https://author.substack.com/p/lesson', body=video.replace('id="v"', 'id="v" data-video-id="123"'), script='window._preloads='+json.dumps({'post': {'videoUpload': {'id': 123, 'transcription': {'cdn_url': 'https://substackcdn.com/video_upload/123/transcription.json'}}}}), resources={'/video_upload/123/transcription.json': [{'start': 1, 'end': 3, 'text': 'Existing caption.'}, {'start': 4, 'end': 6, 'text': 'Correct lesson.'}]})
    yield case('bloomberg', 'https://www.bloomberg.com/news/videos/lesson', body='<div id="skylight-vod-123">'+video+'</div>', resources={'/media-manifest/embed': {'id': '123', 'captions': CAPTION}})
    yield case('dailymotion', 'https://geo.dailymotion.com/player/p1.html?video=v1', resources={'/video/v1.json': {'subtitles': {'data': {'en': {'urls': [CAPTION]}}}}})
    yield case('archive', 'https://archive.org/details/item', body='<div class="jwplayer" id="jw">'+video+'</div>', script='window.jwplayer=()=>({getPlaylistItem:()=>({orig:"lecture.mp4"})});', resources={'/metadata/item': {'metadata': {'identifier': 'item'}, 'files': [{'name': 'other.vtt'}, {'name': 'lecture.en.vtt'}]}, '/download/item/lecture.en.vtt': VTT})
    yield case('vidyard', 'https://play.vidyard.com/player1.html', body=video.replace('id="v"','id="v" aria-label="Second"'), resources={'/player/player1.json': {'payload': {'chapters': [{'name': 'First', 'captions': [{'vttUrl': 'https://captions.fixture.test/wrong.vtt'}]}, {'name': 'Second', 'captions': [{'vttUrl': CAPTION, 'language': 'en'}]}]}}})
    yield case('adobe', 'https://video.tv.adobe.com/v/123', script='window.bridge='+json.dumps({'humanID': 123, 'translations': [{'vttPath': CAPTION, 'language_locale': 'en_US'}]}))
    yield case('feynman', 'https://www.feynmanlectures.caltech.edu/fml.html', body='<a class="videolink"></a><a class="videolink current"></a>'+video, script='window.FMLCaptions='+json.dumps([{'src': 'https://captions.fixture.test/wrong.vtt'}, {'src': CAPTION, 'srclang': 'en'}]))
    yield case('videojs_mediainfo', 'https://www.aljazeera.com/video/lesson', body='<div class="video-js">'+video+'</div>', script='window.videojs={getPlayers:()=>({own:{el:()=>document.querySelector(".video-js"),mediainfo:{text_tracks:[{kind:"captions",src:'+json.dumps(CAPTION)+',srclang:"en"}]}}})};')
    yield case('videojs_other_player', 'https://www.aljazeera.com/video/lesson', script='window.videojs={getPlayers:()=>({other:{el:()=>document.createElement("div"),mediainfo:{text_tracks:[{src:'+json.dumps(CAPTION)+'}]}}})};', ready=False)
    api='/api-2.0/users/me/subscribed-courses/1/lectures/123/'
    yield case('ted_ad_players', 'https://www.ted.com/talks/ads', body='<script id="__NEXT_DATA__" type="application/json">'+json.dumps({'props':{'pageProps':{'videoData':{'slug':'ads','videoPlayerData':{'slug':'ads','nativeLanguage':'en','resources':{'hls':{'metadata':'https://captions.fixture.test/ted.json'}}}}}}})+'</script><media-controller id="video-player-container">'+video.replace('id="v"','id="video"')+'<div id="ad-container">'+video.replace('id="v"','id="ad"')+'</div><div id="media-control-bar"></div></media-controller>', resources={'/ted.json':{'subtitles':[{'code':'en','webvtt':CAPTION}]}})
    yield case('ted_current_schema', 'https://www.ted.com/talks/current', body=next_data({'videoData': {'slug':'current','videoPlayerData':{'slug':'current','nativeLanguage':'en','resources':{'hls':{'metadata':'https://captions.fixture.test/ted.json'}}}}}), resources={'/ted.json':{'subtitles':[{'code':'pt-br','webvtt':'https://captions.fixture.test/wrong.vtt'},{'code':'en','webvtt':CAPTION}]}})
    yield case('videojs_attached', 'https://www.lecturio.com/medical-courses/lesson.lecture', body='<div class="video-js">'+video+'</div>', script='document.querySelector(".video-js").player={remoteTextTracks:()=>({tracks_:[{kind_:"captions",src_:'+json.dumps(CAPTION)+',language_:"en_US"}]})};')
    args=html.escape(json.dumps({'courseId':1}),quote=True)
    yield case('udemy_no_history', 'https://www.udemy.com/course/test/learn/lecture/123', body='<div data-module-id="course-taking" data-module-args="'+args+'"></div>'+video,
        resources={api:{'id':123,'asset':{'id':9,'captions':[{'url':'https://captions.fixture.test/wrong.vtt','locale_id':'de_DE','source':'auto','asset_id':9,'status':1},
            {'url':CAPTION,'locale_id':'en_US','source':'manual','asset_id':9,'status':1}]}}, '/api-2.0/courses/1/':{'id':1,'locale':{'locale':'en_US'}}})
    yield case('udemy_missed_hook', 'https://www.udemy.com/course/test/learn/lecture/123', script='window.__early=window.fetch('+json.dumps(api)+').then(r=>r.json());', resources={api: {'id': 123, 'asset': {'captions': [{'url': CAPTION, 'locale_id': 'en_US'}]}}})
    yield case('udemy_stale', 'https://www.udemy.com/course/test/learn/lecture/124', script='fetch('+json.dumps(api)+').then(r=>r.json());', resources={api: {'id': 123, 'asset': {'captions': [{'url': CAPTION, 'locale_id': 'en_US'}]}}}, ready=False)


def main():
    private = ROOT / '.private/platform-qa'
    private.mkdir(parents=True, exist_ok=True)
    report = {'scope': 'Packaged Chromium MV3; explicit metadata fixtures; not live site acceptance', 'checks': []}
    from urllib.parse import urlsplit
    with sync_playwright() as p, tempfile.TemporaryDirectory(prefix='profile-', dir=private) as profile:
        extension=ROOT/'dist/chrome'
        ctx=p.chromium.launch_persistent_context(profile, channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'])
        try:
            worker=ctx.service_workers[0] if ctx.service_workers else ctx.wait_for_event('serviceworker')
            for case in scenarios():
                requests=[]
                page=ctx.new_page()
                # Save native fetch before MAIN scripts for the missed-hook regression.
                if case['name']=='udemy_missed_hook':
                    page.add_init_script('window.__originalFetch=window.fetch;')
                    case['script']=case['script'].replace('window.fetch(', 'window.__originalFetch(')
                def route(r):
                    url=r.request.url
                    path=urlsplit(url).path
                    origin=urlsplit(case['url'])
                    cors={'Access-Control-Allow-Origin':origin.scheme+'://'+origin.netloc,'Access-Control-Allow-Credentials':'true'}
                    requests.append(path)
                    if r.request.is_navigation_request() and r.request.frame==page.main_frame:
                        r.fulfill(body='<!doctype html><html><head><title>Platform fixture</title></head><body>'+case['body']+'<script>'+case['script']+'</script></body></html>', content_type='text/html')
                    elif url==CAPTION:
                        r.fulfill(body=VTT, content_type='text/vtt', headers=cors)
                    elif path=='/u/0/timedtext' and case.get('drive_tracks'):
                        from urllib.parse import parse_qs
                        query=parse_qs(urlsplit(url).query)
                        if query.get('type')==['list']:
                            r.fulfill(body='<transcript_list><track lang_code="en" lang_default="true" name=""/></transcript_list>',content_type='application/xml',headers=cors)
                        else:
                            r.fulfill(json={'events':[{'tStartMs':1000,'dDurationMs':2000,'segs':[{'utf8':'Existing caption.'}]},{'tStartMs':4000,'dDurationMs':2000,'segs':[{'utf8':'Correct lesson.'}]}]},headers=cors)
                    elif path=='/api' and case.get('rpc_responses'):
                        if r.request.method=='OPTIONS':
                            r.fulfill(status=204,headers={**cors,'Access-Control-Allow-Methods':'POST','Access-Control-Allow-Headers':'content-type'})
                            return
                        payload=r.request.post_data_json or {}
                        operation=(payload.get('data') or [{}])[0].get('context',{}).get('functionName')
                        result=case['rpc_responses'].get(operation)
                        r.fulfill(status=200 if result else 403,json=[{'output':{'status':'ok','data':{'response':result}}}],headers=cors)
                    elif path in case['resources']:
                        if path == case.get('change_on_path'):
                            r.request.frame.evaluate(case['change_script'])
                        if path.startswith('/playback/v1/') and r.request.headers.get('accept') != 'application/json;pk=public-fixture-policy':
                            r.fulfill(status=403,body='Missing public playback policy',headers=cors)
                            return
                        if case.get('denied'):
                            r.fulfill(status=403, body='Fixture: denied',headers=cors)
                            return
                        data=case['resources'][path]
                        r.fulfill(body=data if isinstance(data,str) else json.dumps(data), content_type='text/vtt' if isinstance(data,str) else 'application/json', headers=cors)
                    else:
                        r.fulfill(status=404, body='Fixture: resource absent')
                page.route('**/*', route)
                try:
                    page.goto(case['url'])
                    page.wait_for_function('!!window.__veloaSiteCaptions')
                    page.wait_for_timeout(250)
                    tab=worker.evaluate('async url=>(await chrome.tabs.query({})).find(t=>t.url===url).id', page.url)
                    result=worker.evaluate('''async tab=>(await chrome.scripting.executeScript({target:{tabId:tab},world:'MAIN',func:async()=>{
                      const v=VeloaMedia.videos()[0];return __veloaSiteCaptions.acquire({href:location.href,src:VeloaMedia.source(v)});
                    }}))[0].result''',tab)
                    if case['ready']:
                        assert result['state']=='ready',result
                        assert [(c['start'],c['end'],c['text']) for c in result['cues']]==[(1,3,'Existing caption.'),(4,6,'Correct lesson.')],result
                    else:
                        assert result['state']!='ready',result
                    assert '/wrong.vtt' not in requests,requests
                    row={'name':case['name'],'passed':True,'state':result['state'],'cues':len(result.get('cues',[]))}
                    if case['name']=='udemy_missed_hook':
                        row['lecture_requests']=sum('/lectures/123/' in path for path in requests)
                        assert row['lecture_requests']>=2, 'Fixture did not exercise missed-hook recovery'
                    report['checks'].append(row)
                except Exception as error:
                    report['checks'].append({'name':case['name'],'passed':False,'error':str(error)[:1000]})
                finally:
                    page.close()
            report['passed']=all(row['passed'] for row in report['checks'])
        finally:
            ctx.close()
            (ROOT/'research/platform-acceptance.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return 0 if report.get('passed') else 1


if __name__=='__main__':
    raise SystemExit(main())
