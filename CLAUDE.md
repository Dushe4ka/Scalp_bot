# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

Scalp_bot — a Bybit futures scalping system with a multiuser Telegram bot (aiogram), a FastAPI trading API, and Celery
workers that run the actual trading algorithms. Signals (usually from TradingView webhooks) hit the API, which fans
the trade out to every subscriber via Celery and an async trading engine.

Two parallel bot/product lines live in this repo:

- **`feature/bot_multiuser` (current branch)** — many users stored in MongoDB (`users`), each with their own Bybit
  API key/secret and trade amount; subscription-gated; `bot/` + `bybit_logic/api_algorithms/short_bu_ts_limit_engine.py`.
- **`feature/bot_nomultiuser`** — single account driven from `.env`; `bot_nomultiuser/` +
  `bybit_logic/api_algorithms/short_bu_ts_limit.py`, `hedge_long_short_bu_ts.py`, `custom_algo_nomulti.py`.

Both branches share `bybit_logic/`, `server_api/`, `celery_app/`, `database/`, `services/`, `config.py`.

## Commands

```bash
# venv
python -m venv myvenv && source myvenv/bin/activate
pip install -r requirements.txt

# FastAPI trading API (port 8050)
python -m server_api.main

# Celery worker (single process recommended — one AsyncTradeEngine per process)
celery -A celery_app.celery_config worker --loglevel=info -Q default,trade_user --concurrency=1

# Celery Beat (subscription + API-key lifecycle checks) — exactly one instance cluster-wide
celery -A celery_app.celery_config beat -l info

# Price feed service (Phase 2, required for multiuser async engine)
python -m services.market_price_feed

# Telegram bot — multiuser
python -m bot.main

# Telegram bot — single-account
python -m bot_nomultiuser.main

# Redis (local, matches docker-compose.yml)
docker compose up -d redis
```

### Phase 2 sharded engine workers (production multiuser)

Each engine worker owns queue `trade_engine_{i}`, `--concurrency=1`, capped at `MAX_SESSIONS_PER_ENGINE`:

```bash
CELERY_ENGINE_ID=0 celery -A celery_app.celery_config worker -Q trade_engine_0 --concurrency=1 --loglevel=info
CELERY_ENGINE_ID=1 celery -A celery_app.celery_config worker -Q trade_engine_1 --concurrency=1 --loglevel=info
# router: queues default, trade_user (hedge/custom, subscription checks)
celery -A celery_app.celery_config worker -Q default,trade_user --concurrency=1 --loglevel=info
```

`TRADE_ENGINE_COUNT` (`.env`) must match the number of engine workers actually running. See
[docs/phase2_scaling.md](docs/phase2_scaling.md) and [quickstart.md](quickstart.md) for full deploy sequencing
(PM2 for Python services, screen for Celery, Cloudflare Tunnel for the TradingView webhook).

### Tests

Tests use stdlib `unittest`, not pytest — there is no pytest config in the repo.

```bash
# Fast unit tests (mocked Redis, no external services needed)
python -m unittest tests.test_trade_orchestrator tests.test_redis_market_keys \
  tests.test_dual_feed_failover tests.test_redis_price_subscriber -v

# Single test
python -m unittest tests.test_trade_orchestrator -v
python -m unittest tests.test_trade_orchestrator.TradeOrchestratorTests.test_assign_trade_picks_least_loaded -v
```

Load/benchmark scripts (need real Redis, and for `demo`/full-path modes, `.env` demo keys +
feed/engine/router running): `tests/load/phase2_sharding_benchmark.py`,
`tests/load/short_bu_ts_limit_async_benchmark.py`, `tests/load/short_bu_ts_limit_multiprocess_benchmark.py` — see
"Бенчмарки и тесты" in [quickstart.md](quickstart.md) for exact invocations and expected output.

Manual one-off checks (hit real Bybit API, use `.env` keys):

```bash
python -m bybit_logic.ready_func.ex_api_key_info
celery -A celery_app.celery_config call check_subscription_lifecycle
celery -A celery_app.celery_config call check_api_key_lifecycle
```

## Architecture

### Request flow (multiuser production path)

