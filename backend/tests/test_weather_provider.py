"""
Automated unit and integration tests for WeatherProvider.
Tests:
1. Parsing against saved sample payload fixture.
2. Unit conversions and range validation.
3. Cache expiry and caching logic.
4. Fallback on network timeout / failure.
5. Stale status reporting.
6. Mock server integration test (NO REAL NETWORK).
"""
import json
import os
import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime, timezone

from backend.services.weather_provider import (
    OpenMeteoProvider,
    ReplayWeatherProvider,
    HybridWeatherProvider,
    validate_weather_dict,
    WeatherPoint
)


class TestWeatherProvider(unittest.TestCase):

    def setUp(self):
        fixture_path = ".claude/weather/fixtures/open_meteo_sample.json"
        with open(fixture_path, "r") as f:
            self.sample_payload = json.load(f)

    def test_parse_sample_payload(self):
        provider = OpenMeteoProvider()
        resp = provider.parse_api_payload(self.sample_payload)
        self.assertIsNotNone(resp)
        self.assertEqual(resp.source, "Live (Open-Meteo)")
        self.assertTrue(resp.is_live)
        self.assertEqual(resp.status, "live")

        curr = resp.current
        self.assertIsInstance(curr.outdoor_temp_c, float)
        self.assertIsInstance(curr.relative_humidity, float)
        self.assertGreater(len(resp.forecast_24h), 12)
        self.assertGreater(len(resp.forecast_7d), 20)

    def test_range_validation(self):
        # Valid point
        valid_pt = {"outdoor_temp_c": 32.5, "relative_humidity": 65.0, "solar_irradiance_wm2": 500.0}
        self.assertTrue(validate_weather_dict(valid_pt))

        # Out-of-bounds temperature (-50 C or 90 C)
        invalid_temp = {"outdoor_temp_c": 95.0, "relative_humidity": 50.0}
        self.assertFalse(validate_weather_dict(invalid_temp))

        # Out-of-bounds humidity (>100%)
        invalid_hum = {"outdoor_temp_c": 28.0, "relative_humidity": 120.0}
        self.assertFalse(validate_weather_dict(invalid_hum))

    def test_cache_and_stale_behavior(self):
        provider = OpenMeteoProvider(cache_ttl_current_sec=1.0)
        # Seed cache manually
        parsed = provider.parse_api_payload(self.sample_payload)
        provider._cached_response = parsed
        provider._last_fetch_mono = 1000.0

        # Query immediately within TTL
        with patch("time.monotonic", return_value=1000.5):
            res1 = provider.get_weather()
            self.assertEqual(res1.status, "cached")

        # Query after TTL expires with network failure -> returns stale
        with patch("time.monotonic", return_value=1005.0):
            with patch.object(provider, "fetch_from_api", return_value=None):
                res2 = provider.get_weather()
                self.assertEqual(res2.status, "stale")

    def test_fallback_on_network_timeout(self):
        hybrid = HybridWeatherProvider(mode="auto")
        # Mock network failure
        with patch.object(hybrid.open_meteo, "get_weather", side_effect=Exception("Connection timed out")):
            res = hybrid.get_weather()
            self.assertEqual(res.status, "fallback")
            self.assertIn("Fallback", res.source)
            self.assertFalse(res.is_live)
            self.assertGreater(res.current.outdoor_temp_c, 10.0)

    def test_mock_server_integration(self):
        provider = OpenMeteoProvider()
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = json.dumps(self.sample_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp

        with patch("urllib.request.urlopen", return_value=mock_resp):
            res = provider.fetch_from_api()
            self.assertIsNotNone(res)
            self.assertEqual(res.status, "live")
            self.assertEqual(res.source, "Live (Open-Meteo)")


if __name__ == "__main__":
    unittest.main()
