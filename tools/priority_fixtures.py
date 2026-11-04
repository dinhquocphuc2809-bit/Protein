"""Labelled regressions for the five-platform priority batch; not live evidence."""
import json


def scenarios(video, caption, vtt):
    def case(name, url, script='', body=video, resources=None, ready=True, **extra):
        return dict(name=name, url=url, script=script, body=body,
                    resources=resources or {}, ready=ready, **extra)
    api = '/intl/gateway/web/v2/subtitle'
    resource = 'https://s.bstarstatic.com/ogv/subtitle/full.json'
    cues = {'body': [{'from': 1, 'to': 3, 'content': 'Existing caption.'},
                     {'from': 4, 'to': 6, 'content': 'Correct lesson.'}]}
    metadata = {'code': 0, 'data': {'video_subtitle': [
        {'lang_key': 'en', 'srt': {'url': resource}, 'ass': None}]}}
    assets = {api: metadata, '/ogv/subtitle/full.json': cues}
    season = 'https://www.bilibili.tv/en/play/37976'
    episode = season + '/10344255'
    active = '<a class="ep-item ep-item--active" href="/en/play/37976/10344255">Current</a>'
    yield case('biliintl_episode', episode, resources=assets)
    yield case('biliintl_season', season, body=video+active, resources=assets)
    yield case('biliintl_ugc', 'https://www.bilibili.tv/en/video/204123', resources=assets)
    yield case('biliintl_unresolved_season', season, resources=assets, ready=False)
    yield case('biliintl_denied', episode, resources=assets, denied=True, ready=False)
    yield case('biliintl_empty', episode, resources={api: {'code': 0, 'data': {'video_subtitle': []}}}, ready=False)
    yield case('biliintl_changed_episode', season, body=video+active, resources=assets,
               change_on_path=api, change_script='document.querySelector("a").href="/en/play/37976/10344397"', ready=False)
    ass = '[Script Info]\n[Events]\nFormat: Layer, Start, End, Style, Text\nDialogue: 0,0:00:01.00,0:00:03.00,Default,Existing caption.\nDialogue: 0,0:00:04.00,0:00:06.00,Default,Correct lesson.'
    yield case('biliintl_ass_only', episode, resources={api: {'code': 0, 'data': {
        'subtitles': [{'lang_key': 'en', 'url': 'https://s.bstarstatic.com/full.ass'}]}}, '/full.ass': ass})
    current = '6961737553342991651'
    other = '6963263655114722595'
    url = 'https://www.douyin.com/video/'+current
    detail = '/aweme/v1/web/aweme/detail/'
    data = {'status_code': 0, 'aweme_detail': {'aweme_id': current,
        'video': {'cla_info': {'caption_infos': [{'url': caption, 'lang': 'zh'}]}}}}
    yield case('douyin_detail', url, resources={detail: data})
    yield case('douyin_stale', url, resources={detail: {**data, 'aweme_detail': {**data['aweme_detail'], 'aweme_id': other}}}, ready=False)
    yield case('douyin_denied', url, resources={detail: data}, denied=True, ready=False)
    feed = '<section data-e2e="feed-video" data-aweme-id="'+other+'">'+video.replace('id="v"', 'id="old"')+'</section><section data-e2e="feed-active-video" data-aweme-id="'+current+'">'+video+'</section>'
    yield case('douyin_active_feed', 'https://www.douyin.com/jingxuan', body=feed,
               script='window._ROUTER_DATA='+json.dumps(data), resources={detail: data})
    utterances = {'utterances': [{'start_time': 1000, 'end_time': 3000, 'text': 'Existing caption.'},
                               {'start_time': 4000, 'end_time': 6000, 'text': 'Correct lesson.'}]}
    yield case('douyin_auto_caption', url, resources={detail: {'status_code': 0, 'aweme_detail': {
        'aweme_id': current, 'interaction_stickers': [{'auto_video_caption_info': {
            'auto_captions': [{'language': 'zh', 'url': {'url_list': ['https://captions.fixture.test/utterances.json']}}]}}]}},
        '/utterances.json': utterances})