1. `POST /short_3_limit` (`server_api/routes/trading.py`) receives a raw-text body — ticker plus an optional
   space-separated alert-type marker, parsed by `server_api/utils.py::parse_short_signal_body()`: `"{ticker}"` /
   `"{ticker} SHORT SIGNAL"` → normal trade, `"{ticker} Short1"` → **risk mode** (any other/unknown marker also
   falls back to normal — safe default). It reads `db.list_trading_candidates()` from Mongo, filters out users
   without keys / with `stop_trading` / over `max_concurrent_trades`, requests the feed WS via
   `request_feed_symbol()`, then enqueues one `short_3_limit` Celery task per user (staggered by
   `TRADE_SUBMIT_STAGGER_SEC`), carrying `risk_mode` as a kwarg.
2. `celery_app/tasks/short_3_limit.py` → `celery_app/trade_orchestrator.py::assign_trade()` picks the least-loaded
   `trade_engine_{i}` queue via a Redis Lua script (`engine:{id}:load` / `engine:{id}:alive`), then dispatches
   `engine_execute_trade` onto that queue.
3. The engine worker process (env `CELERY_ENGINE_ID`, `concurrency=1`, cap `MAX_SESSIONS_PER_ENGINE`) hosts a
   **singleton `AsyncTradeEngine`** (daemon thread + asyncio loop) in
   `bybit_logic/api_algorithms/short_bu_ts_limit_engine.py`. `submit_trade()` creates a `TradeSession` holding a
   `TradeState` dataclass — no global mutable state, so many sessions run concurrently in one process.
4. Prices come from `MarketFeedHub` (`bybit_logic/feeds/hybrid_feed_hub.py`): normally Redis Pub/Sub
   (`market:ticker:{SYMBOL}`) published by the standalone `services/market_price_feed` process (one WS per symbol,
   shared across all subscribers trading it); if the feed reports `feed:down`, the engine falls back to opening its
   own local WebSocket for that symbol. Refcounting in Redis governs when feed WS connections open/close.
5. Bybit HTTP calls (pybit) go through `BybitHttpAdapter` via `asyncio.to_thread` so they never block the event loop.
6. `TradeStateStore` (Redis) gives idempotency (`trade_cmd:{tg_id}:{symbol}`) and periodic state snapshots for crash
   recovery.
7. On close: breakeven → trailing stop (`bybit_logic/bybit_func/trailing_stop.py`), trade written to
   `database/history_trades_repository.py` (`state: active → closed`), Telegram notification, feed unsubscribe.

The **nomulti** path (`start_trading_nomulti()`) reuses the exact same async engine with one hardcoded `tg_id`/keys
from `.env` — it is not a separate implementation.

**Not yet migrated to the async engine** (still sync, worker blocks for the whole trade):
`hedge_long_short_bu_ts.py` (two independent long+short legs in hedge mode) and `custom_algo_nomulti.py`
(user-configurable algorithm, config stored in Mongo `custom_algo_configs`). A legacy sync multiuser implementation
is kept for reference/rollback at `bybit_logic/api_algorithms/_legacy/short_bu_ts_limit_multiuser_sync.py`.

### Layer responsibilities

| Layer | Path | Role |
|---|---|---|
| API | `server_api/` | FastAPI app; routes only validate input and enqueue Celery tasks — no trading logic lives here |
| Task routing | `celery_app/` | Celery config/queues, `trade_orchestrator.py` (engine assignment), `trade_idempotency.py`, task wrappers per algorithm |
| Trading algorithms | `bybit_logic/api_algorithms/` | The actual strategies (async engine + legacy sync ones) |
| Bybit primitives | `bybit_logic/bybit_func/` | Thin wrappers over pybit: session, orders, position, calculator, trailing_stop, api_key_info |
| Price feed | `bybit_logic/feeds/`, `services/market_price_feed/` | `MarketFeedHub`, Redis pub/sub feed process, dual-feed failover |
| Persistence | `database/` | Motor (async) repositories for bot/API; a few sync pymongo repositories used inside Celery fork-workers (subscription/api-key lifecycle, history_trades) — intentional, Motor is not safe across forked workers |
| Telegram bot (multiuser) | `bot/` | aiogram handlers/keyboards/states/languages; profile, subscription, admin, payment screen |
| Telegram bot (single-account) | `bot_nomultiuser/` | Same idea, no Mongo multiuser layer, driven from `.env` |

### Config loading pattern

