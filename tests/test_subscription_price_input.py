"""Unit tests for parsing admin input when changing the subscription price."""
from __future__ import annotations

import unittest

from bot.utils.subscription_price import parse_admin_price_input


class ParseAdminPriceInputTests(unittest.TestCase):
    def test_single_value_sets_only_price(self):
        price, old_price = parse_admin_price_input("59")
        self.assertEqual(price, 59.0)
        self.assertIsNone(old_price)

    def test_two_values_separated_by_slash_set_both(self):
        price, old_price = parse_admin_price_input("59/79")
        self.assertEqual(price, 59.0)
        self.assertEqual(old_price, 79.0)

    def test_whitespace_around_values_is_ignored(self):
        price, old_price = parse_admin_price_input("  59  /  79  ")
        self.assertEqual(price, 59.0)
        self.assertEqual(old_price, 79.0)

    def test_decimal_values_are_supported(self):
        price, old_price = parse_admin_price_input("59.5/79.5")
        self.assertEqual(price, 59.5)
        self.assertEqual(old_price, 79.5)

    def test_non_numeric_input_raises(self):
        with self.assertRaises(ValueError):
            parse_admin_price_input("abc")

    def test_non_positive_price_raises(self):
        with self.assertRaises(ValueError):
            parse_admin_price_input("0")
        with self.assertRaises(ValueError):
            parse_admin_price_input("-5")

    def test_old_price_not_greater_than_price_raises(self):
        with self.assertRaises(ValueError):
            parse_admin_price_input("79/59")

    def test_too_many_parts_raises(self):
        with self.assertRaises(ValueError):
            parse_admin_price_input("59/79/99")


if __name__ == "__main__":
    unittest.main()
