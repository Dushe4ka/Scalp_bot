"""Redis keys/channels for centralized market price feed (Phase 2)."""
from __future__ import annotations

import json
import time
from enum import Enum
from typing import Any


class FeedSource(str, Enum):
    PRIMARY = "primary"
    BACKUP = "backup"


class FeedStatus(str, Enum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


def ticker_channel(symbol: str) -> str:
    return f"market:ticker:{symbol.upper()}"


def last_price_key(symbol: str) -> str:
    return f"market:last:{symbol.upper()}"


KEY_FEED_ACTIVE = "market:feed:active"
KEY_FEED_STATUS = "market:feed:status"
KEY_FEED_PRIMARY_ALIVE = "market:feed:primary:alive"
KEY_FEED_BACKUP_ALIVE = "market:feed:backup:alive"
KEY_FEED_SYMBOLS = "market:feed:symbols"


def encode_ticker_message(symbol: str, price: float, source: FeedSource | str) -> str:
    return json.dumps(
        {
            "symbol": symbol.upper(),
            "price": price,
            "ts": time.time(),
            "source": source.value if isinstance(source, FeedSource) else str(source),
        },
        ensure_ascii=False,
    )


def parse_ticker_message(raw: str | bytes) -> dict[str, Any] | None:
    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        data = json.loads(raw)
        price = float(data.get("price", 0))
        if price <= 0:
            return None
        return {
            "symbol": str(data.get("symbol", "")).upper(),
            "price": price,
            "ts": float(data.get("ts", time.time())),
            "source": data.get("source", "unknown"),
        }
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
