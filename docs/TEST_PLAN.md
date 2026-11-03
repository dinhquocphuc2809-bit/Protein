# Acceptance and regression plan

Status: planned unless accompanied by recorded execution evidence. Never count test
fixtures or simulated provider responses as successful live integrations.

| ID | Layer | Scenario | Required observation |
| --- | --- | --- | --- |
| SEC-01 | Auth | Invalid, inactive, expired, revoked ticket; activation race | Reject; one activation time; no provider calls |
| SEC-02 | Auth | Tampered body/path/token, old/future timestamp, duplicate nonce | Reject each; nonce unique under concurrent requests |
| SEC-03 | Auth | Revocation during queued/running job | No new paid steps; subsequent reads reject |
| SEC-04 | Rate | Login brute force, one noisy ticket, forged forwarding header | Independent limits; attacker cannot select client IP |
| SEC-05 | Network | Private/loopback/metadata IPv4+IPv6, redirects, DNS changes | No internal fetch; no secret forwarded across hosts |
| SEC-06 | Input | Oversized/chunked SRT/WAV, spoofed suffix, NaN/Inf times, HTML | Bounded rejection; UI renders text; no execution |
| SEC-07 | Modal | Unauthenticated TTS, bad proxy token, account-4 deployment | Rejected before GPU; client credentials absent on backend |
| SEC-08 | Repo | Secret scan tracked files, extension zip and logs | No backend keys/token values/HAR/private addresses |
| KEY-01 | Provider | First key depleted/invalid then healthy second | One transparent bounded retry; state persisted |
| KEY-02 | Provider | 429 with Retry-After; 403 permissions; 500 outage | Cooldown/forbidden/transient distinguished |
| KEY-03 | Provider | All keys unavailable; simultaneous reservations | Clear bounded failure; no double charge/account oversubscription |
| DB-01 | Persistence | Crash/restart, stale lease, migration failure | Recover jobs; preserve data; transactional migration rollback |
| DISK-01 | Storage | Unknown download length and oversized stream | Stop at cap; remove partial file; release reservation |
| DISK-02 | Storage | Near-full root, concurrent jobs, crash orphan | Reject safely; evict only owned inactive cache; preserve reserve |
| DISK-03 | Storage | Retention sweep with active jobs and symlinks | Do not follow symlinks/delete active or unrelated files |
| MED-01 | Live | YouTube no captions -> Tunelio -> Nova-3 URL | Valid timed transcript; no direct yt-dlp |
| MED-02 | Live | TikTok/Bilibili/Douyin/Vimeo/X etc -> Apify -> VPS -> Nova-3 | Actual selected media; bounded spool; run cancelled on failure |
| MED-03 | Live | Expired signed URL, 403 CDN, wrong multipart Bilibili page | Refresh bounded; no silent first-part substitution |
| CAP-01 | Browser | YouTube manual/automatic captions, TextTracks, uploaded SRT | Correct language/source; timestamps preserved |
| CAP-02 | Browser | Same-language SRT | No translation API call; direct TTS |
| ASR-01 | GPU | T4/L4 English and Vietnamese, silence/music, long speech | Real transcript; monotonic timestamps within input duration |
| ASR-02 | GPU | Forced-aligner unsupported language, unknown characters | Explicit fallback/error; no fabricated timings |
| ASR-03 | GPU | Cold/warm, 1/2 concurrent, timeout, GPU OOM | Record wall time, RTF, VRAM/RAM, failure and cleanup |
| LLM-01 | Live | Each configured Gemini/DeepSeek model | Official endpoint, validated response, usage recorded |
| LLM-02 | Translation | Missing/duplicate IDs, malformed JSON, injection in captions | Reject/repair only affected batch; no timestamps from model |
| CACHE-01 | Integration | Replay same video; change voice A->B->A | Zero extra translation calls; audio A reused |
| CACHE-02 | Integration | Change source/target/model/glossary/prompt; concurrent misses | Correct invalidation; single-flight paid work |
| TTS-01 | GPU | Each preset, user WAV, short/long text and punctuation | Nonempty decodable audio; correct single voice; bounded duration |
| TTS-02 | Audio | Trim/fade, tiny clips, all silence, clipping, overlong cue | No invalid buffers; no word truncation; inspect/listen joins |
| PLAY-01 | Browser | Pause/resume, seeking storms, 0.5x/1x/1.5x/2x | No stale overlapping speech; pitch preserved; drift measured |
| PLAY-02 | Browser | Buffer underrun, timeout, tab background, worker restart | Visible recoverable state; no silent skipped cue |
| PLAY-03 | Browser | Ads, SPA navigation, video replacement, MSE source update | Correct logical video identity; old tasks/gains disposed |
| MEM-01 | Browser | Two-hour session + repeated seeks/voice changes | Cache bounds; no monotonic decoded-memory/object-URL growth |
| UI-01 | Browser | Chrome/Firefox; small/large viewport; fullscreen/theater | Shadow DOM isolation; controls/subtitles remain reachable |
| UI-02 | Accessibility | Keyboard, zoom 200%, reduced motion, high contrast | Labels/focus/order/contrast intact; no required animation |
| STUDY-01 | Live | Timestamp summary click and contextual follow-up | Seek to valid time; grounded answer; injection cannot change system rules |
| ADMIN-01 | Private | Create/extend/revoke/delete ticket, bulk key add, stats | DB consistency; secrets masked; route inaccessible publicly |
| OPS-01 | VPS | Public TLS API + Tailscale admin/SSH + restart | Valid TLS; private-only listeners; non-root process |
| OPS-02 | VPS | Deployment health failure and rollback | Restore previous release/config; preserve database |
| E2E-01 | Full | Captions -> translation -> clone -> playback -> study | End-to-end live evidence in both browsers |
| E2E-02 | Full | No captions fast and HQ; seek/change voice/reopen | Correct acquisition, cache, audio and recovery |
| E2E-03 | Full | Ticket expiry, provider exhaustion, network loss, disk pressure | Safe failure and recovery without uncontrolled spend |

