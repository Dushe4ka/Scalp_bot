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
)
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
            except Exception as e:
                logger.error("Feed status watch error: %s", e)
            await asyncio.sleep(2.0)

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

        if mode == PriceSourceMode.REDIS and PRICE_FEED_REDIS_ENABLED:
            await asyncio.to_thread(acquire_symbol_price_session, symbol)
            sub.redis_sub = RedisPriceSubscriber(symbol, self._loop)
            await sub.redis_sub.start()
            fanout = asyncio.create_task(self._redis_fanout(sub, entry))
            with self._lock:
                entry["queue_subs"][id(queue)] = (sub, fanout)
        else:
            await self._ensure_local_stream(symbol, entry)

        return queue

    async def _redis_fanout(self, sub: _Subscription, entry: dict[str, Any]) -> None:
        if sub.redis_sub is None:
            return
        try:
            while True:
                price = await sub.redis_sub.get()
                if sub.redis_sub.is_stale(PRICE_FEED_STALE_SEC):
                    if PRICE_FEED_LOCAL_FALLBACK and get_feed_status() == FeedStatus.DOWN:
                        await self._ensure_local_stream(sub.symbol, entry)
                        continue
                await self._dispatch_to_queue(sub.queue, price)
        except asyncio.CancelledError:
            pass

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
            self._loop.call_soon_threadsafe(self._publish_local, symbol, price)

        stream = PriceStream(symbol=symbol, price_handler=_dispatch, testnet=False)
        stream.start()
        with self._lock:
            entry["local_stream"] = stream
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
        release_feed = False
        with self._lock:
            entry = self._symbols.get(symbol)
            if not entry:
                return
            entry["queues"].discard(queue)
            pair = entry.get("queue_subs", {}).pop(id(queue), None)
            if pair:
                sub, fanout = pair
                if fanout is not None:
                    fanout.cancel()
                if sub.redis_sub is not None:
                    try:
                        await sub.redis_sub.stop()
                    except Exception:
                        pass
            if entry["queues"]:
                return
            stream = entry.get("local_stream")
            if stream is not None:
                try:
                    stream.stop()
                except Exception:
                    pass
            self._symbols.pop(symbol, None)
            release_feed = True
        if release_feed:
            await asyncio.to_thread(release_symbol_price_session, symbol)

    @property
    def mode(self) -> PriceSourceMode:
        return self._mode

    def local_stream_count(self) -> int:
        with self._lock:
            return sum(1 for e in self._symbols.values() if e.get("local_started"))
