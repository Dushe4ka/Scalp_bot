"""Request centralized price feed to open WS for a symbol (on trading signal)."""
from __future__ import annotations

import json
import logging

from bybit_logic.feeds.redis_market_keys import (
    CHANNEL_FEED_ENSURE,
    CHANNEL_FEED_RELEASE,
    KEY_FEED_ACTIVE_SYMBOLS,
    encode_release_message,
)
from celery_app.config import REDIS_URL

logger = logging.getLogger(__name__)


def request_feed_symbol(symbol: str, *, redis_url: str | None = None) -> None:
    """
    Notify market_price_feed process to start primary/backup WS for symbol.
    Safe to call from API router, orchestrator, or engine (idempotent).
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return
    try:
        import redis

        url = redis_url or REDIS_URL
        client = redis.Redis.from_url(url, decode_responses=True)
        client.sadd(KEY_FEED_ACTIVE_SYMBOLS, sym)
        payload = json.dumps({"symbol": sym}, ensure_ascii=False)
        client.publish(CHANNEL_FEED_ENSURE, payload)
        logger.info("Requested feed WS for %s", sym)
    except Exception as e:
        logger.warning("request_feed_symbol(%s) failed: %s", sym, e)


def release_feed_symbol(symbol: str, *, redis_url: str | None = None) -> None:
    """Ask market_price_feed to close WS for symbol (when no sessions need price)."""
    sym = (symbol or "").strip().upper()
    if not sym:
        return
    try:
        import redis

        url = redis_url or REDIS_URL
        client = redis.Redis.from_url(url, decode_responses=True)
        client.srem(KEY_FEED_ACTIVE_SYMBOLS, sym)
        client.publish(CHANNEL_FEED_RELEASE, encode_release_message(sym))
        logger.info("Released feed WS for %s", sym)
    except Exception as e:
        logger.warning("release_feed_symbol(%s) failed: %s", sym, e)
