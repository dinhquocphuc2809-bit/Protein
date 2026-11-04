"""Authorized Udemy caption-only probe; never serialize cookies or signed URLs."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
import re
import tempfile
import time
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]


def cookies_from_export(path):
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    rows = data if isinstance(data, list) else data.get("cookies", [])
    result = []
    for row in rows:
        domain = str(row.get("domain", "")).lstrip(".").lower()
        if domain != "udemy.com" and not domain.endswith(".udemy.com"):
            continue
        if not row.get("name") or not isinstance(row.get("value"), str):
            continue
        cookie = {key: row[key] for key in ("name", "value", "domain", "path")}
        cookie.update(secure=bool(row.get("secure")), httpOnly=bool(row.get("httpOnly")))
        cookie["sameSite"] = {"strict": "Strict", "lax": "Lax", "no_restriction": "None", "none": "None"}.get(str(row.get("sameSite", "")).lower(), "Lax")
        if not row.get("session") and row.get("expirationDate"):
            cookie["expires"] = float(row["expirationDate"])
            if cookie["expires"] <= time.time():
                continue
        result.append(cookie)
    if not result:
        raise ValueError("No current Udemy cookies in the supplied export")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cookies", required=True, type=Path)
    parser.add_argument("--url", required=True)
    parser.add_argument("--headed", action="store_true")
    parser.add_argument("--browser", choices=["chromium", "chrome"], default="chromium")
    args = parser.parse_args()
    address = urlsplit(args.url)
    if address.scheme != "https" or address.hostname != "www.udemy.com" or not re.search(r"/learn/lecture/\d+", address.path):
        parser.error("Expected an HTTPS www.udemy.com lecture URL")
    report = {"scope": "Authorized live Udemy; actual packaged MV3 caption acquisition; no ASR, translation or GPU calls", "at": datetime.now(timezone.utc).isoformat(), "headed": args.headed, "browser": args.browser, "lecture_path": address.path, "network": [], "checks": []}
    if args.browser == "chrome":
        report['scope'] = 'Authorized live Udemy in installed Chrome; source acquisition probe, not packaged MV3 acceptance; no paid providers'
    private = ROOT / ".private/udemy-live"
    private.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p, tempfile.TemporaryDirectory(prefix="profile-", dir=private) as profile:
        extension = ROOT / "dist/chrome"
        context = p.chromium.launch_persistent_context(profile, channel=args.browser, headless=not args.headed,
            args=[f"--disable-extensions-except={extension}", f"--load-extension={extension}"] if args.browser == 'chromium' else [], viewport={"width": 1440, "height": 1000})
        try:
            context.add_cookies(cookies_from_export(args.cookies))
            worker = None
            if args.browser == 'chromium':
                worker = context.service_workers[0] if context.service_workers else context.wait_for_event("serviceworker")
                report["extension_version"] = worker.evaluate("chrome.runtime.getManifest().version")
            else:
                scripts=['lib/captions.js','lib/sites.js','lib/media.js','lib/subtitle-formats.js','lib/bilibili.js','lib/platform-captions.js','multisite-main.js']
                context.add_init_script(script='\n;\n'.join((ROOT/'extension'/name).read_text(encoding='utf-8') for name in scripts))
            page = context.new_page()

            def observe(response):
                parsed = urlsplit(response.url)
                if parsed.hostname == 'www.udemy.com' and parsed.path.startswith('/api-2.0/'):
                    report['network'].append({'kind': 'api', 'path': parsed.path, 'status': response.status})
                if parsed.hostname and parsed.hostname.endswith("udemy.com") and re.search(r"/lectures/\d+/?$", parsed.path):
                    entry = {"kind": "lecture_metadata", "path": parsed.path, "status": response.status}
                    report["network"].append(entry)
                    try:
                        data = response.json()
                        entry.update(lecture_id=data.get("id"), asset_id=data.get("asset", {}).get("id"), caption_count=len(data.get("asset", {}).get("captions", [])))
                    except Exception:
                        entry["json"] = False
                elif re.search(r"\.(vtt|srt)(?:$)", parsed.path, re.I):
                    report["network"].append({"kind": "caption", "host": parsed.hostname, "status": response.status})

            page.on("response", observe)
            response = page.goto(args.url, wait_until="domcontentloaded", timeout=45000)
            report["http_status"] = response.status if response else None
            try:
                page.wait_for_selector("video", state="attached", timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(4000)
            report["page"] = page.evaluate("""()=>({path:location.pathname,videoCount:document.querySelectorAll('video').length,
                loginForm:!!document.querySelector('input[name=email],input[name=password]'),
                challenge:!!document.querySelector('#challenge-running,#challenge-form,iframe[src*="challenges.cloudflare.com"]'),
                title:document.title.slice(0,100)})""")
            page.screenshot(path=str(private / 'page.png'), full_page=False)
            (private / 'page-text.txt').write_text(page.locator('body').inner_text()[:16000], encoding='utf-8')
            tab = worker.evaluate("async url=>(await chrome.tabs.query({})).find(t=>t.url===url)?.id", page.url) if worker else None
            if not worker:
                result=page.evaluate('''async()=>{
                  const v=globalThis.VeloaMedia?.videos()[0];if(!v)return {state:'no-player'};
                  v.pause();const r=await __veloaSiteCaptions.acquire({href:location.href,src:VeloaMedia.source(v)});
                  return {state:r.state,cues:r.cues?.length||0,language:r.language,first:r.cues?.[0]?.start,last:r.cues?.at(-1)?.end};
                }''')
                report['checks'].append({'name':'source_probe','frames':[result]})
            if tab is not None:
                for label in ("initial", "repeat"):
                    started = time.monotonic()
                    rows = worker.evaluate("""async tab=>await chrome.scripting.executeScript({target:{tabId:tab,allFrames:true},world:'MAIN',func:async()=>{
                        const v=globalThis.VeloaMedia?.videos()[0];if(!v)return {state:'no-player'};
                        v.pause();
                        const result=await globalThis.__veloaSiteCaptions?.acquire({href:location.href,src:VeloaMedia.source(v)});
                        const cues=result?.cues||[];
                        const digest=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(JSON.stringify(cues)));
                        return {host:location.hostname,state:result?.state||'no-bridge',reason:result?.reason,
                            cues:cues.length,language:result?.language,first:cues[0]?.start,last:cues.at(-1)?.end,
                            cueHash:[...new Uint8Array(digest)].map(b=>b.toString(16).padStart(2,'0')).join(''),
                            duration:Number.isFinite(v.duration)?v.duration:null,tracks:v.textTracks.length,
                            button:!!document.querySelector('.vocalm-player-button'),
                            rules:VeloaMedia.rules(location.href).map(r=>r.site)};
                    }})""", tab)
                    report["checks"].append({"name": label, "seconds": round(time.monotonic()-started, 3), "frames": [row.get("result") for row in rows]})
            report["acquired"] = any(frame and frame.get("state") == "ready" and frame.get("cues", 0) > 0 for row in report["checks"] for frame in row["frames"])
        except Exception as error:
            # Playwright errors may include request URLs with signatures. Keep only the class.
            report["error_type"] = type(error).__name__
            report["acquired"] = False
        finally:
            context.close()
    target = ROOT / ("research/udemy-live-chrome.json" if args.browser == 'chrome' else "research/udemy-live-headed.json" if args.headed else "research/udemy-live.json")
    target.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report))
    return 0 if report.get("acquired") else 1


if __name__ == "__main__":
    raise SystemExit(main())
