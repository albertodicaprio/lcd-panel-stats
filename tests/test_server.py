"""HTTP contract checks for the server stats endpoint."""

import os
from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

with patch.dict(os.environ, {"LCD_STATS_CONFIG": str(Path(__file__).resolve().parents[1] / "server/config.example.toml")}):
    from server import stats as server_stats


class StatsEndpointTests(TestCase):
    def test_cpu_usage_is_reported_as_a_rounded_percent(self):
        with (
            patch.object(server_stats.psutil, "cpu_percent", return_value=37.46) as cpu_percent,
            patch.object(server_stats, "get_cpu_temp", return_value=48.0),
            patch.object(server_stats, "get_nvidia_gpu_temp", return_value=54),
            patch.object(server_stats, "get_network_speed", return_value=(1.0, 2.0)),
        ):
            response = server_stats.app.test_client().get("/stats")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["cpu_usage_percent"], 37.5)
        self.assertEqual(response.json["cpu_temp"], 48.0)
        cpu_percent.assert_called_once_with(interval=0.1)
