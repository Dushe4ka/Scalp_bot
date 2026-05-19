"""Tests for Redis market message encoding."""
from __future__ import annotations

import unittest

from bybit_logic.feeds.redis_market_keys import (
    FeedSource,
    encode_ensure_message,
    encode_ticker_message,
    parse_ensure_message,
    parse_ticker_message,
    ticker_channel,
)


class RedisMarketKeysTests(unittest.TestCase):
    def test_roundtrip(self):
        raw = encode_ticker_message("BTCUSDT", 50000.5, FeedSource.PRIMARY)
        parsed = parse_ticker_message(raw)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["symbol"], "BTCUSDT")
        self.assertAlmostEqual(parsed["price"], 50000.5)
        self.assertEqual(parsed["source"], "primary")

    def test_channel_name(self):
        self.assertEqual(ticker_channel("btcusdt"), "market:ticker:BTCUSDT")

    def test_ensure_message_roundtrip(self):
        raw = encode_ensure_message("xnyusdt")
        self.assertEqual(parse_ensure_message(raw), "XNYUSDT")


if __name__ == "__main__":
    unittest.main()
