"""Build separate MV3 packages and local-only reference assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--local-assets', action='store_true', help='Include user-supplied assets only in ignored local builds')
    args = parser.parse_args()
    source = ROOT / 'assets/imported'
    converted = ROOT / '.private/converted-voices'
    converted.mkdir(parents=True, exist_ok=True)
    presets, bgm = [], []
    if args.local_assets:
        presets = json.loads((source / 'presets.json').read_text(encoding='utf-8'))
        for preset in presets:
            original = source / preset['path']
            target = converted / (hashlib.sha256(original.read_bytes()).hexdigest() + '.wav')
            if not target.exists():
                subprocess.run(['ffmpeg', '-nostdin', '-v', 'error', '-i', str(original), '-t', '30', '-ac', '1', '-ar', '24000', '-c:a', 'pcm_s16le', str(target)], check=True, timeout=30)
            preset['path'] = 'voices/' + target.name
        bgm = [{'id': path.stem, 'name': path.stem.replace('-', ' ').replace('_', ' ').title(), 'path': 'bgm/' + path.name} for path in sorted((source / 'bgm').glob('*.ogg'))]
    shared = {
        'manifest_version': 3, 'name': 'Vocalm', 'version': '0.6.1', 'description': 'Contextual subtitles, private single-voice dubbing and video study tools.',
        'permissions': ['storage', 'scripting', 'nativeMessaging', 'activeTab'], 'host_permissions': ['https://*/*'],
        'action': {'default_popup': 'popup.html', 'default_title': 'Vocalm'},
        'options_ui': {'page': 'options.html', 'open_in_tab': False},
        'icons': {str(size): f'icons/icon-{size}.png' for size in (16, 32, 48, 128)},
        'content_scripts': [
            {'matches': ['https://*.youtube.com/*', 'https://youtube.com/*', 'https://*.youtube-nocookie.com/*'], 'js': ['lib/captions.js', 'lib/media.js', 'youtube-main.js'], 'run_at': 'document_start', 'world': 'MAIN', 'all_frames': True},
            {'matches': ['https://*/*'], 'js': ['lib/captions.js', 'lib/sites.js', 'lib/media.js', 'lib/subtitle-formats.js', 'lib/bilibili.js', 'lib/platform-captions.js', 'lib/platform-readers.js', 'multisite-main.js'], 'run_at': 'document_start', 'world': 'MAIN', 'all_frames': True},
            {'matches': ['https://*/*'], 'js': ['lib/core.js', 'lib/sites.js', 'lib/media.js', 'lib/window-queue.js', 'lib/audio.js', 'lib/sidebar.js', 'lib/voice-picker.js', 'lib/player-ui.js', 'content.js'], 'run_at': 'document_idle', 'all_frames': True}],
        'web_accessible_resources': [{'resources': ['content.css', 'voice-picker.css', 'player.css', 'sidebar.css', 'sidebar-page.css', 'assets/bgm/*', 'icons/icon-*.png'], 'matches': ['https://*/*']}],
        'content_security_policy': {'extension_pages': "script-src 'self'; object-src 'none'; base-uri 'none'"},
    }
    for browser in ('chrome', 'firefox'):
        output = ROOT / 'dist' / browser
        if output.exists():
            shutil.rmtree(output)
        shutil.copytree(ROOT / 'extension', output)
        manifest = dict(shared)
        if browser == 'chrome':
            manifest['minimum_chrome_version'] = '120'
            manifest['background'] = {'service_worker': 'background.js'}
        else:
            manifest['background'] = {'scripts': ['lib/core.js', 'lib/cache.js', 'lib/captions.js', 'lib/media.js', 'lib/voice-transport.js', 'background.js']}
            manifest['browser_specific_settings'] = {'gecko': {'id': 'auvirel@protein.local', 'strict_min_version': '128.0', 'data_collection_permissions': {'required': ['websiteContent', 'authenticationInfo']}}}
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        (output / 'assets/voices').mkdir(parents=True)
        (output / 'assets/presets.json').write_text(json.dumps(presets, ensure_ascii=False), encoding='utf-8')
        (output / 'assets/bgm.json').write_text(json.dumps(bgm), encoding='utf-8')
        for preset in presets:
            shutil.copyfile(converted / Path(preset['path']).name, output / 'assets' / preset['path'])
        if args.local_assets:
            shutil.copytree(source / 'bgm', output / 'assets/bgm')
        shutil.make_archive(str(ROOT / 'dist' / ('auvirel-' + browser)), 'zip', output)
        shutil.copyfile(ROOT / 'dist' / ('auvirel-' + browser + '.zip'),
                        ROOT / 'dist' / ('veloa-' + browser + '.zip'))
        shutil.copyfile(ROOT / 'dist' / ('auvirel-' + browser + '.zip'),
                        ROOT / 'dist' / ('vocalm-' + browser + '.zip'))
        print(browser, len(presets), 'voices;', len(bgm), 'BGM; build complete')


if __name__ == '__main__':
    main()
