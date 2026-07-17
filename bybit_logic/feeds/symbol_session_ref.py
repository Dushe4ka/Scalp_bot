"""
Global Redis refcount of active trade sessions per symbol (all engine processes).

- acquire on feed_hub.subscribe (first session → open feed WS)
- release on feed_hub.unsubscribe when last queue in process removed;
  when global ref hits 0 → close feed WS
"""
from __future__ import annotations

import logging

from bybit_logic.feeds.feed_symbol_request import release_feed_symbol, request_feed_symbol
from bybit_logic.feeds.redis_market_keys import KEY_FEED_REF_SYMBOLS, symbol_ref_key
from celery_app.config import REDIS_URL

logger = logging.getLogger(__name__)

_REFC_TTL_SECONDS = 8 * 60 * 60  # 8 часов — перекрывает любую сделку, но ключ не висит вечно

_ACQUIRE_LUA = """
local ref_key = KEYS[1]
local ttl = tonumber(ARGV[3])
local symbol = ARGV[1]
local n = redis.call('INCR', ref_key)
redis.call('SADD', ARGV[2], symbol)
-- Обновляем TTL при каждом acquire, чтобы ключ не протух, пока есть активные сессии
redis.call('EXPIRE', ref_key, ttl)
return n
"""

_RELEASE_LUA = """
local ref_key = KEYS[1]
local symbols_set = ARGV[1]
local symbol = ARGV[2]
local n = redis.call('DECR', ref_key)
if n < 0 then
  redis.call('SET', ref_key, 0)
  n = 0
end
if n == 0 then
  redis.call('DEL', ref_key)
  redis.call('SREM', symbols_set, symbol)
  return 0
end
-- Продлеваем TTL, пока есть оставшиеся сессии
local ttl = tonumber(ARGV[3])
redis.call('EXPIRE', ref_key, ttl)
return n
"""


def _client():
    import redis

    return redis.Redis.from_url(REDIS_URL, decode_responses=True)


def acquire_symbol_price_session(symbol: str, *, redis_url: str | None = None) -> int:
    """
    Register one active session needing price for symbol.
    Returns new global refcount. If 1, requests feed WS.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return 0
    try:
        import redis

        url = redis_url or REDIS_URL
        client = redis.Redis.from_url(url, decode_responses=True)
        n = int(
            client.eval(
                _ACQUIRE_LUA,
                1,
                symbol_ref_key(sym),
                sym,
                KEY_FEED_REF_SYMBOLS,
                str(_REFC_TTL_SECONDS),
            )
        )
        if n == 1:
            request_feed_symbol(sym, redis_url=url)
        logger.debug("acquire_symbol_price_session %s -> ref=%s", sym, n)
        return n
    except Exception as e:
        logger.warning("acquire_symbol_price_session(%s) failed: %s", sym, e)
        request_feed_symbol(sym, redis_url=redis_url)
        return -1


def release_symbol_price_session(symbol: str, *, redis_url: str | None = None) -> int:
    """
    Unregister one session. Returns remaining global refcount.
    If 0, requests feed to close WS for symbol.
    """
    sym = (symbol or "").strip().upper()
    if not sym:
        return 0
    try:
        import redis

        url = redis_url or REDIS_URL
        client = redis.Redis.from_url(url, decode_responses=True)
        n = int(
            client.eval(
                _RELEASE_LUA,
                1,
                symbol_ref_key(sym),
                KEY_FEED_REF_SYMBOLS,
                sym,
                str(_REFC_TTL_SECONDS),
            )
        )
        if n == 0:
            release_feed_symbol(sym, redis_url=url)
            logger.info("Last session closed for %s — feed WS release requested", sym)
        else:
            logger.debug("release_symbol_price_session %s -> ref=%s", sym, n)
        return n
    except Exception as e:
        logger.warning("release_symbol_price_session(%s) failed: %s", sym, e)
        return -1


def get_symbol_refcount(symbol: str, *, redis_url: str | None = None) -> int:
    sym = (symbol or "").strip().upper()
    if not sym:
        return 0
    try:
        client = _client() if redis_url is None else __import__("redis").Redis.from_url(redis_url, decode_responses=True)
        return int(client.get(symbol_ref_key(sym)) or 0)
    except Exception:
        return 0
