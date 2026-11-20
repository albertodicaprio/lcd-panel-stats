"""Check CPU gauge parsing and movement without Pi hardware."""

import io
import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from cpu_gauge import cpu_gauge


class CpuGaugeTests(TestCase):
    def test_config_example_parses(self):
        example = Path(__file__).resolve().parents[1] / "cpu_gauge/config.example.toml"
        with patch.dict(os.environ, {"LCD_STATS_CONFIG": str(example)}):
            config = cpu_gauge.load_config()
        self.assertEqual(config["gauge"]["pin"], 17)
        self.assertTrue(config["server"]["url"].endswith("/stats"))

    def test_fetches_cpu_usage(self):
        with patch.object(cpu_gauge.urllib.request, "urlopen", return_value=io.BytesIO(b'{"cpu_usage_percent": 37.5}')) as open_url:
            self.assertEqual(cpu_gauge.get_cpu_usage("http://host:5000/stats", 2), 37.5)
        self.assertEqual(open_url.call_args.kwargs["timeout"], 2)

    def test_invalid_cpu_usage_is_ignored(self):
        with patch.object(cpu_gauge.urllib.request, "urlopen", return_value=io.BytesIO(b'{"cpu_usage_percent": "NaN"}')):
            self.assertIsNone(cpu_gauge.get_cpu_usage("http://host:5000/stats", 2))

    def test_servo_mapping_and_smoothing(self):
        self.assertEqual([cpu_gauge.cpu_to_servo(value) for value in (-10, 0, 50, 100, 110)], [-1, -1, 0, 1, 1])
        self.assertEqual(cpu_gauge.move_toward(-1, 1, 0.06), -0.94)
        self.assertEqual(cpu_gauge.move_toward(0.98, 1, 0.06), 1)
