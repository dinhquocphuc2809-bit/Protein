"""Load the actual Firefox MV3 package in an isolated temporary Firefox profile."""
import base64
import json
from pathlib import Path
import re
import time
import uuid

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.service import Service

ROOT = Path(__file__).resolve().parents[1]


def main():
    output = ROOT / '.private/firefox-qa'
    output.mkdir(parents=True, exist_ok=True)
    options = webdriver.FirefoxOptions()
    options.binary_location = 'C:/Program Files/Mozilla Firefox/firefox.exe'
    options.add_argument('-headless')
    extension_uuid = str(uuid.uuid4())
    options.set_preference('extensions.webextensions.uuids', json.dumps({'auvirel@protein.local': extension_uuid}))
    options.set_preference('media.autoplay.default', 0)
    options.set_preference('media.autoplay.blocking_policy', 0)
    options.set_preference('extensions.autoDisableScopes', 0)
    report = {'checks': []}
    driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access']))
    try:
        identity = driver.install_addon(str(ROOT / 'dist/veloa-firefox.zip'), temporary=True)
        origin = 'moz-extension://' + extension_uuid + '/'
        driver.set_window_size(1440, 1000)
        driver.get(origin + 'options.html')
        wait = WebDriverWait(driver, 30)
        wait.until(lambda d: len(d.find_elements(By.CSS_SELECTOR, '#voice option')) > 0)
        def message(value):
            result = driver.execute_async_script('const done=arguments[arguments.length-1]; browser.runtime.sendMessage(arguments[0]).then(done,e=>done({ok:false,error:e.message}));', value)
            if not result.get('ok'):
                raise RuntimeError(result.get('error', 'Extension request failed'))
            return result.get('value')
        endpoint = json.loads((ROOT / '.private/public-endpoint.json').read_text())['url']
        ticket = json.loads((ROOT / '.private/owner-ticket.json').read_text())['code']
        proxy = json.loads((ROOT / '.private/modal-4-proxy.json').read_text())
        voice = re.search(r'https://[^\s]+\.modal\.run', (ROOT / '.private/tts-deploy.log').read_text(encoding='utf-16'))[0]
        message({'type': 'activate', 'backend': endpoint, 'code': ticket})
        message({'type': 'connectVoice', 'endpoint': voice, 'id': proxy['Modal-Key'], 'secret': proxy['Modal-Secret']})
        driver.save_screenshot(str(output / 'options.png'))
        report['checks'].append('Firefox MV3 background scripts, presets, real ticket and Modal authentication')
        driver.get('https://example.org/')
        audio = base64.b64encode((ROOT / 'assets/imported/presets/vietnamese/Dang-Khoa.wav').read_bytes()).decode()
        driver.execute_script('''document.title='Auvirel Firefox acceptance';document.body.style.cssText='margin:40px;background:#20303d;color:white';
          const v=document.createElement('video');v.controls=true;v.style.cssText='width:850px;height:480px;background:#0c1a24';
          v.src=URL.createObjectURL(new Blob([Uint8Array.from(atob(arguments[0]),c=>c.charCodeAt(0))],{type:'audio/wav'}));
          const t=v.addTextTrack('subtitles','English','en');t.mode='hidden';t.addCue(new VTTCue(0,3,'A cache stores results for later use.'));t.addCue(new VTTCue(3,6.2,'Changing the voice reuses the translation.'));document.body.prepend(v);''', audio)
        host = wait.until(lambda d: d.find_element(By.ID, 'auvirel-surface'))
        root = host.shadow_root
        time.sleep(2)
        root.find_element(By.CSS_SELECTOR, '.launcher').click()
        time.sleep(.5)
        root.find_element(By.ID, 'start').click()
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            state = root.find_element(By.ID, 'state').text
            if 'Ready. Press play' in state:
                break
            if root.find_element(By.CSS_SELECTOR, '.status').get_attribute('data-state') == 'error':
                raise RuntimeError(state)
            time.sleep(.5)
        else:
            raise TimeoutError('Firefox subtitle preparation timed out: '+state)
        assert len(root.find_elements(By.CSS_SELECTOR, '.cue')) == 2
        driver.save_screenshot(str(output / 'panel.png'))
        root.find_element(By.CSS_SELECTOR, '.grove-ready').click()
        states = set()
        deadline = time.monotonic()+180
        while time.monotonic() < deadline:
            state = root.find_element(By.CSS_SELECTOR, '.status').get_attribute('data-state')
            states.add(state)
            if state == 'error':
                raise RuntimeError(root.find_element(By.ID, 'state').text)
            if driver.execute_script('return document.querySelector("video").ended'):
                break
            time.sleep(.3)
        else:
            raise TimeoutError('Firefox dubbing did not finish')
        assert 'playing' in states
        report['checks'].append('Firefox TextTrack acquisition, real translation and real dubbed audio playback to end')
        root.find_element(By.ID, 'stop').click()
        report['passed'] = True
        report['browser_version'] = driver.capabilities['browserVersion']
    except Exception as error:
        report.update(passed=False, error=str(error)[:1200])
        raise
    finally:
        driver.quit()
        (ROOT / 'research/browser-firefox.json').write_text(json.dumps(report, indent=2))
    print(json.dumps(report))


if __name__ == '__main__':
    main()
