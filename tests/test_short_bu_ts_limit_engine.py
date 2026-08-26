"""Unit tests for pure decision logic in the async short_bu_ts_limit engine (no network/Bybit)."""
from __future__ import annotations

import unittest

from bybit_logic.api_algorithms import short_bu_ts_limit_engine as engine_module


def _make_session(*, risk_mode: bool = False, averaging_count: int = 0) -> engine_module.TradeSession:
    state = engine_module.TradeState(
        trade_id="t1",
        symbol="BTCUSDT",
        tg_id=1,
        name="test",
        sum_for_trades=10.0,
        algorithms_sum_for_trades=100.0,
        api_key="k",
        api_secret="s",
        risk_mode=risk_mode,
        averaging_count=averaging_count,
    )
    return engine_module.TradeSession(state=state, adapter=None, feed_hub=None, store=None)


class BreakevenTriggerPercentTests(unittest.TestCase):
    def test_normal_mode_uses_trigger_percentage(self):
        session = _make_session(risk_mode=False, averaging_count=0)
        self.assertEqual(session._breakeven_trigger_percent(), engine_module.TRIGGER_PERCENTAGE)

    def test_normal_mode_after_averaging_threshold_uses_reduced_trigger(self):
        session = _make_session(
            risk_mode=False,
            averaging_count=engine_module.BREAKEVEN_AFTER_AVERAGING_COUNT,
        )
        self.assertEqual(
            session._breakeven_trigger_percent(),
            engine_module.TRIGGER_PERCENTAGE_AFTER_AVERAGING,
        )

    def test_risk_mode_uses_risk_mode_trigger_percentage(self):
        session = _make_session(risk_mode=True, averaging_count=0)
        self.assertEqual(
            session._breakeven_trigger_percent(),
            engine_module.RISK_MODE_TRIGGER_PERCENTAGE,
        )

    def test_risk_mode_takes_priority_over_averaging_count(self):
        session = _make_session(
            risk_mode=True,
            averaging_count=engine_module.BREAKEVEN_AFTER_AVERAGING_COUNT,
        )
        self.assertEqual(
            session._breakeven_trigger_percent(),
            engine_module.RISK_MODE_TRIGGER_PERCENTAGE,
        )


if __name__ == "__main__":
    unittest.main()
