"""Redis-блокировки trade_cmd:{tg_id}:{SYMBOL} для async trade engine."""
from __future__ import annotations

from celery_app.config import REDIS_URL
from logger_config import setup_logger

logger = setup_logger(__name__)

_DEFAULT_TTL_SECONDS = 60 * 60 * 4


class TradeIdempotencyStore:
    def __init__(self, redis_url: str | None = None) -> None:
        self._redis_url = redis_url or REDIS_URL
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import redis

            self._client = redis.Redis.from_url(self._redis_url, decode_responses=True)
        return self._client

    @staticmethod
    def idempotency_key(symbol: str, tg_id: int) -> str:
        return f"trade_cmd:{tg_id}:{symbol.upper()}"

    def acquire(self, symbol: str, tg_id: int, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> bool:
        key = self.idempotency_key(symbol, tg_id)
        return bool(self.client.set(key, "1", ex=ttl_seconds, nx=True))

    def release(self, symbol: str, tg_id: int) -> None:
        self.client.delete(self.idempotency_key(symbol, tg_id))

    def release_all_for_tg_id(self, tg_id: int) -> int:
        pattern = f"trade_cmd:{tg_id}:*"
        keys = list(self.client.scan_iter(match=pattern, count=200))
        if not keys:
            return 0
        deleted = int(self.client.delete(*keys))
        if deleted:
            logger.info("🔓 Снято блокировок trade_cmd для tg_id=%s: %s", tg_id, deleted)
        return deleted


_store: TradeIdempotencyStore | None = None


def get_trade_idempotency_store() -> TradeIdempotencyStore:
    global _store
    if _store is None:
        _store = TradeIdempotencyStore()
    return _store


def clear_trade_lock(tg_id: int, symbol: str) -> None:
    get_trade_idempotency_store().release(symbol, tg_id)


def clear_all_trade_locks_for_user(tg_id: int) -> int:
    return get_trade_idempotency_store().release_all_for_tg_id(tg_id)
