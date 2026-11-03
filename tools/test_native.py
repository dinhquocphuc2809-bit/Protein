"""Exercise the real native host through a loaded extension, without printing secrets."""
import argparse
import json
from pathlib import Path
import re

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start', action='store_true')
    args = parser.parse_args()
    with sync_playwright() as playwright:
        extension = ROOT / 'dist/chrome'
        context = playwright.chromium.launch_persistent_context(str(ROOT / '.private/native-qa-profile'), channel='chromium', headless=True,
            args=[f'--disable-extensions-except={extension}', f'--load-extension={extension}'])
        worker = context.service_workers[0] if context.service_workers else context.wait_for_event('serviceworker')
        page = context.new_page()
        page.goto(worker.url.rsplit('/', 1)[0] + '/options.html')
        message = {'type': 'deployStatus'}
        if args.start:
            lines = [line for line in (ROOT.parent / 'modal.com.txt').read_text(encoding='utf-8-sig').splitlines() if line.strip()]
            message = {'type': 'deployVoice', 'command': lines[3], 'gpu': 'T4'}
        response = page.evaluate('(message) => chrome.runtime.sendMessage(message)', message)
        if not response.get('ok'):
            raise RuntimeError(response.get('error', 'Native host failed'))
        result = response['value']
        report = {key: result.get(key) for key in ('state', 'stage', 'error') if key in result}
        if result.get('state') == 'done':
            conf = page.evaluate('() => chrome.runtime.sendMessage({type:"publicSettings"})')
            report['voice_ready'] = conf['value']['voiceReady']
        (ROOT / 'research/native-bridge.json').write_text(json.dumps(report, indent=2))
        print(json.dumps(report))
        context.close()


if __name__ == '__main__':
    main()
