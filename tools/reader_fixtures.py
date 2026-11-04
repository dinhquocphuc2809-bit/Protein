"""Explicit source-mechanism fixtures; these never establish live-site support."""
import base64
import json
import html


def scenarios(video, caption, vtt):
    def case(name, url, script='', body=video, resources=None, ready=True):
        return dict(name=name, url=url, script=script, body=body, resources=resources or {}, ready=ready)
    master='#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="en",DEFAULT=YES,URI="https://captions.fixture.test/sub.m3u8"\n#EXT-X-STREAM-INF:BANDWIDTH=1000\nvideo.m3u8'
    hls={'/manifest.m3u8':master,'/sub.m3u8':'#EXTM3U\n#EXTINF:8,\nfull.vtt\n#EXT-X-ENDLIST'}
    rows=[]
    rows.append(case('artstation', 'https://www.artstation.com/learning/courses/course/drawing/chapters/current/intro', resources={'/api/v2/learning/courses/course.json':{'hash_id':'course','chapters':[{'hash_id':'old','subtitles':[{'format':'vtt','file_url':'https://captions.fixture.test/wrong.vtt'}]},{'hash_id':'current','subtitles':[{'format':'vtt','file_url':caption,'locale':'en'}]}]}}))
    encoded=base64.urlsafe_b64encode(json.dumps([{'uri':caption,'language':'en'}]).encode()).decode().rstrip('=')
    rows.append(case('platzi', 'https://platzi.com/cursos/course/123-lesson/', script='document.querySelector("video").src="https://media.fixture.test/video.mp4?subtitles='+encoded+'";'))
    panda='11111111-2222-3333-4444-555555555555'
    rows.append(case('pandavideo', 'https://player-vz-12345678-abc.tv.pandavideo.com.br/embed/?v='+panda, script='window.pandaLoad={configVideoLoaded:true,playerLoaded:true};window.player_configs={subtitles:[{srclang:"pt"}]};', resources={'/vz-12345678-abc/'+panda+'/pt-BR.vtt':vtt}))
    rows.append(case('tella', 'https://www.tella.tv/video/current/embed', resources={'/api/stories/current/manifest-refresh':{'signedManifestUrl':'https://prod-stream.tella.tv/media/manifest.m3u8?story_id=current&token=fixture-only'},'/media/manifest.m3u8':master,**hls}))
    bootstrap={'serverBootstrap':{'pageData':{'videoPlayerData':{'units':[{'sessions':[{'id':'old'},{'id':'current'}]}]}}}}
    rows.append(case('skillshare', 'https://www.skillshare.com/en/classes/test/123', body='<div class="session-item active"><span data-rank="2"></span></div>'+video, script='window.SS='+json.dumps(bootstrap), resources={'/sessions/current/stream':{'streams':[{'type':'hls','url':'https://customer-test.cloudflarestream.com/manifest.m3u8'}]},**hls}))
    ld={'@type':'VideoObject','url':'https://updraft.cyfrin.io/courses/course/chapter/lesson','contentUrl':'https://stream.mux.com/manifest.m3u8?token=fixture-only'}
    rows.append(case('updraft','https://updraft.cyfrin.io/courses/course/chapter/lesson',body='<script type="application/ld+json">'+json.dumps(ld)+'</script>'+video,resources=hls))
    selector='/mediaselector/6/select/version/3.0/mediaset/pc/cvid/urn:bbc:pips:pid:v123/format/json/cors/1'
    rows.append(case('bbc', 'https://www.bbc.com/news/videos/p123', resources={'/xd/page/content':{'blocks':[{'model':{'id':'p123','versionId':'v123','type':'video'}}]},selector:{'media':[{'kind':'captions','language':'en','connection':[{'href':caption}]}]}}))
    loom='1234567890abcdef1234567890abcdef'
    rows.append(case('loom','https://www.loom.com/embed/'+loom,resources={'/share/'+loom:'<script type="application/json">'+json.dumps({'captions':'https://cdn.loom.com/mediametadata/captions/'+loom+'.vtt?signature=fixture-only'})+'</script>','/mediametadata/captions/'+loom+'.vtt':vtt}))
    for row in rows:
        yield row
        if row['resources']:
            yield {**row,'name':row['name']+'_denied','denied':True,'ready':False}
    yield case('artstation_stale','https://www.artstation.com/learning/courses/course/drawing/chapters/new/intro',resources=rows[0]['resources'],ready=False)
    yield case('platzi_malformed','https://platzi.com/cursos/course/123-lesson/',script='document.querySelector("video").src="https://media.fixture.test/video.mp4?subtitles=bad";',ready=False)
    yield case('pandavideo_not_ready',rows[2]['url'],script='window.player_configs={subtitles:[{srclang:"pt"}]};',ready=False)
    yield case('tella_wrong_story',rows[3]['url'],resources={'/api/stories/current/manifest-refresh':{'signedManifestUrl':'https://prod-stream.tella.tv/media/manifest.m3u8?story_id=other'}},ready=False)
    yield case('skillshare_ambiguous',rows[4]['url'],script='window.SS='+json.dumps(bootstrap),ready=False)
    yield case('updraft_stale',rows[5]['url']+'/new',body=rows[5]['body'],ready=False)
    yield case('bbc_ambiguous',rows[6]['url'],resources={'/xd/page/content':{'a':{'model':{'id':'other','versionId':'v1'}},'b':{'model':{'id':'another','versionId':'v2'}}}},ready=False)
    yield case('loom_missing',rows[7]['url'],resources={'/share/'+loom:'<html>No captions advertised</html>'},ready=False)
    osmosis = {'/learnData': {'lesson': {'slug':'Heart', 'captions':[{'src':'heart.vtt','srcLang':'en'}]}}, '/heart.vtt':vtt}
    yield case('osmosis','https://www.osmosis.org/learn/Heart',resources=osmosis)
    yield case('osmosis_localized','https://www.osmosis.org/learn/es/Heart?from=library',resources=osmosis)
    yield case('osmosis_denied','https://www.osmosis.org/learn/Heart',resources=osmosis,ready=False) | {'denied':True}
    yield case('osmosis_stale','https://www.osmosis.org/learn/Other',resources=osmosis,ready=False)
    yield case('osmosis_ambiguous','https://www.osmosis.org/learn/Heart',resources={'/learnData':{'a':{'captions':[{'src':caption}]},'b':{'captions':[{'src':caption}]}}},ready=False)
    gaia_script='document.querySelector("video").player={mediainfo:{id:123},audioTracks:()=>[{enabled:true,language:"en"}]};'
    gaia={'/node/123':{'nid':123,'feature':{'nid':456},'preview':{'nid':789}},'/v1/media-info/456':{'textTracks':{'captions':{'en':'https://brooklyn.gaia.com/captions/lesson.vtt'}}},'/captions/lesson.vtt':vtt}
    yield case('gaia','https://www.gaia.com/video/lesson',script=gaia_script,resources=gaia)
    yield case('gaia_denied','https://www.gaia.com/video/lesson',script=gaia_script,resources=gaia,ready=False) | {'denied':True}
    yield case('gaia_preview','https://www.gaia.com/video/lesson?fullplayer=preview',script=gaia_script,resources=gaia,ready=False)
    yield case('gaia_stale','https://www.gaia.com/video/lesson',script=gaia_script,resources={'/node/123':{'nid':124,'feature':{'nid':456}}},ready=False)
    bright='<video-js data-account="123" data-player="default" data-video-id="456">'+video+'</video-js>'
    bright_resources={'/123/default_default/config.json':{'video_cloud':{'policy_key':'public-fixture-policy'}},'/playback/v1/accounts/123/videos/456':{'id':'456','text_tracks':[{'kind':'captions','src':caption,'srclang':'en'}]}}
    for name,url in [('aljazeera','https://www.aljazeera.com/video/lesson'),('oracle','https://mylearn.oracle.com/ou/course/lesson'),('sonicwall','https://www.sonicwall.com/support/video-tutorials/lesson'),('servicenow','https://learning.servicenow.com/lxp/en/pages/learning-course'),('mathworks','https://www.mathworks.com/videos/lesson.html')]:
        yield case(name+'_playback',url,body=bright,resources=bright_resources)
    yield case('brightcove_stale','https://www.aljazeera.com/video/lesson',body=bright,resources={**bright_resources,'/playback/v1/accounts/123/videos/456':{'id':'other','text_tracks':[{'kind':'captions','src':caption}]}},ready=False)
    yield case('brightcove_denied','https://www.aljazeera.com/video/lesson',body=bright,resources=bright_resources,ready=False) | {'denied':True}
    kollus='window.KollusPlayers=[{player:{el:()=>document.body},media_info:{items:[{attr:{media_content_key:"current"},subtitles:[{subtitle_url:'+json.dumps(caption)+',subtitle_language_code:"en"}]}]}}];'
    yield case('kollus','https://v.kr.kollus.com/s?mckey=current',script=kollus)
    yield case('kollus_stale','https://v.kr.kollus.com/s?mckey=new',script=kollus,ready=False)
    skool={'props':{'pageProps':{'selectedModule':{'id':'current'},'video':{'id':'vid','playbackId':'manifest','playbackToken':'fixture-only'}}}}
    body='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(skool)+'</script>'+video
    yield case('skool','https://www.skool.com/community/classroom/course?md=current',body=body,resources=hls)
    yield case('skool_stale','https://www.skool.com/community/classroom/course?md=new',body=body,resources=hls,ready=False)
    skool['props']['pageProps']['video']['playbackToken']=''
    yield case('skool_locked','https://www.skool.com/community/classroom/course?md=current',body='<script id="__NEXT_DATA__" type="application/json">'+json.dumps(skool)+'</script>'+video,ready=False)
    multilingual='#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="bg-BG",URI="wrong.m3u8"\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="en-US",URI="https://captions.fixture.test/sub.m3u8"'
    yield case('updraft_original_language',rows[5]['url'],body=rows[5]['body'],resources={**hls,'/manifest.m3u8':multilingual},script='const v=document.querySelector("video");const t=v.addTextTrack("subtitles","Bulgarian","bg");t.addCue(new VTTCue(1,3,"Wrong language"));Object.defineProperty(v,"duration",{value:3});')
    options={'flashvars':json.dumps({'metadata':json.dumps({'movie':{'id':123,'subtitleTracks':[{'url':caption,'lang':'en'}]}})})}
    okbody='<div data-options="'+html.escape(json.dumps(options),quote=True)+'">'+video+'</div>'
    yield case('okru','https://ok.ru/video/123',body=okbody)
    yield case('okru_stale','https://ok.ru/video/124',body=okbody,ready=False)
    cf='https://customer-uvgt1jgt7nqod9np.cloudflarestream.com/1234567890abcdef1234567890abcdef/iframe'
    yield case('sketchy_cloudflare',cf,resources={'/1234567890abcdef1234567890abcdef/manifest/video.m3u8':master,**hls})
    yield case('sketchy_cloudflare_denied',cf,resources={'/1234567890abcdef1234567890abcdef/manifest/video.m3u8':master},ready=False) | {'denied':True}
    plex='#EXTM3U\n#EXT-X-MEDIA:TYPE=SUBTITLES,LANGUAGE="en",URI="https://vod.provider.plex.tv/captions?url=https%3A%2F%2Fvod-static.plex.tv%2Fa.vtt"'
    yield case('plex','https://watch.plex.tv/watch/movie/lesson',script='fetch("https://media.fixture.test/master.m3u8");',resources={'/master.m3u8':plex,'/a.vtt':vtt})
    mpd='<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static"><Period><AdaptationSet contentType="text" lang="en" mimeType="text/vtt"><Representation><BaseURL>'+caption+'</BaseURL></Representation></AdaptationSet></Period></MPD>'
    yield case('vkvideo_mpd','https://vkvideo.ru/video-123_456',script='fetch("https://media.fixture.test/manifest.mpd");',resources={'/manifest.mpd':mpd})
    yield case('vkvideo_mpd_segmented','https://vkvideo.ru/video-123_456',script='fetch("https://media.fixture.test/manifest.mpd");',resources={'/manifest.mpd':mpd.replace('<Representation>','<SegmentTemplate media="chunk-$Number$.m4s"/><Representation>')},ready=False)
    yield case('vkvideo_mpd_dynamic','https://vkvideo.ru/video-123_456',script='fetch("https://media.fixture.test/manifest.mpd");',resources={'/manifest.mpd':mpd.replace('type="static"','type="dynamic"')},ready=False)
    yield case('vkvideo_mpd_protected','https://vkvideo.ru/video-123_456',script='fetch("https://media.fixture.test/manifest.mpd");',resources={'/manifest.mpd':mpd.replace('<Representation>','<ContentProtection schemeIdUri="urn:fixture"/><Representation>')},ready=False)
    yield case('vkvideo_mpd_malformed','https://vkvideo.ru/video-123_456',script='fetch("https://media.fixture.test/manifest.mpd");',resources={'/manifest.mpd':'<MPD><broken></MPD>'},ready=False)
    carousel='<div class="vertical-video-player-container"><video-js data-video-id="old">'+video.replace('id="v"','id="old"')+'</video-js></div><div class="vertical-video-player-container vve-is-active"><video-js id="current" data-video-id="current">'+video+'</video-js></div>'
    yield case('aljazeera_carousel','https://www.aljazeera.com/video/lesson',body=carousel,script='document.querySelector("#current").player={mediainfo:{text_tracks:[{kind:"captions",src:'+json.dumps(caption)+',srclang:"en"}]}};')
    drop={'segments':[{'startTime':1,'endTime':3,'text':'Existing caption.'},{'startTime':4,'endTime':6,'text':'Correct lesson.'}],'transcriptLocale':'en_US'}
    yield case('dropbox','https://www.dropbox.com/scl/fi/lesson/video',script='fetch("/p/transcript/lesson");',resources={'/p/transcript/lesson':drop})
    yield case('dropbox_invalid','https://www.dropbox.com/scl/fi/lesson/video',script='fetch("/p/transcript/lesson");',resources={'/p/transcript/lesson':{'segments':[{'startTime':3,'endTime':1,'text':'Invalid'}]}},ready=False)
    circle='/internal_api/courses/course/sections/section/lessons/123'
    yield case('circle_academy','https://circle-academy.circle.so/c/course/sections/section/lessons/123',script='fetch('+json.dumps(circle)+');',resources={circle:{'lesson':{'id':123,'media_transcript_id':'transcript','language':'en'}},'/media_transcripts/transcript.vtt':vtt})
    yield case('circle_academy_stale','https://circle-academy.circle.so/c/course/sections/section/lessons/124',script='fetch('+json.dumps(circle)+');',resources={circle:{'lesson':{'id':123,'media_transcript_id':'transcript'}}},ready=False)
    yield case('circle_academy_mosaic','https://circle-academy.circle.so/c/course/sections/section/lessons/123',script='fetch('+json.dumps(circle)+');',resources={circle:{'lesson':{'id':123,'webvtt_file_url':'https://captions.fixture.test/mosaic.vtt'}}},ready=False)
    move='/wefeed-h5api-bff/subject/caption'
    yield case('movebox','https://movebox.run/movies/current',script='fetch("https://h5-api.aoneroom.com'+move+'?id=123&detailPath=movies/current");',resources={move:{'data':{'captions':[{'url':caption,'lan':'en'}]}}})
    yield case('movebox_stale','https://movebox.run/movies/new',script='fetch("https://h5-api.aoneroom.com'+move+'?id=123&detailPath=movies/old");',resources={move:{'data':{'captions':[{'url':caption,'lan':'en'}]}}},ready=False)
    course={'data':{'courseItemData':{'id':'item','videoData':{'availabilityState':'ready-for-playback','videoId':'video','playbackToken':'fixture-only'}}}}
    playback={'availabilityState':'ready-for-playback','data':{'signedCaptions':[{'src':caption,'language':'en'}]}}
    rpc={'get-course-item-information':course,'get-details-to-play-fermion-saas-recorded-video':playback}
    yield case('motionmagic','https://www.themotionmagic.com/course-item?item-id=item') | {'rpc_responses':rpc}
    yield case('motionmagic_stale','https://www.themotionmagic.com/course-item?item-id=new',ready=False) | {'rpc_responses':rpc}
    yield case('motionmagic_locked','https://www.themotionmagic.com/course-item?item-id=item',ready=False) | {'rpc_responses':{'get-course-item-information':{'data':{'courseItemData':{'id':'item','videoData':{'availabilityState':'locked'}}}}}}
    yield case('vidlove','https://vidlove.cc/embed/movie/123',resources={'/movie':{'subtitles':[{'file':caption,'language':'en'}]}})
    yield case('vidlove_denied','https://vidlove.cc/embed/movie/123',resources={'/movie':{}},ready=False) | {'denied':True}
    patreon={'post':{'id':'123','attributes':{'viewer_playback_data':{'hls':'https://stream.mux.com/manifest.m3u8?token=fixture-only'}}}}
    body='<script type="application/json">'+json.dumps(patreon)+'</script>'+video
    yield case('patreon','https://www.patreon.com/posts/lesson-123',body=body,resources=hls)
    yield case('patreon_stale','https://www.patreon.com/posts/lesson-124',body=body,resources=hls,ready=False)
    drive='<div id="movie_player">'+video+'</div>'
    script='document.querySelector("#movie_player").getVideoData=()=>({video_id:"drive123"});'
    yield case('google_drive_youtube','https://youtube.googleapis.com/embed/drive123',body=drive,script=script) | {'drive_tracks':True}
    yield case('google_drive_youtube_stale','https://youtube.googleapis.com/embed/other123',body=drive,script=script,ready=False) | {'drive_tracks':True}
    yield case('loom_preview','https://www.loom.com/embed/'+loom,body='<video class="components_animatedPreviewVideo_Miy" style="width:900px;height:600px"></video>'+video.replace('id="v"','id="LoomShakaVideoPlayer"'),resources=rows[7]['resources'])
    sprite='WEBVTT\n\n00:00.000 --> 00:06.000\npreview.jpg#xywh=0,0,249,140'
    yield case('loom_storyboard','https://www.loom.com/embed/'+loom,script='fetch("https://captions.fixture.test/sprite.vtt");Object.defineProperty(document.querySelector("video"),"duration",{value:6});',resources={**rows[7]['resources'],'/sprite.vtt':sprite})
    yield case('storyboard_only','https://www.example.org/video',script='fetch("https://captions.fixture.test/sprite.vtt");Object.defineProperty(document.querySelector("video"),"duration",{value:6});',resources={'/sprite.vtt':sprite},ready=False)
    guid='00000000-0000-0000-0000-000000000001'
    other='00000000-0000-0000-0000-000000000002'
    route='https://app.pluralsight.com/ilx/video-courses/'+guid+'/'+guid+'/'+guid
    for suffix,clip,file,ready in [('',guid,'master',True),('_stale',other,'master',False),('_variant',guid,'audio',False)]:
        payload=base64.urlsafe_b64encode(json.dumps({'path':'clips2/'+clip+'/hls/'+file+'.m3u8'}).encode()).decode().rstrip('=')
        path='/video/delivery/api/v1/manifests/header.'+payload+'.signature.m3u8'
        yield case('pluralsight'+suffix,route,script='fetch('+json.dumps(path)+');',resources={path:master,**hls},ready=ready)
    absolute={'/manifest.m3u8':master,'/sub.m3u8':'#EXTM3U\n#EXTINF:4,\na.vtt\n#EXTINF:4,\nb.vtt\n#EXT-X-ENDLIST','/a.vtt':vtt,'/b.vtt':vtt}
    for suffix,duration,ready in [('',8,True),('_duration_missing',None,False),('_out_of_range',1,False)]:
        script='fetch("https://media.fixture.test/manifest.m3u8");'
        if duration is not None:
            script+='Object.defineProperty(document.querySelector("video"),"duration",{value:'+str(duration)+'});'
        yield case('medbridge_course'+suffix,'https://www.medbridge.com/player/course/lesson',script=script,resources=absolute,ready=ready)
    jwbody='<div class="jwplayer" id="owned">'+video+'</div>'
    jwscript='window.jwplayer=()=>({getContainer:()=>document.querySelector("#owned"),getPlaylistItem:()=>({tracks:[],sources:[]}),getCaptionsList:()=>[{id:"off"},{id:'+json.dumps(caption)+',label:"English"}],getCurrentCaptions:()=>1});'
    yield case('coindesk_jwplayer','https://www.coindesk.com/videos/lesson',body=jwbody,script=jwscript)
    yield case('jwplayer_hosted','https://cdn.jwplayer.com/players/example.html',body=jwbody,script=jwscript)
    yield case('jwplayer_foreign','https://www.coindesk.com/videos/lesson',body=jwbody+'<div id="foreign"></div>',script=jwscript.replace('querySelector("#owned")','querySelector("#foreign")'),ready=False)
    reuters='window.jwplayer=()=>({getContainer:()=>document.querySelector("#owned"),getPlaylistItem:()=>({sources:[{file:"https://media.fixture.test/manifest.m3u8"}]})});'
    yield case('reuters_jwplayer','https://www.reuters.com/video/watch/lesson',body=jwbody,script=reuters,resources=hls)
    for family,url in [('mindvalley','https://home.mindvalley.com/quests/lesson'),('domestika','https://www.domestika.org/en/courses/course/units/lesson')]:
        sdk='document.querySelector("video").player={currentSource:()=>({src:"https://media.fixture.test/manifest.m3u8?token=current"})};'
        yield case(family,url,script=sdk,resources=hls)
        yield case(family+'_stale',url,script=sdk.replace('manifest.m3u8','new.m3u8')+'fetch("https://media.fixture.test/manifest.m3u8");',resources=hls,ready=False)
        yield case(family+'_denied',url,script=sdk,resources=hls,ready=False) | {'denied':True}
        second=video.replace('id="v"','id="other"').replace('width:800px','width:1000px')
        # Another lesson can be larger; the actually playing one remains selected.
        script='const chosen=document.querySelector("#v");Object.defineProperty(chosen,"paused",{value:false});chosen.player={currentSource:()=>({src:"https://media.fixture.test/manifest.m3u8"})};'
        yield case(family+'_multiple',url,body=second+video,script=script,resources=hls)
    mind='https://home.mindvalley.com/quests/lesson'
    source='<source src="https://assets.mindvalley.com/api/v1/assets/12345678.mp4"><source src="https://assets.mindvalley.com/api/v1/assets/87654321.vtt">'
    mp4video=video.replace('</video>',source+'</video>')
    yield case('mindvalley_mp4',mind,body=mp4video,resources={'/api/v1/assets/87654321.vtt':vtt})
    yield case('mindvalley_mp4_storyboard',mind,body=mp4video,resources={'/api/v1/assets/87654321.vtt':sprite},ready=False)
    yield case('mindvalley_mp4_ambiguous',mind,body=mp4video.replace('</video>','<source src="https://assets.mindvalley.com/api/v1/assets/99999999.vtt"></video>'),resources={'/api/v1/assets/87654321.vtt':vtt},ready=False)
    yield case('mindvalley_mp4_foreign',mind,body=mp4video.replace('assets.mindvalley.com','example.org'),ready=False)
    query='/i/api/graphql/fixture/TweetDetail'
    poster='https://pbs.twimg.com/ext_tw_video_thumb/1234567890123456789/pu/img/sample.jpg'
    twitter_video=video.replace('<video','<video poster="'+poster+'"')
    manifest='https://video.twimg.com/ext_tw_video/1234567890123456789/pu/pl/master.m3u8'
    media={'video_info':{'variants':[{'content_type':'application/x-mpegURL','url':manifest}]}}
    response={'data':{'tweet':{'legacy':{'extended_entities':{'media':[media]}}}}}
    resources={query:response,'/ext_tw_video/1234567890123456789/pu/pl/master.m3u8':master,**hls}
    for name,url in [('twitter','https://x.com/user/status/987654321'),('twitter_legacy','https://twitter.com/user/status/987654321')]:
        yield case(name,url,body=twitter_video,script='fetch('+json.dumps(query)+');',resources=resources)
    yield case('twitter_stale','https://x.com/user/status/987654321',body=twitter_video.replace('thumb/1234567890123456789/','thumb/9999999999999999999/'),script='fetch('+json.dumps(query)+');',resources=resources,ready=False)
    yield case('twitter_multiple','https://x.com/home',body=twitter_video+video.replace('id="v"','id="other"'),script='fetch('+json.dumps(query)+');',resources=resources)
    unified={'binding_values':[{'key':'unified_card','value':{'string_value':json.dumps({'media_entities':{'clip':media}})}}]}
    yield case('twitter_card','https://x.com/user/status/987654321',body=twitter_video,script='fetch('+json.dumps(query)+');',resources={**resources,query:unified})
    yield case('twitter_denied','https://x.com/user/status/987654321',body=twitter_video,script='fetch('+json.dumps(query)+');',resources=resources,ready=False) | {'denied':True}
    facebook='https://www.facebook.com/watch/?v=123456789012345'
    fbtrack='https://scontent.fixture.fbcdn.net/captions.vtt'
    props={'video':{'videoFBID':'123456789012345','sideLoadCaptionsUrl':fbtrack}}
    script='document.querySelector("video").__reactProps$fixture='+json.dumps(props)+';'
    yield case('facebook',facebook,script=script,resources={'/captions.vtt':vtt})
    yield case('facebook_denied',facebook,script=script,resources={'/captions.vtt':vtt},ready=False) | {'denied':True}
    ambiguous={'current':props['video'],'other':{'videoFBID':'999999999999999','sideLoadCaptionsUrl':fbtrack}}
    yield case('facebook_ambiguous',facebook,script='document.querySelector("video").__reactProps$fixture='+json.dumps(ambiguous)+';',resources={'/captions.vtt':vtt},ready=False)
    yield case('facebook_foreign_url',facebook,script=script.replace('scontent.fixture.fbcdn.net','example.org'),ready=False)
    yield case('facebook_getter',facebook,script='document.querySelector("video").__reactProps$fixture={video:{videoFBID:"123456789012345",get sideLoadCaptionsUrl(){throw Error("Must not execute page getter")}}};',ready=False)
    yield case('facebook_changed',facebook,script=script,resources={'/captions.vtt':vtt},ready=False) | {'change_on_path':'/captions.vtt','change_script':'document.querySelector("video").__reactProps$fixture.video.videoFBID="999999999999999";'}
    yield case('twitter_changed','https://x.com/user/status/987654321',body=twitter_video,script='fetch('+json.dumps(query)+');',resources=resources,ready=False) | {'change_on_path':'/ext_tw_video/1234567890123456789/pu/pl/master.m3u8','change_script':'document.querySelector("video").poster="https://pbs.twimg.com/ext_tw_video_thumb/9999999999999999999/pu/img/new.jpg";'}
