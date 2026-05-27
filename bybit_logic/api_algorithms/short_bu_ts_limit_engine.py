"""
Production async execution-engine для short BU TS limit (multiuser).

Ключевые свойства:
- без глобального mutable состояния;
- MarketFeedHub: Redis price feed + local WS fallback (Phase 2);
- sync pybit HTTP через asyncio.to_thread;
- idempotency + snapshots в Redis для recovery.
"""
from __future__ import annotations

import asyncio
import json
import os
from datetime import date, datetime
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import dotenv

from bybit_logic.bybit_func import calculator, market, orders, position, session, stop_trade
from bybit_logic.bybit_func.trailing_stop import TrailingStop
from bybit_logic.feeds.feed_config import MAX_SESSIONS_PER_ENGINE
from bybit_logic.feeds.hybrid_feed_hub import MarketFeedHub
from celery_app.config import REDIS_URL
from celery_app.tasks.notifications import send_notification_to_user_task
from config import USE_DEMO as USE_DEMO_FROM_ENV
from database.history_trades_repository import build_trade_doc, history_trades_db
from logger_config import setup_logger

dotenv.load_dotenv()
logger = setup_logger(__name__)

# Переопределяется в тестах/benchmark; по умолчанию из .env (config.USE_DEMO).
USE_DEMO = USE_DEMO_FROM_ENV

