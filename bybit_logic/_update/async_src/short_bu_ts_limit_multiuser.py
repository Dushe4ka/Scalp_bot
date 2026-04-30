"""
Асинхронный execution-engine для short алгоритма.

Ключевые свойства:
- без глобального mutable состояния;
- одна WS-подписка на символ (fan-out по сессиям);
- sync pybit HTTP вызовы через asyncio.to_thread;
- idempotency + периодические snapshots для recovery.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any

import dotenv

from bybit_logic.bybit_func import calculator, market, orders, position, session, stop_trade
from bybit_logic.bybit_func.price_stream import PriceStream
from bybit_logic.bybit_func.trailing_stop import TrailingStop
from celery_app.config import REDIS_URL
from celery_app.tasks.notifications import send_notification_task, send_notification_to_user_task
from history_trades_repository import build_trade_doc, history_trades_db
from logger_config import setup_logger

dotenv.load_dotenv()
logger = setup_logger(__name__)

TRIGGER_PERCENTAGE = float(os.getenv("TRIGGER_PERCENTAGE"))
TRIGGER_TS_PERCENTAGE = float(os.getenv("TRIGGER_TS_PERCENTAGE"))
TRIGGER_PERCENTAGE_INITIAL_TS = TRIGGER_PERCENTAGE + 1
STOP_LOSS_PERCENTAGE = float(os.getenv("STOP_LOSS_PERCENTAGE"))
CORRECTION_SL_PERCENTAGE = float(os.getenv("CORRECTION_SL_PERCENTAGE"))
POSITION_SIDE = os.getenv("POSITION_SIDE")
USE_DEMO = False
LEVERAGE = 10
COUNT_LIMIT_ORDERS = int(os.getenv("COUNT_LIMIT_ORDERS"))
LIMIT_PERCENTAGE = float(os.getenv("LIMIT_PERCENTAGE"))
PNL_LOG_INTERVAL = float(os.getenv("PNL_LOG_INTERVAL"))
SNAPSHOT_INTERVAL_SECONDS = 3.0


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
            json.dumps(payload, ensure_ascii=False),
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

    async def place_order(self, symbol: str, qty: float, side: str, http_session) -> dict[str, Any] | None:
        return await asyncio.to_thread(orders.place_order, symbol, qty, side, "Market", http_session)

    async def get_positions_by_symbol(self, http_session, symbol: str):
        return await asyncio.to_thread(position.get_positions_by_symbol, http_session, symbol)

    async def set_stop_loss(self, symbol: str, stop_loss_price: float, http_session):
        return await asyncio.to_thread(orders.set_stop_loss, symbol, stop_loss_price, http_session)

    async def place_n_limit_order(self, symbol: str, amount: float, side: str, entry_price: float, http_session):
        return await asyncio.to_thread(
            orders.place_n_limit_order,
            symbol,
            amount,
            side,
            entry_price,
            http_session,
            COUNT_LIMIT_ORDERS,
            LIMIT_PERCENTAGE,
        )

    async def set_breakeven_with_retries(self, symbol: str, current_price: float, http_session, side: str):
        return await asyncio.to_thread(
            orders.set_stop_loss_with_breakeven_retries,
            symbol,
            current_price,
            http_session,
            side,
            correction_percent_start=CORRECTION_SL_PERCENTAGE,
            correction_percent_stop=2.0,
            correction_percent_step=0.5,
        )

    async def stop_trading(self, symbol: str, http_session) -> None:
        await asyncio.to_thread(stop_trade.stop_trading_by_symbol, symbol, http_session)

    async def get_result_position_info(self, symbol: str, http_session):
        return await asyncio.to_thread(position.result_position_info_data, symbol, http_session)


class MarketFeedHub:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._feeds: dict[str, dict[str, Any]] = {}
        self._lock = threading.Lock()

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    async def subscribe(self, symbol: str) -> asyncio.Queue[float]:
        symbol = symbol.upper()
        queue: asyncio.Queue[float] = asyncio.Queue(maxsize=500)
        with self._lock:
            if symbol not in self._feeds:
                self._feeds[symbol] = {"stream": None, "queues": set(), "started": False}
            entry = self._feeds[symbol]
            entry["queues"].add(queue)
            if not entry["started"]:
                entry["stream"] = self._start_stream(symbol)
                entry["started"] = True
        return queue

    async def unsubscribe(self, symbol: str, queue: asyncio.Queue[float]) -> None:
        symbol = symbol.upper()
        with self._lock:
            entry = self._feeds.get(symbol)
            if not entry:
                return
            entry["queues"].discard(queue)
            if not entry["queues"]:
                stream = entry.get("stream")
                if stream is not None:
                    try:
                        stream.stop()
                    except Exception:
                        pass
                self._feeds.pop(symbol, None)

    def _start_stream(self, symbol: str) -> PriceStream:
        def _dispatch(message: dict[str, Any]) -> None:
            try:
                data = message.get("data")
                if isinstance(data, list):
                    data = data[0] if data else None
                if not data:
                    return
                price = float(data.get("lastPrice", 0))
                if price <= 0:
                    return
            except Exception:
                return
            if self._loop is None:
                return
            self._loop.call_soon_threadsafe(self._publish_price, symbol, price)

        stream = PriceStream(symbol=symbol, price_handler=_dispatch, testnet=False)
        stream.start()
        return stream

    def _publish_price(self, symbol: str, price: float) -> None:
        entry = self._feeds.get(symbol)
        if not entry:
            return
        queues = list(entry["queues"])
        for q in queues:
            if q.full():
                try:
                    q.get_nowait()
                except Exception:
                    pass
            try:
                q.put_nowait(price)
            except Exception:
                pass


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
                send_notification_to_user_task.delay(
                    s.tg_id,
                    "❌ Позиция не открыта: ограничение плеча\n\n"
                    f"👤 Пользователь: {s.name} ({s.tg_id})\n"
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

        if await self.adapter.if_position_open(self.http_session, s.symbol):
            send_notification_task.delay(
                f"⚠️ Дубликат отфильтрован\n\n👤 Пользователь: {s.name} ({s.tg_id})\n📊 Символ: {s.symbol}\nℹ️ По этой монете уже ведется торговля"
            )
            s.should_stop = True
            return

        self.trailing_stop = TrailingStop(
            symbol=s.symbol,
            session=self.http_session,
            trigger_percentage=TRIGGER_TS_PERCENTAGE,
            position_side=POSITION_SIDE,
            offset_percentage=0.1,
        )

        qty = await self.adapter.calculate_qty(s.symbol, s.algorithms_sum_for_trades, self.http_session)
        order_result = await self.adapter.place_order(s.symbol, qty, POSITION_SIDE, self.http_session)
        if not order_result or order_result.get("retCode") != 0:
            logger.error("❌ Ошибка открытия позиции trade_id=%s: %s", s.trade_id, order_result)
            s.should_stop = True
            return

        send_notification_task.delay(
            f"🚀 Алгоритм запущен!\n\n👤 Пользователь: {s.name} ({s.tg_id})\n📊 Символ: {s.symbol}\n💰 Сумма: {s.sum_for_trades} USDT\n📈 Сторона: {POSITION_SIDE}\n"
        )

        await asyncio.sleep(1)
        position_data = await self.adapter.get_positions_by_symbol(self.http_session, s.symbol)
        if not position_data or not position_data.get("result", {}).get("list"):
            logger.error("❌ Не удалось получить позицию trade_id=%s", s.trade_id)
            s.should_stop = True
            return
        position_info = position_data["result"]["list"][0]
        s.entry_price = float(position_info["avgPrice"])
        s.position_qty = float(position_info["size"])
        s.previous_avg_price = s.entry_price
        s.previous_position_size = s.position_qty
        s.last_position_check_time = time.time()
        s.position_opened = True

        sl = calculator.calculate_stop_loss(s.entry_price, STOP_LOSS_PERCENTAGE, POSITION_SIDE)
        await self.adapter.set_stop_loss(s.symbol, sl, self.http_session)
        await self.adapter.place_n_limit_order(s.symbol, s.algorithms_sum_for_trades, POSITION_SIDE, s.entry_price, self.http_session)
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
        ok, _, _ = await self.adapter.set_breakeven_with_retries(s.symbol, s.current_price, self.http_session, POSITION_SIDE)
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
            await self.adapter.stop_trading(s.symbol, self.http_session)
            s.should_stop = True
            closed = await self._persist_closed_trade()
            closed_info = closed or {}
            pnl = float(closed_info.get("pnl_usdt") or 0.0)
            pnl_sign = "+" if pnl >= 0 else ""
            send_notification_to_user_task.delay(
                s.tg_id,
                "🔄 Позиция закрыта\n\n"
                f"👤 Пользователь: {s.name} ({s.tg_id})\n"
                f"📊 Символ: {closed_info.get('symbol') or s.symbol}\n"
                f"📈 Сторона: {'Лонг' if closed_info.get('side') == 'Buy' else 'Шорт'}\n"
                f"💰 Цена входа: {float(closed_info.get('entry_price') or 0.0):.8g}\n"
                f"💸 Цена выхода: {float(closed_info.get('exit_price') or 0.0):.8g}\n"
                f"💵 Финальный PnL: {pnl_sign}{pnl:.2f} USDT",
            )
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

    async def _persist_closed_trade(self) -> dict[str, Any] | None:
        s = self.state
        if s.trade_saved:
            return s.closed_position_info
        if self.http_session is None:
            return None
        try:
            position_info = await self.adapter.get_result_position_info(s.symbol, self.http_session)
            if not position_info or position_info.get("is_open") is True:
                return None
            trade_doc = build_trade_doc(
                tg_id=int(s.tg_id),
                name=s.name,
                symbol=s.symbol,
                position_info=position_info,
            )
            await asyncio.to_thread(history_trades_db.insert_closed_trade, trade_doc)
            await asyncio.to_thread(
                history_trades_db.apply_user_statistics_delta,
                int(s.tg_id),
                float(position_info.get("pnl_usdt") or 0.0),
            )
            s.trade_saved = True
            s.closed_position_info = position_info
            return position_info
        except Exception as e:
            logger.error("❌ Ошибка сохранения history_trades/statistics: %s", e)
            return None

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
        loop.run_forever()

    def submit_trade(
        self,
        symbol: str,
        tg_id: int,
        name: str,
        api_key: str,
        api_secret: str,
        sum_for_trades: float,
    ) -> str:
        self.ensure_started()
        trade_id = f"{tg_id}:{symbol.upper()}:{uuid.uuid4().hex[:10]}"
        fut = asyncio.run_coroutine_threadsafe(
            self._submit_trade_async(
                trade_id=trade_id,
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
        return trade_id

    async def _submit_trade_async(self, trade_id: str, symbol: str, tg_id: int, name: str, api_key: str, api_secret: str, sum_for_trades: float) -> None:
        symbol = symbol.upper()
        ok = await self.store.acquire_idempotency(symbol=symbol, tg_id=tg_id)
        if not ok:
            logger.warning("⏭️ Дубликат команды отфильтрован: tg_id=%s symbol=%s", tg_id, symbol)
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
):
    """
    Backward-compatible API.
    Теперь стартует async-торговую сессию и сразу возвращает trade_id.
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
