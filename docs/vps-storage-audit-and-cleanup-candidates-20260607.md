# VPS Storage Audit and Cleanup Candidates

Date: 2026-06-07

## 1. Scope

This is a read-only storage audit for the VPS before the real exam window.

Operator-selected constraints:

```text
scope: all safe areas
backup retention before exam: keep all backups until after exam
cleanup mode: dry-run / recommendation only
```

No cleanup was performed:

```text
file deletion: NO
Docker prune: NO
Docker log truncate: NO
journal vacuum: NO
apt/npm cache cleanup: NO
DB vacuum/compaction: NO
Redis rewrite/flush: NO
service restart: NO
```

## 2. Latest GitHub head reviewed

```text
84b399813bfab51f26393024d88548bd8433491f
```

Commit reviewed:

```text
docs: record exam freeze readiness and phase 6 cleanup
```

New commits before this audit:

```text
none
```

## 3. Disk overview

VPS:

```text
hostname=adminujian
audit_time_utc=2026-06-07T17:01:50+00:00
```

Main disk:

```text
filesystem=/dev/sda1
type=ext4
size=58G
used=30G
available=29G
use_percent=51%
```

Inodes:

```text
inode_use_percent=5%
```

Decision:

```text
Disk is not in emergency state.
There is enough room for tomorrow exam if no load-test/build/large backup is run.
Best action before exam: do not perform risky cleanup; document candidates and clean after exam with approval.
```

## 4. Biggest storage consumers

Top-level relevant usage:

| Area | Size | Notes |
|---|---:|---|
| `/var/lib/docker` | 26G | largest consumer; mostly images/build cache/logs |
| `/var/log` | 4.1G | mostly systemd journal |
| `/usr` | 3.1G | OS/packages, do not delete manually |
| `/root` | 1.5G | app tree + npm/cache/backups |
| `/root/ujian_online` | 805M | app tree, backups, reports, APK artifacts |
| `/root/.npm` | 643M | npm cache/npx cache |
| `/root/ujian_online/backups` | 340M | project DB/source backup artifacts |
| `/root/ujian_online/reports` | 204M | old load-test/benchmark reports |
| `/var/cache/apt` | 165M | apt package cache |
| `/root/ujian_online/apk_builds` | 102M | APK build artifacts |
| `/root/.cache` | 60M | prisma/pip/matplotlib caches |
| `/tmp` | 7.4M | negligible |
| `/root/ujian_online_backups` | 2.5M | phase deploy backups, small |

## 5. Docker storage audit

Docker system df:

```text
Images: 10 total, 9 active, 11.42GB size, 11.12GB marked reclaimable by Docker accounting
Containers: 18 total, 18 active, 119.5MB
Local Volumes: 4 total, 386.8MB
Build Cache: 20 entries, 3.081GB
```

Important interpretation:

```text
Do not run broad docker system prune before exam.
Docker image reclaimable accounting can include shared layers; running broad prune without review can remove useful build cache/images.
Build cache is the safest Docker candidate after approval, because it is unused and reclaimable.
```

Docker build cache:

```text
reclaimable_build_cache=3.081GB
last_accessed=about 7 weeks ago
```

Candidate after exam / explicit approval:

```bash
# Not executed during this audit
docker builder prune
```

Recommended timing:

```text
after exam, not before exam unless disk emergency
```

## 6. Docker container log audit

Largest Docker JSON logs:

| Size | Container | Image |
|---:|---|---|
| 5.6GB | `ujian_online-pgbouncer-1` | `ujian_online-pgbouncer` |
| 713MB | `ujian_online-nginx-1` | `nginx:alpine` |
| 20MB | `ujian_online-redis-1` | `redis:7-alpine` |
| 16MB | `ujian_online-db-1` | `postgres:15-alpine` |
| 1.5MB | `grafana` | `grafana/grafana:11.1.0` |

Docker logging config:

```text
log driver=json-file
container log Config={}
/etc/docker/daemon.json=missing
max-size/max-file log rotation: not configured
```

Cleanup candidate classification:

```text
safe log rotation/truncate after approval
high value: pgbouncer log + nginx log, potential recovery about 6.3GB
```

Recommended future fix:

```text
Add Docker log rotation (json-file max-size/max-file) in daemon config or compose-level logging options, then recreate containers in a maintenance window.
```

Possible cleanup command after approval only:

```bash
# Not executed during this audit
truncate -s 0 /var/lib/docker/containers/<pgbouncer-container-id>/<pgbouncer-container-id>-json.log
truncate -s 0 /var/lib/docker/containers/<nginx-container-id>/<nginx-container-id>-json.log
```

Risk:

