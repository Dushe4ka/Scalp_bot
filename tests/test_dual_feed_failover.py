"""Unit tests for dual feed failover logic (no WebSocket / pybit)."""
from __future__ import annotations

import time
import unittest

from bybit_logic.feeds.redis_market_keys import FeedSource
from services.market_price_feed.failover_logic import (
    LegState,
    extract_ticker_price,
    maybe_failover,
)


class DualFeedFailoverTests(unittest.TestCase):
    def test_promote_backup_when_primary_stale(self):
        primary = LegState(FeedSource.PRIMARY)
        backup = LegState(FeedSource.BACKUP)
        primary.last_tick_ts = time.time() - 10
        backup.mark_tick()

        active, _ = maybe_failover(
            active=FeedSource.PRIMARY,
            primary=primary,
            backup=backup,
            stale_sec=1.0,
            hysteresis_sec=0.0,
            last_failover_ts=0.0,
        )
        self.assertEqual(active, FeedSource.BACKUP)

    def test_extract_price(self):
        price = extract_ticker_price({"data": {"lastPrice": "123.45"}})
        self.assertAlmostEqual(price, 123.45)


if __name__ == "__main__":
    unittest.main()
