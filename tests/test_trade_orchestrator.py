"""Unit tests for trade orchestrator (mocked Redis)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from celery_app import trade_orchestrator as orch


class TradeOrchestratorTests(unittest.TestCase):
    def test_assign_trade_picks_least_loaded(self):
        mock_client = MagicMock()
        mock_client.smembers.return_value = {"0", "1"}
        mock_client.eval.return_value = ["1", "15"]

        with patch.object(orch, "_client", return_value=mock_client):
            orch.ensure_engine_registry(2)
            result = orch.assign_trade(
                symbol="BTCUSDT",
                tg_id=1,
                name="t",
                api_key="k",
                api_secret="s",
                sum_for_trades=10.0,
            )

        self.assertEqual(result["status"], "assigned")
        self.assertEqual(result["engine_id"], "1")
        mock_client.eval.assert_called()

    def test_assign_trade_queues_when_full(self):
        mock_client = MagicMock()
        mock_client.smembers.return_value = {"0"}
        mock_client.eval.return_value = [None, "30"]

        with patch.object(orch, "_client", return_value=mock_client):
            result = orch.assign_trade(
                symbol="ETHUSDT",
                tg_id=2,
                name="t",
                api_key="k",
                api_secret="s",
                sum_for_trades=10.0,
            )

        self.assertEqual(result["status"], "queued")
        mock_client.rpush.assert_called()

    def test_release_engine_slot_clamps_negative(self):
        mock_client = MagicMock()
        mock_client.decr.return_value = -1

        with patch.object(orch, "_client", return_value=mock_client):
            with patch.dict("os.environ", {"CELERY_ENGINE_ID": "0"}):
                orch.release_engine_slot()

        mock_client.set.assert_called_with("engine:0:load", 0)


if __name__ == "__main__":
    unittest.main()
