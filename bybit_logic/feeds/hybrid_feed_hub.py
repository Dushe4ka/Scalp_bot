"""
Price hub: Redis central feed with per-process local WS fallback.
"""
from __future__ import annotations

import asyncio
import threading
import time
from typing import Any

from bybit_logic.bybit_func.price_stream import PriceStream
from bybit_logic.feeds.feed_config import (
    PRICE_FEED_LOCAL_FALLBACK,
    PRICE_FEED_REDIS_ENABLED,
    PRICE_FEED_STALE_SEC,
    PRICE_FEED_TICK_TIMEOUT_SEC,
)
from bybit_logic.feeds.feed_symbol_request import request_feed_symbol
from bybit_logic.feeds.price_source import PriceSourceMode
from bybit_logic.feeds.redis_market_keys import FeedStatus
from bybit_logic.feeds.redis_price_subscriber import RedisPriceSubscriber, get_feed_status
from bybit_logic.feeds.symbol_session_ref import (
    acquire_symbol_price_session,
    release_symbol_price_session,
)
from logger_config import setup_logger

logger = setup_logger(__name__)


class _Subscription:
    """One session subscription: redis and/or local queue."""

    def __init__(self, symbol: str, queue: asyncio.Queue[float]) -> None:
        self.symbol = symbol.upper()
        self.queue = queue
        self.redis_sub: RedisPriceSubscriber | None = None
        self.fanout: asyncio.Task | None = None
        # True only if acquire_symbol_price_session succeeded for this subscription;
        # unsubscribe releases the global refcount exactly once per acquire.
        self.acquired_refcount = False
        # Explicit stop flag: task.cancel() alone is not reliable here — asyncio.wait_for on
        # Python < 3.12 swallows a cancel that races with a ready price.
        self.closed = False


