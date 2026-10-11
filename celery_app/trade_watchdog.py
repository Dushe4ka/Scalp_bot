"""
Сторож сделок: сверка «active-сделка в Mongo» ↔ «живая сессия в движке» ↔ «позиция на бирже».

Ловит любые причины, по которым сделка осталась без сопровождения (умер процесс движка,
сессия не получает цены, позицию закрыли вручную при мёртвой сессии):

- сессия жива, но цен нет дольше WATCHDOG_NO_PRICE_ALERT_SEC → алерт админам;
- сессии нет, позиция на бирже открыта → алерт админам (брейк-ивен/трейлинг не работают);
- сессии нет, позиции нет → сделка закрыта вне алгоритма: закрываем запись, считаем
  статистику и шлём пользователю то же уведомление «Позиция закрыта», что и алгоритм.

Пульс сессий пишет AsyncTradeEngine (ключ trade_alive:{trade_id}). Закрытие атомарное
(history_trades_db.claim_close), поэтому движок и сторож не могут закрыть сделку дважды.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Callable, Protocol

from bybit_logic.api_algorithms.trade_close_format import format_close_notification
from logger_config import setup_logger

logger = setup_logger(__name__)

WATCHDOG_INTERVAL_SEC = float(os.getenv("WATCHDOG_INTERVAL_SEC", "60"))
# Сессии нет дольше этого после открытия сделки → проверяем биржу (пульс пишется каждые 15 с).
WATCHDOG_GRACE_SEC = float(os.getenv("WATCHDOG_GRACE_SEC", "180"))
WATCHDOG_NO_PRICE_ALERT_SEC = float(os.getenv("WATCHDOG_NO_PRICE_ALERT_SEC", "300"))
# Позиции нет, но Bybit ещё не отдал closed PnL — ждём, потом закрываем с PnL = 0 и алертом.
WATCHDOG_PNL_WAIT_SEC = float(os.getenv("WATCHDOG_PNL_WAIT_SEC", "600"))
WATCHDOG_ALERT_REPEAT_SEC = int(os.getenv("WATCHDOG_ALERT_REPEAT_SEC", "3600"))


class ExchangeGateway(Protocol):
    def get_open_size(self, api_key: str, api_secret: str, symbol: str) -> float: ...

    def get_closed_pnl_since(
        self, api_key: str, api_secret: str, symbol: str, since_ts: float
    ) -> dict[str, Any] | None: ...

    def get_last_price(self, api_key: str, api_secret: str, symbol: str) -> float: ...


def _created_ts(doc: dict[str, Any]) -> float:
    created = doc.get("created_at")
    if isinstance(created, datetime):
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)  # history_trades пишет utcnow()
        return created.timestamp()
    return 0.0


def aggregate_closed_pnl(rows: list[dict[str, Any]], since_ts: float) -> dict[str, Any] | None:
    """
    Суммирует Bybit closed PnL по закрытиям после открытия сделки (позиция может
    закрываться частями: трейлинг, ручное частичное закрытие).
    """
    since_ms = since_ts * 1000
    own = [r for r in rows if float(r.get("updatedTime") or 0) >= since_ms]
    if not own:
        return None
    total_qty = sum(float(r.get("closedSize") or 0) for r in own)
    pnl = sum(float(r.get("closedPnl") or 0) for r in own)
    if total_qty > 0:
        exit_price = sum(
            float(r.get("avgExitPrice") or 0) * float(r.get("closedSize") or 0) for r in own
        ) / total_qty
        entry_price = sum(
            float(r.get("avgEntryPrice") or 0) * float(r.get("closedSize") or 0) for r in own
        ) / total_qty
    else:
        exit_price = float(own[0].get("avgExitPrice") or 0)
        entry_price = float(own[0].get("avgEntryPrice") or 0)
    return {
        "entry_price": entry_price,
        "exit_price": exit_price,
        "pnl_usdt": pnl,
        "size": total_qty,
        "close_ts": max(float(r.get("updatedTime") or 0) for r in own) / 1000,
        "source": "exchange",
    }


class TradeWatchdog:
    def __init__(
        self,
        *,
        history: Any,
        redis_client: Any,
        get_user_keys: Callable[[int], tuple[str, str] | None],
        exchange: ExchangeGateway,
        notify_user: Callable[[int, str], None],
        notify_admins: Callable[[str], None],
        position_side: str,
        skip_tg_ids: set[int] | None = None,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._history = history
        self._redis = redis_client
        self._get_user_keys = get_user_keys
        self._exchange = exchange
        self._notify_user = notify_user
        self._notify_admins = notify_admins
        self._position_side = position_side
        self._skip_tg_ids = skip_tg_ids or set()
        self._now = now

    def run_once(self) -> dict[str, int]:
        summary = {"checked": 0, "alive": 0, "no_price": 0, "orphaned": 0, "closed": 0, "errors": 0}
        for doc in self._history.list_active_trades():
            tg_id = int(doc.get("tg_id") or 0)
            if not doc.get("trade_id") or tg_id in self._skip_tg_ids:
                continue
            summary["checked"] += 1
            try:
                outcome = self._check_trade(doc)
            except Exception as e:
                outcome = "errors"
                logger.error("Watchdog: ошибка проверки %s: %s", doc.get("trade_id"), e, exc_info=True)
            summary[outcome] = summary.get(outcome, 0) + 1
        return summary

    def _check_trade(self, doc: dict[str, Any]) -> str:
        trade_id = str(doc["trade_id"])
        tg_id = int(doc["tg_id"])
        symbol = str(doc.get("symbol") or "").upper()
        now = self._now()
        created_ts = _created_ts(doc)

        heartbeat = self._read_heartbeat(trade_id)
        if heartbeat is not None:
            last_price_at = float(heartbeat.get("last_price_at") or 0)
            silent_since = last_price_at or created_ts
            if silent_since and now - silent_since > WATCHDOG_NO_PRICE_ALERT_SEC:
                self._alert_once(
                    "no_price",
                    trade_id,
                    "⚠️ Сделка не получает цены\n\n"
                    f"👤 tg_id: {tg_id}\n📊 Символ: {symbol}\n🆔 {trade_id}\n"
                    f"⏱ Без цены: {int(now - silent_since)} сек\n"
                    "ℹ️ Сессия жива, но брейк-ивен и трейлинг не срабатывают",
                )
                return "no_price"
            return "alive"

        if created_ts and now - created_ts < WATCHDOG_GRACE_SEC:
            return "alive"  # только что открыта / движок ещё не записал пульс

        keys = self._get_user_keys(tg_id)
        if not keys:
            self._alert_once(
                "no_keys",
                trade_id,
                f"⚠️ Сторож: нет API-ключей для проверки сделки\n\n👤 tg_id: {tg_id}\n"
                f"📊 Символ: {symbol}\n🆔 {trade_id}",
            )
            return "errors"
        api_key, api_secret = keys

        try:
            open_size = self._exchange.get_open_size(api_key, api_secret, symbol)
        except Exception as e:
            self._alert_once(
                "api_error",
                trade_id,
                f"⚠️ Сторож: не удалось проверить позицию на Bybit\n\n👤 tg_id: {tg_id}\n"
                f"📊 Символ: {symbol}\n🆔 {trade_id}\n❗ {str(e)[:200]}",
            )
            return "errors"

        if open_size > 0:
            self._alert_once(
                "orphaned",
                trade_id,
                "🚨 Позиция без сопровождения алгоритма\n\n"
                f"👤 tg_id: {tg_id}\n📊 Символ: {symbol}\n📦 Размер: {open_size:g}\n🆔 {trade_id}\n"
                "ℹ️ Сессии в движке нет — брейк-ивен и трейлинг НЕ работают.\n"
                "👉 Закройте позицию вручную (админка или Bybit) — после закрытия "
                "пользователь получит уведомление автоматически.",
            )
            return "orphaned"

        return self._close_outside_algorithm(doc, api_key, api_secret, created_ts, now)

    def _close_outside_algorithm(
        self, doc: dict[str, Any], api_key: str, api_secret: str, created_ts: float, now: float
    ) -> str:
        trade_id = str(doc["trade_id"])
        tg_id = int(doc["tg_id"])
        symbol = str(doc.get("symbol") or "").upper()

        info = self._exchange.get_closed_pnl_since(api_key, api_secret, symbol, created_ts)
        if info is None:
            first_seen = self._first_seen("pending_close", trade_id, now)
            if now - first_seen < WATCHDOG_PNL_WAIT_SEC:
                return "alive"  # Bybit ещё не отдал closed PnL — попробуем в следующий проход
            # Как движок без closed PnL: итог приблизительно, по последней цене (рыночной).
            last_price = self._exchange.get_last_price(api_key, api_secret, symbol)
            entry_price = float(doc.get("entry_price") or 0)
            size = float(doc.get("size") or 0)
            direction = 1.0 if self._position_side == "Buy" else -1.0
            info = {
                "entry_price": entry_price,
                "exit_price": last_price,
                "pnl_usdt": (last_price - entry_price) * size * direction,
                "source": "market_price",
            }
            self._notify_admins(
                "⚠️ Сторож: позиция закрыта, но Bybit не отдал closed PnL\n\n"
                f"👤 tg_id: {tg_id}\n📊 Символ: {symbol}\n🆔 {trade_id}\n"
                f"ℹ️ Итог посчитан по рыночной цене {last_price:.8g} — сверьте вручную"
            )

        close_info = {
            "symbol": symbol,
            "side": self._position_side,
            "entry_price": float(info.get("entry_price") or doc.get("entry_price") or 0),
            "exit_price": float(info.get("exit_price") or 0),
            "size": float(info.get("size") or doc.get("size") or 0),
            "pnl_usdt": float(info.get("pnl_usdt") or 0),
            "open_time": doc.get("open_time"),
            "close_time": datetime.utcnow().isoformat(),
            "source": info.get("source", "exchange"),
        }
        trade_doc = {
            "trade_id": trade_id,
            "tg_id": tg_id,
            "name": doc.get("name", ""),
            "symbol": symbol,
            "side": close_info["side"],
            "entry_price": close_info["entry_price"],
            "exit_price": close_info["exit_price"],
            "size": close_info["size"],
            "pnl_usdt": close_info["pnl_usdt"],
            "open_time": close_info["open_time"],
            "close_time": close_info["close_time"],
            "source": doc.get("source", "short_3_limit"),
            "closed_by": "watchdog",
        }
        if not self._history.claim_close(trade_doc):
            return "alive"  # движок успел закрыть сам

        try:
            self._history.apply_user_statistics_delta(tg_id, close_info["pnl_usdt"])
        except Exception as e:
            logger.error("Watchdog: статистика tg_id=%s: %s", tg_id, e, exc_info=True)

        self._notify_user(
            tg_id,
            format_close_notification(
                close_info,
                symbol=symbol,
                position_side=self._position_side,
                created_at=created_ts or now,
                closed_at=float(info.get("close_ts") or now),
            ),
        )
        self._notify_admins(
            "ℹ️ Сделка закрыта вне алгоритма (вручную или при неработающей сессии)\n\n"
            f"👤 tg_id: {tg_id}\n📊 Символ: {symbol}\n🆔 {trade_id}\n"
            f"💰 PnL: {close_info['pnl_usdt']:+.2f} USDT\n"
            "✅ Запись закрыта, статистика учтена, пользователь уведомлён"
        )
        self._cleanup_trade_keys(trade_id, tg_id, symbol)
        logger.info("Watchdog: закрыта вне алгоритма %s pnl=%s", trade_id, close_info["pnl_usdt"])
        return "closed"

    def _read_heartbeat(self, trade_id: str) -> dict[str, Any] | None:
        raw = self._redis.get(f"trade_alive:{trade_id}")
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (TypeError, ValueError):
            return {}

    def _alert_once(self, kind: str, trade_id: str, text: str) -> None:
        key = f"watchdog:alert:{kind}:{trade_id}"
        if self._redis.set(key, "1", nx=True, ex=WATCHDOG_ALERT_REPEAT_SEC):
            logger.warning("Watchdog alert %s %s", kind, trade_id)
            self._notify_admins(text)

    def _first_seen(self, kind: str, trade_id: str, now: float) -> float:
        key = f"watchdog:{kind}:{trade_id}"
        self._redis.set(key, str(now), nx=True, ex=int(WATCHDOG_PNL_WAIT_SEC * 3))
        raw = self._redis.get(key)
        try:
            return float(raw)
        except (TypeError, ValueError):
            return now

    def _cleanup_trade_keys(self, trade_id: str, tg_id: int, symbol: str) -> None:
        keys = [
            f"trade_cmd:{tg_id}:{symbol}",  # блокировка повторного входа по монете
            f"trade_state:{trade_id}",
            f"watchdog:pending_close:{trade_id}",
        ]
        keys += [f"watchdog:alert:{k}:{trade_id}" for k in ("no_price", "orphaned", "api_error", "no_keys")]
        try:
            self._redis.delete(*keys)
        except Exception as e:
            logger.warning("Watchdog: не удалось очистить ключи %s: %s", trade_id, e)


class BybitExchangeGateway:
    """Реальная биржа через pybit (sync — сторож работает в Celery-воркере)."""

    def _session(self, api_key: str, api_secret: str):
        from bybit_logic.bybit_func import session
        from config import USE_DEMO

        return session.create_session(use_demo=USE_DEMO, api_key=api_key, api_secret=api_secret)

    def get_open_size(self, api_key: str, api_secret: str, symbol: str) -> float:
        resp = self._session(api_key, api_secret).get_positions(category="linear", symbol=symbol)
        rows = (resp or {}).get("result", {}).get("list", []) or []
        return sum(float(r.get("size") or 0) for r in rows)

    def get_closed_pnl_since(
        self, api_key: str, api_secret: str, symbol: str, since_ts: float
    ) -> dict[str, Any] | None:
        kwargs: dict[str, Any] = {"category": "linear", "symbol": symbol, "limit": 100}
        if since_ts:
            # Bybit: только startTime → окно [startTime, startTime + 7 дней]. Для сделки старше
            # недели берём последние ~7 дней, свои закрытия отфильтрует aggregate_closed_pnl.
            start_ts = max(since_ts, time.time() - 6.9 * 24 * 3600)
            kwargs["startTime"] = int(start_ts * 1000)
        resp = self._session(api_key, api_secret).get_closed_pnl(**kwargs)
        rows = (resp or {}).get("result", {}).get("list", []) or []
        return aggregate_closed_pnl(rows, since_ts)

    def get_last_price(self, api_key: str, api_secret: str, symbol: str) -> float:
        resp = self._session(api_key, api_secret).get_tickers(category="linear", symbol=symbol)
        rows = (resp or {}).get("result", {}).get("list", []) or []
        price = float(rows[0].get("lastPrice") or 0) if rows else 0.0
        if price <= 0:
            raise RuntimeError(f"no last price for {symbol}")
        return price


def build_default_watchdog() -> TradeWatchdog:
    import redis
    from pymongo import MongoClient

    from celery_app.config import REDIS_URL
    from celery_app.tasks.notifications import (
        send_notification_to_admins_task,
        send_notification_to_user_task,
    )
    from config import MONGO_DB, MONGO_URI
    from database.history_trades_repository import history_trades_db
    from demo_showcase.config import DEMO_SHOWCASE_TG_ID

    users = MongoClient(MONGO_URI)[MONGO_DB]["users"]

    def get_user_keys(tg_id: int) -> tuple[str, str] | None:
        doc = users.find_one({"tg_id": int(tg_id)}, {"bybit_data": 1}) or {}
        bybit = doc.get("bybit_data") or {}
        key = (bybit.get("api_key") or "").strip()
        secret = (bybit.get("api_secret") or "").strip()
        return (key, secret) if key and secret else None

    return TradeWatchdog(
        history=history_trades_db,
        redis_client=redis.Redis.from_url(REDIS_URL, decode_responses=True),
        get_user_keys=get_user_keys,
        exchange=BybitExchangeGateway(),
        notify_user=lambda tg_id, text: send_notification_to_user_task.delay(int(tg_id), text),
        notify_admins=lambda text: send_notification_to_admins_task.delay(text),
        position_side=os.getenv("POSITION_SIDE") or "Sell",
        skip_tg_ids={int(DEMO_SHOWCASE_TG_ID)} if DEMO_SHOWCASE_TG_ID else set(),
    )
