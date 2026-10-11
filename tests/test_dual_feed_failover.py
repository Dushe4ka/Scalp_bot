"""Unit tests for dual feed failover logic (no WebSocket / pybit)."""
from __future__ import annotations

import time
import unittest
from unittest.mock import MagicMock, patch

from bybit_logic.feeds.redis_market_keys import FeedSource
from services.market_price_feed.failover_logic import (
    LegState,
    extract_ticker_price,
    find_silent_symbols,
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

    def test_find_silent_symbols(self):
        now = 1000.0
        silent = find_silent_symbols(
            {"BTWUSDT": now - 120, "MOVRUSDT": now - 1, "NEWUSDT": 0.0},
            now=now,
            silent_sec=60.0,
        )
        self.assertEqual(silent, ["BTWUSDT"])

    def test_find_silent_symbols_disabled(self):
        self.assertEqual(find_silent_symbols({"BTWUSDT": 1.0}, now=1000.0, silent_sec=0), [])


class DualFeedSilentSymbolTests(unittest.TestCase):
    def _feed(self):
        from services.market_price_feed.dual_feed import DualMarketFeed

        feed = DualMarketFeed(redis_url="redis://unused", symbol_silent_sec=60.0)
        feed._stop_symbol = MagicMock()
        feed.ensure_symbol = MagicMock()
        return feed

    def _restart_and_wait(self, feed, refcount: int) -> None:
        with patch(
            "bybit_logic.feeds.symbol_session_ref.get_symbol_refcount", return_value=refcount
        ):
            feed._restart_silent_symbols()
            deadline = time.time() + 2
            while feed._symbols_recreating and time.time() < deadline:
                time.sleep(0.01)

    def test_restarts_only_silent_symbol(self):
        feed = self._feed()
        now = time.time()
        feed._symbol_streams = {"BTWUSDT": {}, "MOVRUSDT": {}}
        feed._symbol_last_message = {"BTWUSDT": now - 3600, "MOVRUSDT": now}

        self._restart_and_wait(feed, refcount=3)

        feed._stop_symbol.assert_called_once_with("BTWUSDT")
        feed.ensure_symbol.assert_called_once_with("BTWUSDT")

    def test_silent_symbol_without_sessions_is_stopped_not_recreated(self):
        feed = self._feed()
        feed._symbol_streams = {"BTWUSDT": {}}
        feed._symbol_last_message = {"BTWUSDT": time.time() - 3600}

        self._restart_and_wait(feed, refcount=0)

        feed._stop_symbol.assert_called_once_with("BTWUSDT")
        feed.ensure_symbol.assert_not_called()

    def test_failed_start_is_retried_later(self):
        from services.market_price_feed import dual_feed as feed_mod

        feed = feed_mod.DualMarketFeed(redis_url="redis://unused", symbol_silent_sec=60.0)
        broken = MagicMock()
        broken.return_value.start.side_effect = RuntimeError("connect failed")
        with patch.object(feed_mod, "PriceStream", broken):
            with self.assertRaises(RuntimeError):
                feed._start_symbol_leg("BTWUSDT", feed._primary)
        # Timestamp exists → after silent_sec the symbol is picked up for recreation.
        self.assertIn("BTWUSDT", feed._symbol_last_message)
        self.assertIn("BTWUSDT", feed._symbol_streams)

    def test_concurrent_ensure_does_not_leak_a_second_ws(self):
        from services.market_price_feed import dual_feed as feed_mod

        feed = feed_mod.DualMarketFeed(redis_url="redis://unused")
        winner = MagicMock()
        loser = MagicMock()

        def start_side_effect():
            # Another thread registers its stream while ours is connecting.
            feed._symbol_streams["BTWUSDT"][feed._primary.name] = winner

        loser.start.side_effect = start_side_effect
        with patch.object(feed_mod, "PriceStream", return_value=loser):
            feed._start_symbol_leg("BTWUSDT", feed._primary)

        self.assertIs(feed._symbol_streams["BTWUSDT"][feed._primary.name], winner)
        loser.stop.assert_called_once()

    def test_any_ws_message_counts_as_alive(self):
        feed = self._feed()
        handler = feed._make_handler("BTWUSDT", feed._primary)
        # Ticker delta without lastPrice: no publish, but the stream is alive.
        handler({"topic": "tickers.BTWUSDT", "data": {"symbol": "BTWUSDT", "markPrice": "1.6"}})
        self.assertGreater(feed._symbol_last_message["BTWUSDT"], time.time() - 5)


if __name__ == "__main__":
    unittest.main()
