"""
Primary + backup WebSocket feeds with Redis publishing and failover.

Symbols are subscribed dynamically on trading signal (Redis channel market:feed:ensure),
not from a static list at startup.
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
    MARKET_FEED_SYMBOL_IDLE_SEC,
    PRICE_FEED_FAILOVER_HYSTERESIS_SEC,
)
from bybit_logic.feeds.redis_market_keys import (
    CHANNEL_FEED_ENSURE,
    KEY_FEED_ACTIVE,
    KEY_FEED_ACTIVE_SYMBOLS,
    KEY_FEED_BACKUP_ALIVE,
    KEY_FEED_PRIMARY_ALIVE,
    KEY_FEED_STATUS,
    KEY_FEED_SYMBOLS,
    FeedSource,
    FeedStatus,
    encode_ticker_message,
    last_price_key,
    CHANNEL_FEED_RELEASE,
    KEY_FEED_REF_SYMBOLS,
    parse_ensure_message,
    parse_release_message,
    ticker_channel,
)
from celery_app.config import REDIS_URL
from logger_config import setup_logger

dotenv.load_dotenv()
logger = setup_logger(__name__)


class DualMarketFeed:
    def __init__(
        self,
        *,
        redis_url: str | None = None,
        stale_sec: float = FEED_STALE_SEC,
        down_sec: float = FEED_DOWN_SEC,
        hysteresis_sec: float = PRICE_FEED_FAILOVER_HYSTERESIS_SEC,
        symbol_idle_sec: float = MARKET_FEED_SYMBOL_IDLE_SEC,
    ) -> None:
        self._redis_url = redis_url or REDIS_URL
        self._stale_sec = stale_sec
        self._down_sec = down_sec
        self._hysteresis_sec = hysteresis_sec
        self._symbol_idle_sec = symbol_idle_sec
        self._primary = LegState(FeedSource.PRIMARY)
        self._backup = LegState(FeedSource.BACKUP)
        self._active: FeedSource = FeedSource.PRIMARY
        self._last_failover_ts: float = 0.0
        self._stop = threading.Event()
        self._redis = None
        self._symbol_streams: dict[str, dict[FeedSource, PriceStream]] = {}
        self._symbol_last_publish: dict[str, float] = {}
        self._active_symbols: set[str] = set()
        self._symbol_lock = threading.Lock()
        self._ensure_listener: threading.Thread | None = None

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
        self._symbol_last_publish[symbol.upper()] = time.time()

    def _set_meta(self) -> None:
        client = self._redis_client()
        now = str(time.time())
        client.set(KEY_FEED_ACTIVE, self._active.value)
        with self._symbol_lock:
            active_list = sorted(self._active_symbols)
        client.set(KEY_FEED_SYMBOLS, ",".join(active_list))

        has_streams = bool(self._symbol_streams)
        if not has_streams:
            client.set(KEY_FEED_PRIMARY_ALIVE, "0")
            client.set(KEY_FEED_BACKUP_ALIVE, "0")
            client.set(KEY_FEED_STATUS, FeedStatus.OK.value)
            return

        client.set(
            KEY_FEED_PRIMARY_ALIVE,
            now if self._primary.age_sec() <= self._stale_sec else "0",
        )
        client.set(
            KEY_FEED_BACKUP_ALIVE,
            now if self._backup.age_sec() <= self._stale_sec else "0",
        )

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

    def _start_symbol_leg(self, symbol: str, leg: LegState) -> None:
        symbol = symbol.upper()
        with self._symbol_lock:
            if symbol not in self._symbol_streams:
                self._symbol_streams[symbol] = {}
            if leg.name in self._symbol_streams[symbol]:
                return
        stream = PriceStream(symbol, self._make_handler(symbol, leg), testnet=False)
        stream.start()
        with self._symbol_lock:
            self._symbol_streams.setdefault(symbol, {})[leg.name] = stream
            self._active_symbols.add(symbol)
        logger.info("Started %s WS for %s", leg.name.value, symbol)

    def ensure_symbol(self, symbol: str) -> None:
        """Open primary + backup WS for symbol if not already running."""
        symbol = symbol.upper()
        if not symbol:
            return
        with self._symbol_lock:
            entry = self._symbol_streams.get(symbol)
            if entry and FeedSource.PRIMARY in entry and FeedSource.BACKUP in entry:
                return
        self._start_symbol_leg(symbol, self._primary)
        self._start_symbol_leg(symbol, self._backup)
        client = self._redis_client()
        client.sadd(KEY_FEED_ACTIVE_SYMBOLS, symbol)

    def _stop_symbol(self, symbol: str) -> None:
        symbol = symbol.upper()
        with self._symbol_lock:
            streams = self._symbol_streams.pop(symbol, None)
            self._active_symbols.discard(symbol)
        if not streams:
            return
        for stream in streams.values():
            try:
                stream.stop()
            except Exception:
                pass
        try:
            self._redis_client().srem(KEY_FEED_ACTIVE_SYMBOLS, symbol)
        except Exception:
            pass
        self._symbol_last_publish.pop(symbol, None)
        logger.info("Stopped WS streams for idle symbol %s", symbol)

    def _reap_idle_symbols(self) -> None:
        if self._symbol_idle_sec <= 0:
            return
        from bybit_logic.feeds.symbol_session_ref import get_symbol_refcount

        now = time.time()
        with self._symbol_lock:
            symbols = list(self._symbol_streams.keys())
        for symbol in symbols:
            if get_symbol_refcount(symbol) > 0:
                continue
            last = self._symbol_last_publish.get(symbol, 0.0)
            if last <= 0:
                continue
            if (now - last) >= self._symbol_idle_sec:
                self._stop_symbol(symbol)

    def _listen_ensure_loop(self) -> None:
        import redis

        client = redis.Redis.from_url(self._redis_url, decode_responses=True)
        pubsub = client.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(CHANNEL_FEED_ENSURE, CHANNEL_FEED_RELEASE)
        logger.info(
            "Listening on %s and %s",
            CHANNEL_FEED_ENSURE,
            CHANNEL_FEED_RELEASE,
        )
        while not self._stop.is_set():
            try:
                message = pubsub.get_message(timeout=1.0)
                if not message or message.get("type") != "message":
                    continue
                data = message.get("data")
                if data is None:
                    continue
                channel = message.get("channel") or ""
                if channel == CHANNEL_FEED_RELEASE:
                    symbol = parse_release_message(data)
                    if symbol:
                        self._stop_symbol(symbol)
                else:
                    symbol = parse_ensure_message(data)
                    if symbol:
                        self.ensure_symbol(symbol)
            except Exception as e:
                if not self._stop.is_set():
                    logger.error("Ensure listener error: %s", e)
        try:
            pubsub.close()
        except Exception:
            pass

    def _restore_symbols_from_redis(self) -> None:
        """After feed restart: reconnect symbols with active session refcount."""
        from bybit_logic.feeds.symbol_session_ref import get_symbol_refcount

        try:
            client = self._redis_client()
            symbols = client.smembers(KEY_FEED_REF_SYMBOLS) or set()
            for sym in sorted(symbols):
                if sym and get_symbol_refcount(str(sym)) > 0:
                    self.ensure_symbol(str(sym))
        except Exception as e:
            logger.warning("Could not restore symbols from Redis: %s", e)

    def _stop_all_streams(self) -> None:
        with self._symbol_lock:
            symbols = list(self._symbol_streams.keys())
        for symbol in symbols:
            self._stop_symbol(symbol)

    def _maybe_failover(self) -> None:
        if not self._symbol_streams:
            return
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
        self._ensure_listener = threading.Thread(
            target=self._listen_ensure_loop,
            name="feed-ensure-listener",
            daemon=True,
        )
        self._ensure_listener.start()
        self._restore_symbols_from_redis()
        logger.info("DualMarketFeed started (dynamic symbols only, idle_sec=%s)", self._symbol_idle_sec)

    def run_forever(self, tick_interval: float = 1.0) -> None:
        self.start()
        try:
            while not self._stop.is_set():
                self._maybe_failover()
                self._reap_idle_symbols()
                self._set_meta()
                time.sleep(tick_interval)
        except KeyboardInterrupt:
            logger.info("DualMarketFeed interrupted")
        finally:
            self.stop()

    def stop(self) -> None:
        self._stop.set()
        if self._ensure_listener and self._ensure_listener.is_alive():
            self._ensure_listener.join(timeout=3.0)
        self._stop_all_streams()
        client = self._redis_client()
        client.set(KEY_FEED_STATUS, FeedStatus.DOWN.value)
        client.set(KEY_FEED_SYMBOLS, "")
        logger.info("DualMarketFeed stopped")
