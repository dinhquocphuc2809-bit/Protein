"""Firefox MV3 MAIN-world and open-shadow acquisition with labelled local cues."""
import json
from pathlib import Path
import uuid

from selenium import webdriver
from selenium.webdriver.firefox.service import Service

ROOT = Path(__file__).resolve().parents[1]


def main():
    options = webdriver.FirefoxOptions()
    options.binary_location = 'C:/Program Files/Mozilla Firefox/firefox.exe'
    options.add_argument('-headless')
    identity = str(uuid.uuid4())
    options.set_preference('extensions.webextensions.uuids', json.dumps({'auvirel@protein.local': identity}))
    report = {'scope': 'Actual Firefox MV3 package; labelled local caption fixtures on example.org; no providers', 'checks': []}
    driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access']))
    try:
        driver.install_addon(str(ROOT / 'dist/veloa-firefox.zip'), temporary=True)
        driver.set_window_size(1440, 1000)
        driver.get('https://example.org/')
        driver.switch_to.new_window('tab')
        driver.get('moz-extension://' + identity + '/popup.html')
        driver.set_script_timeout(35)
        for shadow in [False, True]:
            result = driver.execute_async_script('''const done=arguments[arguments.length-1],shadow=arguments[0];
                (async()=>{const tab=(await browser.tabs.query({})).find(t=>t.url==='https://example.org/');
                    return await browser.scripting.executeScript({target:{tabId:tab.id},world:'MAIN',args:[shadow],func:async shadow=>{
                        document.body.replaceChildren();const host=document.createElement('div');document.body.append(host);
                        const root=shadow?host.attachShadow({mode:'open'}):host;
                        const v=document.createElement('video');v.style.cssText='width:800px;height:450px';root.append(v);
                        Object.defineProperty(v,'duration',{value:6});
                        const track=v.addTextTrack('subtitles','English','en');track.mode='disabled';
                        track.addCue(new VTTCue(1,3,'Firefox caption fixture.'));track.addCue(new VTTCue(4,6,'Full timing.'));
                        const result=await globalThis.__veloaSiteCaptions?.acquire({href:location.href,src:''});
                        return {result,mode:track.mode};
                    }});
                })().then(done,e=>done({error:e.message}));''', shadow)
            assert isinstance(result, list), result
            value = result[0]['result']
            assert value['result']['state'] == 'ready', value
            assert value['result']['cues'][0] == {'start': 1, 'end': 3, 'text': 'Firefox caption fixture.'}
            assert value['mode'] == 'disabled'
            report['checks'].append(('open shadow' if shadow else 'DOM') + ': full native cues and original CC mode restored')
        result=driver.execute_async_script('''const done=arguments[arguments.length-1];
          (async()=>{const tab=(await browser.tabs.query({})).find(t=>t.url==='https://example.org/');
            return await browser.scripting.executeScript({target:{tabId:tab.id},world:'MAIN',func:()=>{
              const F=VeloaSubtitleFormats;
              const xml='<MPD xmlns="urn:mpeg:dash:schema:mpd:2011"><BaseURL>https://captions.test/base/</BaseURL><Period><AdaptationSet mimeType="text/vtt" lang="en"><BaseURL>lesson.vtt</BaseURL><Representation id="en"/></AdaptationSet></Period></MPD>';
              const tracks=F.mpd(xml,'https://media.test/master.mpd');
              const protectedTracks=F.mpd(xml.replace('<Representation','<ContentProtection/><Representation'),'https://media.test/master.mpd');
              let rejected=false;try{F.mpd(xml.replace('<MPD ','<MPD type="dynamic" '),'https://media.test/master.mpd')}catch{rejected=true}
              return {tracks,protectedTracks,rejected,reader:typeof VocalmReaders.discover};
            }});
          })().then(done,e=>done({error:e.message}));''')
        assert isinstance(result,list),result
        value=result[0]['result']
        assert value['tracks']==[{'url':'https://captions.test/base/lesson.vtt','language':'en'}],value
        assert value['protectedTracks']==[] and value['rejected'] and value['reader']=='function',value
        report['checks'].append('DASH inherited BaseURL; reject protected/dynamic tracks; reader module loaded')
        result=driver.execute_async_script('''const done=arguments[arguments.length-1];
          (async()=>{const tab=(await browser.tabs.query({})).find(t=>t.url==='https://example.org/');
            return await browser.scripting.executeScript({target:{tabId:tab.id},world:'MAIN',func:()=>{
              let getterCalls=0;const props={videoFBID:'123456789012345',sideLoadCaptionsUrl:'https://scontent.test.fbcdn.net/captions.vtt'};
              Object.defineProperty(props,'danger',{enumerable:true,get(){getterCalls++;throw Error('Do not execute')}});
              const video={__reactProps$fixture:{video:props},querySelectorAll:()=>[],parentElement:null};
              const tracks=VocalmReaders.sourceCaptions(video,'https://www.facebook.com/watch/?v=123456789012345');
              const poster={poster:'https://pbs.twimg.com/ext_tw_video_thumb/12345/pu/img/preview.jpg'};
              const allowed=VocalmReaders.manifestAllowed('https://video.twimg.com/ext_tw_video/12345/pu/pl/master.m3u8',poster,'https://x.com/user/status/999');
              const stale=VocalmReaders.manifestAllowed('https://video.twimg.com/ext_tw_video/99999/pu/pl/master.m3u8',poster,'https://x.com/user/status/999');
              return {tracks,getterCalls,allowed,stale};
            }});
          })().then(done,e=>done({error:e.message}));''')
        assert isinstance(result,list),result
        value=result[0]['result']
        assert len(value['tracks'])==1 and value['getterCalls']==0 and value['allowed'] and not value['stale'],value
        report['checks'].append('Social readers: exact Twitter media ownership; Facebook descriptors without executing getters')
        result=driver.execute_async_script('''const done=arguments[arguments.length-1];
          (async()=>{const tab=(await browser.tabs.query({})).find(t=>t.url==='https://example.org/');
            return await browser.scripting.executeScript({target:{tabId:tab.id},world:'MAIN',func:()=>{
              const route=VeloaMedia.biliInternationalRoute('https://www.bilibili.tv/en/play/37976/10344255');
              const ass='[Script Info]\\n[Events]\\nFormat: Layer, Start, End, Style, Text\\nDialogue: 0,0:00:01.00,0:00:03.00,Default,Caption, with comma.';
              const captions=VeloaSubtitleFormats.parse(ass);
              const id='6961737553342991651';
              const tracks=VocalmReaders.douyinTracks({aweme_detail:{aweme_id:id,video:{cla_info:{caption_infos:[{url:'https://media.test/caption.vtt',lang:'zh'}]}}}},id,'https://www.douyin.com/video/'+id);
              const timing=VocalmPlatforms.parse(JSON.stringify({utterances:[{start_time:1000,end_time:3000,text:'Caption.'}]}),'douyin-utterances');
              return {route,captions,tracks,timing};
            }});
          })().then(done,e=>done({error:e.message}));''')
        assert isinstance(result,list),result
        value=result[0]['result']
        assert value['route']['id']=='10344255' and value['captions']==[{'start':1,'end':3,'text':'Caption, with comma.'}],value
        assert len(value['tracks'])==1 and value['timing']==[{'start':1,'end':3,'text':'Caption.'}],value
        report['checks'].append('Priority readers: Bilibili international identity/ASS; Douyin exact owner/millisecond timing')
        report['browser'] = driver.capabilities['browserVersion']
        report['passed'] = True
    except Exception as error:
        report.update(passed=False, error=str(error)[:1000])
        raise
    finally:
        driver.quit()
        (ROOT / 'research/multisite-firefox.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report))


if __name__ == '__main__':
    main()
