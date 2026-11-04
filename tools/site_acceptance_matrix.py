"""Join reference routes to explicit evidence; never infer live success from fixtures."""
import fnmatch
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]

# Reviewed mechanism descriptions. An absent family remains explicitly unreviewed.
MECHANISMS = {
    'youtube': 'Player response captionTracks and timedtext; native tracks; separate YouTube bridge',
    'egghead': 'Current Next lesson/videoResource SRT',
    'wistia': 'Owned Wistia media ID -> captions JSON',
    'kajabi': 'Owned Wistia custom element/media ID -> captions JSON',
    'domTrack': 'Owned HTML track URLs/native cues; site DOM selectors',
    'commonVtt': 'Intercepted VTT; owned native/SDK descriptor preferred',
    'commonM3u8': 'Observed/owned HLS master -> subtitle rendition -> VTT segments',
    'datacamp': 'Projector key -> course/language VTT',
    'lecturio': 'Owned attached Video.js tracks/options',
    'platzi': 'Owned Video.js; base64 subtitles parameter on media URL',
    'kollus': 'Owned KollusPlayers media_content_key -> subtitles; reference also numeric-ID resource lookup',
    'dailymotion': 'Current player video ID -> video metadata subtitles URLs',
    'bbc': 'Current BBC path -> content model -> media selector -> captions',
    'bloomberg': 'Owned skylight media ID -> manifest captions',
    'coindesk_jwplayer': 'Owned JW getCaptionsList URL/label association; playlist captions fallback',
    'reuters_jwplayer': 'Owned JW current item sources -> HLS subtitles, direct VTT or playlist',
    'jwplayer': 'Owned JW playlist caption tracks/HLS',
    'jwplayer_hosted': 'Owned JW getCaptionsList URL IDs, then playlist caption tracks/HLS',
    'plex': 'HLS subtitle URL wrapper -> vod-static.plex.tv VTT',
    'aljazeera_brightcove': 'Owned Brightcove -> public config policy -> playback text_tracks',
    'oracle_mylearn_brightcove': 'Owned Brightcove -> public config policy -> playback text_tracks',
    'sonicwall_brightcove': 'Owned Brightcove mediainfo.text_tracks; public playback fallback',
    'servicenow_brightcove': 'Owned Brightcove mediainfo.text_tracks; public playback fallback',
    'mathworks_brightcove': 'Owned Brightcove mediainfo.text_tracks; public playback fallback',
    'narto': 'Selected TextTrack snapshots with transition stability',
    'kinescope': 'Captured owned Kinescope player playlist',
    'mux': 'Owned Mux/open-shadow tracks and HLS',
    'bili': 'Current CID/aid/bvid -> browser-session metadata -> subtitle JSON',
    'udemy': 'Current course/lecture asset.captions -> original course locale -> VTT',
    'videojs': 'Owned Video.js remoteTextTracks/options/mediainfo',
    'dropbox': 'Current-player observed transcript JSON segments in seconds and transcriptLocale',
    'edx': 'Owned video data-metadata -> language transcript parallel millisecond arrays',
    'internet_archive': 'Owned JW item -> associated archive metadata caption sidecar',
    'ted': 'Current Next talk -> player resources.hls.metadata -> subtitles.webvtt',
    'apiIntercept': 'Configured request URL -> exact JSON caption-list path; per-site configuration required',
    'artstation': 'Course hash API -> exact chapter hash -> subtitles.file_url',
    'feynmanlectures': 'Selected lecture index -> FMLCaptions[index].src',
    'motionmagic': 'Course item RPC -> video playback token -> signedCaptions RPC',
    'pendo': 'Owned Wistia custom media-id -> captions hash.lines; media title lookup not needed for captions',
    'cursor_blog': 'Selected Mux TextTrack snapshots',
    'updraft': 'Owned JSON-LD Mux contentUrl -> HLS; English/source language priority',
    'osmosis': 'Current slug/language learnData -> unique caption owner -> CloudFront VTT',
    'medbridge_course': 'Course HLS segments carry absolute cue times; preserve and deduplicate, bound to loaded duration',
    'patreon': 'Current post-associated Mux bootstrap URL; reference text proximity heuristic not adopted',
    'substack': 'Owned videoUpload -> extractedAudio transcription CDN JSON',
    'navertv': 'Current Next clip -> videoId/inKey -> play API captions.list',
    'rutube': 'Current video ID -> play/options captions.file',
    'gaia': 'Owned Video.js page node -> feature/preview media-info -> textTracks VTT',
    'skillshare': 'Current active session rank -> session stream -> Cloudflare HLS',
    'tella': 'Owned story -> manifest-refresh -> signed matching HLS',
    'skool': 'Current classroom module -> Next video playbackId/token -> signed HLS; Loom iframe separate',
    'loom': 'Current share/embed ID -> page-specific unique VTT; JSON timing guesses excluded',
    'chartacademy': 'Current masterclass/video API -> captions[].url/locale',
    'circle_academy': 'Lesson/post video attachment -> transcript ID or webvtt_file_url; asset ownership required',
    'vidtube': 'getSources JSON tracks; owned JW fallback',
    'vidyard': 'Active chapter identity -> player JSON captions.vttUrl',
    'gumlet': 'Owned DOM track subtitles; override only supplies duration/media/title',
    'ftstreaming': 'Owned video/source Mux HLS -> subtitle renditions',
    'pandavideo': 'Ready player config subtitles -> library/video/language VTT',
    'adobetv': 'Current bridge humanID -> translations.vttPath',
    'domestika': 'Current video/source/attached Video.js HLS; reject unowned observed manifests',
    'mindvalley': 'Current video/source/attached Video.js HLS; reject unowned manifest and storyboard VTT',
    'pluralsight': 'JWT descriptor path must be clips2/current-clip/hls/master.m3u8; route or selected lesson link ownership',
    'mightynetworks': 'Common HLS; reference dedupes emissions ignoring signed query, Vocalm acquires on demand',
    'nebula': 'Common HLS; reference dedupes by video/language, Vocalm acquires on demand',
    'gitir': 'DOM track reader with video identity and cue normalization overrides',
    'glo': 'Reference only identifies ready MP4 media; explicitly empty caption tracks',
    'oba': 'Reference only identifies ready media; explicitly empty caption tracks',
    'internetfundamentals': 'Observed VTT; current source signature; replay and active lesson title',
    'movebox': 'Observed caption API id/subjectId/detailPath -> data.captions URL/lan',
    'okru': 'Current movie ID -> data-options flashvars.metadata -> subtitleTracks',
    'sketchy_cloudflare': 'Exact Cloudflare customer host and asset ID -> manifest/video.m3u8',
    'vidlove': 'Movie ID -> api.shows.st/movie -> subtitles[].file; reference TV reader unimplemented',
    'vkvideo': 'Native/open-shadow tracks, direct MPD BaseURL caption tracks; rolling-cue cleanup',
    'google_drive_youtube': 'Embedded Drive timedtext/player activation; large specialized pipeline still under review',
    'twitter': 'Content runtime + background maps Tweet/media ID to HLS; Vocalm matches observed GraphQL variants/cards to selected poster media ID',
    'facebook': 'Content runtime reads selected React videoFBID/caption URLs; bounded owned React reader, no getters or GraphQL replay',
}
DEDICATED = set('egghead datacamp platzi kollus dailymotion bbc bloomberg udemy edx internet_archive ted artstation feynmanlectures updraft osmosis substack navertv rutube gaia skillshare tella skool loom vidyard pandavideo adobetv'.split())
DEDICATED.update(f for f in MECHANISMS if f.endswith('_brightcove'))
DEDICATED.update(['okru','sketchy_cloudflare','plex','vkvideo','dropbox','circle_academy','movebox','motionmagic','patreon','vidlove','google_drive_youtube'])
DEDICATED.update(['pluralsight','medbridge_course','coindesk_jwplayer','reuters_jwplayer','jwplayer_hosted'])
DEDICATED.update(['domestika','mindvalley'])
DEDICATED.update(['twitter','facebook'])
GAPS = {
    'kollus': 'Numeric-ID resource-history fallback not yet implemented; no live sample',
    'skool': 'Requires exact md/selectedModule; alternate nested state shapes need live account sample',
    'loom': 'Owner Skool about embed passed acquisition and native control; Skool classroom remains separate',
    'aljazeera_brightcove': 'Live carousel SDK path passed; config fallback needs DOM account; empty-track videos stay unknown/failed',
    'plex': 'Safe direct subtitle wrapper rewrite implemented; real movie/ad acceptance pending',
    'dropbox': 'Observed current-player transcript implemented; missed-hook recovery and live file sample pending',
    'motionmagic': 'Two strictly allowlisted metadata RPCs implemented; live entitled lesson pending',
    'circle_academy': 'Observed matching lesson/attachment transcript implemented; missed-hook recovery and live lesson pending',
    'medbridge_course': 'Absolute timing and overlap fixtures pass; live entitled course pending',
    'pluralsight': 'Current master/variant/stale-clip fixtures pass; live entitled course pending',
    'mindvalley': 'Owned HLS and MP4/VTT, active multiple-player fixtures; live entitled course pending',
    'domestika': 'Owned HLS, active multiple-player fixtures; remote per-video mapping fallback/live course pending',
    'twitter': 'Poster-bound HLS/card fixtures; live post, missed GraphQL capture and alternate poster formats pending',
    'facebook': 'Owned React data descriptors; ambiguous owners/getters rejected; live video and GraphQL recovery pending',
    'universal': 'Player-specific content runtime review required; injectScript factory alone cannot establish absence of captions',
    'patreon': 'Exact post-owned bootstrap reader implemented; alternate escaped script formats and live post pending',
    'bili': 'Anonymous sample no tracks; authenticated and PGC/PUGV paths remain unverified',
    'google_drive_youtube': 'Direct account-specific timedtext list/JSON3 implemented; mobile activation variants and live Drive file pending',
    'vkvideo': 'Direct MPD and overlapping rolling-caption cleanup implemented; live sample pending',
    'vidlove': 'Movie endpoint implemented; TV is unimplemented in reference and still unsupported here; live sample pending',
    'glo': 'Reference does not supply existing captions; native fallback only; no live sample',
    'oba': 'Reference does not supply existing captions; native fallback only; no live sample',
}
FIXTURES = {f: [f] for f in DEDICATED}
FIXTURES.update({
    'internet_archive':['archive'], 'feynmanlectures':['feynman'], 'navertv':['naver'], 'adobetv':['adobe'],
    'udemy':['udemy_no_history','udemy_missed_hook','udemy_stale'],
    'aljazeera_brightcove':['aljazeera_playback','brightcove_stale','brightcove_denied'],
    'oracle_mylearn_brightcove':['oracle_playback'], 'sonicwall_brightcove':['sonicwall_playback'],
    'servicenow_brightcove':['servicenow_playback'], 'mathworks_brightcove':['mathworks_playback'],
})

