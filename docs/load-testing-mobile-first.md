# Mobile-first load testing runbook

Tujuan runbook ini adalah memberi bukti staging bahwa optimasi mobile-first menurunkan DB pressure tanpa mengorbankan jawaban siswa. Jangan jalankan traffic ke production tanpa approval operator eksplisit.

## Guardrail wajib

- Gunakan data staging/synthetic saja; jangan pakai token, akun, atau session siswa asli.
- Jangan menjalankan test di `man1rokanhulu.cloud` saat ujian aktif.
- Jangan langsung menguji 100% queue/buffer di production.
- Final submit tetap prioritas; hentikan test jika 503 final submit naik atau ada indikasi answer loss.

## Env stage

### Baseline direct

```env
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
VIOLATION_ASYNC_ENABLED=true
ADMIN_MONITORING_DETAIL_LEVEL=summary
```

### Hybrid 10% canary

```env
ANSWER_WRITE_MODE=hybrid
ANSWER_QUEUE_ENABLED=true
ANSWER_QUEUE_PERCENTAGE=10
VIOLATION_ASYNC_ENABLED=true
ADMIN_MONITORING_DETAIL_LEVEL=summary
```

### Hybrid 50% canary

```env
ANSWER_WRITE_MODE=hybrid
ANSWER_QUEUE_ENABLED=true
ANSWER_QUEUE_PERCENTAGE=50
VIOLATION_ASYNC_ENABLED=true
ADMIN_MONITORING_DETAIL_LEVEL=summary
```

Naik ke 50% hanya jika 10% stabil.

## Virtual users

Jalankan bertahap:

1. 100 VU selama 3-5 menit.
2. 300 VU selama 5-10 menit.
3. 600 VU selama 10-15 menit.

Setiap stage wajib menyertakan:

- answer submit/autosave traffic,
- journal sync bila tersedia di harness,
- violation burst ringan,
- final submit sample,
- admin monitoring summary tetap terbuka di satu browser/admin session.

## Script smoke/load helper

Script aman tersedia di:

```bash
scripts/load_test_answer_sync.py
```

Dry-run plan:

```bash
python scripts/load_test_answer_sync.py \
  --base-url https://staging.example.test \
  --session-id 1001 \
  --question-id 2001 \
  --vus 100 \
  --duration-seconds 60
```

Eksekusi staging:

```bash
python scripts/load_test_answer_sync.py \
  --base-url https://staging.example.test \
  --token "$STAGING_TEST_TOKEN" \
  --session-id 1001 \
  --question-id 2001 \
  --selected-option-id 3001 \
  --vus 100 \
  --duration-seconds 180 \
  --include-violation-burst \
  --execute
```

Script menolak host production yang dikenal kecuali diberi `--allow-production`; flag itu tetap membutuhkan approval operator terpisah.

## Metrik yang harus dicatat

Untuk setiap stage catat:

| Metrik | Target awal |
| --- | --- |
| p50 latency `/api/exams/submit-answer` | stabil/turun vs baseline |
| p95 latency `/api/exams/submit-answer` | tidak naik tajam |
| p99 latency `/api/exams/submit-answer` | tidak ada spike berkepanjangan |
| final submit success rate | 100% pada sample test |
| 429 rate | terukur dan tidak massal |
| 503 rate | 0 atau sangat rendah; investigasi jika muncul |
| Redis pending queue size | tidak naik terus-menerus |
| DB writes/minute | turun pada hybrid vs direct |
| DB CPU/connection count | stabil dan tidak mendekati limit |
| answer loss | 0 |

## Redis/DB observation contoh

Jalankan hanya di staging/VPS test yang disetujui:

```bash
redis-cli LLEN runtime:answer_queue:pending
redis-cli SCARD runtime:answer_queue:queued:pending
```

DB connection sample:

```sql
SELECT state, count(*)
FROM pg_stat_activity
WHERE datname = 'exam_system'
GROUP BY state;
```

DB write pressure sample:

```sql
SELECT relname, n_tup_ins, n_tup_upd, n_tup_del
FROM pg_stat_user_tables
WHERE relname IN ('answers', 'exam_sessions', 'exam_logs')
ORDER BY relname;
```

## Pass/fail criteria

Pass:

- Answer loss = 0.
- Final submit sample sukses 100%.
- Redis pending queue tidak tumbuh tanpa drain.
- p95/p99 tidak lebih buruk dari baseline direct secara signifikan.
- DB connection count dan CPU lebih stabil pada hybrid canary.

Fail/stop:

- Ada jawaban hilang atau mismatch saat final submit.
- 503 final submit muncul berulang.
- Redis dirty/pending terus naik.
- DB connection mendekati limit.
- Admin monitoring mengganggu answer/final-submit path.

## Rollback env

Rollback total:

```env
ANSWER_WRITE_MODE=direct
ANSWER_QUEUE_ENABLED=false
ANSWER_QUEUE_PERCENTAGE=0
```

Graceful drain rollback jika masih ada dirty buffer:

```env
ANSWER_WRITE_MODE=hybrid
ANSWER_QUEUE_ENABLED=true
ANSWER_QUEUE_PERCENTAGE=0
```

Setelah pending/dirty buffer kosong, pindahkan ke rollback total.
