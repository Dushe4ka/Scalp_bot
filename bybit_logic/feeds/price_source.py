"""Price delivery mode for TradeSession."""
from __future__ import annotations

from enum import Enum


class PriceSourceMode(str, Enum):
    REDIS = "redis"
    LOCAL = "local"
