"""Unit tests for RedisPriceSubscriber stale detection and message parsing."""
from __future__ import annotations

import asyncio
import time
import unittest

from bybit_logic.feeds.redis_market_keys import encode_ticker_message, parse_ticker_message
from bybit_logic.feeds.redis_price_subscriber import RedisPriceSubscriber


class RedisPriceSubscriberTests(unittest.TestCase):
    def test_parse_ticker_roundtrip(self):
        raw = encode_ticker_message("BTCUSDT", 50000.5, "primary")
        parsed = parse_ticker_message(raw)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["symbol"], "BTCUSDT")
        self.assertAlmostEqual(parsed["price"], 50000.5)

    def test_is_stale_without_ticks(self):
        loop = asyncio.new_event_loop()
        try:
            sub = RedisPriceSubscriber("ETHUSDT", loop)
            self.assertTrue(sub.is_stale(stale_sec=5.0))
        finally:
            loop.close()

    def test_is_stale_after_recent_tick(self):
        loop = asyncio.new_event_loop()
        try:
            sub = RedisPriceSubscriber("ETHUSDT", loop)
            sub._last_tick_ts = time.time()
            self.assertFalse(sub.is_stale(stale_sec=5.0))
        finally:
            loop.close()


if __name__ == "__main__":
    unittest.main()
