"""Build separate MV3 packages and local-only reference assets."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import zlib

ROOT = Path(__file__).resolve().parents[1]


def icon(size):
    def chunk(kind, value):
        return struct.pack('>I', len(value)) + kind + value + struct.pack('>I', zlib.crc32(kind + value))
    rows = bytearray()
    segments = [(33, 48, 84, 48), (45, 79, 96, 79)]
    def pixel(px, py):
        corner = max(abs(px-64)-29, 0)**2 + max(abs(py-64)-29, 0)**2
        if corner > 34**2:
            return (0, 0, 0, 0)
        distance = min(((px-max(x1, min(x2, px)))**2+(py-y1)**2)**.5
                       for x1, y1, x2, _ in segments)
        if distance < 6:
            return (255, 255, 255, 255) if py < 64 else (195, 201, 210, 255)
        t = (px+py)/256
        return (round(54-29*t), round(57-30*t), round(64-32*t), 255)
    # Supersampling keeps the rounded mark legible at toolbar sizes.
    for y in range(size):
        rows.append(0)
        for x in range(size):
            samples = [pixel((x+(sx+.5)/4)*128/size, (y+(sy+.5)/4)*128/size)
                       for sy in range(4) for sx in range(4)]
            opaque = [sample for sample in samples if sample[3]]
            if not opaque:
                rows.extend((0, 0, 0, 0))
            else:
                rows.extend([round(sum(sample[c] for sample in opaque)/len(opaque)) for c in range(3)]
                            + [round(255*len(opaque)/16)])
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(rows)) + chunk(b'IEND', b'')


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
        'manifest_version': 3, 'name': 'Veloa', 'version': '0.2.1', 'description': 'Contextual subtitles, private single-voice dubbing and video study tools.',
        'permissions': ['storage', 'scripting', 'nativeMessaging', 'activeTab'], 'host_permissions': ['https://*/*'],
        'action': {'default_popup': 'popup.html', 'default_title': 'Veloa'},
        'options_ui': {'page': 'options.html', 'open_in_tab': False},
        'icons': {str(size): f'icons/icon-{size}.png' for size in (16, 32, 48, 128)},
        'content_scripts': [
            {'matches': ['https://www.youtube.com/*', 'https://m.youtube.com/*', 'https://youtube.com/*'], 'js': ['lib/captions.js', 'youtube-main.js'], 'run_at': 'document_start', 'world': 'MAIN'},
            {'matches': ['https://*/*'], 'js': ['lib/core.js', 'lib/audio.js', 'lib/sidebar.js', 'content.js'], 'run_at': 'document_idle', 'all_frames': True}],
        'web_accessible_resources': [{'resources': ['content.css', 'sidebar.css', 'sidebar-page.css', 'assets/bgm/*'], 'matches': ['https://*/*']}],
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
            manifest['background'] = {'scripts': ['lib/core.js', 'lib/cache.js', 'lib/captions.js', 'background.js']}
            manifest['browser_specific_settings'] = {'gecko': {'id': 'auvirel@protein.local', 'strict_min_version': '128.0', 'data_collection_permissions': {'required': ['websiteContent', 'authenticationInfo']}}}
        (output / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        for size in (16, 32, 48, 128):
            (output / f'icons/icon-{size}.png').write_bytes(icon(size))
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
        print(browser, len(presets), 'voices;', len(bgm), 'BGM; build complete')


if __name__ == '__main__':
    main()
