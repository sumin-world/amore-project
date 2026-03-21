"""Tests for configuration loading."""

import json
import os
import tempfile

from src.config import load_target_products


class TestLoadTargetProducts:
    def test_loads_from_file(self):
        data = {
            "products": {
                "B0TEST1": {"brand": "TestBrand", "name": "Test Product"},
                "B0TEST2": {"brand": "OtherBrand", "name": "Other Product"},
            }
        }
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(data, f)
            path = f.name

        try:
            products = load_target_products(path)
            assert len(products) == 2
            assert products["B0TEST1"]["brand"] == "TestBrand"
            assert products["B0TEST2"]["name"] == "Other Product"
        finally:
            os.unlink(path)

    def test_missing_file_returns_empty(self):
        products = load_target_products("/nonexistent/path.json")
        assert products == {}

    def test_default_config_exists(self):
        """The default config/products.json should exist and be valid."""
        products = load_target_products()
        assert len(products) >= 1
        for asin, meta in products.items():
            assert "brand" in meta
            assert "name" in meta