def read(name):
    path = ROOT / 'research' / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}

def matches(pattern, value):
    expected = re.fullmatch(r'(\*|https?)://([^/]+)(/.*)',pattern)
    if not expected:
        return False
    actual = urlsplit(value)
    scheme, host, path = expected.groups()
    host_match = fnmatch.fnmatchcase(actual.netloc, host) or (host.startswith('*.') and actual.netloc == host[2:])
    return (scheme in ('*', actual.scheme) and host_match and
            fnmatch.fnmatchcase(actual.path + ('?' + actual.query if actual.query else '') + ('#' + actual.fragment if actual.fragment else ''), path))


def sample_status(result, rule):
    # Retain failed historical probes as evidence without counting them as passes.
    if 'reject' in result.get('acceptance', '').lower():
        return 'rejected'
    frames = [f for f in result.get('frames', []) if isinstance(f, dict)]
    matching = [f for f in frames if rule['site'] in f.get('rules', [])]
    if not matching:
        matching = [f for f in frames if not f.get('rules') and
                    f.get('host') == urlsplit(result['url']).hostname and
                    any(matches(p, result['url']) for p in rule['pages'])]
    ready = [f for f in matching if f.get('state') == 'ready' and f.get('cues', 0) > 0]
    if ready:
        for frame in ready:
            duration, first, last = frame.get('duration'), frame.get('first'), frame.get('last')
            if (isinstance(duration, (int, float)) and duration > 0 and
                isinstance(first, (int, float)) and isinstance(last, (int, float)) and
                0 <= first < last <= duration + 2 and frame.get('playerButton') and
                'mediaError' in frame and frame['mediaError'] is None):
                return 'captions-and-player-sample'
        return 'captions-only'
    if result.get('http_status') in (401, 403) or result.get('error'):
        return 'access-blocked'
    return 'no-caption-result'

