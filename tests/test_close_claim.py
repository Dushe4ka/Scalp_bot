"""Atomic close (claim_close) and the engine side of it: no double stats / notifications."""
from __future__ import annotations

import asyncio
import os
import tempfile
import unittest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from bybit_logic.api_algorithms import short_bu_ts_limit_engine as engine_module
from database.history_trades_repository import HistoryTradesRepository


def _repo_with(history: MagicMock) -> HistoryTradesRepository:
    repo = HistoryTradesRepository.__new__(HistoryTradesRepository)
    repo._history = history
    repo._users = MagicMock()
    return repo


class ClaimCloseTests(unittest.TestCase):
    def _doc(self):
        return {"trade_id": "1:X:a", "tg_id": 1, "symbol": "X", "pnl_usdt": 3.0,
                "created_at": datetime(2026, 1, 1)}

    def test_active_record_is_claimed_and_keeps_open_time(self):
        history = MagicMock()
        history.update_one.return_value = MagicMock(matched_count=1)
        self.assertTrue(_repo_with(history).claim_close(self._doc()))
        query, update = history.update_one.call_args[0][:2]
        self.assertEqual(query["state"], "active")
        self.assertEqual(update["$set"]["state"], "closed")
        self.assertNotIn("created_at", update["$set"])

    def test_already_closed_is_not_claimed(self):
        history = MagicMock()
        history.update_one.return_value = MagicMock(matched_count=0)
        history.find_one.return_value = {"_id": 1}
        self.assertFalse(_repo_with(history).claim_close(self._doc()))
        history.insert_one.assert_not_called()

    def test_missing_record_is_inserted_as_closed(self):
        history = MagicMock()
        history.update_one.return_value = MagicMock(matched_count=0)
        history.find_one.return_value = None
        self.assertTrue(_repo_with(history).claim_close(self._doc()))
        inserted = history.insert_one.call_args[0][0]
        self.assertEqual(inserted["state"], "closed")


class EngineCloseNotificationTests(unittest.IsolatedAsyncioTestCase):
    def _session(self):
        state = engine_module.TradeState(
            trade_id="1:BTWUSDT:a", symbol="BTWUSDT", tg_id=1, name="u",
            sum_for_trades=10.0, algorithms_sum_for_trades=100.0, api_key="k", api_secret="s",
            entry_price=1.5, position_qty=100.0, previous_avg_price=1.5, previous_position_size=100.0,
        )
        adapter = MagicMock()
        adapter.get_positions_by_symbol = AsyncMock(
            return_value={"result": {"list": [{"size": "0", "avgPrice": "0"}]}}
        )
        adapter.get_result_position_info = AsyncMock(
            return_value={"is_open": False, "pnl_usdt": 4.0, "entry_price": 1.5, "exit_price": 1.44}
        )
        adapter.stop_trading = AsyncMock()
        session = engine_module.TradeSession(state=state, adapter=adapter, feed_hub=None, store=None)
        session.http_session = object()
        session._notify_user = MagicMock()
        return session

    async def _close(self, claim_result: bool):
        session = self._session()
        with patch.object(engine_module.history_trades_db, "claim_close", return_value=claim_result), \
                patch.object(engine_module.history_trades_db, "apply_user_statistics_delta") as stats:
            await session._check_position_once()
        return session, stats

    async def test_engine_close_notifies_and_counts_once(self):
        session, stats = await self._close(claim_result=True)
        session._notify_user.assert_called_once()
        self.assertIn("🔄 Позиция закрыта", session._notify_user.call_args[0][0])
        stats.assert_called_once_with(1, 4.0)

    async def test_engine_skips_when_watchdog_already_closed(self):
        session, stats = await self._close(claim_result=False)
        session._notify_user.assert_not_called()
        stats.assert_not_called()
        self.assertTrue(session.state.should_stop)


class EngineHeartbeatTests(unittest.IsolatedAsyncioTestCase):
    async def test_heartbeat_written_for_each_session_with_ttl(self):
        engine = engine_module.AsyncTradeEngine()
        pipe = MagicMock()
        engine.store._client = MagicMock()
        engine.store._client.pipeline.return_value = pipe
        runner = MagicMock()
        runner.state.last_price_at = 123.0
        runner.state.position_opened = True
        engine._sessions = {"1:X:a": runner}

        with patch.object(engine_module, "SESSION_HEARTBEAT_INTERVAL_SECONDS", 0.01):
            task = asyncio.create_task(engine._heartbeat_loop())
            await asyncio.sleep(0.05)
            task.cancel()

        key, value = pipe.set.call_args[0]
        self.assertEqual(key, "trade_alive:1:X:a")
        self.assertIn('"last_price_at": 123.0', value)
        self.assertEqual(pipe.set.call_args[1]["ex"], engine_module.SESSION_HEARTBEAT_TTL_SECONDS)


class DailyFileHandlerTests(unittest.TestCase):
    def test_switches_file_when_date_changes(self):
        import logging

        from logger_config import DailyFileHandler

        with tempfile.TemporaryDirectory() as tmp:
            handler = DailyFileHandler(tmp)
            handler.setFormatter(logging.Formatter("%(message)s"))
            record = logging.LogRecord("t", logging.INFO, __file__, 1, "msg", None, None)
            with patch.object(DailyFileHandler, "_today", return_value="2026-10-11"):
                handler._current_date = "2026-10-11"
                handler.baseFilename = handler._path_for("2026-10-11")
                handler.emit(record)
            with patch.object(DailyFileHandler, "_today", return_value="2026-10-12"):
                handler.emit(record)
            handler.close()
            self.assertEqual(sorted(os.listdir(tmp)), ["2026-10-11.log", "2026-10-12.log"])


if __name__ == "__main__":
    unittest.main()
