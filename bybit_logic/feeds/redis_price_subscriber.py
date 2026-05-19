"""Subscribe to centralized market ticks via Redis Pub/Sub."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from typing import Any

from bybit_logic.feeds.feed_config import PRICE_FEED_STALE_SEC
from bybit_logic.feeds.redis_market_keys import (
    KEY_FEED_STATUS,
    FeedStatus,
    last_price_key,
    parse_ticker_message,
    ticker_channel,
)
from celery_app.config import REDIS_URL
from logger_config import setup_logger

logger = setup_logger(__name__)


class RedisPriceSubscriber:
    """
    Background thread reads Redis pub/sub; pushes prices into asyncio.Queue
    via loop.call_soon_threadsafe.
    """

    def __init__(
        self,
        symbol: str,
        loop: asyncio.AbstractEventLoop,
        *,
        redis_url: str | None = None,
        queue_maxsize: int = 500,
    ) -> None:
        self.symbol = symbol.upper()
        self._loop = loop
        self._redis_url = redis_url or REDIS_URL
        self._queue: asyncio.Queue[float] = asyncio.Queue(maxsize=queue_maxsize)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._last_tick_ts: float = 0.0
        self._client = None
        self._pubsub = None

    @property
    def last_tick_ts(self) -> float:
        return self._last_tick_ts

    def is_stale(self, stale_sec: float | None = None) -> bool:
        if self._last_tick_ts <= 0:
            return True
        limit = stale_sec if stale_sec is not None else PRICE_FEED_STALE_SEC
        return (time.time() - self._last_tick_ts) > limit

    async def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._run,
            name=f"redis-price-{self.symbol}",
            daemon=True,
        )
        self._thread.start()
        await self._seed_from_last_price()

    async def _seed_from_last_price(self) -> None:
        def _get():
            import redis

            client = redis.Redis.from_url(self._redis_url, decode_responses=True)
            raw = client.get(last_price_key(self.symbol))
            if not raw:
                return None
            return json.loads(raw)

        try:
            data = await asyncio.to_thread(_get)
            if data:
                price = float(data.get("price", 0))
                if price > 0:
                    self._last_tick_ts = float(data.get("ts", time.time()))
                    await self._queue.put(price)
        except Exception as e:
            logger.debug("No seed price for %s: %s", self.symbol, e)

    def _run(self) -> None:
        import redis

        try:
            self._client = redis.Redis.from_url(self._redis_url, decode_responses=True)
            self._pubsub = self._client.pubsub(ignore_subscribe_messages=True)
            self._pubsub.subscribe(ticker_channel(self.symbol))
            while not self._stop.is_set():
                message = self._pubsub.get_message(timeout=1.0)
                if not message or message.get("type") != "message":
                    continue
                data = message.get("data")
                if data is None:
                    continue
                parsed = parse_ticker_message(data)
                if not parsed or parsed["symbol"] != self.symbol:
                    continue
                price = parsed["price"]
                self._last_tick_ts = parsed["ts"]
                self._loop.call_soon_threadsafe(self._put_price, price)
        except Exception as e:
            if not self._stop.is_set():
                logger.error("Redis price subscriber error %s: %s", self.symbol, e)
        finally:
            try:
                if self._pubsub is not None:
                    self._pubsub.close()
            except Exception:
                pass

    def _put_price(self, price: float) -> None:
        if self._queue.full():
            try:
                self._queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            self._queue.put_nowait(price)
        except asyncio.QueueFull:
            pass

    async def get(self) -> float:
        return await self._queue.get()

    async def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)


def get_feed_status(redis_url: str | None = None) -> FeedStatus:
    import redis

    client = redis.Redis.from_url(redis_url or REDIS_URL, decode_responses=True)
    raw = client.get(KEY_FEED_STATUS) or FeedStatus.DOWN.value
    try:
        return FeedStatus(str(raw))
    except ValueError:
        return FeedStatus.DOWN


async def get_feed_status_async(redis_url: str | None = None) -> FeedStatus:
    return await asyncio.to_thread(get_feed_status, redis_url)