def main():
    inventory = read('multisite-inventory.json')
    audit = {r['family']: r for r in read('extractor-audit.json')['families']}
    runtime = {r['family']: r for r in read('runtime-extractor-audit.json').get('families',[])}
    fixtures = {r['name']:r for r in read('platform-acceptance.json').get('checks',[])}
    live = []
    for name in ['multisite-live.json','platform-live.json','reader-live.json','updraft-live.json','public-access-live.json','aljazeera-live.json','aljazeera-carousel-live.json','owner-samples-live.json','skool-loom-live.json','jw-live.json']:
        for row in read(name).get('pages',[]):
            live.append((name,row))
    rows=[]
    for index, rule in enumerate(inventory['rules'],1):
        family=rule['family']; source=audit[family]
        runtime_source=runtime.get(family)
        has_handler=source.get('className') is not None or runtime_source is not None
        mechanism=MECHANISMS.get(family, 'Unmapped injectScript factory; content runtime audit required' if not has_handler else 'Detailed source review pending; AST handler located')
        checks=[name for name in fixtures if any(name==prefix or name.startswith(prefix+'_') for prefix in FIXTURES.get(family,[]))]
        samples=[]
        for name, result in live:
            if any(matches(p,result['url']) for p in rule['pages']) or any(rule['site'] in frame.get('rules',[]) for frame in result.get('frames',[]) if frame):
                samples.append({'report':name,'url':result['url'],'acquired':result.get('acquired',False),
                                'status':sample_status(result,rule),
                                'http_status':result.get('http_status'),'error':result.get('error'),
                                'acceptance':result.get('acceptance','Acquisition only; inspect language/timing/player evidence'),
                                'frames':result.get('frames',[])})
        # Dedicated authorized Udemy report has a different schema; retain it as scoped evidence.
        authorized='research/udemy-attached-live.json' if family=='udemy' else None
        rows.append({'route':index,**rule,'referenceHandler':source.get('className'),'mechanism':mechanism,
            'runtimeHandler':runtime_source.get('className') if runtime_source else None,
            'review':'mechanism-identified; detailed gaps remain' if family in MECHANISMS else 'runtime-review-pending',
            'implementation':'dedicated-and-shared' if family in DEDICATED else 'shared-path-only',
            'fixtureChecks':[{'name':n,'passed':fixtures[n]['passed']} for n in checks],
            'liveSamples':samples,'authorizedEvidence':authorized,
            'remaining':GAPS.get(family,'Per-route live acceptance still required; shared fixtures do not certify the site'),
            'acceptedAllRoutes':False})
    report={'scope':'159 reference route entries, not 159 independently verified websites. Live results certify only the listed sample.',
            'sourceSha256':inventory['sha256'],'routes':rows}
    (ROOT/'research/site-acceptance-matrix.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    lines=['# Per-route acceptance matrix','',report['scope'],'',
           'Historical full-reference ledger. Current user scope and newer evidence: `docs/PRIORITY_SITE_ACCEPTANCE.md`.', '',
           'Generated by `tools/site_acceptance_matrix.py`. Detailed evidence and sample URLs are in `research/site-acceptance-matrix.json`.',
           'The registry and DOM-only tests are not proof that a platform-specific caption reader works. No whole platform is declared complete.',
           '', '| Route | Site / family | Reference mechanism | Fixture | Live sample | Remaining |',
           '| --- | --- | --- | --- | --- | --- |']
    for row in rows:
        checks=row['fixtureChecks']; fixture=f"{sum(c['passed'] for c in checks)}/{len(checks)} mechanism cases" if checks else 'No dedicated evidence'
        samples=row['liveSamples']
        counts={status:sum(s['status']==status for s in samples) for status in sorted(set(s['status'] for s in samples))}
        live_status='; '.join(f'{count} {status}' for status,count in counts.items()) if samples else 'Not tested'
        if row['authorizedEvidence']: live_status='Authorized Udemy sample: see attached-live report'
        lines.append(f"| {row['route']} | {row['site']} / {row['family']} | {row['mechanism']} | {fixture} | {live_status} | {row['remaining']} |")
    (ROOT/'docs/SITE_ACCEPTANCE_MATRIX.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'routes':len(rows),'families':len(audit),'mechanismUnidentified':sorted(set(r['family'] for r in rows if r['review']=='runtime-review-pending'))}))

if __name__=='__main__':
    main()
