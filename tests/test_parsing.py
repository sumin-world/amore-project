"""Tests for shared parsing utilities."""

from src.utils.parsing import to_float, to_int


class TestToFloat:
    def test_price_string(self):
        assert to_float("$29.99") == 29.99

    def test_with_commas(self):
        assert to_float("$1,234.56") == 1234.56

    def test_plain_number(self):
        assert to_float("42.5") == 42.5

    def test_empty_string(self):
        assert to_float("") == 0.0

    def test_invalid_string(self):
        assert to_float("not a number") == 0.0

    def test_none_returns_zero(self):
        assert to_float(None) == 0.0


class TestToInt:
    def test_number_with_text(self):
        assert to_int("1,234 ratings") == 1234

    def test_plain_number(self):
        assert to_int("500") == 500

    def test_empty_string(self):
        assert to_int("") == 0

    def test_no_digits(self):
        assert to_int("no numbers here") == 0

    def test_none_returns_zero(self):
        assert to_int(None) == 0
