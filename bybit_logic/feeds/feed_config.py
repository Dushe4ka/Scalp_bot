"""Phase 2 feed / engine tuning from environment."""
from __future__ import annotations

import os


def _bool(name: str, default: bool = True) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("true", "1", "yes")


def _float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return float(raw)


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return int(raw)


PRICE_FEED_REDIS_ENABLED = _bool("PRICE_FEED_REDIS_ENABLED", True)
PRICE_FEED_LOCAL_FALLBACK = _bool("PRICE_FEED_LOCAL_FALLBACK", True)
PRICE_FEED_STALE_SEC = _float("PRICE_FEED_STALE_SEC", 5.0)
PRICE_FEED_DOWN_SEC = _float("PRICE_FEED_DOWN_SEC", 15.0)
PRICE_FEED_FAILOVER_HYSTERESIS_SEC = _float("PRICE_FEED_FAILOVER_HYSTERESIS_SEC", 30.0)

MAX_SESSIONS_PER_ENGINE = _int("MAX_SESSIONS_PER_ENGINE", 30)
TRADE_ENGINE_COUNT = _int("TRADE_ENGINE_COUNT", 2)
TRADE_SUBMIT_STAGGER_SEC = _float("TRADE_SUBMIT_STAGGER_SEC", 0.03)

FEED_STALE_SEC = _float("FEED_STALE_SEC", 5.0)
FEED_DOWN_SEC = _float("FEED_DOWN_SEC", 15.0)
