"""Unit tests for the trade watchdog (fake Mongo/Redis/Bybit, no network)."""
from __future__ import annotations

import json
import unittest
from datetime import datetime, timedelta

from celery_app import trade_watchdog as wd


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value, nx=False, ex=None):
        if nx and key in self.data:
            return None
        self.data[key] = value
        return True

    def delete(self, *keys):
        return sum(1 for k in keys if self.data.pop(k, None) is not None)


class FakeHistory:
    def __init__(self, docs) -> None:
        self.docs = docs
        self.claimed: list[dict] = []
        self.stats: list[tuple[int, float]] = []
        self.claim_result = True

    def list_active_trades(self):
        return [d for d in self.docs if d["state"] == "active"]

    def claim_close(self, trade_doc):
        if not self.claim_result:
            return False
        self.claimed.append(trade_doc)
        for d in self.docs:
            if d["trade_id"] == trade_doc["trade_id"]:
                d["state"] = "closed"
        return True

    def apply_user_statistics_delta(self, tg_id, pnl):
        self.stats.append((tg_id, pnl))


class FakeExchange:
    def __init__(self, open_size=0.0, closed=None, error=None) -> None:
        self.open_size = open_size
        self.closed = closed
        self.error = error

    def get_open_size(self, api_key, api_secret, symbol):
        if self.error:
            raise self.error
        return self.open_size

    def get_closed_pnl_since(self, api_key, api_secret, symbol, since_ts):
        return self.closed

    def get_last_price(self, api_key, api_secret, symbol):
        return 1.35


NOW = 1_800_000_000.0


def _doc(trade_id="1:BTWUSDT:abc", tg_id=1, age_sec=3600):
    return {
        "trade_id": trade_id,
        "tg_id": tg_id,
        "symbol": "BTWUSDT",
        "name": "u",
        "state": "active",
        "entry_price": 1.5,
        "size": 100.0,
        "created_at": datetime.utcfromtimestamp(NOW - age_sec),
        "source": "short_3_limit",
    }


class TradeWatchdogTests(unittest.TestCase):
    def _make(self, docs, exchange, keys=("k", "s")):
        self.history = FakeHistory(docs)
        self.redis = FakeRedis()
        self.user_msgs: list[tuple[int, str]] = []
        self.admin_msgs: list[str] = []
        return wd.TradeWatchdog(
            history=self.history,
            redis_client=self.redis,
            get_user_keys=lambda tg_id: keys,
            exchange=exchange,
            notify_user=lambda tg_id, text: self.user_msgs.append((tg_id, text)),
            notify_admins=self.admin_msgs.append,
            position_side="Sell",
            skip_tg_ids={490882969},
            now=lambda: NOW,
        )

    def _heartbeat(self, trade_id, last_price_at):
        self.redis.data[f"trade_alive:{trade_id}"] = json.dumps({"last_price_at": last_price_at})

    def test_alive_session_with_prices_is_left_alone(self):
        dog = self._make([_doc()], FakeExchange(open_size=0))
        self._heartbeat("1:BTWUSDT:abc", NOW - 2)
        self.assertEqual(dog.run_once()["alive"], 1)
        self.assertEqual(self.admin_msgs, [])
        self.assertEqual(self.user_msgs, [])
        self.assertEqual(self.history.claimed, [])

    def test_alive_session_without_prices_alerts_admin_once(self):
        dog = self._make([_doc()], FakeExchange())
        self._heartbeat("1:BTWUSDT:abc", 0.0)  # never got a price (incident 11.10)
        dog.run_once()
        dog.run_once()
        self.assertEqual(len(self.admin_msgs), 1)
        self.assertIn("не получает цены", self.admin_msgs[0])

    def test_dead_session_within_grace_is_skipped(self):
        dog = self._make([_doc(age_sec=30)], FakeExchange(open_size=5))
        dog.run_once()
        self.assertEqual(self.admin_msgs, [])

    def test_dead_session_with_open_position_alerts_orphan_once(self):
        dog = self._make([_doc()], FakeExchange(open_size=100))
        self.assertEqual(dog.run_once()["orphaned"], 1)
        dog.run_once()
        self.assertEqual(len(self.admin_msgs), 1)
        self.assertIn("без сопровождения", self.admin_msgs[0])
        self.assertEqual(self.history.claimed, [])

    def test_manual_close_with_dead_session_notifies_user_like_algorithm(self):
        closed = {"entry_price": 1.5, "exit_price": 1.35, "pnl_usdt": 15.0, "size": 100.0,
                  "close_ts": NOW - 60, "source": "exchange"}
        dog = self._make([_doc()], FakeExchange(open_size=0, closed=closed))
        self.redis.data["trade_cmd:1:BTWUSDT"] = "1"

        self.assertEqual(dog.run_once()["closed"], 1)

        self.assertEqual(self.history.stats, [(1, 15.0)])
        self.assertEqual(len(self.user_msgs), 1)
        tg_id, text = self.user_msgs[0]
        self.assertEqual(tg_id, 1)
        self.assertTrue(text.startswith("🔄 Позиция закрыта"))
        self.assertIn("BTWUSDT", text)
        self.assertIn("+10.00% (+15.00 USDT)", text)
        self.assertNotIn("trade_cmd:1:BTWUSDT", self.redis.data)
        self.assertEqual(self.history.claimed[0]["closed_by"], "watchdog")

        dog.run_once()  # record is closed now → nothing repeats
        self.assertEqual(len(self.user_msgs), 1)
        self.assertEqual(len(self.history.stats), 1)

    def test_engine_already_closed_means_no_duplicate_notification(self):
        closed = {"entry_price": 1.5, "exit_price": 1.4, "pnl_usdt": 5.0, "source": "exchange"}
        dog = self._make([_doc()], FakeExchange(open_size=0, closed=closed))
        self.history.claim_result = False
        dog.run_once()
        self.assertEqual(self.user_msgs, [])
        self.assertEqual(self.history.stats, [])

    def test_missing_closed_pnl_waits_then_closes_by_market_price(self):
        dog = self._make([_doc()], FakeExchange(open_size=0, closed=None))
        dog.run_once()
        self.assertEqual(self.history.claimed, [])  # wait for Bybit

        self.redis.data["watchdog:pending_close:1:BTWUSDT:abc"] = str(NOW - wd.WATCHDOG_PNL_WAIT_SEC - 1)
        dog.run_once()
        self.assertEqual(len(self.history.claimed), 1)
        # short 100 @ 1.5, market 1.35 → +15 USDT, +10%
        self.assertAlmostEqual(self.history.claimed[0]["pnl_usdt"], 15.0)
        self.assertEqual(len(self.user_msgs), 1)
        text = self.user_msgs[0][1]
        self.assertIn("+10.00% (+15.00 USDT)", text)
        self.assertIn("по рыночной цене", text)
        self.assertNotIn("Цена выхода: 0\n", text)
        self.assertTrue(any("closed PnL" in m for m in self.admin_msgs))

    def test_exchange_error_alerts_once_and_does_not_close(self):
        dog = self._make([_doc()], FakeExchange(error=RuntimeError("api key expired")))
        dog.run_once()
        dog.run_once()
        self.assertEqual(len(self.admin_msgs), 1)
        self.assertIn("api key expired", self.admin_msgs[0])
        self.assertEqual(self.history.claimed, [])

    def test_demo_showcase_is_skipped(self):
        dog = self._make([_doc(trade_id="490882969:BTWUSDT:x", tg_id=490882969)], FakeExchange(open_size=5))
        self.assertEqual(dog.run_once()["checked"], 0)

    def test_one_bad_trade_does_not_stop_the_others(self):
        docs = [_doc(trade_id="1:BTWUSDT:a", tg_id=1), _doc(trade_id="2:BTWUSDT:b", tg_id=2)]
        dog = self._make(docs, FakeExchange(open_size=100))
        calls = {"n": 0}

        def flaky_keys(tg_id):
            calls["n"] += 1
            if tg_id == 1:
                raise RuntimeError("mongo hiccup")
            return ("k", "s")

        dog._get_user_keys = flaky_keys
        summary = dog.run_once()
        self.assertEqual(summary["errors"], 1)
        self.assertEqual(summary["orphaned"], 1)


