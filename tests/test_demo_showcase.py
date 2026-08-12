"""Unit tests for demo_showcase (mocked — no real Bybit/Celery/Redis/Mongo)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from demo_showcase.repository import NoOpHistoryTradesDb


class NoOpHistoryTradesDbTests(unittest.TestCase):
    def test_methods_are_safe_no_ops(self):
        stub = NoOpHistoryTradesDb()
        stub.save_trade_by_state({"trade_id": "x"}, "active")
        stub.apply_user_statistics_delta(1, 10.0)
        self.assertEqual(stub.count_active_trades(1), 0)


class DemoShowcaseIsolationTests(unittest.TestCase):
    def test_force_demo_isolation_sets_use_demo_true_and_stubs_history(self):
        import bybit_logic.api_algorithms.short_bu_ts_limit_engine as engine_module
        import database.history_trades_repository as history_trades_repository
        from demo_showcase.repository import NoOpHistoryTradesDb
        from demo_showcase.tasks import _force_demo_isolation

        original_use_demo = engine_module.USE_DEMO
        original_history_db = history_trades_repository.history_trades_db
        try:
            _force_demo_isolation()
            self.assertTrue(engine_module.USE_DEMO)
            self.assertIsInstance(history_trades_repository.history_trades_db, NoOpHistoryTradesDb)
        finally:
            engine_module.USE_DEMO = original_use_demo
            history_trades_repository.history_trades_db = original_history_db


class DemoShowcaseTaskTests(unittest.TestCase):
    def test_skips_when_credentials_missing(self):
        with patch("demo_showcase.tasks.DEMO_SHOWCASE_API_KEY", ""), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_API_SECRET", ""), \
             patch("demo_showcase.tasks._force_demo_isolation") as mock_isolation:
            from demo_showcase.tasks import demo_showcase_trade

            result = demo_showcase_trade.run(symbol="btcusdt")

        mock_isolation.assert_called_once()
        self.assertEqual(result, {"status": "error", "symbol": "BTCUSDT", "error": "missing_credentials"})

    def test_starts_trade_with_demo_credentials_and_audits(self):
        fake_redis_client = MagicMock()
        fake_lock = MagicMock()
        fake_lock.acquire.return_value = True
        fake_redis_client.lock.return_value = fake_lock

        with patch("demo_showcase.tasks.DEMO_SHOWCASE_API_KEY", "demo_key"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_API_SECRET", "demo_secret"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_TG_ID", 490882969), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_NAME", "demo_showcase"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_USDT_AMOUNT", 5000.0), \
             patch("demo_showcase.tasks._force_demo_isolation") as mock_isolation, \
             patch("demo_showcase.tasks.redis.Redis.from_url", return_value=fake_redis_client), \
             patch("demo_showcase.tasks.demo_showcase_trades_db") as mock_audit_db, \
             patch(
                 "bybit_logic.api_algorithms.short_bu_ts_limit_engine.start_trading",
                 return_value="490882969:BTCUSDT:abc123",
             ) as mock_start_trading:
            from demo_showcase.tasks import demo_showcase_trade

            result = demo_showcase_trade.run(symbol="btcusdt")

        mock_isolation.assert_called_once()
        mock_start_trading.assert_called_once_with(
            symbol="BTCUSDT",
            tg_id=490882969,
            name="demo_showcase",
            api_key="demo_key",
            api_secret="demo_secret",
            sum_for_trades=5000.0,
        )
        mock_audit_db.insert_trade.assert_called_once()
        fake_lock.release.assert_called_once()
        self.assertEqual(result["status"], "started")
        self.assertEqual(result["trade_id"], "490882969:BTCUSDT:abc123")

    def test_skips_duplicate_when_lock_not_acquired(self):
        fake_redis_client = MagicMock()
        fake_lock = MagicMock()
        fake_lock.acquire.return_value = False
        fake_redis_client.lock.return_value = fake_lock

        with patch("demo_showcase.tasks.DEMO_SHOWCASE_API_KEY", "demo_key"), \
             patch("demo_showcase.tasks.DEMO_SHOWCASE_API_SECRET", "demo_secret"), \
             patch("demo_showcase.tasks._force_demo_isolation"), \
             patch("demo_showcase.tasks.redis.Redis.from_url", return_value=fake_redis_client), \
             patch(
                 "bybit_logic.api_algorithms.short_bu_ts_limit_engine.start_trading"
             ) as mock_start_trading:
            from demo_showcase.tasks import demo_showcase_trade

            result = demo_showcase_trade.run(symbol="btcusdt")

        mock_start_trading.assert_not_called()
        self.assertEqual(result, {"status": "skipped_duplicate", "symbol": "BTCUSDT"})


class DemoShowcaseTriggerTests(unittest.TestCase):
    @patch("demo_showcase.trigger.DEMO_SHOWCASE_ENABLED", False)
    def test_disabled_does_not_queue(self):
        from demo_showcase import trigger

        with patch("demo_showcase.tasks.demo_showcase_trade") as mock_task:
            trigger.maybe_trigger_demo_showcase("BTCUSDT")
            mock_task.delay.assert_not_called()

    @patch("demo_showcase.trigger.DEMO_SHOWCASE_ENABLED", True)
    def test_enabled_queues_task_with_symbol(self):
        from demo_showcase import trigger

        with patch("demo_showcase.tasks.demo_showcase_trade") as mock_task:
            trigger.maybe_trigger_demo_showcase("BTCUSDT")
            mock_task.delay.assert_called_once_with(symbol="BTCUSDT")


if __name__ == "__main__":
    unittest.main()
