"""Admin mass stop must also cover users with an open trade whose subscription has expired."""
from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from server_api.routes import trading


class MassStopTargetsTests(unittest.IsolatedAsyncioTestCase):
    async def test_adds_users_with_active_trades_without_subscription(self):
        subscribed = [{"tg_id": 1, "bybit_data": {"api_key": "a", "api_secret": "b"}}]
        expired = {"tg_id": 2, "bybit_data": {"api_key": "c", "api_secret": "d"}}
        active = [{"tg_id": 1}, {"tg_id": 2}, {"tg_id": 490882969}]
        with patch.object(trading.db, "list_trading_candidates", AsyncMock(return_value=subscribed)), \
                patch.object(trading.db, "get_user", AsyncMock(return_value=expired)) as get_user, \
                patch("database.history_trades_repository.history_trades_db.list_active_trades",
                      return_value=active), \
                patch("demo_showcase.config.DEMO_SHOWCASE_TG_ID", 490882969):
            users = await trading._mass_stop_targets()

        self.assertEqual([u["tg_id"] for u in users], [1, 2])
        get_user.assert_awaited_once_with(2)  # subscribed user and demo showcase are not re-fetched

    async def test_no_active_trades_keeps_old_behaviour(self):
        subscribed = [{"tg_id": 1}]
        with patch.object(trading.db, "list_trading_candidates", AsyncMock(return_value=subscribed)), \
                patch.object(trading.db, "get_user", AsyncMock()) as get_user, \
                patch("database.history_trades_repository.history_trades_db.list_active_trades",
                      return_value=[]):
            users = await trading._mass_stop_targets()
        self.assertEqual(users, subscribed)
        get_user.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
