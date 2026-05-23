"""Tests for user statistics coercion before Mongo $inc."""
from __future__ import annotations

import unittest

from database.user_statistics_coercion import statistics_coerce_update


class StatisticsCoerceTests(unittest.TestCase):
    def test_string_fields_converted(self):
        sets = statistics_coerce_update(
            {
                "sum_positive_trades": "42.5",
                "sum_negative_trades": "0",
                "total_pnl": "10",
                "total_trades": "3",
            }
        )
        self.assertEqual(sets["statistics.sum_positive_trades"], 42.5)
        self.assertEqual(sets["statistics.total_trades"], 3)

    def test_numeric_unchanged(self):
        self.assertEqual(statistics_coerce_update({"sum_positive_trades": 1.0}), {})


if __name__ == "__main__":
    unittest.main()
