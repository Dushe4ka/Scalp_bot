"""
Primary + backup WebSocket feeds with Redis publishing and failover.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

import dotenv

from bybit_logic.bybit_func.price_stream import PriceStream
from services.market_price_feed.failover_logic import (
    LegState,
    extract_ticker_price,
    maybe_failover,
)
from bybit_logic.feeds.feed_config import (
    FEED_DOWN_SEC,
    FEED_STALE_SEC,
    PRICE_FEED_FAILOVER_HYSTERESIS_SEC,
)
from bybit_logic.feeds.redis_market_keys import (
    KEY_FEED_ACTIVE,
    KEY_FEED_BACKUP_ALIVE,
    KEY_FEED_PRIMARY_ALIVE,
    KEY_FEED_STATUS,
    KEY_FEED_SYMBOLS,
    FeedSource,
    FeedStatus,
    encode_ticker_message,
    last_price_key,
    ticker_channel,
)
from celery_app.config import REDIS_URL
from logger_config import setup_logger

dotenv.load_dotenv()
logger = setup_logger(__name__)

DEFAULT_SYMBOLS = [
    s.strip().upper()
    for s in os.getenv(
        "MARKET_FEED_SYMBOLS",
        "BTCUSDT,ETHUSDT,SOLUSDT,XRPUSDT,BNBUSDT,DOGEUSDT,ADAUSDT,AVAXUSDT,DOTUSDT,LINKUSDT",
    ).split(",")
    if s.strip()
]


class DualMarketFeed:
    def __init__(
        self,
        symbols: list[str] | None = None,
        *,
        redis_url: str | None = None,
        stale_sec: float = FEED_STALE_SEC,
        down_sec: float = FEED_DOWN_SEC,
        hysteresis_sec: float = PRICE_FEED_FAILOVER_HYSTERESIS_SEC,
    ) -> None:
        self.symbols = [s.upper() for s in (symbols or DEFAULT_SYMBOLS)]
        self._redis_url = redis_url or REDIS_URL
        self._stale_sec = stale_sec
        self._down_sec = down_sec
        self._hysteresis_sec = hysteresis_sec
        self._primary = LegState(FeedSource.PRIMARY)
        self._backup = LegState(FeedSource.BACKUP)
        self._active: FeedSource = FeedSource.PRIMARY
        self._last_failover_ts: float = 0.0
        self._stop = threading.Event()
        self._redis = None
        self._symbol_streams: dict[str, dict[FeedSource, PriceStream]] = {}

    def _redis_client(self):
        if self._redis is None:
            import redis

            self._redis = redis.Redis.from_url(self._redis_url, decode_responses=True)
        return self._redis

    def _publish(self, symbol: str, price: float, source: FeedSource) -> None:
        client = self._redis_client()
        payload = encode_ticker_message(symbol, price, source)
        client.publish(ticker_channel(symbol), payload)
        client.set(
            last_price_key(symbol),
            json.dumps({"symbol": symbol, "price": price, "ts": time.time(), "source": source.value}),
            ex=120,
        )

    def _set_meta(self) -> None:
        client = self._redis_client()
        now = str(time.time())
        client.set(KEY_FEED_ACTIVE, self._active.value)
        client.set(KEY_FEED_PRIMARY_ALIVE, now if self._primary.age_sec() <= self._stale_sec else "0")
        client.set(KEY_FEED_BACKUP_ALIVE, now if self._backup.age_sec() <= self._stale_sec else "0")
        client.set(KEY_FEED_SYMBOLS, ",".join(self.symbols))

        primary_stale = self._primary.is_stale(self._down_sec)
        backup_stale = self._backup.is_stale(self._down_sec)
        if primary_stale and backup_stale:
            status = FeedStatus.DOWN
        elif self._active == FeedSource.BACKUP and not backup_stale:
            status = FeedStatus.DEGRADED
        else:
            status = FeedStatus.OK
        client.set(KEY_FEED_STATUS, status.value)

    def _extract_price(self, message: dict[str, Any]) -> float | None:
        return extract_ticker_price(message)

    def _make_handler(self, symbol: str, leg: LegState):
        def _handler(message: dict[str, Any]) -> None:
            price = self._extract_price(message)
            if price is None:
                return
            leg.mark_tick()
            if self._active == leg.name:
                self._publish(symbol, price, leg.name)

        return _handler

    def _start_leg_streams(self, leg: LegState) -> None:
        for symbol in self.symbols:
            if symbol not in self._symbol_streams:
                self._symbol_streams[symbol] = {}
            if leg.name in self._symbol_streams[symbol]:
                continue
            stream = PriceStream(symbol, self._make_handler(symbol, leg), testnet=False)
            stream.start()
            self._symbol_streams[symbol][leg.name] = stream
            logger.info("Started %s WS for %s", leg.name.value, symbol)

    def _stop_all_streams(self) -> None:
        for sym_streams in self._symbol_streams.values():
            for stream in sym_streams.values():
                try:
                    stream.stop()
                except Exception:
                    pass
        self._symbol_streams.clear()

    def _maybe_failover(self) -> None:
        prev = self._active
        self._active, self._last_failover_ts = maybe_failover(
            active=self._active,
            primary=self._primary,
            backup=self._backup,
            stale_sec=self._stale_sec,
            hysteresis_sec=self._hysteresis_sec,
            last_failover_ts=self._last_failover_ts,
        )
        if self._active != prev:
            logger.warning(
                "Failover: active publisher %s -> %s",
                prev.value,
                self._active.value,
            )

    def start(self) -> None:
        self._start_leg_streams(self._primary)
        self._start_leg_streams(self._backup)
        logger.info("DualMarketFeed started for symbols: %s", self.symbols)

    def run_forever(self, tick_interval: float = 1.0) -> None:
        self.start()
        try:
            while not self._stop.is_set():
                self._maybe_failover()
                self._set_meta()
                time.sleep(tick_interval)
        except KeyboardInterrupt:
            logger.info("DualMarketFeed interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        self._stop_all_streams()
        client = self._redis_client()
        client.set(KEY_FEED_STATUS, FeedStatus.DOWN.value)
        logger.info("DualMarketFeed stopped")