Benchmark records must separate image build, model download, container init, inference,
network transfer and audio playback time. Measure RTF as inference seconds / audio seconds;
startup p50/p95 need repeated cold starts, not a single run. T4/L4 selection considers
cost per synthesized minute and quality, not latency alone. Do not extrapolate a tiny
sample into a production SLA. Human listening and visual browser QA remain required.

## Executed evidence on 2026-11-03

| Scope | Evidence | Outcome |
| --- | --- | --- |
| Local security/storage/jobs/core | pytest, 34 tests | Passed; includes race/replay/revocation, bounded body, cancellation join, preserved existing files, ASR transfer-window coverage and history byte retention |
| Client signing/SRT/endpoint/DSP | node --test tests/extension.test.cjs, 5 tests | Passed; sine pitch/duration and cancellation checked |
| Caption policy/parsing/track choice | node --test tests/extension.test.cjs, 3 additional tests | Errors/unknown metadata never authorize ASR; current-language selection and JSON3 append events |
| YouTube acquisition branches | research/caption-acceptance.json | 11 explicitly mocked transport scenarios with actual extension; successful captions forwarded unchanged and no job on lookup failure |
| Affected YouTube video | research/caption-live.json | Actual metadata has 21 tracks; empty responses produce clear error and zero backend jobs; successful download remains unverified in owner's session |
| Official translation models | research/live-translation.json | All 3 routes passed; cue times unchanged; repeated translation returns cache; translated SRT bypass works |
| Summary/chat | research/live-translation.json | Passed after fixing schema compatibility; numeric citations additionally requested |
| YouTube fast ASR | research/live-youtube.json | Passed, real Tunelio and Deepgram URL request |
| TikTok fast ASR | research/live-apify.json | Passed, real Actor, VPS download and Deepgram upload |
| YouTube quality ASR | research/live-quality-asr.json | Passed, production Modal ASR plus alignment and translation |
| Production GPU HTTP/RPC | research/benchmarks/production-voice.json, production-asr.json | Passed on T4; real generated audio and timed words |
| Chrome/Chromium | research/browser-chromium.json | Actual MV3 extension, live backend/TTS, bilingual display, playback, replay, A->B->A cache, summary/chat |
| Firefox 159 | research/browser-firefox.json | Actual MV3 addon, live backend/TTS and playback to end |
| Veloa toolbar popup | research/ui-acceptance.json | Actual Chromium popup, inline settings without new tabs, active-video control, live translation after closing popup, SRT upload preserved across model changes |
| YouTube sidebar layout | research/ui-acceptance.json | Labelled DOM fixture: source-first rows, light/dark, seek/highlight, theater/narrow fallback, 5,000-cue virtualization and manual-scroll override |
| Real YouTube layout | research/ui-youtube-live.json | Fixed-panel layout dock stays beside video; mode/native panel transitions and 1000px/800px responsiveness passed; no paid provider calls |
| Local deployment bridge | research/native-bridge.json | Browser native message deployed account-4 worker and stored working proxy configuration |
| Admin | research/admin-acceptance.json | Ticket lifecycle, private/public route separation, 132 keys, model list and browser UI passed |
| SSH | research/ssh-hardening.json | Tailscale-only binding and independent reconnect passed; rollback timer cancelled after verification |
| Disk | research/admin-acceptance.json | ~198.6 GB free; spool/cache/log caps and release-retention timer deployed |
| Modal cost cap | research/modal-spend-cap-confirmation.json | Owner confirmed $0 spend limit on all four accounts; not API-verified |

Not yet certified: L4 successful inference, two-hour memory soak, subjective audio joins,
all 84 voices individually synthesized, every third-party media site, DRM/closed-shadow
players, all ad/SPA behaviors, and Firefox store signing. The acceptance scripts use short
controlled video fixtures for browser playback; provider responses are real, not mocks.