```text
Truncating logs removes historical troubleshooting context.
Do not do during active exam unless disk is emergency.
```

## 7. System journal and OS logs

Journal usage:

```text
systemd journal size=4.0G
/var/log size=4.1G
```

Cleanup candidate classification:

```text
safe log retention cleanup after approval
potential recovery about 3.0G-3.5G if vacuumed to 512M-1G
```

Candidate command after approval only:

```bash
# Not executed during this audit
journalctl --vacuum-size=512M
# or
journalctl --vacuum-time=7d
```

Risk:

```text
Reduces historical operating logs.
Prefer after exam unless disk emergency.
```

## 8. Project backups audit

### 8.1 `/root/ujian_online_backups`

Total:

```text
/root/ujian_online_backups=2.5M
```

Inventory summary:

```text
phase-6.4-five-session-shadow-validation-20260607T125415Z: 48K
phase-6.3-shadow-summary-tool-20260607T122943Z: 20K
phase-6.2e-repeated-shadow-validation-20260607T113855Z: 48K
phase-6.2e-shadow-refresh-observability-20260607T112205Z: 88K
phase-6.2d-shadow-retry-after-post-final-refresh-20260607T101739Z: 44K
phase-6.2c-post-final-shadow-refresh-20260607T084932Z: 88K
phase-6.2b/6.2 trial backups: small, around 44K each
phase-6.1-shadow-allowlist-default-off-20260607T042302Z: 84K
phase-5.6-activity-logs-20260607T021532Z: 40K
phase-5.4-auth-frontend-20260606T203324Z: 1.6M
phase-5.2-default-off-20260606T145304Z: 132K
```

Classification:

```text
KEEP until after exam
low space impact
not worth deleting before exam
```

### 8.2 `/root/ujian_online/backups`

Total:

```text
/root/ujian_online/backups=340M
```

Largest entries:

```text
pre_quote_fix_20260529_201012=78M
pre_editor_quote_fix_20260530_194743=78M
pre_deploy_snapshots=18M
several SQL gzip backups around 11M-15M each
many small historical patch backups
```

Classification:

```text
KEEP until after exam
candidate delete/archive after exam with manual review
```

Reason:

```text
Contains DB/source backup-like artifacts.
Should not be cleaned blindly before a real exam.
```

## 9. Reports, APK artifacts, and project artifacts

### 9.1 `/root/ujian_online/reports`

Total:

```text
/root/ujian_online/reports=204M
```

Observed mostly old benchmark/load-test reports from March 2026.

Classification:

```text
candidate delete/archive after exam
not required for tomorrow runtime
manual review recommended because reports can contain diagnostics
```

### 9.2 `/root/ujian_online/apk_builds`

Total:

```text
/root/ujian_online/apk_builds=102M
apk/aab file count under app tree=2
```

Classification:

```text
KEEP until after exam
candidate delete/archive obsolete APK artifacts after exam, but keep latest known stable/new-update APK references as needed
```

Reason:

```text
APK rollout is exam-critical; do not remove APK artifacts before exam unless operator confirms exact obsolete files.
```

### 9.3 Project artifact counts

Sanitized counts under `/root/ujian_online`:

```text
__pycache_dirs=12
pytest_cache_dirs=0
node_modules_dirs=0
flutter_build_dirs=0
apk_aab_files=2
sql_dump_like_files=29
csv_like_files=10
env_key_like_files=10
```

Classification:

```text
__pycache__: small, safe after approval but low value
SQL/DB dump-like files: sensitive; do not delete blindly before exam
CSV-like files: sensitive; do not print contents, do not delete blindly
.env/key-like files: sensitive; do not print/delete blindly
```

## 10. Cache audit

Caches:

```text
/root/.npm=643M
/root/.npm/_cacache=417M
/root/.npm/_npx=226M
/root/.cache=60M
/root/.cache/prisma=55M
/root/.cache/pip=5M
/var/cache/apt=165M
flutter gradle cache under project=29M
```

Classification:

```text
safe cache cleanup after approval
moderate value: about 800M-900M recoverable
```

Candidate commands after approval only:

```bash
# Not executed during this audit
npm cache clean --force
rm -rf /root/.npm/_npx
apt-get clean
pip cache purge
```

Risk:

```text
Low runtime risk, but may slow future builds/maintenance.
Not urgent because disk is 51% used.
```

## 11. Database and Redis disk footprint

Docker volumes:

```text
PostgreSQL volume=314M
Redis volume=46M
Prometheus volume=7.1M
Grafana volume=3.6M
```

Redis files:

```text
appendonly incr AOF=36M
base RDB=5.1M
dump.rdb=5.1M
manifest=small
```

Postgres largest relation file aggregate:

