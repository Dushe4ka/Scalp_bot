"""Unit tests for demo_showcase (mocked — no real Bybit/Celery/Redis/Mongo)."""
from __future__ import annotations

import unittest

from demo_showcase.repository import NoOpHistoryTradesDb


class NoOpHistoryTradesDbTests(unittest.TestCase):
    def test_methods_are_safe_no_ops(self):
        stub = NoOpHistoryTradesDb()
        stub.save_trade_by_state({"trade_id": "x"}, "active")
        stub.apply_user_statistics_delta(1, 10.0)
        self.assertEqual(stub.count_active_trades(1), 0)


if __name__ == "__main__":
    unittest.main()