TRIGGER_PERCENTAGE = float(os.getenv("TRIGGER_PERCENTAGE"))
TRIGGER_TS_PERCENTAGE = float(os.getenv("TRIGGER_TS_PERCENTAGE"))
TRIGGER_PERCENTAGE_INITIAL_TS = TRIGGER_PERCENTAGE + 1
STOP_LOSS_PERCENTAGE = float(os.getenv("STOP_LOSS_PERCENTAGE"))
CORRECTION_SL_PERCENTAGE = float(os.getenv("CORRECTION_SL_PERCENTAGE"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
LEVERAGE = 10
COUNT_LIMIT_ORDERS = int(os.getenv("COUNT_LIMIT_ORDERS"))
LIMIT_PERCENTAGE = float(os.getenv("LIMIT_PERCENTAGE"))
PNL_LOG_INTERVAL = float(os.getenv("PNL_LOG_INTERVAL"))
SNAPSHOT_INTERVAL_SECONDS = 3.0


def _hedge_leg_position_idx(side: str | None) -> int:
    return 1 if (side or "").strip() == "Buy" else 2


def _json_default(obj: Any) -> str:
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


@dataclass
class TradeState:
    trade_id: str
    symbol: str
    tg_id: int
    name: str
    sum_for_trades: float
    algorithms_sum_for_trades: float
    api_key: str = field(repr=False)
    api_secret: str = field(repr=False)
    entry_price: float | None = None
    position_qty: float | None = None
    trigger_called: bool = False
    current_price: float | None = None
    price_change_percent: float = 0.0
    pnl_usdt: float = 0.0
    last_log_time: int = 0
    previous_avg_price: float | None = None
    previous_position_size: float | None = None
    last_position_check_time: float = 0.0
    should_stop: bool = False
    trade_saved: bool = False
    closed_position_info: dict[str, Any] | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    started: bool = False
    position_opened: bool = False
    trailing_active: bool = False
    last_snapshot_at: float = 0.0
    active_position_idx: int | None = None


class TradeStateStore:
    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import redis
            self._client = redis.Redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    def snapshot_key(self, trade_id: str) -> str:
        return f"trade_state:{trade_id}"

    def idempotency_key(self, symbol: str, tg_id: int) -> str:
        return f"trade_cmd:{tg_id}:{symbol.upper()}"

    async def save_snapshot(self, state: TradeState) -> None:
        payload = asdict(state)
        payload.pop("api_key", None)
        payload.pop("api_secret", None)
        await asyncio.to_thread(
            self.client.set,
            self.snapshot_key(state.trade_id),
            json.dumps(payload, ensure_ascii=False, default=_json_default),
            ex=60 * 60 * 8,
        )

    async def clear_snapshot(self, trade_id: str) -> None:
        await asyncio.to_thread(self.client.delete, self.snapshot_key(trade_id))

    async def acquire_idempotency(self, symbol: str, tg_id: int, ttl_seconds: int = 60 * 60 * 4) -> bool:
        key = self.idempotency_key(symbol, tg_id)
        return bool(await asyncio.to_thread(self.client.set, key, "1", ex=ttl_seconds, nx=True))

    async def release_idempotency(self, symbol: str, tg_id: int) -> None:
        await asyncio.to_thread(self.client.delete, self.idempotency_key(symbol, tg_id))


class BybitHttpAdapter:
    async def create_session(self, api_key: str, api_secret: str):
        return await asyncio.to_thread(session.create_session, use_demo=USE_DEMO, api_key=api_key, api_secret=api_secret)

    async def if_position_open(self, http_session, symbol: str) -> bool:
        return bool(await asyncio.to_thread(position.if_position_open, http_session, symbol))

    async def set_leverage(self, http_session, symbol: str, leverage: int = 10) -> dict[str, Any]:
        return await asyncio.to_thread(position.set_leverage, http_session, symbol, leverage)

    async def get_ticker_price(self, http_session, symbol: str) -> float:
        tickers = await asyncio.to_thread(market.get_tickers_by_symbol, http_session, symbol)
        return float(tickers["result"]["list"][0]["lastPrice"])

    async def calculate_qty(self, symbol: str, amount: float, http_session) -> float:
        return float(await asyncio.to_thread(calculator.calculate_qty, symbol, amount, http_session))

    async def place_order(
        self,
        symbol: str,
        qty: float,
        side: str,
        http_session,
        *,
        position_idx: int | None = None,
    ) -> dict[str, Any] | None:
        return await asyncio.to_thread(
            lambda: orders.place_order(
                symbol, qty, side, "Market", http_session, position_idx=position_idx
            )
        )

    async def get_positions_by_symbol(self, http_session, symbol: str):
        return await asyncio.to_thread(position.get_positions_by_symbol, http_session, symbol)

    async def set_stop_loss(
        self,
        symbol: str,
        stop_loss_price: float,
        http_session,
        *,
        position_idx: int | None = None,
    ):
        return await asyncio.to_thread(
            lambda: orders.set_stop_loss(
                symbol, stop_loss_price, http_session, position_idx=position_idx
            )
        )

    async def place_n_limit_order(
        self,
        symbol: str,
        amount: float,
        side: str,
        entry_price: float,
        http_session,
        *,
        position_idx: int | None = None,
    ):
        return await asyncio.to_thread(
            lambda: orders.place_n_limit_order_v2(
                symbol,
                amount,
                side,
                entry_price,
                http_session,
                COUNT_LIMIT_ORDERS,
                LIMIT_PERCENTAGE,
                position_idx=position_idx,
            )
        )

    async def set_breakeven_with_retries(
        self,
        symbol: str,
        current_price: float,
        http_session,
        side: str,
        *,
        position_idx: int | None = None,
    ):
        return await asyncio.to_thread(
            lambda: orders.set_stop_loss_with_breakeven_retries(
                symbol,
                current_price,
                http_session,
                side,
                correction_percent_start=CORRECTION_SL_PERCENTAGE,
                correction_percent_stop=2.0,
                correction_percent_step=0.5,
                position_idx=position_idx,
            )
        )

    async def stop_trading(self, symbol: str, http_session) -> None:
        await asyncio.to_thread(stop_trade.stop_trading_by_symbol, symbol, http_session)

    async def get_result_position_info(self, symbol: str, http_session):
        return await asyncio.to_thread(position.result_position_info_data, symbol, http_session)


class TradeSession:
    def __init__(
        self,
        state: TradeState,
        adapter: BybitHttpAdapter,
        feed_hub: MarketFeedHub,
        store: TradeStateStore,
    ) -> None:
        self.state = state
        self.adapter = adapter
        self.feed_hub = feed_hub
        self.store = store
        self.http_session = None
        self.trailing_stop: TrailingStop | None = None
        self._queue: asyncio.Queue[float] | None = None
        self._lock = asyncio.Lock()

    def _notify_user(self, text: str) -> None:
        """Multiuser: уведомление только владельцу сделки (tg_id), без рассылки subscribers."""
        send_notification_to_user_task.delay(int(self.state.tg_id), text)

    def _close_info_from_state(self) -> dict[str, Any]:
        s = self.state
        return {
            "symbol": s.symbol,
            "side": POSITION_SIDE or "Sell",
            "entry_price": float(s.entry_price or 0),
            "exit_price": float(s.current_price or 0),
            "pnl_usdt": float(s.pnl_usdt or 0),
            "is_open": False,
            "source": "trade_state",
        }

    def _merge_close_info(self, exchange_info: dict[str, Any] | None) -> dict[str, Any]:
        """Bybit closed PnL + fallback на последние значения из TradeState."""
        state_info = self._close_info_from_state()
        if not exchange_info:
            return state_info
        merged = dict(exchange_info)
        merged.setdefault("symbol", state_info["symbol"])
        if not merged.get("side"):
            merged["side"] = state_info["side"]
        if not float(merged.get("entry_price") or 0):
            merged["entry_price"] = state_info["entry_price"]
        if not float(merged.get("exit_price") or 0):
            merged["exit_price"] = state_info["exit_price"]
        if float(merged.get("pnl_usdt") or 0) == 0 and state_info["pnl_usdt"]:
            merged["pnl_usdt"] = state_info["pnl_usdt"]
        merged["source"] = "exchange"
        return merged

    def _format_close_notification(self, close_info: dict[str, Any]) -> str:
        side_raw = close_info.get("side") or POSITION_SIDE or "Sell"
        side_label = "Лонг" if side_raw == "Buy" else "Шорт"
        pnl = float(close_info.get("pnl_usdt") or 0)
        pnl_sign = "+" if pnl >= 0 else ""
        source = close_info.get("source", "")
        source_note = ""
        if source == "trade_state":
            source_note = "\nℹ️ Итог по последней цене в алгоритме (Bybit ещё не отдал closed PnL)"
        return (
            "🔄 Позиция закрыта\n\n"
            f"📊 Символ: {close_info.get('symbol') or self.state.symbol}\n"
            f"📈 Сторона: {side_label}\n"
            f"💰 Цена входа: {float(close_info.get('entry_price') or 0):.8g}\n"
            f"💸 Цена выхода: {float(close_info.get('exit_price') or 0):.8g}\n"
            f"💵 Финальный PnL: {pnl_sign}{pnl:.2f} USDT"
            f"{source_note}"
        )

    async def _fetch_closed_position_from_exchange(
        self,
        *,
        retries: int = 3,
        delay_sec: float = 1.0,
    ) -> dict[str, Any] | None:
        if self.http_session is None:
            return None
        symbol = self.state.symbol
        for attempt in range(1, retries + 1):
            position_info = await self.adapter.get_result_position_info(symbol, self.http_session)
            if position_info and position_info.get("is_open") is not True:
                logger.info(
                    "Closed position from exchange: symbol=%s attempt=%s pnl=%s",
                    symbol,
                    attempt,
                    position_info.get("pnl_usdt"),
                )
                return position_info
            if attempt < retries:
                await asyncio.sleep(delay_sec)
        logger.warning("Exchange closed PnL not ready for %s after %s attempts", symbol, retries)
        return None

    async def run(self) -> None:
        try:
            await self._bootstrap()
            await self._price_loop()
        except Exception as e:
            logger.error("❌ Ошибка TradeSession trade_id=%s: %s", self.state.trade_id, e, exc_info=True)
        finally:
            await self._cleanup()

    async def _bootstrap(self) -> None:
        s = self.state
        s.started = True
        s.updated_at = time.time()
        self.http_session = await self.adapter.create_session(s.api_key, s.api_secret)

        leverage_result = await self.adapter.set_leverage(self.http_session, s.symbol, LEVERAGE)
        if not leverage_result.get("ok"):
            if leverage_result.get("error_type") == "leverage_too_high":
                max_lev = leverage_result.get("max_leverage")
                self._notify_user(
                    "❌ Позиция не открыта: ограничение плеча\n\n"
                    f"📊 Символ: {s.symbol}\n"
                    f"🎯 Запрошено: {LEVERAGE}x\n"
                    f"📉 Максимум по инструменту: {max_lev}x\n"
                    "ℹ️ По правилам проекта снижение плеча отключено",
                )
            logger.error(
                "❌ Не удалось установить кредитное плечо %sx trade_id=%s symbol=%s: %s",
                LEVERAGE, s.trade_id, s.symbol, leverage_result
            )
            s.should_stop = True
            return

        if os.getenv("FORCE_LINEAR_ONE_WAY", "true").strip().lower() in ("true", "1", "yes"):
            await asyncio.to_thread(position.try_switch_linear_one_way, self.http_session, s.symbol)

        if await self.adapter.if_position_open(self.http_session, s.symbol):
            self._notify_user(
                f"⚠️ Дубликат отфильтрован\n\n📊 Символ: {s.symbol}\n"
                "ℹ️ По этой монете у вас уже открыта позиция — новый вход пропущен"
            )
            s.should_stop = True
            return

        s.active_position_idx = None
        qty = await self.adapter.calculate_qty(s.symbol, s.algorithms_sum_for_trades, self.http_session)
        leg_idx = _hedge_leg_position_idx(POSITION_SIDE)
        order_result = await self.adapter.place_order(s.symbol, qty, POSITION_SIDE, self.http_session)
        if order_result and order_result.get("retCode") == 0:
            s.active_position_idx = None
        else:
            logger.warning(
                "Повтор входа Market с positionIdx=%s trade_id=%s (hedge / режим позиции)",
                leg_idx,
                s.trade_id,
            )
            order_result = await self.adapter.place_order(
                s.symbol, qty, POSITION_SIDE, self.http_session, position_idx=leg_idx
            )
            if order_result and order_result.get("retCode") == 0:
                s.active_position_idx = leg_idx
            else:
                s.active_position_idx = None

        if not order_result or order_result.get("retCode") != 0:
            logger.error("❌ Ошибка открытия позиции trade_id=%s: %s", s.trade_id, order_result)
            err = order_result or {}
            err_text = err.get("retMsg") or str(err)[:300]
            self._notify_user(
                f"❌ Позиция не открыта\n\n📊 Символ: {s.symbol}\n"
                f"💰 Сумма: {s.sum_for_trades} USDT\n"
                f"📈 Сторона: {POSITION_SIDE}\n"
                f"ℹ️ Bybit: {err_text}"
            )
            s.should_stop = True
            return

        self._notify_user(
            f"🚀 Алгоритм запущен!\n\n📊 Символ: {s.symbol}\n"
            f"💰 Сумма: {s.sum_for_trades} USDT\n📈 Сторона: {POSITION_SIDE}\n"
        )

        self.trailing_stop = TrailingStop(
            symbol=s.symbol,
            session=self.http_session,
            trigger_percentage=TRIGGER_TS_PERCENTAGE,
            position_side=POSITION_SIDE,
            offset_percentage=0.1,
            position_idx=s.active_position_idx,
        )

        await asyncio.sleep(1)
        position_data = await self.adapter.get_positions_by_symbol(self.http_session, s.symbol)
        if not position_data or not position_data.get("result", {}).get("list"):
            logger.error("❌ Не удалось получить позицию trade_id=%s", s.trade_id)
            s.should_stop = True
            return
        rows = position_data["result"]["list"]
        position_info = None
        for row in rows:
            sz = float(row.get("size", 0) or 0)
            if sz <= 0:
                continue
            if s.active_position_idx is not None:
                if int(row.get("positionIdx", 0) or 0) == int(s.active_position_idx):
                    position_info = row
                    break
            else:
                position_info = row
                break
        if position_info is None and rows:
            position_info = rows[0]
        s.entry_price = float(position_info["avgPrice"])
        s.position_qty = float(position_info["size"])
        s.previous_avg_price = s.entry_price
        s.previous_position_size = s.position_qty
        s.last_position_check_time = time.time()
        s.position_opened = True

        sl = calculator.calculate_stop_loss(s.entry_price, STOP_LOSS_PERCENTAGE, POSITION_SIDE)
        await self.adapter.set_stop_loss(s.symbol, sl, self.http_session, position_idx=s.active_position_idx)
        await self.adapter.place_n_limit_order(
            s.symbol,
            s.algorithms_sum_for_trades,
            POSITION_SIDE,
            s.entry_price,
            self.http_session,
            position_idx=s.active_position_idx,
        )
        self._queue = await self.feed_hub.subscribe(s.symbol)

    async def _price_loop(self) -> None:
        if self._queue is None:
            return
        while not self.state.should_stop:
            price = await self._queue.get()
            async with self._lock:
                await self._on_price(price)
            await self._maybe_snapshot()

    async def _on_price(self, current_price: float) -> None:
        s = self.state
        s.current_price = current_price
        if s.entry_price is None or s.position_qty is None:
            return

        if POSITION_SIDE == "Buy":
            s.price_change_percent = ((current_price - s.entry_price) / s.entry_price) * 100
            s.pnl_usdt = (current_price - s.entry_price) * s.position_qty
        else:
            s.price_change_percent = ((s.entry_price - current_price) / s.entry_price) * 100
            s.pnl_usdt = (s.entry_price - current_price) * s.position_qty

        if s.price_change_percent >= TRIGGER_PERCENTAGE and not s.trigger_called:
            if await self._apply_breakeven_and_activate_trailing():
                s.trigger_called = True

        if self.trailing_stop is not None and self.trailing_stop.is_active:
            await asyncio.to_thread(self.trailing_stop.update, current_price)

        now = int(time.time())
        if now % int(PNL_LOG_INTERVAL) == 0 and now != s.last_log_time:
            s.last_log_time = now
            pnl_sign = "+" if s.pnl_usdt >= 0 else ""
            logger.info("📊 [%s:%s] %.8g | %+.2f%% | %s%.2f USDT", s.tg_id, s.symbol, current_price, s.price_change_percent, pnl_sign, s.pnl_usdt)

        await self._check_position_once()
        s.updated_at = time.time()

    async def _apply_breakeven_and_activate_trailing(self) -> bool:
        s = self.state
        if s.current_price is None:
            return False
        ok, _, _ = await self.adapter.set_breakeven_with_retries(
            s.symbol,
            s.current_price,
            self.http_session,
            POSITION_SIDE,
            position_idx=s.active_position_idx,
        )
        if not ok:
            return False
        if self.trailing_stop is None:
            return True
        await asyncio.to_thread(self.trailing_stop.activate, s.current_price)
        s.trailing_active = True
        if s.price_change_percent >= TRIGGER_PERCENTAGE_INITIAL_TS:
            await asyncio.to_thread(self.trailing_stop.set_initial_stop, s.current_price)
        return True

    async def _check_position_once(self, interval: float = 1.0) -> None:
        s = self.state
        now = time.time()
        if now - s.last_position_check_time < interval:
            return
        s.last_position_check_time = now

        position_data = await self.adapter.get_positions_by_symbol(self.http_session, s.symbol)
        if not position_data or not position_data.get("result", {}).get("list"):
            return
        info = position_data["result"]["list"][0]
        current_size = float(info.get("size", 0))
        current_avg_price = float(info.get("avgPrice", 0))

        if current_size == 0:
            s.should_stop = True
            exchange_info = await self._fetch_closed_position_from_exchange()
            close_info = self._merge_close_info(exchange_info)
            await self._persist_closed_trade(close_info)
            try:
                await self.adapter.stop_trading(s.symbol, self.http_session)
            except Exception as e:
                logger.warning("stop_trading after close %s: %s", s.symbol, e)
            self._notify_user(self._format_close_notification(close_info))
            return

        if s.previous_avg_price is None or s.entry_price is None:
            s.previous_avg_price = current_avg_price
            s.previous_position_size = current_size
            s.entry_price = current_avg_price
            s.position_qty = current_size
            return

        if abs(current_avg_price - s.previous_avg_price) > 1e-8 or abs(current_size - (s.previous_position_size or 0)) > 1e-8:
            s.entry_price = current_avg_price
            s.position_qty = current_size
            s.previous_avg_price = current_avg_price
            s.previous_position_size = current_size

    async def _persist_closed_trade(self, close_info: dict[str, Any]) -> None:
        """Mongo history + statistics; ошибки не блокируют Telegram (данные уже в close_info)."""
        s = self.state
        if s.trade_saved:
            return
        if self.http_session is None:
            s.closed_position_info = close_info
            return

        s.closed_position_info = close_info
        pnl_usdt = float(close_info.get("pnl_usdt") or 0)

        try:
            trade_doc = build_trade_doc(
                tg_id=int(s.tg_id),
                name=s.name,
                symbol=s.symbol,
                position_info=close_info,
            )
            await asyncio.to_thread(history_trades_db.insert_closed_trade, trade_doc)
        except Exception as e:
            logger.error("❌ Ошибка insert_closed_trade tg_id=%s: %s", s.tg_id, e, exc_info=True)

        try:
            await asyncio.to_thread(
                history_trades_db.apply_user_statistics_delta,
                int(s.tg_id),
                pnl_usdt,
            )
        except Exception as e:
            logger.error("❌ Ошибка apply_user_statistics_delta tg_id=%s: %s", s.tg_id, e, exc_info=True)

        s.trade_saved = True

    async def _maybe_snapshot(self) -> None:
        now = time.time()
        if now - self.state.last_snapshot_at < SNAPSHOT_INTERVAL_SECONDS:
            return
        self.state.last_snapshot_at = now
        await self.store.save_snapshot(self.state)

    async def _cleanup(self) -> None:
        s = self.state
        if self._queue is not None:
            await self.feed_hub.unsubscribe(s.symbol, self._queue)
        await self.store.clear_snapshot(s.trade_id)
        await self.store.release_idempotency(s.symbol, s.tg_id)
        try:
            from celery_app.trade_orchestrator import release_engine_slot

            release_engine_slot()
        except Exception:
            pass


class AsyncTradeEngine:
    def __init__(self) -> None:
        self.feed_hub = MarketFeedHub()
        self.adapter = BybitHttpAdapter()
        self.store = TradeStateStore(REDIS_URL)
        self._tasks: dict[str, asyncio.Task] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._boot_lock = threading.Lock()

    def ensure_started(self) -> None:
        with self._boot_lock:
            if self._thread and self._thread.is_alive():
                return
            self._thread = threading.Thread(target=self._run_loop, daemon=True, name="async-trade-engine")
            self._thread.start()
            deadline = time.time() + 5
            while self._loop is None and time.time() < deadline:
                time.sleep(0.05)
            if self._loop is None:
                raise RuntimeError("Не удалось запустить event loop AsyncTradeEngine")

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self.feed_hub.attach_loop(loop)
        loop.create_task(self.feed_hub.start_watch())
        loop.run_forever()

    def submit_trade(
        self,
        symbol: str,
        tg_id: int,
        name: str,
        api_key: str,
        api_secret: str,
        sum_for_trades: float,
        trade_id: str | None = None,
    ) -> str:
        self.ensure_started()
        tid = trade_id or f"{tg_id}:{symbol.upper()}:{uuid.uuid4().hex[:10]}"
        fut = asyncio.run_coroutine_threadsafe(
            self._submit_trade_async(
                trade_id=tid,
                symbol=symbol,
                tg_id=tg_id,
                name=name,
                api_key=api_key,
                api_secret=api_secret,
                sum_for_trades=sum_for_trades,
            ),
            self._loop,
        )
        fut.result(timeout=10)
        return tid

    async def _submit_trade_async(self, trade_id: str, symbol: str, tg_id: int, name: str, api_key: str, api_secret: str, sum_for_trades: float) -> None:
        symbol = symbol.upper()
        if len(self._tasks) >= MAX_SESSIONS_PER_ENGINE:
            raise RuntimeError(
                f"Engine at capacity ({MAX_SESSIONS_PER_ENGINE} sessions). "
                "Use trade orchestrator to route to another engine."
            )
        ok = await self.store.acquire_idempotency(symbol=symbol, tg_id=tg_id)
        if not ok:
            logger.warning("⏭️ Дубликат команды отфильтрован: tg_id=%s symbol=%s", tg_id, symbol)
            try:
                from celery_app.trade_orchestrator import release_engine_slot

                release_engine_slot()
            except Exception:
                pass
            return

        state = TradeState(
            trade_id=trade_id,
            symbol=symbol,
            tg_id=int(tg_id),
            name=name or "",
            api_key=api_key,
            api_secret=api_secret,
            sum_for_trades=float(sum_for_trades),
            algorithms_sum_for_trades=float(sum_for_trades) * 10,
        )
        session_runner = TradeSession(state=state, adapter=self.adapter, feed_hub=self.feed_hub, store=self.store)
        task = asyncio.create_task(session_runner.run(), name=f"trade:{trade_id}")
        self._tasks[trade_id] = task
        task.add_done_callback(lambda _: self._tasks.pop(trade_id, None))

    def running_count(self) -> int:
        return len(self._tasks)

    def local_ws_count(self) -> int:
        return self.feed_hub.local_stream_count()


_engine_singleton: AsyncTradeEngine | None = None


def get_async_trade_engine() -> AsyncTradeEngine:
    global _engine_singleton
    if _engine_singleton is None:
        _engine_singleton = AsyncTradeEngine()
    return _engine_singleton


def start_trading(
    symbol: str,
    tg_id: int,
    name: str,
    api_key: str,
    api_secret: str,
    sum_for_trades: float,
) -> str:
    """
    Стартует async-торговую сессию и сразу возвращает trade_id.
    Исполнение идёт в фоне в AsyncTradeEngine (daemon thread + event loop).
    """
    engine = get_async_trade_engine()
    return engine.submit_trade(
        symbol=symbol,
        tg_id=tg_id,
        name=name,
        api_key=api_key,
        api_secret=api_secret,
        sum_for_trades=float(sum_for_trades),
    )


def _resolve_nomulti_sum(sum_for_trades: float | None) -> float:
    if sum_for_trades is not None:
        return float(sum_for_trades)
    raw = os.getenv("SHORT_BU_TS_LIMIT_USDT_AMOUNT") or os.getenv("USDT_AMOUNT")
    if raw is None or str(raw).strip() == "":
        raise ValueError("Задайте SHORT_BU_TS_LIMIT_USDT_AMOUNT или USDT_AMOUNT в .env")
    value = float(raw)
    if value <= 0:
        raise ValueError("Сумма для торговли должна быть > 0")
    return value


def start_trading_nomulti(
    symbol: str,
    *,
    use_demo: bool | None = None,
    sum_for_trades: float | None = None,
) -> str:
    """
    Nomulti: один аккаунт из .env (API_KEY / DEMO_API_KEY), тот же async-движок.
    tg_id — NOMULTI_TG_ID или ADMIN_CHAT_ID для уведомлений и history_trades.
    """
    effective_demo = bool(use_demo) if use_demo is not None else USE_DEMO_FROM_ENV
    if use_demo is not None:
        global USE_DEMO
        USE_DEMO = effective_demo

    from bybit_logic.config import API_KEY, API_SECRET, DEMO_API_KEY, DEMO_API_SECRET

    if effective_demo:
        api_key = (DEMO_API_KEY or "").strip()
        api_secret = (DEMO_API_SECRET or "").strip()
    else:
        api_key = (API_KEY or "").strip()
        api_secret = (API_SECRET or "").strip()
    if not api_key or not api_secret:
        raise ValueError(
            "В .env не заданы API_KEY/API_SECRET (или DEMO_* при USE_DEMO=true)"
        )

    tg_raw = os.getenv("NOMULTI_TG_ID") or os.getenv("ADMIN_CHAT_ID") or "0"
    tg_id = int(tg_raw)
    amount = _resolve_nomulti_sum(sum_for_trades)
    return start_trading(
        symbol=symbol,
        tg_id=tg_id,
        name=os.getenv("NOMULTI_USER_NAME", "nomulti"),
        api_key=api_key,
        api_secret=api_secret,
        sum_for_trades=amount,
    )