```text
largest observed relation file about 79M
```

Classification:

```text
DO NOT DELETE
DO NOT VACUUM FULL before exam
DO NOT compact/rewrite Redis before exam
```

Reason:

```text
DB/Redis footprints are small and operationally critical.
Cleanup risk is not justified before exam.
```

## 12. Temporary files

`/tmp` total:

```text
/tmp=7.4M
```

Largest temp path:

```text
/tmp/phase55_payload_extract=1.6M
```

Classification:

```text
low value, safe to ignore before exam
cleanup later optional
```

## 13. Cleanup candidate classification

### 13.1 Safe cache cleanup after approval

| Candidate | Estimated recovery | Timing |
|---|---:|---|
| Docker build cache | 3.081GB | after exam preferred |
| npm cache + npx cache | ~643M | after approval |
| apt cache | 165M | after approval |
| `/root/.cache` | ~60M | after approval/manual review |
| Python/pycache dirs | small | optional, low priority |

### 13.2 Safe log rotation/truncate after approval

| Candidate | Estimated recovery | Timing |
|---|---:|---|
| Pgbouncer Docker JSON log | 5.6GB | after approval; before exam only if urgent |
| Nginx Docker JSON log | 713MB | after approval; before exam only if urgent |
| Systemd journal vacuum | ~3G-3.5G | after approval; after exam preferred |

### 13.3 Backup keep until after exam

| Area | Size | Reason |
|---|---:|---|
| `/root/ujian_online_backups` | 2.5M | small, phase rollback context |
| `/root/ujian_online/backups` | 340M | backup/dump-like artifacts, useful before exam |
| `/root/ujian_online/deploy-backups` | 816K | small, deploy rollback context |
| `/root/prechange_backups` | 3.9M | small |
| `/root/hardening_backups` | 24K | small |

### 13.4 Candidate delete/archive after exam

| Area | Size | Notes |
|---|---:|---|
| `/root/ujian_online/reports` | 204M | old benchmark/load-test diagnostics |
| obsolete APK artifacts in `/root/ujian_online/apk_builds` | up to 102M | keep latest/stable references first |
| old SQL gzip backups in `/root/ujian_online/backups` | part of 340M | review retention after exam |
| old pre-quote/editor backups | 156M | review after exam |

### 13.5 Do not delete

```text
PostgreSQL Docker volume
Redis Docker volume
Grafana/Prometheus volumes unless monitoring retention policy is approved
current app source
current compose/env files
active Docker images/containers
APK artifacts needed for current Stable/New Update rollout
.env/key/keystore files without explicit secrets migration/backup plan
```

## 14. Highest impact cleanup order after exam

Recommended order after exam and approval:

1. Configure Docker log rotation to prevent recurrence.
2. Truncate or rotate only the two largest Docker JSON logs after preserving any needed recent diagnostics.
3. Vacuum system journal to a fixed size/time retention.
4. Prune Docker build cache.
5. Clean npm/apt/cache directories.
6. Review old reports and APK artifacts.
7. Review backup retention and delete/archive only after confirming rollback no longer needed.

Potential recovery if the top safe candidates are approved:

```text
Docker JSON logs: about 6.3GB
Systemd journal: about 3.0G-3.5G
Docker build cache: about 3.1GB
npm/apt/cache: about 0.8G
Total likely recoverable after approval: about 13G-14G
```

## 15. Before-exam recommendation

Because disk usage is only 51% and the exam is soon:

```text
Do not delete backups before exam.
Do not prune Docker broadly before exam.
Do not vacuum/compact DB or Redis.
Do not run production load-test/builds that create large artifacts.
Only consider log cleanup before exam if disk usage suddenly rises above a danger threshold.
```

Suggested danger threshold:

```text
if / reaches >80%: consider approved Docker log truncate/journal vacuum
if / reaches >90%: emergency cleanup with operator approval, starting with logs/cache only
```

## 16. Commands not executed

These commands are candidates only and were **not** run:

```bash
docker system prune
docker builder prune
journalctl --vacuum-size=512M
journalctl --vacuum-time=7d
truncate -s 0 /var/lib/docker/containers/.../*-json.log
apt-get clean
npm cache clean --force
rm -rf /root/.npm/_npx
rm -rf /root/ujian_online/reports/*
rm -rf /root/ujian_online/backups/*
```

## 17. Final decision

```text
storage audit completed: YES
cleanup executed: NO
backup deletion before exam: NO
current disk emergency: NO
ready to keep production frozen/direct safe-mode: YES
best immediate action: no cleanup before exam, monitor disk/log growth
best after-exam action: approve staged cleanup starting with Docker logs + journal + build/cache, then review old reports/backups
```
