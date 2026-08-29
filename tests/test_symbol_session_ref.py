"""Unit tests for global symbol session refcount (mocked Redis)."""
from __future__ import annotations

import sys
import unittest
from unittest.mock import MagicMock, patch

from bybit_logic.feeds import symbol_session_ref as ref_mod


def _fake_redis_client(eval_return: int) -> MagicMock:
    mock_client = MagicMock()
    mock_client.eval.return_value = eval_return
    fake_redis = MagicMock()
    fake_redis.Redis.from_url.return_value = mock_client
    return fake_redis


class SymbolSessionRefTests(unittest.TestCase):
    def test_acquire_first_session_requests_feed(self):
        fake_redis = _fake_redis_client(1)
        with patch.dict(sys.modules, {"redis": fake_redis}):
            with patch.object(ref_mod, "request_feed_symbol") as req:
                n = ref_mod.acquire_symbol_price_session("BTCUSDT")
        self.assertEqual(n, 1)
        req.assert_called_once()

    def test_release_last_session_closes_feed(self):
        fake_redis = _fake_redis_client(0)
        with patch.dict(sys.modules, {"redis": fake_redis}):
            with patch.object(ref_mod, "release_feed_symbol") as rel:
                n = ref_mod.release_symbol_price_session("ETHUSDT")
        self.assertEqual(n, 0)
        rel.assert_called_once()

    def test_refresh_refcount_returns_value_and_touches_ttl(self):
        fake_redis = _fake_redis_client(2)
        with patch.dict(sys.modules, {"redis": fake_redis}):
            n = ref_mod.get_symbol_refcount_and_refresh("BTCUSDT")
        self.assertEqual(n, 2)
        fake_redis.Redis.from_url.return_value.eval.assert_called_once()


if __name__ == "__main__":
    unittest.main()
