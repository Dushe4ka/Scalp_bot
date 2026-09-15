"""Unit tests for bybit_logic.bybit_func.position.if_position_open (mocked HTTP session)."""
from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from bybit_logic.bybit_func.position import if_position_open


def _session_returning(payload):
    session = MagicMock()
    session.get_positions.return_value = payload
    return session


class IfPositionOpenTests(unittest.TestCase):
    def test_true_when_size_positive(self):
        session = _session_returning(
            {"result": {"list": [{"size": "1.5"}]}}
        )
        self.assertTrue(if_position_open(session, "BTCUSDT"))

    def test_false_when_size_zero(self):
        session = _session_returning(
            {"result": {"list": [{"size": "0"}]}}
        )
        self.assertFalse(if_position_open(session, "BTCUSDT"))

    def test_false_when_list_empty(self):
        session = _session_returning({"result": {"list": []}})
        self.assertFalse(if_position_open(session, "BTCUSDT"))

    def test_false_when_result_missing(self):
        session = _session_returning({})
        self.assertFalse(if_position_open(session, "BTCUSDT"))

    def test_false_when_session_raises(self):
        session = MagicMock()
        session.get_positions.side_effect = RuntimeError("boom")
        self.assertFalse(if_position_open(session, "BTCUSDT"))


if __name__ == "__main__":
    unittest.main()
