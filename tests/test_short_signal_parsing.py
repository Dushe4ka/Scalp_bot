"""Unit tests for parsing the /short_3_limit webhook body (ticker + alert-type marker)."""
from __future__ import annotations

import unittest

from server_api.utils import parse_short_signal_body


class ParseShortSignalBodyTests(unittest.TestCase):
    def test_bare_ticker_is_normal_mode(self):
        symbol, risk_mode = parse_short_signal_body("ACEUSDT")
        self.assertEqual(symbol, "ACEUSDT")
        self.assertFalse(risk_mode)

    def test_short_signal_marker_is_normal_mode(self):
        symbol, risk_mode = parse_short_signal_body("ACEUSDT SHORT SIGNAL")
        self.assertEqual(symbol, "ACEUSDT")
        self.assertFalse(risk_mode)

    def test_short1_marker_is_risk_mode(self):
        symbol, risk_mode = parse_short_signal_body("ACEUSDT Short1")
        self.assertEqual(symbol, "ACEUSDT")
        self.assertTrue(risk_mode)

    def test_short1_marker_is_case_insensitive(self):
        symbol, risk_mode = parse_short_signal_body("aceusdt short1")
        self.assertEqual(symbol, "ACEUSDT")
        self.assertTrue(risk_mode)

    def test_short1_marker_with_dot_suffix_and_whitespace(self):
        symbol, risk_mode = parse_short_signal_body("  ACEUSDT.P   Short1  ")
        self.assertEqual(symbol, "ACEUSDT")
        self.assertTrue(risk_mode)

    def test_unknown_marker_defaults_to_normal_mode(self):
        symbol, risk_mode = parse_short_signal_body("ACEUSDT FOOBAR")
        self.assertEqual(symbol, "ACEUSDT")
        self.assertFalse(risk_mode)

    def test_empty_body_raises(self):
        with self.assertRaises(ValueError):
            parse_short_signal_body("   ")


if __name__ == "__main__":
    unittest.main()