class AggregateClosedPnlTests(unittest.TestCase):
    def test_sums_partial_closes_after_open_and_ignores_older(self):
        since = NOW - 3600
        rows = [
            {"updatedTime": str(int((NOW - 7200) * 1000)), "closedPnl": "99", "closedSize": "1",
             "avgEntryPrice": "9", "avgExitPrice": "9"},  # previous trade
            {"updatedTime": str(int((NOW - 100) * 1000)), "closedPnl": "10", "closedSize": "60",
             "avgEntryPrice": "1.5", "avgExitPrice": "1.4"},
            {"updatedTime": str(int((NOW - 50) * 1000)), "closedPnl": "5", "closedSize": "40",
             "avgEntryPrice": "1.5", "avgExitPrice": "1.3"},
        ]
        info = wd.aggregate_closed_pnl(rows, since)
        self.assertAlmostEqual(info["pnl_usdt"], 15.0)
        self.assertAlmostEqual(info["exit_price"], 1.36)
        self.assertAlmostEqual(info["entry_price"], 1.5)
        self.assertAlmostEqual(info["close_ts"], NOW - 50)

    def test_none_when_only_older_records(self):
        rows = [{"updatedTime": str(int((NOW - 7200) * 1000)), "closedPnl": "1", "closedSize": "1"}]
        self.assertIsNone(wd.aggregate_closed_pnl(rows, NOW - 3600))


class BybitGatewayTests(unittest.TestCase):
    def test_closed_pnl_window_capped_to_bybit_7_day_limit(self):
        import time
        from unittest.mock import MagicMock, patch

        http = MagicMock()
        http.get_closed_pnl.return_value = {"result": {"list": []}}
        gw = wd.BybitExchangeGateway()
        with patch.object(gw, "_session", return_value=http):
            gw.get_closed_pnl_since("k", "s", "BTWUSDT", time.time() - 30 * 24 * 3600)
        start_ms = http.get_closed_pnl.call_args[1]["startTime"]
        self.assertGreater(start_ms / 1000, time.time() - 7 * 24 * 3600)

    def test_open_size_sums_hedge_legs(self):
        from unittest.mock import MagicMock, patch

        http = MagicMock()
        http.get_positions.return_value = {"result": {"list": [{"size": "0"}, {"size": "12.5"}]}}
        gw = wd.BybitExchangeGateway()
        with patch.object(gw, "_session", return_value=http):
            self.assertEqual(gw.get_open_size("k", "s", "BTWUSDT"), 12.5)


class CreatedTsTests(unittest.TestCase):
    def test_naive_utc_datetime(self):
        doc = {"created_at": datetime(2026, 10, 11, 6, 14, 0)}
        self.assertEqual(wd._created_ts(doc), 1791699240.0)

    def test_missing(self):
        self.assertEqual(wd._created_ts({}), 0.0)


if __name__ == "__main__":
    unittest.main()
