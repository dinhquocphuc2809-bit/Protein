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
