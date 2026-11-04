"""Firefox MV3 picker selection/persistence without backend or GPU calls."""
import json
from pathlib import Path
import uuid

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.firefox.service import Service

ROOT = Path(__file__).resolve().parents[1]


def main():
    options = webdriver.FirefoxOptions()
    options.binary_location = 'C:/Program Files/Mozilla Firefox/firefox.exe'
    options.add_argument('-headless')
    identity = str(uuid.uuid4())
    options.set_preference('extensions.webextensions.uuids', json.dumps({'auvirel@protein.local':identity}))
    report = {'scope':'Actual Firefox MV3 settings; no backend/GPU calls','checks':[]}
    driver = webdriver.Firefox(options=options, service=Service(service_args=['--allow-system-access']))
    try:
        driver.install_addon(str(ROOT/'dist/vocalm-firefox.zip'), temporary=True)
        driver.set_window_size(460,820)
        driver.get(f'moz-extension://{identity}/options.html?embedded=1')
        WebDriverWait(driver,20).until(lambda d:len(d.find_elements(By.CSS_SELECTOR,'#voice option'))==84)
        driver.execute_script('document.querySelector(".voice-picker").closest("details").open=true')
        driver.find_element(By.CSS_SELECTOR,'.voice-picker-toggle').click()
        assert len(driver.find_elements(By.CSS_SELECTOR,'section[data-gender=M] [data-voice]'))==6
        assert len(driver.find_elements(By.CSS_SELECTOR,'section[data-gender=F] [data-voice]'))==6
        assert driver.execute_script('return document.documentElement.scrollWidth<=innerWidth')
        driver.find_element(By.CSS_SELECTOR,'[data-voice=vi-ngoc-linh]').click()
        WebDriverWait(driver,10).until(lambda d:d.execute_async_script('const done=arguments[arguments.length-1];browser.storage.local.get("settings").then(v=>done(v.settings.voiceId))')=='vi-ngoc-linh')
        driver.refresh()
        WebDriverWait(driver,20).until(lambda d:d.find_element(By.ID,'voice').get_attribute('value')=='vi-ngoc-linh')
        driver.execute_script('document.querySelector(".voice-picker").closest("details").open=true')
        driver.find_element(By.CSS_SELECTOR,'.voice-picker-toggle').click()
        assert driver.find_element(By.CSS_SELECTOR,'[data-voice=vi-ngoc-linh]').get_attribute('aria-pressed')=='true'
        report.update(passed=True,browser_version=driver.capabilities.get('browserVersion'))
        report['checks']=['Six male/six female columns fit narrow Firefox settings','Selection saves exact voice ID and survives reload with correct highlight']
    except Exception as error:
        report.update(passed=False,error=str(error)[:1000]);raise
    finally:
        driver.quit()
        (ROOT/'research/voice-picker-firefox.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
        print(json.dumps(report))


if __name__=='__main__':
    main()
