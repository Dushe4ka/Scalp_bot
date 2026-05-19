# Load tests

Перед demo на Bybit: [docs/multiuser_demo_testing.md](../docs/multiuser_demo_testing.md).

## Phase 1 (async, single process)

```bash
python -m tests.load.short_bu_ts_limit_async_benchmark --sessions 10 --minutes 5 --stagger 0.3
```

Отчёт: `tests/load/reports/short_bu_ts_limit_async_benchmark.txt`

## Phase 2 (sharding + Redis feed)

### 1. Orchestrator only (без Bybit)

Проверяет распределение `engine:*:load` при 30/60 assign:

```bash
export TRADE_ENGINE_COUNT=2
export MAX_SESSIONS_PER_ENGINE=30
python -m tests.load.phase2_sharding_benchmark --sessions 60 --mode orchestrator
```

Ожидание: `engine:0:load` + `engine:1:load` ≈ 30+30, `Sharding OK: True`.

Отчёт: `tests/load/reports/phase2_orchestrator_60.txt`

### 2. Demo (полный путь)

Требуется: Redis, `.env` с `DEMO_API_*`, feed service, 2 engine workers, router worker.

Терминал 1 — feed:

```bash
python -m services.market_price_feed
```

Терминал 2 — engine 0:

```bash
CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker -Q trade_engine_0 -n engine0@%h --concurrency=1 -l info
```

Терминал 3 — engine 1:

```bash
CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker -Q trade_engine_1 -n engine1@%h --concurrency=1 -l info
```

Терминал 4 — router:

```bash
celery -A celery_app.celery_config worker -Q default,trade_user --concurrency=4 -l info
```

Терминал 5 — benchmark:

```bash
python -m tests.load.phase2_sharding_benchmark --sessions 30 --mode demo --minutes 3 --stagger 0.2
```

Отчёт: `tests/load/reports/phase2_sharding_30.txt`

### 3. Multiprocess sync (legacy comparison)

```bash
python -m tests.load.short_bu_ts_limit_multiprocess_benchmark --processes 10 --minutes 5
```