`config.py` (repo root) is the shared config; `bot/config.py`, `bot_nomultiuser/config.py`, `bybit_logic/config.py`,
`celery_app/config.py` layer more env vars on top for their own domain. All load via `python-dotenv` from the repo
root `.env`. Notable dual-naming support: `MONGO_URI`/`MONGO_DB` (new) vs `MONGODB_URI`/`MONGODB_DB` (legacy, still
read as fallback), and `LOCAL_SERVER_URL` (internal calls from bot/Celery to the API) vs `SERVER_URL` (public URL,
only used for the startup notification message).

### Subscription & API-key lifecycle (Celery Beat)

Two periodic tasks (`SUBSCRIPTION_LIFECYCLE_CHECK_HOURS`, default 12h, timezone `Europe/Moscow`):
`check_subscription_lifecycle` and `check_api_key_lifecycle`. Both use idempotency flags stored per-user in Mongo
(`notify_3d_for_end` / `notify_1d_for_end` / `notify_expired_for_end` under `subscription_data`; equivalent
`notify_api_key_*` under `bybit_data`) keyed to the current expiry date, so extending a subscription/renewing a key
naturally resets reminders. `POST /short_3_limit` only ever picks up users with `subscription_data.subscription: true`.

### Trade amount limits

Regular users are capped at `balance × RECOMMENDED_TRADE_AMOUNT_PERCENT / 100` (`bybit_logic/bybit_func/calculator.py`).
Users listed in Mongo `app_settings` (`_id: trade_amount_unlimited_tg_ids`) bypass the cap (still get a risk
confirmation prompt above the recommended amount). `ADMIN_IDS` are auto-added to that whitelist on every
`bot.main` start.

### Risk mode ("Short1" alert)

`/short_3_limit` accepts an optional alert-type marker after the ticker in the raw webhook body
(`server_api/utils.py::parse_short_signal_body()`): `"{ticker} Short1"` (case-insensitive) sets
`risk_mode=True`; `"{ticker}"`, `"{ticker} SHORT SIGNAL"`, or any other/unrecognized marker is the normal
trade — this is a safe-default fallback, not an error. `risk_mode` is threaded as a plain kwarg through
`trade_jobs` → `short_3_limit` task → `trade_orchestrator.assign_trade()` → `engine_execute_trade` →
`AsyncTradeEngine.submit_trade()` → `TradeState.risk_mode`. In `TradeSession` it overrides, for that one
trade only: the breakeven/trailing-stop activation threshold (`RISK_MODE_TRIGGER_PERCENTAGE`, default 1%,
vs. the normal `TRIGGER_PERCENTAGE`/averaging-aware threshold), the initial stop-loss
(`RISK_MODE_STOP_LOSS_PERCENTAGE`, default 10%, vs. `STOP_LOSS_PERCENTAGE`), and skips the DCA limit-order
placement entirely (`place_n_limit_order`) — there is still no hard take-profit order anywhere in this
engine, profit-taking always goes through breakeven+trailing, just at a tighter threshold in risk mode.
The user's launch notification gets an extra "⚠️ Сделка с повышенным риском" line. Scope: `/short_3_limit`
(multiuser) only — nomulti/hedge/custom_algo/demo_showcase don't pass `risk_mode` and are unaffected.

### Payment flow

Manual crypto payment, not a payment gateway: user sees a QR + `URL_PAYMENT` wallet address → submits a payment ID →
confirms "✅ Всё верно" (only then does the admin get notified, via `AdminOpenUserCb` / `AdminConfirmSubscriptionCb`
etc. callbacks carrying `tg_id`, independent of FSM state) → admin approves/rejects → user gets a Telegram DM either
way.

## Non-obvious conventions

- Sync pymongo (not Motor) is used deliberately inside Celery tasks/repositories that run in forked worker
  processes — see `database/history_trades_repository.py`, `database/subscription_lifecycle_repository.py`,
  `database/api_key_lifecycle_repository.py`.
- `worker_prefetch_multiplier=1` and single-concurrency workers throughout — this is load-bearing for the
  singleton-`AsyncTradeEngine`-per-process design, not an arbitrary tuning choice.
- Stopping trading (`POST /stop_trading_by_symbol`, `/stop_trading_all`) only acts on the `.env` account keys; it
  does not touch per-user multiuser sessions — those self-terminate on `size=0` or manual exchange-side closure, or
  via the `/user_stop_trading_*` endpoints which target one `tg_id`'s own keys.
- Leverage is set centrally through `bybit_logic/bybit_func/position.py::set_leverage`; by default the strict mode
  refuses to open a position if requested leverage exceeds the instrument's exchange max (rather than silently
  clamping) and notifies subscribers.