class MarketFeedHub:
    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._lock = threading.Lock()
        self._symbols: dict[str, dict[str, Any]] = {}
        self._mode: PriceSourceMode = PriceSourceMode.REDIS
        self._status_watch_task: asyncio.Task | None = None

    def attach_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _current_mode(self) -> PriceSourceMode:
        if not PRICE_FEED_REDIS_ENABLED:
            return PriceSourceMode.LOCAL
        if not PRICE_FEED_LOCAL_FALLBACK:
            return PriceSourceMode.REDIS
        status = get_feed_status()
        if status == FeedStatus.DOWN:
            return PriceSourceMode.LOCAL
        return PriceSourceMode.REDIS

    async def _status_watch_loop(self) -> None:
        while True:
            try:
                new_mode = self._current_mode()
                if new_mode != self._mode:
                    logger.warning(
                        "MarketFeedHub mode switch: %s -> %s",
                        self._mode.value,
                        new_mode.value,
                    )
                    self._mode = new_mode
                    if new_mode == PriceSourceMode.LOCAL:
                        await self._ensure_local_streams_for_all()
                    # When returning to REDIS, local streams stay until unused (lazy stop on unsubscribe)
                await self._restart_silent_local_streams()
            except Exception as e:
                logger.error("Feed status watch error: %s", e)
            await asyncio.sleep(2.0)

    async def _restart_silent_local_streams(self) -> None:
        """Local WS can die silently too (pybit gives up reconnecting) — recreate it."""
        now = time.time()
        with self._lock:
            silent = [
                (symbol, entry)
                for symbol, entry in self._symbols.items()
                if entry["queues"]
                and entry.get("local_started")
                and now - entry.get("local_last_message", 0.0) > PRICE_FEED_TICK_TIMEOUT_SEC
            ]
        for symbol, entry in silent:
            logger.warning(
                "Local WS for %s silent for >%.0fs — recreating it",
                symbol,
                PRICE_FEED_TICK_TIMEOUT_SEC,
            )
            with self._lock:
                stream = entry.get("local_stream")
                entry["local_stream"] = None
                entry["local_started"] = False
            if stream is not None:
                try:
                    await asyncio.to_thread(stream.stop)
                except Exception:
                    pass
            await self._ensure_local_stream(symbol, entry)

    async def start_watch(self) -> None:
        if self._status_watch_task is None and self._loop is not None:
            self._mode = self._current_mode()
            self._status_watch_task = asyncio.create_task(self._status_watch_loop())

    async def subscribe(self, symbol: str) -> asyncio.Queue[float]:
        symbol = symbol.upper()
        if self._loop is None:
            raise RuntimeError("MarketFeedHub loop not attached")

        queue: asyncio.Queue[float] = asyncio.Queue(maxsize=500)
        sub = _Subscription(symbol, queue)

        with self._lock:
            if symbol not in self._symbols:
                self._symbols[symbol] = {
                    "queues": set(),
                    "queue_subs": {},
                    "local_stream": None,
                    "local_started": False,
                }
            entry = self._symbols[symbol]
            entry["queues"].add(queue)
            entry["queue_subs"][id(queue)] = sub

        mode = self._current_mode()
        self._mode = mode

        try:
            if mode == PriceSourceMode.REDIS and PRICE_FEED_REDIS_ENABLED:
                ref = await asyncio.to_thread(acquire_symbol_price_session, symbol)
                sub.acquired_refcount = ref > 0
                sub.redis_sub = RedisPriceSubscriber(symbol, self._loop)
                await sub.redis_sub.start()
                sub.fanout = asyncio.create_task(self._redis_fanout(sub, entry))
            else:
                await self._ensure_local_stream(symbol, entry)
        except BaseException:
            await self.unsubscribe(symbol, queue)
            raise

        return queue

    async def _redis_fanout(self, sub: _Subscription, entry: dict[str, Any]) -> None:
        if sub.redis_sub is None:
            return
        try:
            while not sub.closed:
                try:
                    price = await asyncio.wait_for(
                        sub.redis_sub.get(), timeout=PRICE_FEED_TICK_TIMEOUT_SEC
                    )
                except asyncio.TimeoutError:
                    # Central feed silent for this symbol (e.g. its WS died while feed status
                    # stays OK thanks to other symbols) — don't wait forever, go local.
                    await self._fallback_on_silence(sub, entry)
                    continue
                if sub.closed:
                    break
                if sub.redis_sub.is_stale(PRICE_FEED_STALE_SEC):
                    if PRICE_FEED_LOCAL_FALLBACK and get_feed_status() == FeedStatus.DOWN:
                        await self._ensure_local_stream(sub.symbol, entry)
                        continue
                await self._dispatch_to_queue(sub.queue, price)
        except asyncio.CancelledError:
            pass

    async def _fallback_on_silence(self, sub: _Subscription, entry: dict[str, Any]) -> None:
        with self._lock:
            if sub.closed or self._symbols.get(sub.symbol) is not entry:
                return
            if entry.get("local_started"):
                return
        logger.warning(
            "No Redis ticks for %s for %.0fs — starting local WS fallback",
            sub.symbol,
            PRICE_FEED_TICK_TIMEOUT_SEC,
        )
        # Nudge the central feed too, so it recreates the symbol's WS.
        await asyncio.to_thread(request_feed_symbol, sub.symbol)
        await self._ensure_local_stream(sub.symbol, entry)

    async def _ensure_local_streams_for_all(self) -> None:
        with self._lock:
            symbols = list(self._symbols.keys())
        for symbol in symbols:
            with self._lock:
                entry = self._symbols.get(symbol)
            if entry and entry["queues"]:
                await self._ensure_local_stream(symbol, entry)

    async def _ensure_local_stream(self, symbol: str, entry: dict[str, Any]) -> None:
        with self._lock:
            if entry.get("local_started"):
                return
            entry["local_started"] = True
            # Grace period for the connect; any WS message refreshes it.
            entry["local_last_message"] = time.time()

        def _dispatch(message: dict[str, Any]) -> None:
            entry["local_last_message"] = time.time()
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
            self._loop.call_soon_threadsafe(self._publish_local, symbol, price)

        stream = PriceStream(symbol=symbol, price_handler=_dispatch, testnet=False)
        try:
            # pybit connects synchronously — keep it off the event loop.
            await asyncio.to_thread(stream.start)
        except Exception as e:
            # local_started stays True: _restart_silent_local_streams retries after the timeout.
            logger.error("Local WS fallback failed to start for %s: %s", symbol, e)
            return
        with self._lock:
            still_used = self._symbols.get(symbol) is entry and bool(entry["queues"])
            if still_used:
                entry["local_stream"] = stream
        if not still_used:
            # Last session unsubscribed while we were connecting.
            stream.stop()
            return
        logger.info("Local WS fallback started for %s in engine process", symbol)

    def _publish_local(self, symbol: str, price: float) -> None:
        entry = self._symbols.get(symbol)
        if not entry:
            return
        for q in list(entry["queues"]):
            asyncio.create_task(self._dispatch_to_queue(q, price))

    async def _dispatch_to_queue(self, queue: asyncio.Queue[float], price: float) -> None:
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(price)
        except asyncio.QueueFull:
            pass

    async def unsubscribe(self, symbol: str, queue: asyncio.Queue[float]) -> None:
        symbol = symbol.upper()
        stream = None
        with self._lock:
            entry = self._symbols.get(symbol)
            if not entry:
                return
            entry["queues"].discard(queue)
            sub = entry["queue_subs"].pop(id(queue), None)
            if not entry["queues"]:
                stream = entry.get("local_stream")
                self._symbols.pop(symbol, None)

        if sub is not None:
            sub.closed = True
            if sub.fanout is not None:
                sub.fanout.cancel()
            if sub.redis_sub is not None:
                try:
                    await sub.redis_sub.stop()
                except Exception:
                    pass
            if sub.acquired_refcount:
                sub.acquired_refcount = False
                await asyncio.to_thread(release_symbol_price_session, symbol)

        if stream is not None:
            try:
                stream.stop()
            except Exception:
                pass

    @property
    def mode(self) -> PriceSourceMode:
        return self._mode

    def local_stream_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._symbols.values() if e.get("local_started"))
