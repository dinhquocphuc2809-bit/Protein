# Operations and recovery

## Deployment boundaries

`auvirel-public.service`: Uvicorn bound to `127.0.0.1:8000`, exposed by Tailscale Funnel
HTTPS. `auvirel-admin.service`: bound only to the VPS Tailscale IPv4 address, port 8001.
Admin requests require the separate admin token. No admin routes exist in the public app.
Tailscale encrypts private admin transport; the private origin currently uses HTTP inside
the encrypted tailnet. Do not publish or reverse-proxy port 8001 through Funnel.

Both services use the non-root `auvirel` account, a restrictive umask, read-only system
filesystem, restricted address families, no capabilities and a 6 GiB memory ceiling.
Provider keys are encrypted in `/var/lib/auvirel/auvirel.sqlite3`. Master/admin secrets
are in root-only `/etc/auvirel/server.env`; losing the master key loses the ability to
decrypt provider keys and verify existing tickets. Do not regenerate it on upgrades.

Source releases are stored in `/opt/auvirel/releases/YYYYMMDD-HHMMSS`; `current` points
to the active release. A daily timer retains the active release and two rollback releases,
deleting only older project release directories with strictly validated names/parents.

```sh
sudo systemctl status auvirel-public auvirel-admin
sudo journalctl --namespace=auvirel -u auvirel-public -n 100 --no-pager
tailscale funnel status
curl --fail http://127.0.0.1:8000/healthz
sudo systemctl list-timers auvirel-release-cleanup.timer
```

## Upgrading

Run `tools/deploy_backend.py` from the supplied Windows workspace. It builds an explicit
source allowlist, sends only backend credentials (Modal accounts 1-3), installs an ARM64
virtual environment, preserves existing secrets and verifies both health endpoints.
No client Modal deployment token is sent to the VPS. This deployment tool is tailored
to the supplied credential-file layout, not a general public provisioning installer.

Database schema changes must be backward-compatible or receive a migration with backup
and rollback steps. Current schema version is 1; fresh databases use incremental vacuum.
Existing DBs without auto-vacuum can reuse free pages but require an offline migration
to shrink their allocated file. Do not vacuum a busy database without a maintenance plan.

To roll back application code, select an existing validated release directory, atomically
change `current`, restart both services and check health. Preserve the database and master
key. Do not automatically roll back a schema that has undergone destructive migrations.

## Storage policy

- Temporary download: actual byte cap 512 MiB, no trust in Content-Length alone.
- Temporary spool reservations: aggregate 8 GiB, two workers, bounded media durations.
- Subtitle/translation cache: 4 GiB logical cap, TTL/LRU; no dubbed audio stored on VPS.
- SQLite allocation cap: 6 GiB; WAL checkpoint and incremental vacuum during maintenance.
- Stop admitting new media/cache work below 30 GiB free or above 80% filesystem use.
- Service journal namespace: 512 MiB disk / 64 MiB runtime cap, seven-day retention.
- Terminal job payloads removed; results retained up to seven days / 512 MiB (oldest
  first), usage records 90 days. A purged result requires preparing the video again
  before study chat; the independent translation cache can still avoid model calls.
- Local compressed audio: extension-origin IndexedDB, 80 MiB and 48-hour TTL.

Application code never enlarges Oracle disks or provisions additional block volumes.
The observed root capacity is about 192.7 GiB. Disk-full prevention does not govern
unrelated applications, Oracle backup policies, traffic billing or account resources.

## SSH recovery

SSH socket activation and sshd both bind to the Tailscale address. The hardening tool
verifies an independent SSH connection, arms a 120-second rollback, changes both listeners,
then reconnects and cancels the rollback only after verifying no wildcard SSH listeners.
Backup/rollback script: `/root/auvirel-ssh-backup/rollback.sh`. Running it deliberately
restores the prior wildcard socket configuration; use it only as an intentional recovery.
Keep Oracle console recovery available if the tailnet itself becomes inaccessible.

## Modal and provider costs

Account 1-3: app `auvirel-asr`, class `Recognizer`. Account 4: app `auvirel-voice`,
authenticated CPU ingress plus `Voice` GPU class. Other pre-existing apps are untouched.
Read-only probes cannot prove remaining Modal promotional credit. Owner confirmed custom
spend limits of $0 for all four accounts. Keep these limits when credits renew or cards
change. Usage and spend limits have different meanings in Modal's official documentation.

Balance refresh uses official APIs where exposed. Unknown balance is displayed as unknown.
401 marks invalid credentials, explicit depletion marks depleted, 403 marks forbidden,
429/network failures cool down. Temporary upstream data failures do not permanently
strand a key. Do not interpret every 403 or 429 as exhausted credit.

For client deployment, confirm spend limit in that user's account. Auto-scale-down reduces
idle compute; it does not itself cap total money. Small CPU/Volume/storage usage can remain
even while GPU containers are stopped.

## Evidence and troubleshooting

The `research/live-*.json`, `research/browser-*.json`, `research/admin-acceptance.json`,
`research/native-bridge.json` and benchmark reports contain actual test outcomes.
Private screenshots/audio/logs live under `.private`. Some historic failure reports are
retained intentionally. Read dates and `passed` fields rather than assuming a script's
existence means it passed. Live test scripts can consume provider credit.
